from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import PyPDF2
from openai import OpenAI, AsyncOpenAI
import subprocess
import base64
import os
import re
import json
import asyncio
from pathlib import Path
import shutil
import tempfile

from prompts import get_initial_diagnose_prompt, get_system_instruction, get_b_side_evaluation_prompt

try:
    from dotenv import load_dotenv

    _backend_dir = Path(__file__).resolve().parent
    _repo_root = _backend_dir.parent
    load_dotenv(_repo_root / ".env")
    load_dotenv(_backend_dir / ".env", override=True)
except ImportError:
    pass

_BACKEND_DIR = Path(__file__).resolve().parent

def _llm_config():
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    return api_key, base_url, model

API_KEY, BASE_URL, MODEL_NAME = _llm_config()
if not API_KEY:
    raise RuntimeError(
        "未配置大模型 API Key：请在环境变量中设置 DEEPSEEK_API_KEY（或兼容的 OPENAI_API_KEY），"
        f"或在 `{_BACKEND_DIR / '.env'}` 中写入（可参考同目录 `.env.example`）。"
    )

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
aclient = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    resume_data: Dict[str, Any]
    jd_input: str

class CompileRequest(BaseModel):
    resume_data: Dict[str, Any]
    template: int = 1        # 模板编号：1/2/3
    font_size: float = 10    # 字号（pt）
    line_spacing: float = 1.0  # 行距（em 倍数）
    photo_base64: Optional[str] = None  # 证件照（data URL 或裸 base64）


def _repair_json_text(s: str) -> str:
    """修复 LLM 输出 JSON 的常见小瑕疵：字符串内出现真实换行/制表符、尾随逗号。

    典型场景：AI 把 "- 点1\\n- 点2" 写成了真实的换行，导致 json.loads 解析失败、
    更新字段丢失、右侧 PDF 不同步。
    """
    out = []
    in_str = False
    escaped = False
    for ch in s:
        if in_str:
            if escaped:
                escaped = False
                out.append(ch)
            elif ch == "\\":
                escaped = True
                out.append(ch)
            elif ch == '"':
                out.append(ch)
                in_str = False
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
    text = "".join(out)
    # 去掉对象/数组结尾的尾随逗号
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def _try_parse_json(raw: str):
    """尝试解析 JSON（先原样，失败后修复再试）。"""
    if not raw or not raw.strip():
        return None
    for candidate in (raw, _repair_json_text(raw)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _extract_json_object(text: str) -> dict:
    """从 LLM 回复中鲁棒地提取 JSON 对象。

    优先匹配 ```json 代码块（大小写不敏感）；失败时按括号配平兜底扫描文本，
    并对常见的 JSON 瑕疵（字符串内真实换行、尾随逗号）做修复后重试，
    避免因 LLM 输出格式稍有变化导致更新数据解析失败、C 端简历无法同步。
    """
    m = re.search(r'```(?:json)?[ \t]*\n?(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if m:
        parsed = _try_parse_json(m.group(1).strip())
        if parsed is not None:
            return parsed

    # 兜底：从前往后扫描，优先匹配【最外层】的 JSON 对象
    # （注意：不能从后往前找，否则会命中最后一个内层对象，丢掉外层结构）
    for start in range(len(text)):
        if text[start] != "{":
            continue
        depth = 0
        in_str = False
        escaped = False
        for end in range(start, len(text)):
            ch = text[end]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    parsed = _try_parse_json(text[start:end + 1])
                    if parsed is not None:
                        return parsed
                    break
    return {}


# 模板所需的完整字段（LLM 漏输出时用默认值兜底）
_EMPTY_RESUME = {
    "NAME": "", "GENDER": "", "BIRTH_YEAR": "", "POLITICAL": "", "ORIGIN": "", "GRAD_YEAR": "",
    "LOCATION": "", "EMAIL": "", "PHONE": "", "GITHUB": "", "LINKEDIN": "", "SITE": "",
    "EDU_SCHOOL": "", "EDU_MAJOR": "", "EDU_LOCATION": "", "EDU_DATE": "", "EDU_DEGREE": "", "EDU_COURSES": "", "EDU_AWARDS": "",
    "EXPERIENCES": [], "CAMPUS": [],
    "SKILL_PRO": "", "SKILL_TOOL": "", "SKILL_LANG": "",
}

# LLM 偶尔会把平面字段按分组嵌套输出，兼容拍平
_GROUP_KEYS = ("基础信息", "教育背景", "技能特长")

_EXP_ALIASES = {"company": "company", "Company": "company", "公司": "company", "role": "role", "Role": "role", "职位": "role", "岗位": "role", "title": "role", "location": "location", "Location": "location", "地点": "location", "date": "date", "Date": "date", "dates": "date", "时间": "date", "content": "content", "Content": "content", "内容": "content", "description": "content"}
_CAMPUS_ALIASES = {"org": "org", "Org": "org", "organization": "org", "组织": "org", "机构": "org", "name": "org", "role": "role", "职位": "role", "岗位": "role", "location": "location", "地点": "location", "date": "date", "时间": "date", "content": "content", "内容": "content"}


def _normalize_entry(item: dict, aliases: dict, is_campus: bool) -> dict:
    base = ({"org": "", "role": "", "location": "", "date": "", "content": ""} if is_campus
            else {"company": "", "role": "", "location": "", "date": "", "content": ""})
    if not isinstance(item, dict):
        return base
    for k, v in item.items():
        canon = aliases.get(k)
        if canon and canon in base and v is not None:
            base[canon] = v
    return base


def _normalize_resume_data(raw) -> dict:
    """把 LLM 提取结果归一化为模板所需结构（扁平顶层键 + 数组），漏字段补默认值。"""
    out = dict(_EMPTY_RESUME)
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if key in _GROUP_KEYS and isinstance(value, dict):
            # 分组嵌套 → 拍平到顶层
            for k2, v2 in value.items():
                k2u = str(k2).upper()
                if k2u in out:
                    out[k2u] = v2
        else:
            ku = str(key).upper()
            if ku in out:
                out[ku] = value
    # 归一化经历/校园数组
    exps = out.get("EXPERIENCES")
    out["EXPERIENCES"] = [_normalize_entry(e, _EXP_ALIASES, False) for e in exps] if isinstance(exps, list) else []
    camps = out.get("CAMPUS")
    out["CAMPUS"] = [_normalize_entry(e, _CAMPUS_ALIASES, True) for e in camps] if isinstance(camps, list) else []
    return out


@app.post("/api/extract")
async def extract_resume(file: UploadFile = File(...)):
    pdf_reader = PyPDF2.PdfReader(file.file)
    raw_text = "".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
    
    # 提取全部经历（数组），不删减，供后续 AI 对话中灵活增删改
    prompt = (
        "请将以下简历解析为JSON。输出必须是【扁平】的顶层键值对象（键名见下，不要用“基础信息/教育背景”等分组名，不要嵌套）：\n"
        "基础信息字段（均为字符串）：NAME(姓名), GENDER(性别), BIRTH_YEAR(出生年份), POLITICAL(政治面貌，如中共党员/共青团员/群众), ORIGIN(籍贯或生源地), LOCATION(现居地或住址), GRAD_YEAR(毕业年份), EMAIL, PHONE, GITHUB, LINKEDIN, SITE\n"
        "EDU_SCHOOL（学校）, EDU_MAJOR（专业）, EDU_LOCATION, EDU_DATE（起止时间）, EDU_DEGREE（学历/学位，如本科/硕士）, EDU_COURSES（核心课程）, EDU_AWARDS（荣誉奖项）\n"
        "EXPERIENCES（数组：工作/实习/项目经历，每项含 company, role, location, date, content，content 用 '-' 分点）\n"
        "CAMPUS（数组：校园/学生工作经历，每项含 org, role, location, date, content）\n"
        "SKILL_PRO, SKILL_TOOL, SKILL_LANG\n"
        "要求：1) EXPERIENCES 必须包含简历中【所有】工作/实习/项目经历，按时间倒序排列，不得删减；"
        "2) CAMPUS 必须包含【所有】校园/学生工作/社团经历，不得删减；"
        "3) 以上每个平面字段都必须以顶层键输出，找不到填空字符串；"
        "4) 只输出JSON代码块。\n\n"
        f"{raw_text}"
    )
    
    res = await aclient.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.1)
    ans = res.choices[0].message.content
    data = _normalize_resume_data(_extract_json_object(ans))
    return {"data": data}


@app.post("/api/diagnose")
async def diagnose_resume(req: ChatRequest):
    combined_context = f"【目标岗位描述】\n{req.jd_input}\n\n【当前简历数据字典】\n{json.dumps(req.resume_data, ensure_ascii=False)}"
    prompt = get_initial_diagnose_prompt(combined_context)
    
    res = await aclient.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.5)
    return {"reply": res.choices[0].message.content}


# 标记：AI 回复中出现这些词，说明很可能已经给出了定稿（此时应该有 JSON 更新块）
_FINAL_DRAFT_MARKERS = ("定稿", "已完成", "最终版", "精修后", "润色后", "已完成优化")


def _looks_like_final_draft(text: str) -> bool:
    return any(m in text for m in _FINAL_DRAFT_MARKERS)


async def _recover_update_fields(resume_data: dict, assistant_reply: str) -> dict:
    """兜底补捞：LLM 偶尔漏输出 JSON 更新块，用一次轻量二次调用把定稿内容同步回来。"""
    exps = resume_data.get("EXPERIENCES", []) if isinstance(resume_data, dict) else []
    camps = resume_data.get("CAMPUS", []) if isinstance(resume_data, dict) else []
    if not exps and not camps:
        return {}
    prompt = (
        "你是数据同步助手。下面是一位简历精修导师刚给用户的回复。\n"
        "如果这条回复中给出了某段经历【最终精修定稿】（而不是还在收集信息、或仅给出风格选项），"
        "请把定稿内容同步为 JSON；如果只是收集信息/给选项，输出 {}。\n\n"
        f"当前工作/实习经历（EXPERIENCES 完整数组，未修改的经历必须原样保留）：\n{json.dumps(exps, ensure_ascii=False)}\n\n"
        f"当前校园经历（CAMPUS 完整数组）：\n{json.dumps(camps, ensure_ascii=False)}\n\n"
        f"导师回复：\n{assistant_reply}\n\n"
        "规则：只输出 JSON，不要任何解释；键名用 EXPERIENCES 或 CAMPUS，值为【完整数组】；"
        "被精修的那段用定稿内容替换其 content，其余保持不变；"
        '格式：{"EXPERIENCES": [{"company": "...", "role": "...", "location": "...", "date": "...", "content": "- 点1\\n- 点2"}]} 或 {}'
    )
    res = await aclient.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=2400,
    )
    return _extract_json_object(res.choices[0].message.content or "")


@app.post("/api/chat")
async def chat_with_ai(req: ChatRequest):
    system_context = f"当前数据字典：{json.dumps(req.resume_data, ensure_ascii=False)}\n目标JD：{req.jd_input}"
    sys_prompt = get_system_instruction(system_context)
    
    api_msgs = [{"role": "system", "content": sys_prompt}] + req.messages
    res = await aclient.chat.completions.create(model=MODEL_NAME, messages=api_msgs, temperature=0.5)
    full_ans = res.choices[0].message.content

    # 提取 JSON 更新块（大小写不敏感、兼容各种代码块格式、自动修复小瑕疵），并从回复中剔除
    updated_fields = _extract_json_object(full_ans)
    clean_ans = re.sub(r'```(?:json)?[ \t]*\n?.*?```', '', full_ans, flags=re.DOTALL | re.IGNORECASE).strip()

    # 兜底：AI 漏输出 JSON 但回复里像是有定稿 -> 用轻量二次调用补捞，保证右侧 PDF 能同步
    recovered = False
    if not updated_fields and _looks_like_final_draft(full_ans):
        try:
            updated_fields = await _recover_update_fields(req.resume_data, full_ans)
            recovered = bool(updated_fields)
        except Exception:
            updated_fields = {}

    return {"reply": clean_ans, "updated_fields": updated_fields, "recovered": recovered}


@app.post("/api/compile")
async def compile_pdf(req: CompileRequest):
    # 校验模板编号（1-3），非法值回退到 1
    template_num = req.template if 1 <= int(req.template) <= 3 else 1
    template_path = Path(__file__).with_name(f"resume_template_{template_num}.typ")

    # 使用临时目录隔离，避免并发请求共享 resume_data.json / output.pdf 时互相覆盖
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        temp_typ_path = tmp / "temp_render.typ"
        temp_json_path = tmp / "resume_data.json"
        temp_config_path = tmp / "resume_config.json"
        output_pdf_path = tmp / "output.pdf"

        # 1. 将大模型生成的动态结构化数据写入 JSON 文件（模板通过 json("resume_data.json") 读取）
        with temp_json_path.open("w", encoding="utf-8") as f:
            json.dump(req.resume_data, f, ensure_ascii=False, indent=2)

        # 2. 处理证件照（可选）：解码 base64 写入临时目录，模板按需嵌入
        photo_file = None
        raw_photo = (req.photo_base64 or "").strip()
        if raw_photo:
            try:
                if raw_photo.startswith("data:") and "," in raw_photo:
                    raw_photo = raw_photo.split(",", 1)[1]
                img_bytes = base64.b64decode(raw_photo)
                if img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                    photo_file = "photo.png"
                elif img_bytes[:2] == b"\xff\xd8":
                    photo_file = "photo.jpg"
                else:
                    photo_file = "photo.png"
                (tmp / photo_file).write_bytes(img_bytes)
            except Exception:
                photo_file = None

        # 3. 写入排版配置（模板通过 json("resume_config.json") 读取）
        with temp_config_path.open("w", encoding="utf-8") as f:
            json.dump({
                "template": template_num,
                "font_size": float(req.font_size),
                "line_spacing": float(req.line_spacing),
                "has_photo": photo_file is not None,
                "photo_file": photo_file or "photo.png",
            }, f, ensure_ascii=False, indent=2)

        # 3. 拷贝所选模板，模板自身会去读取同目录下的 resume_data.json / resume_config.json
        shutil.copy(template_path, temp_typ_path)

        # 4. 呼叫 Typst 编译
        subprocess.run(["typst", "compile", str(temp_typ_path), str(output_pdf_path)], check=True)

        # 5. 返回 PDF
        with output_pdf_path.open("rb") as f:
            pdf_base64 = base64.b64encode(f.read()).decode('utf-8')

    return {"pdf_base64": pdf_base64}


# backend/main.py (仅展示需要修改的路由部分，其他保持原样)

@app.post("/api/hr/batch-evaluate")
async def hr_batch_evaluate(
    jd: str = Form(...), 
    dimensions: str = Form(...), # 🌟 新增：接收前端传来的自定义维度 JSON 字符串
    files: List[UploadFile] = File(...)
):
    # 1. 解析前端传来的维度配置并组装成易于 LLM 理解的 Prompt 字符串
    try:
        dim_list = json.loads(dimensions)
        dim_prompt_lines = []
        for i, d in enumerate(dim_list):
            dim_prompt_lines.append(f"{i+1}. {d['name']} ({d['weight']}分)")
        dimensions_config_str = "\n".join(dim_prompt_lines)
    except Exception:
        # 如果解析失败，给一个保底默认值防崩
        dimensions_config_str = "1. 综合匹配度 (100分)"

    async def process_single(file: UploadFile):
        try:
            pdf_reader = PyPDF2.PdfReader(file.file)
            raw_text = "".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
            
            # 🌟 把组装好的维度字符串传给提示词生成器
            prompt = get_b_side_evaluation_prompt(jd, raw_text, dimensions_config_str)
            
            res = await aclient.chat.completions.create(
                model=MODEL_NAME, 
                messages=[{"role": "user", "content": prompt}], 
                temperature=0.1
            )
            ans = res.choices[0].message.content
            
            raw_data = _extract_json_object(ans)
            
            mapped_data = {
                "name": raw_data.get("name", "未知候选人"),
                "filename": file.filename,
                "score": raw_data.get("total_score", 0),
                "pros": raw_data.get("highlights", []), 
                "deductions": raw_data.get("deductions", []), 
                "summary": f"[{raw_data.get('recommendation_level', '观望')}] {raw_data.get('summary', '')}",
                "dimensions": raw_data.get("dimensions", [])
            }
            return mapped_data
            
        except Exception as e:
            return {
                "name": "解析失败",
                "filename": file.filename,
                "score": 0,
                "pros": [],
                "deductions": [{"detail": f"简历评估失败: {str(e)}", "minus": -100}],
                "summary": "[打分异常] 请检查文件内容或 API 额度"
            }

    tasks = [process_single(file) for file in files]
    results = await asyncio.gather(*tasks)
    
    results.append({"_is_sorted": True})
    valid_results = [r for r in results if "score" in r]
    valid_results.sort(key=lambda x: x["score"], reverse=True)
    
    return {"candidates": valid_results}
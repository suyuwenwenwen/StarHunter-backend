from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
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


def _extract_json_object(text: str) -> dict:
    """从 LLM 回复中鲁棒地提取 JSON 对象。

    优先匹配 ```json 代码块（大小写不敏感）；失败时按括号配平兜底扫描文本，
    避免因 LLM 输出格式稍有变化（如 ```JSON、无语言标签、块后有尾随文字）
    导致更新数据解析失败、C 端简历无法同步。
    """
    m = re.search(r'```(?:json)?[ \t]*\n(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            parsed = json.loads(m.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    # 兜底：从后往前找 '{'，括号配平后尝试 json.loads
    for start in range(len(text) - 1, -1, -1):
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
                    try:
                        parsed = json.loads(text[start:end + 1])
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        pass
                    break
    return {}


@app.post("/api/extract")
async def extract_resume(file: UploadFile = File(...)):
    pdf_reader = PyPDF2.PdfReader(file.file)
    raw_text = "".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
    
    # 恢复你最原始的硬编码 Prompt
    prompt = f"请将以下简历解析为JSON格式。字段包括: NAME, LOCATION, EMAIL, PHONE, GITHUB, LINKEDIN, SITE, EDU_SCHOOL, EDU_LOCATION, EDU_DATE, EDU_DEGREE, EDU_COURSES, EDU_AWARDS, EXP_1_COMPANY, EXP_1_ROLE, EXP_1_LOCATION, EXP_1_DATE, EXP_1_CONTENT, EXP_2_COMPANY, EXP_2_ROLE, EXP_2_LOCATION, EXP_2_DATE, EXP_2_CONTENT, CAMPUS_ORG, CAMPUS_ROLE, CAMPUS_LOCATION, CAMPUS_DATE, CAMPUS_CONTENT, SKILL_PRO, SKILL_TOOL, SKILL_LANG。如果有多个经历，挑最重要的2个。经历描述用'-'分点。只输出JSON代码块。\n\n{raw_text}"
    
    res = await aclient.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.1)
    ans = res.choices[0].message.content
    data = _extract_json_object(ans)
    return {"data": data}


@app.post("/api/diagnose")
async def diagnose_resume(req: ChatRequest):
    combined_context = f"【目标岗位描述】\n{req.jd_input}\n\n【当前简历数据字典】\n{json.dumps(req.resume_data, ensure_ascii=False)}"
    prompt = get_initial_diagnose_prompt(combined_context)
    
    res = await aclient.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.5)
    return {"reply": res.choices[0].message.content}


@app.post("/api/chat")
async def chat_with_ai(req: ChatRequest):
    system_context = f"当前数据字典：{json.dumps(req.resume_data, ensure_ascii=False)}\n目标JD：{req.jd_input}"
    sys_prompt = get_system_instruction(system_context)
    
    api_msgs = [{"role": "system", "content": sys_prompt}] + req.messages
    res = await aclient.chat.completions.create(model=MODEL_NAME, messages=api_msgs, temperature=0.5)
    full_ans = res.choices[0].message.content

    # 提取 JSON 更新块（大小写不敏感、兼容各种代码块格式），并从回复中剔除
    updated_fields = _extract_json_object(full_ans)
    clean_ans = re.sub(r'```(?:json)?[ \t]*\n.*?```', '', full_ans, flags=re.DOTALL | re.IGNORECASE).strip()

    return {"reply": clean_ans, "updated_fields": updated_fields}


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

        # 2. 写入排版配置（模板通过 json("resume_config.json") 读取）
        with temp_config_path.open("w", encoding="utf-8") as f:
            json.dump({
                "template": template_num,
                "font_size": float(req.font_size),
                "line_spacing": float(req.line_spacing),
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
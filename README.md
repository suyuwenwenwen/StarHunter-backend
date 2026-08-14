# StarHunter Backend

基于 FastAPI 的 AI 简历评估后端，为前端（求职者工作台 / HR 筛选中心）提供接口。

## 功能

- `POST /api/extract` — 解析 PDF 简历为结构化 JSON
- `POST /api/diagnose` — 首次深度诊断
- `POST /api/chat` — 多轮精修对话，并返回 `updated_fields` 供前端同步更新简历
- `POST /api/compile` — 用 Typst 将结构化数据编译为 PDF
- `POST /api/hr/batch-evaluate` — B 端批量评估

## 环境变量

- `DEEPSEEK_API_KEY`（推荐）或 `OPENAI_API_KEY`
- 可选：`DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）、`LLM_MODEL`（默认 `deepseek-chat`）

复制 `.env.example` 为 `.env` 并填写 Key（`.env` 已被 gitignore，不会提交）。

## 启动

```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

> `/api/compile` 依赖本机安装的 [Typst](https://typst.app/)，请确保其在 PATH 中。

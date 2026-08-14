FROM python:3.10-slim

# 安装系统基础工具
RUN apt-get update && apt-get install -y wget xz-utils

# 下载并安装 Typst 排版引擎
RUN wget https://github.com/typst/typst/releases/download/v0.11.0/typst-x86_64-unknown-linux-musl.tar.xz
RUN tar -xvf typst-x86_64-unknown-linux-musl.tar.xz
RUN mv typst-x86_64-unknown-linux-musl/typst /usr/local/bin/

# 设置工作目录
WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝所有后端代码
COPY . .

# 启动 FastAPI 服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
FROM python:3.11-slim

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制依赖定义文件并安装依赖
# 这样可以利用 Docker 缓存，只有当依赖变化时才重新安装
COPY pyproject.toml README.md /app/

RUN uv pip install --system -e .

# 复制项目剩余文件
COPY . .

EXPOSE 8000

CMD ["python", "run_server.py"]
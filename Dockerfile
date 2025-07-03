FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install uv && \
    uv pip install -r requirements.txt

RUN mkdir -p /app/config

EXPOSE 8000

CMD ["python", "run_server.py"]
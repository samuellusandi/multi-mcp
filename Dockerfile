FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

COPY . .

RUN uv venv \
 && uv pip install -r requirements.txt

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=/app

# Optional: copy config file
COPY ./examples/config/mcp_k8s.json /app/mcp.json

# Start app

CMD ["python", "main.py", "--transport", "sse", "--config", "mcp.json","--host",""]

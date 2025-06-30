FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

RUN apk add --no-cache curl tar ca-certificates openssh-client

RUN curl -LO https://github.com/containers/podman/releases/download/v5.5.1/podman-remote-static-linux_amd64.tar.gz && \
    tar -xzf podman-remote-static-linux_amd64.tar.gz && \
    cp bin/podman-remote-static-linux_amd64 /usr/bin/podman && \
    chmod +x /usr/bin/podman && \
    rm -rf podman-remote-static-linux_amd64.tar.gz

COPY . .

RUN uv venv && uv sync

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=/app
ENV PATH="/usr/bin:$PATH"

COPY ./examples/config/mcp.json /app/mcp.json

CMD ["python", "main.py", "--transport", "stream", "--host", "0.0.0.0", "--port", "8000", "--log-level", "DEBUG", ""]

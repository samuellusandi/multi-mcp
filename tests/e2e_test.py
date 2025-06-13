import asyncio

import pytest
from langchain_mcp_adapters.client import MultiServerMCPClient

from tests.utils import run_e2e_test_with_client

EXPECTED_TOOLS=["weather::get_weather", "calculator::add", "calculator::multiply"]
TEST_PROMPTS=[
        ("what is the weather in London?", "weather in london"),
        ("what's the answer for (10 + 5)?", "15"),
    ]

@pytest.mark.asyncio
async def test_stdio_mode():
    """Test the MultiMCP server running in stdio mode."""
    async with MultiServerMCPClient() as client:
        await client.connect_to_server(
            "multi-mcp",
            command="python",
            args=["./main.py"],
        )
        await run_e2e_test_with_client(client,EXPECTED_TOOLS,TEST_PROMPTS)

@pytest.mark.asyncio
async def test_sse_mode():
    """Test the MultiMCP server running in SSE mode via subprocess."""
    process = await asyncio.create_subprocess_exec(
        "python", "main.py", "--transport", "sse",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        # ⏳ Wait for the server to be ready (TODO- improve this with health checks or retry)
        await asyncio.sleep(4)
        async with MultiServerMCPClient() as client:
            await client.connect_to_server(
                "multi-mcp",
                transport="sse",
                url="http://127.0.0.1:8080/sse",
            )
            await run_e2e_test_with_client(client,EXPECTED_TOOLS,TEST_PROMPTS)
    finally:
        # 🔚 Cleanup: kill server process
        process.kill()
        # ✅ Read to avoid transport issues
        if process.stdout:
            await process.stdout.read()
        if process.stderr:
            await process.stderr.read()


@pytest.mark.asyncio
async def test_sse_clients_mode():
    """Test MultiMCP with SSE-configured backend clients from a config file."""
    process = await asyncio.create_subprocess_exec(
        "python", "./tests/tools/get_weather_sse.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with MultiServerMCPClient() as client:
            await client.connect_to_server(
                "multi-mcp",
                command="python",
                args=["./main.py", "--config","./examples/config/mcp_sse.json"],
            )
            await run_e2e_test_with_client(client,EXPECTED_TOOLS,TEST_PROMPTS)
    finally:
        # 🔚 Cleanup: kill server process
        process.kill()
        # ✅ Read to avoid transport issues
        if process.stdout:
            await process.stdout.read()
        if process.stderr:
            await process.stderr.read()

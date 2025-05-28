import asyncio
import argparse
from src.multimcp.multi_mcp import MultiMCP

def parse_args():
    parser = argparse.ArgumentParser(description="Run MultiMCP server.")
    parser.add_argument("--transport",choices=["stdio", "sse"], default="stdio", help="Transport mode")
    parser.add_argument("--config",type=str,default="./examples/config/mcp.json",help="Path to MCP config JSON file")
    parser.add_argument("--host", type=str, default="127.0.0.1",help="Host to bind the SSE server")
    parser.add_argument("--port", type=int, default=8080,help="Port to bind the SSE server")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],default="INFO", help="Logging level")
    parser.add_argument("--sse-server-debug", type=str, default="false", help="Enable SSE server debug mode")
    parser.add_argument("--basic-auth", type=str, default=None, help="Basic authentication user:password pair")

    return parser.parse_args()


if __name__ == "__main__":
    # Parse CLI arguments and launch the MultiMCP server with the provided settings
    args = parse_args()

    sse_server_debug = args.sse_server_debug and args.sse_server_debug.lower() in ['true', '1', 't', 'y', 'yes']
    server = MultiMCP(
        transport=args.transport,
        config=args.config,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        sse_server_debug=args.sse_server_debug,
        basic_auth=args.basic_auth
    )
    asyncio.run(server.run())

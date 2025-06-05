"""Main entrypoint."""

import argparse
import asyncio

from src.multimcp.multi_mcp import MultiMCP


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run MultiMCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "stream"],
        default="stdio",
        help="Transport mode",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="./examples/config/mcp.json",
        help="Path to MCP config JSON file",
    )
    parser.add_argument(
        "--host", type=str,
        default="127.0.0.1",
        help="Host to bind the SSE server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind the SSE server",
    )
    parser.add_argument(
        "--sse-port",
        type=int,
        default=8080,
        help="Port to bind the SSE server",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--sse-server-debug",
        type=str,
        default="false",
        help="Enable SSE server debug mode",
    )
    parser.add_argument(
        "--basic-auth",
        type=str,
        default=None,
        help="Basic authentication user:password pair",
    )
    parser.add_argument(
        "--unify",
        type=str,
        default="false",
        help="Open a route for all tools to one server",
    )

    return parser.parse_args()


def str_to_bool(value):
    """Convert string to boolean."""
    return value and value.lower() in ['true', '1', 't', 'y', 'yes']


if __name__ == "__main__":
    # Parse CLI arguments and launch the MultiMCP server with the provided settings
    args = parse_args()

    sse_server_debug = str_to_bool(args.sse_server_debug)
    unify = str_to_bool(args.unify)
    server = MultiMCP(
        transport=args.transport,
        config=args.config,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        sse_server_debug=args.sse_server_debug,
        basic_auth=args.basic_auth,
        unify=unify
    )
    asyncio.run(server.run())

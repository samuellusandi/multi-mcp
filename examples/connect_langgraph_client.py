import asyncio
import os

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

# Initialize the chat model using OpenAI-compatible settings.
model = ChatOpenAI(
    model        =os.environ.get("MODEL_NAME"),
    base_url         = os.environ["BASE_URL"],
    api_key         = os.environ["OPENAI_API_KEY"],
    temperature     = 0.7,
)

async def main():
    # Create and connect a MultiServerMCPClient to the proxy server
    async with MultiServerMCPClient() as client:
        await client.connect_to_server(
            "multi-mcp",
            command="python",
            args=["./main.py"],
            # transport="sse",
            # url="http://127.0.0.1:8080/sse",  # SSE URL
        )

        # Retrieve the tools exposed by the connected MCP server(s)
        tools=client.get_tools()
        print(f"🔧 Tools list:{  [tool.name for tool in tools]}")

        # Create a reactive LangGraph agent using the MCP tools
        agent = create_react_agent(model, tools)

        # Run first message — uses weather tool
        response = await agent.ainvoke({"messages": "what is the weather in London?"})
        for m in response['messages']:
            m.pretty_print()

        # Run second message — uses calculator tool
        response = await agent.ainvoke({"messages": "what's the answer for (10 + 5)?"})
        for m in response['messages']:
            m.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())

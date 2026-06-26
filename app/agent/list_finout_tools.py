"""
Utility script to connect to Finout MCP server and list all available tools.
Run this first to verify your credentials and see what tools are available.

Usage:
    python list_finout_tools.py
"""

import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()

FINOUT_MCP_URL = os.getenv("FINOUT_MCP_URL", "https://mcp.finout.io/mcp")
FINOUT_CLIENT_ID = os.getenv("FINOUT_CLIENT_ID", "")
FINOUT_API_KEY = os.getenv("FINOUT_API_KEY", "")


async def main():
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    if not FINOUT_CLIENT_ID or not FINOUT_API_KEY:
        print("ERROR: Set FINOUT_CLIENT_ID and FINOUT_API_KEY in .env file")
        return

    headers = {
        "x-finout-client-id": FINOUT_CLIENT_ID,
        "Authorization": f"Bearer {FINOUT_API_KEY}",
    }

    print(f"Connecting to: {FINOUT_MCP_URL}")
    print(f"Client ID: {FINOUT_CLIENT_ID[:8]}...")
    print()

    async with sse_client(FINOUT_MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()

            print(f"Found {len(tools_result.tools)} tools:\n")
            for i, tool in enumerate(tools_result.tools, 1):
                print(f"{i:2}. {tool.name}")
                print(f"    {tool.description}")
                if hasattr(tool, 'inputSchema') and tool.inputSchema:
                    props = tool.inputSchema.get('properties', {})
                    if props:
                        print(f"    Parameters: {', '.join(props.keys())}")
                print()


if __name__ == "__main__":
    asyncio.run(main())

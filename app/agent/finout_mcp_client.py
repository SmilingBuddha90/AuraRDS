"""
Finout MCP Client
Connects to the Finout MCP server at https://mcp.finout.io/mcp using
OAuth2 client credentials (client_id + api_key as Bearer token).
"""

import os
import logging
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

FINOUT_MCP_URL = os.getenv("FINOUT_MCP_URL", "https://mcp.finout.io/mcp")
FINOUT_CLIENT_ID = os.getenv("FINOUT_CLIENT_ID", "")
FINOUT_API_KEY = os.getenv("FINOUT_API_KEY", "")


def get_auth_headers() -> dict:
    """Build authentication headers for Finout MCP requests."""
    if not FINOUT_CLIENT_ID or not FINOUT_API_KEY:
        raise ValueError(
            "FINOUT_CLIENT_ID and FINOUT_API_KEY must be set in environment"
        )
    return {
        "x-finout-client-id": FINOUT_CLIENT_ID,
        "Authorization": f"Bearer {FINOUT_API_KEY}",
        "Content-Type": "application/json",
    }


async def list_finout_tools() -> list[dict]:
    """Connect to Finout MCP server and list all available tools."""
    headers = get_auth_headers()
    async with sse_client(FINOUT_MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                }
                for t in tools_result.tools
            ]


async def call_finout_tool(tool_name: str, arguments: dict) -> Any:
    """Call a specific Finout MCP tool and return the result."""
    headers = get_auth_headers()
    async with sse_client(FINOUT_MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                return result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
            return ""


def build_finout_mcp_tool_config() -> dict:
    """
    Returns the MCP server configuration dict for use with strands-agents.
    Strands agents accept an mcp_config that specifies the server URL and headers.
    """
    return {
        "url": FINOUT_MCP_URL,
        "headers": get_auth_headers(),
        "transport": "sse",
    }

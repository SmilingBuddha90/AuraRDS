"""
Finout RDS/Aurora Agentic Cost Review — Entry Point

Usage:
    python main.py --local "Full Finout cost review of my RDS/Aurora fleet"
    python main.py --local "Analyze RDS spend breakdown for last 30 days"
    python main.py --local "Plan forecast and anomaly detection for Aurora clusters"
    python main.py --local "Operate showback report for RDS costs by team"
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0"
)
FINOUT_MCP_URL = os.getenv("FINOUT_MCP_URL", "https://mcp.finout.io/mcp")
FINOUT_DOCS_MCP_URL = os.getenv("FINOUT_DOCS_MCP_URL", "https://docs.finout.io/~gitbook/mcp")
AWS_DOCS_MCP_URL = os.getenv("AWS_DOCS_MCP_URL", "https://docs.aws.amazon.com/mcp")
FINOUT_CLIENT_ID = os.getenv("FINOUT_CLIENT_ID", "")
FINOUT_API_KEY = os.getenv("FINOUT_API_KEY", "")
REPORTS_DIR = os.getenv("REPORTS_DIR", "~/reports")
MAX_PROMPT_LENGTH = 10_000


def validate_config() -> None:
    """Validate required environment variables are set."""
    missing = []
    if not FINOUT_CLIENT_ID:
        missing.append("FINOUT_CLIENT_ID")
    if not FINOUT_API_KEY:
        missing.append("FINOUT_API_KEY")
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Copy .env.example to .env and fill in your Finout credentials.")
        sys.exit(1)


def sanitize_prompt(prompt: str) -> str:
    """Basic prompt length and injection guard."""
    if len(prompt) > MAX_PROMPT_LENGTH:
        logger.warning(f"Prompt truncated from {len(prompt)} to {MAX_PROMPT_LENGTH} chars")
        prompt = prompt[:MAX_PROMPT_LENGTH]

    # Block obvious injection patterns
    injection_patterns = [
        "ignore previous", "ignore all", "disregard", "new instructions",
        "system prompt", "jailbreak", "act as", "you are now",
    ]
    prompt_lower = prompt.lower()
    for pattern in injection_patterns:
        if pattern in prompt_lower:
            logger.warning(f"Potential prompt injection detected: '{pattern}'")
            raise ValueError(f"Prompt contains disallowed pattern: '{pattern}'")

    return prompt.strip()


def _load_mcp_tools(mcp_client_factory) -> list:
    """Load tools from an MCP server, returning empty list on failure."""
    try:
        from strands.tools.mcp import MCPClient
        client = MCPClient(mcp_client_factory)
        tools = client.list_tools_sync()
        return tools
    except Exception as e:
        logger.warning(f"  Could not load MCP tools: {e}")
        return []


async def run_review(query: str) -> None:
    """Main review orchestration using Finout + AWS/Finout Docs MCP tools."""
    from mcp.client.sse import sse_client
    from strands.models import BedrockModel

    from agents.coordinator import run_coordinator
    from report_generator import generate_report

    logger.info("=" * 70)
    logger.info("Finout RDS/Aurora Agentic Cost Review")
    logger.info(f"  Query:  {query}")
    logger.info(f"  Model:  {BEDROCK_MODEL_ID}")
    logger.info(f"  Region: {AWS_REGION}")
    logger.info("=" * 70)

    model = BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
    )

    finout_auth_headers = {
        "x-finout-client-id": FINOUT_CLIENT_ID,
        "Authorization": f"Bearer {FINOUT_API_KEY}",
    }

    # ── Load Finout MCP tools (cost data) ────────────────────────────────────
    logger.info(f"[1/3] Connecting to Finout MCP: {FINOUT_MCP_URL}")
    mcp_tools = _load_mcp_tools(
        lambda: sse_client(FINOUT_MCP_URL, headers=finout_auth_headers)
    )
    logger.info(f"  Loaded {len(mcp_tools)} Finout cost tools.")

    # ── Load AWS Docs MCP tools ───────────────────────────────────────────────
    logger.info(f"[2/3] Connecting to AWS Docs MCP: {AWS_DOCS_MCP_URL}")
    aws_docs_tools = _load_mcp_tools(
        lambda: sse_client(AWS_DOCS_MCP_URL)
    )
    logger.info(f"  Loaded {len(aws_docs_tools)} AWS Docs tools.")

    # ── Load Finout Docs MCP tools ────────────────────────────────────────────
    logger.info(f"[3/3] Connecting to Finout Docs MCP: {FINOUT_DOCS_MCP_URL}")
    finout_docs_tools = _load_mcp_tools(
        lambda: sse_client(FINOUT_DOCS_MCP_URL, headers=finout_auth_headers)
    )
    logger.info(f"  Loaded {len(finout_docs_tools)} Finout Docs tools.")

    if not mcp_tools:
        logger.error("No Finout cost tools loaded. Check FINOUT_CLIENT_ID and FINOUT_API_KEY.")
        sys.exit(1)

    # ── Run pillar agents + docs enrichment via coordinator ───────────────────
    start_time = time.time()
    pillar_results = run_coordinator(
        mcp_tools=mcp_tools,
        model=model,
        query=query,
        aws_docs_tools=aws_docs_tools,
        finout_docs_tools=finout_docs_tools,
    )
    elapsed = time.time() - start_time

    logger.info(f"\nAnalysis complete in {elapsed:.1f}s. Sections: {list(pillar_results.keys())}")

    # ── Generate Word report ──────────────────────────────────────────────────
    report_path = generate_report(pillar_results, query, REPORTS_DIR)
    logger.info("=" * 70)
    logger.info(f"Report saved: {report_path}")
    logger.info("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finout RDS/Aurora Agentic Cost Review"
    )
    parser.add_argument(
        "--local",
        type=str,
        metavar="QUERY",
        help='Run a local review. Example: --local "Full cost review of my RDS fleet"',
    )
    args = parser.parse_args()

    if not args.local:
        parser.print_help()
        sys.exit(1)

    validate_config()

    try:
        query = sanitize_prompt(args.local)
        asyncio.run(run_review(query))
    except ValueError as e:
        logger.error(f"Invalid query: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Review interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Review failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

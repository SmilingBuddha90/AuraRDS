"""
Finout RDS/Aurora Cost Review — Streamlit Frontend
Provides a browser UI for running the agentic cost review and downloading reports.
"""

import asyncio
import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# Add the agent directory to path so we can import from it
AGENT_DIR = Path(__file__).parent.parent / "agent"
sys.path.insert(0, str(AGENT_DIR))

load_dotenv(AGENT_DIR / ".env")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Finout RDS Cost Review",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1A56DB 0%, #374A5C 100%);
        padding: 20px 30px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    .pillar-card {
        background: #f8faff;
        border-left: 4px solid #1A56DB;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .status-running { color: #f59e0b; font-weight: bold; }
    .status-done    { color: #10b981; font-weight: bold; }
    .status-error   { color: #ef4444; font-weight: bold; }
    .stButton > button {
        background-color: #1A56DB;
        color: white;
        border-radius: 8px;
        padding: 10px 30px;
        font-size: 16px;
        border: none;
    }
    .stButton > button:hover { background-color: #1648c0; }
</style>
""", unsafe_allow_html=True)


# ── Helper: run async in a thread ─────────────────────────────────────────────
def run_async(coro):
    """Run an async coroutine from a sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Helper: load config from env ──────────────────────────────────────────────
def get_config():
    return {
        "aws_region":         os.getenv("AWS_REGION", "us-east-1"),
        "bedrock_model":      os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0"),
        "finout_mcp_url":     os.getenv("FINOUT_MCP_URL", "https://mcp.finout.io/mcp"),
        "finout_docs_url":    os.getenv("FINOUT_DOCS_MCP_URL", "https://docs.finout.io/~gitbook/mcp"),
        "aws_docs_url":       os.getenv("AWS_DOCS_MCP_URL", "https://docs.aws.amazon.com/mcp"),
        "finout_client_id":   os.getenv("FINOUT_CLIENT_ID", ""),
        "finout_api_key":     os.getenv("FINOUT_API_KEY", ""),
        "reports_dir":        os.getenv("REPORTS_DIR", "~/reports"),
    }


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(config: dict):
    st.sidebar.markdown("## Configuration")

    st.sidebar.markdown("**AWS Settings**")
    st.sidebar.code(f"Region: {config['aws_region']}\nModel:  {config['bedrock_model'].split('.')[-1]}", language="text")

    st.sidebar.markdown("**Finout Connection**")
    if config["finout_client_id"] and config["finout_api_key"]:
        st.sidebar.success(f"Client ID: {config['finout_client_id'][:8]}...")
    else:
        st.sidebar.error("Finout credentials not set in .env")

    st.sidebar.markdown("**MCP Servers**")
    st.sidebar.markdown(f"- Cost: `mcp.finout.io`")
    st.sidebar.markdown(f"- Finout Docs: `docs.finout.io`")
    st.sidebar.markdown(f"- AWS Docs: `docs.aws.amazon.com`")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Reports folder**")
    reports_path = Path(config["reports_dir"]).expanduser()
    reports = sorted(reports_path.glob("*.docx"), key=os.path.getmtime, reverse=True) if reports_path.exists() else []
    st.sidebar.markdown(f"`{reports_path}` — {len(reports)} report(s)")

    return reports


# ── Main review runner ────────────────────────────────────────────────────────
async def run_review_async(query: str, config: dict, log_callback) -> dict:
    """Run the full agentic review and return pillar results."""
    from mcp.client.sse import sse_client
    from strands.models import BedrockModel
    from agents.coordinator import run_coordinator
    from report_generator import generate_report

    model = BedrockModel(
        model_id=config["bedrock_model"],
        region_name=config["aws_region"],
    )

    finout_headers = {
        "x-finout-client-id": config["finout_client_id"],
        "Authorization": f"Bearer {config['finout_api_key']}",
    }

    def load_tools(url, headers=None):
        try:
            from strands.tools.mcp import MCPClient
            factory = (lambda: sse_client(url, headers=headers)) if headers else (lambda: sse_client(url))
            client = MCPClient(factory)
            tools = client.list_tools_sync()
            log_callback(f"  Loaded {len(tools)} tools from {url.split('/')[2]}")
            return tools
        except Exception as e:
            log_callback(f"  Warning: Could not load tools from {url.split('/')[2]}: {e}")
            return []

    log_callback("[1/3] Connecting to Finout MCP (cost data)...")
    mcp_tools = load_tools(config["finout_mcp_url"], finout_headers)

    if not mcp_tools:
        raise ValueError("No Finout tools loaded. Check your Client ID and API Key in .env")

    log_callback("[2/3] Connecting to AWS Docs MCP...")
    aws_docs_tools = load_tools(config["aws_docs_url"])

    log_callback("[3/3] Connecting to Finout Docs MCP...")
    finout_docs_tools = load_tools(config["finout_docs_url"], finout_headers)

    log_callback("\nRunning pillar agents...")
    start = time.time()

    pillar_results = run_coordinator(
        mcp_tools=mcp_tools,
        model=model,
        query=query,
        aws_docs_tools=aws_docs_tools,
        finout_docs_tools=finout_docs_tools,
    )

    elapsed = time.time() - start
    log_callback(f"\nAnalysis complete in {elapsed:.0f}s")

    report_path = generate_report(pillar_results, query, config["reports_dir"])
    log_callback(f"Report saved: {report_path}")

    return {"pillar_results": pillar_results, "report_path": report_path}


# ── Main page ─────────────────────────────────────────────────────────────────
def main():
    config = get_config()

    # Header
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0">💰 Finout RDS/Aurora Cost Review</h1>
        <p style="margin:5px 0 0 0; opacity:0.85">
            AI-powered cost intelligence — Analyze · Plan · Operate
        </p>
    </div>
    """, unsafe_allow_html=True)

    reports = render_sidebar(config)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_run, tab_reports, tab_help = st.tabs(["Run Review", "Past Reports", "How It Works"])

    # ── Tab 1: Run Review ──────────────────────────────────────────────────────
    with tab_run:
        st.markdown("### What would you like to review?")

        col1, col2 = st.columns([2, 1])

        with col1:
            query = st.text_area(
                "Enter your review query",
                value="Full Finout cost review of my RDS/Aurora fleet",
                height=80,
                help="Describe what you want to analyze. Be specific or broad.",
            )

        with col2:
            st.markdown("**Quick queries:**")
            if st.button("Full 3-Pillar Review"):
                query = "Full Finout cost review of my RDS/Aurora fleet"
            if st.button("Analyze Past Spend"):
                query = "Analyze RDS spend breakdown for last 30 days"
            if st.button("Plan Forecast"):
                query = "Plan forecast and anomaly detection for Aurora clusters"
            if st.button("Operate Showback"):
                query = "Operate showback report for RDS costs by team"

        st.markdown("**Select pillars to run:**")
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            run_analyze = st.checkbox("Analyze (Past)", value=True,
                help="Historical spend breakdown, cost allocation, unit economics")
        with col_b:
            run_plan = st.checkbox("Plan (Future)", value=True,
                help="Forecasts, anomaly detection, RI recommendations")
        with col_c:
            run_operate = st.checkbox("Operate (Teams)", value=True,
                help="Showback, chargeback, team ownership")
        with col_d:
            run_docs = st.checkbox("Docs Enrichment", value=True,
                help="Add AWS and Finout documentation references")

        st.markdown("---")

        # Credential check before allowing run
        creds_ok = config["finout_client_id"] and config["finout_api_key"]
        if not creds_ok:
            st.error("Finout credentials not configured. Edit `.env` file and restart Streamlit.")

        run_btn = st.button("Run Review", disabled=not creds_ok, use_container_width=True)

        if run_btn:
            if not query.strip():
                st.warning("Please enter a query.")
                st.stop()

            # Build query with selected pillars
            pillar_hints = []
            if run_analyze: pillar_hints.append("analyze")
            if run_plan:    pillar_hints.append("plan")
            if run_operate: pillar_hints.append("operate")
            if not pillar_hints:
                st.warning("Select at least one pillar.")
                st.stop()

            if len(pillar_hints) == 3:
                final_query = f"Full review: {query}"
            else:
                final_query = f"{' and '.join(pillar_hints)} review: {query}"

            # Log area
            log_lines = []
            log_placeholder = st.empty()
            status_placeholder = st.empty()

            def log_callback(msg: str):
                log_lines.append(msg)
                log_placeholder.code("\n".join(log_lines), language="text")

            status_placeholder.markdown('<p class="status-running">Running review... this takes 3–8 minutes</p>',
                                        unsafe_allow_html=True)

            with st.spinner("AI agents are analyzing your RDS/Aurora fleet..."):
                try:
                    result = run_async(run_review_async(final_query, config, log_callback))

                    status_placeholder.markdown('<p class="status-done">Review complete!</p>',
                                               unsafe_allow_html=True)

                    # Show results in expandable sections
                    st.markdown("---")
                    st.markdown("### Results")

                    pillar_titles = {
                        "analyze": "Analyze — Visibility into the Past",
                        "plan":    "Plan — Confidence in the Future",
                        "operate": "Operate — Ownership that Scales",
                        "docs_enrichment": "Documentation References",
                    }

                    for key, title in pillar_titles.items():
                        if key in result["pillar_results"]:
                            with st.expander(f"📊 {title}", expanded=(key == "analyze")):
                                st.markdown(result["pillar_results"][key])

                    # Download button
                    report_path = Path(result["report_path"])
                    if report_path.exists():
                        with open(report_path, "rb") as f:
                            st.download_button(
                                label="Download Word Report (.docx)",
                                data=f.read(),
                                file_name=report_path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                            )

                except Exception as e:
                    status_placeholder.markdown('<p class="status-error">Review failed</p>',
                                               unsafe_allow_html=True)
                    st.error(f"Error: {e}")
                    st.info("Check the log above for details. Common fixes:\n"
                            "- Verify `.env` credentials\n"
                            "- Ensure Bedrock Claude access is enabled\n"
                            "- Check internet connectivity to mcp.finout.io")

    # ── Tab 2: Past Reports ────────────────────────────────────────────────────
    with tab_reports:
        st.markdown("### Past Reports")

        if not reports:
            st.info("No reports yet. Run a review first.")
        else:
            for report_file in reports[:10]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    mtime = datetime.fromtimestamp(report_file.stat().st_mtime)
                    size_kb = report_file.stat().st_size // 1024
                    st.markdown(f"**{report_file.name}**  \n"
                                f"Generated: {mtime.strftime('%Y-%m-%d %H:%M')} | Size: {size_kb} KB")
                with col2:
                    with open(report_file, "rb") as f:
                        st.download_button(
                            label="Download",
                            data=f.read(),
                            file_name=report_file.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=str(report_file),
                        )
                st.markdown("---")

    # ── Tab 3: How It Works ────────────────────────────────────────────────────
    with tab_help:
        st.markdown("### How It Works")

        st.markdown("""
        This tool connects to **Finout's MCP server** and uses **Claude AI** (via Amazon Bedrock)
        to automatically review your RDS and Aurora database costs across three pillars:
        """)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            <div class="pillar-card">
                <h4>Analyze</h4>
                <b>Visibility into the Past</b><br><br>
                Breaks down your RDS/Aurora spend by service, instance type, region, and team.
                Finds top cost drivers and idle resources.
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown("""
            <div class="pillar-card">
                <h4>Plan</h4>
                <b>Confidence in the Future</b><br><br>
                Forecasts your next 90 days of spend. Detects anomalies.
                Recommends Reserved Instance purchases with estimated savings.
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown("""
            <div class="pillar-card">
                <h4>Operate</h4>
                <b>Ownership that Scales</b><br><br>
                Shows which team owns which cost. Flags untagged resources.
                Generates per-team showback reports and action items.
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("""
        ```
        Your Query
             |
             v
        Coordinator Agent
             |
        ┌────┼────┐
        v    v    v
     Analyze Plan Operate  ──► Docs Enrichment (AWS + Finout Docs)
        └────┼────┘
             v
        Word Report + Browser Display
        ```
        """)


if __name__ == "__main__":
    main()

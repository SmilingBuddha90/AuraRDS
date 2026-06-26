# Finout RDS/Aurora Agentic Cost Review

A multi-agent AI system that conducts automated **Finout-powered cost reviews** for Amazon RDS and Aurora databases across three pillars using the Finout MCP server and Anthropic Claude via Amazon Bedrock.

## Architecture

```
[main.py]
     |
     v
[Coordinator Agent (Bedrock Claude)]
     |
     +---> Pillar Agent: Analyze   (Visibility into the Past)
     +---> Pillar Agent: Plan      (Confidence in the Future)
     +---> Pillar Agent: Operate   (Ownership that Scales)
              |
              v
     [Finout MCP Server: https://mcp.finout.io/mcp]
              |
     +---------+---------+---------+
     |         |         |         |
  Cost      Forecast  Anomaly   Dashboards
  Alloc     Budgets   Detect    Showback
              |
              v
     [Word Report (~/reports/)]
```

## Three Pillars

| Pillar | Focus | Finout Capabilities Used |
|--------|-------|--------------------------|
| **Analyze** | Visibility into the Past | Cost allocation, spend breakdown by service/tag/team, unit economics |
| **Plan** | Confidence in the Future | Budget forecasting, anomaly detection, trend analysis, commitment planning |
| **Operate** | Ownership that Scales | Role-based showback, chargeback, cross-team dashboards, actionable recommendations |

## Prerequisites

- Python 3.12+
- AWS account with Bedrock Claude access
- Finout account with API credentials
- RDS/Aurora instances to analyze

## Setup

```bash
git clone <this-repo>
cd finout-rds-review/app/agent
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

## Configuration (.env)

```
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0
FINOUT_MCP_URL=https://mcp.finout.io/mcp
FINOUT_CLIENT_ID=<your-client-id>
FINOUT_API_KEY=<your-api-key>
REPORTS_DIR=~/reports
```

## Usage

```bash
# Full 3-pillar review
python main.py --local "Full Finout cost review of my RDS/Aurora fleet"

# Single pillar
python main.py --local "Analyze RDS spend breakdown for last 30 days"
python main.py --local "Plan forecast and anomaly detection for Aurora clusters"
python main.py --local "Operate showback report for RDS costs by team"
```

## Output

Generates an executive Word document (`.docx`) in `~/reports/` with:
- Per-pillar findings and recommendations
- Cost breakdown tables and trend analysis
- Anomaly alerts and budget forecast
- Chargeback/showback summary by team
- Implementation roadmap with estimated savings

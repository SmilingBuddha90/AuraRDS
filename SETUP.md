# Setup Guide — Finout RDS/Aurora Agentic Cost Review

## Project Structure

```
finout-rds-review/
├── app/agent/
│   ├── main.py                  # Entry point
│   ├── finout_mcp_client.py     # Finout MCP connection helper
│   ├── report_generator.py      # Word document generator
│   ├── list_finout_tools.py     # Utility: list all Finout MCP tools
│   ├── requirements.txt
│   ├── .env.example
│   └── agents/
│       ├── __init__.py
│       ├── coordinator.py       # Routes query to pillar agents
│       ├── analyze_agent.py     # Pillar 1: Visibility into the Past
│       ├── plan_agent.py        # Pillar 2: Confidence in the Future
│       └── operate_agent.py     # Pillar 3: Ownership that Scales
├── .gitignore
├── README.md
└── SETUP.md
```

## Step 1: Clone and Set Up

```bash
cd ~/environment
# Already cloned — navigate to project
cd finout-rds-review/app/agent

python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 2: Configure Credentials

```bash
cp .env.example .env
```

Edit `.env`:

```
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0
FINOUT_MCP_URL=https://mcp.finout.io/mcp
FINOUT_CLIENT_ID=8a63cd40-91a7-485f-ab5d-80d0fd646658
FINOUT_API_KEY=f3f42ea4-91d2-4dd1-9c3e-2a9119aaf07e
REPORTS_DIR=~/reports
```

## Step 3: Verify Finout Connection

```bash
python list_finout_tools.py
```

Expected output: list of all available Finout MCP tools with descriptions.
This confirms your credentials work before running the full review.

## Step 4: Run the Review

```bash
# Full 3-pillar review
python main.py --local "Full Finout cost review of my RDS/Aurora fleet"

# Individual pillars
python main.py --local "Analyze RDS spend breakdown for last 30 days"
python main.py --local "Plan forecast and anomaly detection for Aurora clusters"
python main.py --local "Operate showback report for RDS costs by team"
```

## Step 5: View Report

```bash
ls -lh ~/reports/
# Reports are .docx Word files — download via Cloud9 File menu
```

## Differences from Original AWS WAR Project

| Feature | AWS WAR (original) | Finout RDS Review (this project) |
|---------|-------------------|----------------------------------|
| Pillars | 5 (Performance, Security, Reliability, Cost, Ops) | 3 (Analyze, Plan, Operate) |
| Data source | AWS APIs (RDS, CloudWatch, Cost Explorer) | Finout MCP server |
| MCP servers | 5 Lambda containers | 1 remote Finout MCP endpoint |
| Auth | Cognito OAuth + AgentCore Gateway | Finout API key (Bearer token) |
| Deployment | ECR + Lambda + AgentCore | No deployment needed — remote MCP |
| Focus | Well-Architected Review (all pillars) | Cost intelligence and optimization |

## No Lambda/ECR Deployment Needed

Unlike the original project, this does **not** require:
- Docker builds
- ECR repositories
- Lambda functions
- AgentCore Gateway setup
- Cognito User Pool

The Finout MCP server is a hosted remote endpoint — just configure your API key and run.

## Troubleshooting

### Connection Error to Finout MCP
```bash
# Test connectivity
curl -H "x-finout-client-id: YOUR_CLIENT_ID" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     https://mcp.finout.io/mcp
```

### Bedrock Access Denied
```bash
aws bedrock list-foundation-models \
  --query 'modelSummaries[?contains(modelId,`claude-sonnet-4`)].modelId'
```

### Missing python-docx
```bash
pip install python-docx
```

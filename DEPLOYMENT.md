# Deployment Steps — Finout RDS/Aurora Agentic Cost Review
### (Written simply — step by step, nothing skipped)

---

## What Are We Building?

Think of this like a smart robot that:
1. **Logs into Finout** (your cloud cost tool) and reads all your RDS/Aurora database bills
2. **Thinks about the data** using Claude AI (like ChatGPT but from Amazon)
3. **Writes you a report** in a Word document saying what costs too much and how to fix it

The robot has 4 helpers:
- **Analyze helper** — looks at past bills ("what did we spend?")
- **Plan helper** — looks at future bills ("what will we spend?")
- **Operate helper** — looks at who owns what ("which team is spending what?")
- **Docs helper** — finds official guides from AWS and Finout to back up every recommendation

---

## What You Need Before Starting

| Thing | Why you need it | Do you have it? |
|-------|----------------|-----------------|
| AWS account (sandbox) | To run the AI (Claude) | [ ] |
| Cloud9 environment | Your coding workspace in AWS | [ ] |
| Bedrock Claude access | The AI brain | [ ] |
| Finout account | Your cloud cost data | [ ] |
| Finout API key | Password to read Finout data | [ ] |

---

## STEP 1 — Open Your Cloud9 Terminal

1. Go to **AWS Console** → search **Cloud9** → click your environment
2. Click **Open** — a browser window opens with a terminal at the bottom
3. You should see something like:

```
nct-admin:~/environment $
```

That `$` means it is ready for you to type commands.

---

## STEP 2 — Copy the Project to Cloud9

Think of this like downloading a folder from the internet to your computer.

```bash
cd ~/environment
git clone https://github.com/YOUR-ORG/finout-rds-review.git
```

> **Note:** If you haven't pushed this to GitHub yet, copy the folder manually or use the steps below to create it fresh.

If creating fresh, just make the folder:

```bash
mkdir -p ~/environment/finout-rds-review/app/agent/agents
cd ~/environment/finout-rds-review
```

---

## STEP 3 — Install Python 3.12

Cloud9 comes with Python 3.11. This project needs 3.12. Check first:

```bash
python3.12 --version
```

If you see `Python 3.12.x` — skip to Step 4.

If you see `command not found`:

```bash
sudo dnf install -y python3.12 python3.12-pip python3.12-devel
python3.12 --version
```

---

## STEP 4 — Create a Private Python Workspace

Think of this like a clean box where we install only the tools this project needs — so it doesn't mess up anything else on your computer.

```bash
cd ~/environment/finout-rds-review/app/agent
python3.12 -m venv .venv
```

Now **activate** it (turn the box on):

```bash
source .venv/bin/activate
```

Your terminal prompt will change to show `(.venv)` at the start — that means it's working:

```
(.venv) nct-admin:~/environment/finout-rds-review/app/agent $
```

> Every time you open a NEW terminal, you must run `source .venv/bin/activate` again.

---

## STEP 5 — Install the Required Packages

Think of this like installing apps on a phone — but for Python.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- `strands-agents` — the AI agent framework
- `mcp` — connects to Finout's MCP server
- `boto3` — talks to AWS
- `python-docx` — creates the Word report
- `python-dotenv` — reads your secret keys from a file
- `httpx` — makes web requests to Finout

Wait for it to finish. You'll see many lines scroll by — that's normal.

---

## STEP 6 — Create Your Secrets File

This file holds your passwords and settings. It stays on your computer only — never goes to GitHub.

```bash
cd ~/environment/finout-rds-review/app/agent
cp .env.example .env
```

Now open and edit it:

```bash
nano .env
```

You'll see a file like this. Fill in your values:

```
# AWS Configuration
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0

# Finout MCP Server (cost data)
FINOUT_MCP_URL=https://mcp.finout.io/mcp
FINOUT_CLIENT_ID=8a63cd40-91a7-485f-ab5d-80d0fd646658
FINOUT_API_KEY=f3f42ea4-91d2-4dd1-9c3e-2a9119aaf07e

# Documentation MCP Servers
FINOUT_DOCS_MCP_URL=https://docs.finout.io/~gitbook/mcp
AWS_DOCS_MCP_URL=https://docs.aws.amazon.com/mcp

# Where to save reports
REPORTS_DIR=~/reports
```

To save and exit nano:
- Press `Ctrl + O` → then `Enter` (saves the file)
- Press `Ctrl + X` (exits)

---

## STEP 7 — Enable Claude AI in Amazon Bedrock

The AI brain needs to be switched on. You only do this once per AWS account.

1. Go to **AWS Console** → search **Amazon Bedrock** → click it
2. On the left sidebar click **Model access**
3. Click the orange **Manage model access** button
4. Find **Anthropic → Claude Sonnet 4** → tick the checkbox
5. Click **Save changes**
6. Wait 2–3 minutes — the status changes from "Available" to "Access granted"

---

## STEP 8 — Check AWS Credentials Are Working

```bash
aws sts get-caller-identity
```

You should see your account number printed:

```json
{
    "UserId": "...",
    "Account": "062968674300",
    "Arn": "arn:aws:sts::062968674300:assumed-role/RDS_Agentic_WAR/..."
}
```

If you see `ExpiredToken` error:
```bash
# Clear the stale token
rm -f ~/.aws/credentials

# Set your region
aws configure set region us-east-1

# Try again
aws sts get-caller-identity
```

---

## STEP 9 — Test the Finout Connection

Before running the full review, check that your Finout API key works:

```bash
cd ~/environment/finout-rds-review/app/agent
source .venv/bin/activate
python list_finout_tools.py
```

**Good output** looks like:
```
Connecting to: https://mcp.finout.io/mcp
Client ID: 8a63cd40...

Found 25 tools:

 1. get_cost_data
    Get cost and usage data for your cloud resources
    Parameters: start_date, end_date, granularity, filters

 2. get_anomalies
    Get cost anomalies detected in your account
    ...
```

**Bad output** (means credentials are wrong):
```
Error: 401 Unauthorized
```
→ Double-check `FINOUT_CLIENT_ID` and `FINOUT_API_KEY` in your `.env` file.

---

## STEP 10 — Create the Reports Folder

This is where the Word document report will be saved.

```bash
mkdir -p ~/reports
```

---

## STEP 11 — Run the Review!

You are ready. Run the full 3-pillar + docs review:

```bash
cd ~/environment/finout-rds-review/app/agent
source .venv/bin/activate

python main.py --local "Full Finout cost review of my RDS/Aurora fleet"
```

You will see it working step by step:

```
2026-06-26 [INFO] ======================================================================
2026-06-26 [INFO] Finout RDS/Aurora Agentic Cost Review
2026-06-26 [INFO]   Query:  Full Finout cost review of my RDS/Aurora fleet
2026-06-26 [INFO] ======================================================================
2026-06-26 [INFO] [1/3] Connecting to Finout MCP: https://mcp.finout.io/mcp
2026-06-26 [INFO]   Loaded 25 Finout cost tools.
2026-06-26 [INFO] [2/3] Connecting to AWS Docs MCP: https://docs.aws.amazon.com/mcp
2026-06-26 [INFO]   Loaded 3 AWS Docs tools.
2026-06-26 [INFO] [3/3] Connecting to Finout Docs MCP: https://docs.finout.io/~gitbook/mcp
2026-06-26 [INFO]   Loaded 5 Finout Docs tools.
2026-06-26 [INFO] [Coordinator] Routing to pillars: ['analyze', 'plan', 'operate']
2026-06-26 [INFO]   [Analyze] Starting spend breakdown analysis...
  ... (this takes 3-8 minutes) ...
2026-06-26 [INFO] Report saved: /home/ec2-user/reports/finout_rds_review_20260626_143022.docx
```

---

## STEP 12 — Download and Read the Report

The report is a `.docx` Word file saved in `~/reports/`.

**To download from Cloud9:**
1. In Cloud9, click **File** menu (top left)
2. Click **Download**
3. Navigate to `/home/ec2-user/reports/`
4. Click the `.docx` file → Download

Or check what reports exist:

```bash
ls -lh ~/reports/
```

---

## Other Useful Commands

```bash
# Analyze only (past spend breakdown)
python main.py --local "Analyze RDS spend breakdown for last 30 days"

# Plan only (forecasts and anomalies)
python main.py --local "Plan forecast and anomaly detection for Aurora clusters"

# Operate only (team ownership and showback)
python main.py --local "Operate showback report for RDS costs by team"

# Focus on a specific database
python main.py --local "Full review of my aurora-prod-cluster"
```

---

## Something Went Wrong? Check These First

| Error message | What it means | How to fix |
|---------------|---------------|------------|
| `(.venv)` not showing | Virtual environment not active | Run `source .venv/bin/activate` |
| `ModuleNotFoundError` | Package not installed | Run `pip install -r requirements.txt` |
| `ExpiredToken` | AWS credentials expired | Run `rm -f ~/.aws/credentials` then retry |
| `401 Unauthorized` from Finout | Wrong API key | Check `.env` file — copy keys again |
| `AccessDeniedException` from Bedrock | Claude not enabled | Go to Bedrock → Model access → enable Claude Sonnet 4 |
| `No module named dotenv` | python-dotenv missing | Run `pip install python-dotenv` |
| Report not generated | Review failed mid-way | Check the full error log above the failure line |

---

## Project File Map (What Each File Does)

```
finout-rds-review/
│
├── app/agent/
│   │
│   ├── main.py              ← START HERE. This runs everything.
│   ├── list_finout_tools.py ← Run this to test your Finout connection.
│   ├── finout_mcp_client.py ← Handles the Finout login/connection.
│   ├── report_generator.py  ← Turns AI results into a Word document.
│   ├── requirements.txt     ← List of packages to install (Step 5).
│   ├── .env.example         ← Template for your secrets file.
│   ├── .env                 ← YOUR secrets (never share this!).
│   │
│   └── agents/
│       ├── coordinator.py   ← The manager. Decides which helpers to call.
│       ├── analyze_agent.py ← Helper 1: "What did we spend?"
│       ├── plan_agent.py    ← Helper 2: "What will we spend?"
│       ├── operate_agent.py ← Helper 3: "Who owns what cost?"
│       └── docs_agent.py    ← Helper 4: "What do the docs say?"
│
├── DEPLOYMENT.md  ← This file!
├── SETUP.md       ← Technical setup notes
└── README.md      ← Project overview
```

---

## How It All Connects (Simple Picture)

```
You type a question
        |
        v
   main.py starts
        |
        ├── Logs into Finout MCP  ──► Gets your cost data tools
        ├── Logs into AWS Docs    ──► Gets AWS documentation tools
        └── Logs into Finout Docs ──► Gets Finout help docs tools
                    |
                    v
            coordinator.py
            (decides which helpers to wake up)
                    |
        ┌───────────┼───────────┐
        v           v           v
   analyze_    plan_agent   operate_
   agent.py      .py        agent.py
   (past $)  (future $)   (who owns $)
        └───────────┼───────────┘
                    |
                    v
            docs_agent.py
         (finds official guides
          to back up findings)
                    |
                    v
        report_generator.py
        (writes everything into
         a Word document)
                    |
                    v
        ~/reports/finout_rds_review_DATE.docx
```

---

*That's it! You now have a fully automated AI cost review tool for your RDS/Aurora fleet powered by Finout.*

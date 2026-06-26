# Deployment — Finout RDS/Aurora Agentic Cost Review

Choose your deployment platform:

| Guide | Platform | Best for |
|-------|----------|----------|
| [DEPLOYMENT_CLOUD9.md](DEPLOYMENT_CLOUD9.md) | AWS Cloud9 (AL2023) | Quick start — no SSH needed, browser IDE, auto credentials |
| [DEPLOYMENT_EC2.md](DEPLOYMENT_EC2.md) | AWS EC2 (AL2023) | Full control, production-ready, SSH access |

Both guides include the **Streamlit frontend** setup at the end.

## Project Structure

```
finout-rds-review/
├── app/
│   ├── agent/                  ← Core AI agents
│   │   ├── main.py             ← CLI entry point
│   │   ├── requirements.txt    ← Agent packages
│   │   ├── .env.example        ← Credentials template
│   │   ├── list_finout_tools.py
│   │   ├── finout_mcp_client.py
│   │   ├── report_generator.py
│   │   └── agents/
│   │       ├── coordinator.py
│   │       ├── analyze_agent.py
│   │       ├── plan_agent.py
│   │       ├── operate_agent.py
│   │       └── docs_agent.py
│   └── streamlit/              ← Browser frontend
│       ├── app.py              ← Streamlit UI
│       └── requirements.txt    ← Streamlit package
├── DEPLOYMENT.md               ← This file
├── DEPLOYMENT_CLOUD9.md        ← Cloud9 step-by-step guide
├── DEPLOYMENT_EC2.md           ← EC2 step-by-step guide
├── SECURITY.md                 ← Security layers + Cloud9 known issues
└── README.md
```

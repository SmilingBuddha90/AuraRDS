# Deployment Guide — EC2 (Amazon Linux 2023)
### Finout RDS/Aurora Agentic Cost Review — Step by Step

---

## What Are We Building?

A smart robot that:
1. **Logs into Finout** and reads all your RDS/Aurora database bills
2. **Thinks about the data** using Claude AI via Amazon Bedrock
3. **Shows you results** in a browser (Streamlit) AND saves a Word document report

---

## What You Need Before Starting

| Thing | Do you have it? |
|-------|----------------|
| AWS sandbox account with admin access | [ ] |
| SSH key pair (.pem file) downloaded to your laptop | [ ] |
| Amazon Bedrock Claude Sonnet 4 access enabled | [ ] |
| Finout account with Client ID and API Key | [ ] |

---

## STEP 1 — Launch EC2 Instance

1. **AWS Console** → **EC2** → **Launch Instance**
2. Fill in:

| Setting | Value |
|---------|-------|
| Name | `finout-rds-review` |
| AMI | **Amazon Linux 2023** |
| Instance type | `t3.medium` (minimum) or `t3.large` (recommended) |
| Key pair | Select existing or create new → download `.pem` file |
| Security group — Inbound rules | SSH port 22 from your IP; TCP port 8501 from your IP (for Streamlit) |
| Storage | 20 GB gp3 |
| IAM instance profile | Attach your IAM role (e.g. `RDS_Agentic_WAR`) |

3. Click **Launch instance** → wait ~1 minute for status **running**
4. Note the **Public IPv4 address** — you need it for SSH

---

## STEP 2 — Connect via SSH

### Mac / Linux (run on your laptop):
```bash
# Fix key permissions
chmod 400 ~/Downloads/finout-key.pem

# Connect
ssh -i ~/Downloads/finout-key.pem ec2-user@YOUR-EC2-PUBLIC-IP
```

### Windows — PuTTY:
1. Convert `.pem` to `.ppk` using PuTTYgen (Load → Save private key)
2. PuTTY → Host: `ec2-user@YOUR-EC2-IP` → SSH → Auth → Private key file → browse to `.ppk`
3. Click Open

### No SSH client? Use EC2 Instance Connect:
1. EC2 Console → select instance → **Connect** → **EC2 Instance Connect** → **Connect**

You should see:
```
[ec2-user@ip-172-31-xx-xx ~]$
```

---

## STEP 3 — Check AWS Credentials

```bash
# Verify IAM role is attached and working
aws sts get-caller-identity
```

Expected output:
```json
{
    "Account": "062968674300",
    "Arn": "arn:aws:sts::062968674300:assumed-role/RDS_Agentic_WAR/i-..."
}
```

Set your region (EC2 doesn't auto-set it):
```bash
aws configure set region us-east-1
aws configure get region   # prints: us-east-1
```

If `Unable to locate credentials`:
```bash
# Check if IAM role metadata is available
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/iam/info
```
If empty → go to EC2 console → **Actions** → **Security** → **Modify IAM role** → attach your role.

---

## STEP 4 — Update System and Install Build Tools

```bash
sudo dnf update -y
sudo dnf install -y gcc gcc-c++ make openssl-devel bzip2-devel \
  libffi-devel zlib-devel git jq tar
```

---

## STEP 5 — Install Python 3.12

```bash
# Check first
python3.12 --version

# Install via dnf (AL2023)
sudo dnf install -y python3.12 python3.12-pip python3.12-devel
python3.12 --version   # should show Python 3.12.x
```

If `python3.12` not available via dnf, build from source:
```bash
cd /tmp
wget https://www.python.org/ftp/python/3.12.4/Python-3.12.4.tgz
tar xzf Python-3.12.4.tgz && cd Python-3.12.4
./configure --enable-optimizations --with-ensurepip=install
sudo make -j$(nproc) altinstall
python3.12 --version
```

---

## STEP 6 — Copy the Project to EC2

### Option A — Clone from GitHub:
```bash
cd ~
git clone https://github.com/YOUR-ORG/finout-rds-review.git
cd finout-rds-review
```

### Option B — SCP from your laptop (run on your laptop terminal):
```bash
scp -i ~/Downloads/finout-key.pem -r \
  /path/to/finout-rds-review \
  ec2-user@YOUR-EC2-PUBLIC-IP:~/finout-rds-review
```

### Option C — Create folder structure fresh:
```bash
mkdir -p ~/finout-rds-review/app/agent/agents
mkdir -p ~/finout-rds-review/app/streamlit
```
Then create each `.py` file using `nano` and paste code from your Windows machine.

---

## STEP 7 — Set Up Python Virtual Environment

```bash
cd ~/finout-rds-review/app/agent
python3.12 -m venv .venv
source .venv/bin/activate
```

Prompt changes to:
```
(.venv) [ec2-user@ip-172-31-xx-xx agent]$
```

Auto-activate on every login:
```bash
echo 'cd ~/finout-rds-review/app/agent && source .venv/bin/activate' >> ~/.bashrc
```

---

## STEP 8 — Install Packages

```bash
pip install --upgrade pip
pip install -r requirements.txt

# Verify
python -c "import strands; import mcp; import docx; print('Core packages OK')"
```

---

## STEP 9 — Create Your Secrets File

```bash
cp .env.example .env
nano .env
```

Fill in:
```
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0

FINOUT_MCP_URL=https://mcp.finout.io/mcp
FINOUT_CLIENT_ID=8a63cd40-91a7-485f-ab5d-80d0fd646658
FINOUT_API_KEY=f3f42ea4-91d2-4dd1-9c3e-2a9119aaf07e

FINOUT_DOCS_MCP_URL=https://docs.finout.io/~gitbook/mcp
AWS_DOCS_MCP_URL=https://docs.aws.amazon.com/mcp

REPORTS_DIR=~/reports
```

Save: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## STEP 10 — Enable Claude in Amazon Bedrock

1. **AWS Console** → **Amazon Bedrock** → **Model access**
2. Click **Manage model access**
3. Enable **Anthropic Claude Sonnet 4**
4. Click **Save changes** — wait 2–3 minutes

Test:
```bash
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId,`claude-sonnet-4`)].modelId' \
  --output table
```

---

## STEP 11 — Test Finout Connection

```bash
python list_finout_tools.py
```

Good output: 20+ tools listed. Bad (`401`): re-check `.env`.

---

## STEP 12 — Create Reports Folder

```bash
mkdir -p ~/reports
```

---

## STEP 13 — Run CLI Review (Command Line)

```bash
python main.py --local "Full Finout cost review of my RDS/Aurora fleet"
```

Run in background so SSH disconnect doesn't stop it:
```bash
nohup python main.py --local "Full Finout cost review of my RDS/Aurora fleet" \
  > ~/reports/review_log.txt 2>&1 &
echo "Running. PID: $!"
tail -f ~/reports/review_log.txt
```

**Download report to laptop:**

Mac/Linux (run on laptop):
```bash
scp -i ~/Downloads/finout-key.pem \
  ec2-user@YOUR-EC2-IP:~/reports/finout_rds_review_*.docx \
  ~/Desktop/
```

Windows — use WinSCP: connect to EC2 → navigate to `/home/ec2-user/reports/` → drag file to desktop.

---

## STEP 14 — Run Streamlit Frontend (Browser UI)

Install Streamlit:
```bash
pip install streamlit
```

Run the app:
```bash
cd ~/finout-rds-review/app/streamlit
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

**Access in your browser:**

Make sure your EC2 security group allows **TCP port 8501** from your IP (set in Step 1).

Then open in your browser:
```
http://YOUR-EC2-PUBLIC-IP:8501
```

To keep Streamlit running after you close SSH:
```bash
nohup streamlit run app.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  > ~/reports/streamlit.log 2>&1 &
echo "Streamlit running. PID: $!"
```

---

## STEP 15 — Stop EC2 When Not Using It (Save Money)

```bash
# From inside EC2
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 stop-instances --instance-ids $INSTANCE_ID --region us-east-1
```

Or: EC2 Console → select instance → **Instance state** → **Stop**

> Stopped = no compute charge. Only ~$0.02/day for 20GB storage.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Permission denied (publickey)` on SSH | `chmod 400 your-key.pem` then retry |
| `Unable to locate credentials` | Attach IAM role to EC2 in console |
| `(.venv)` missing from prompt | `source .venv/bin/activate` |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| `401 Unauthorized` Finout | Re-check `.env` keys |
| Bedrock `AccessDeniedException` | Enable Claude in Bedrock Model access |
| Streamlit not loading | Check EC2 security group allows port 8501 from your IP |
| SSH disconnects mid-review | Use `nohup` command from Step 13 |

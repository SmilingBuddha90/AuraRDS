# Deployment Guide — Cloud9 (Amazon Linux 2023)
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
| Amazon Bedrock Claude Sonnet 4 access enabled | [ ] |
| Finout account with Client ID and API Key | [ ] |

---

## STEP 1 — Create the Cloud9 Environment

1. Go to **AWS Console** → search **Cloud9** → click **Create environment**
2. Fill in:

| Setting | Value |
|---------|-------|
| Name | `finout-rds-review` |
| Instance type | `t3.medium` |
| Platform | **Amazon Linux 2023** |
| Connection | AWS Systems Manager (SSM) |
| Network | Default VPC |

3. Click **Create** — wait ~2 minutes
4. Click **Open** — a browser IDE opens with a terminal at the bottom

You should see:
```
nct-admin:~/environment $
```

---

## STEP 2 — Disable Managed Credentials / Attach IAM Role

Cloud9 managed temporary credentials expire. Use an IAM instance profile instead.

1. In Cloud9 → click **gear icon** (top right) → **AWS Settings**
2. Turn **OFF** → "AWS managed temporary credentials"
3. Go to **EC2 Console** → find your Cloud9 instance → **Actions** → **Security** → **Modify IAM role**
4. Attach your IAM role (e.g. `RDS_Agentic_WAR`)
5. Back in Cloud9 terminal:

```bash
# Clear any stale cached credentials
rm -f ~/.aws/credentials

# Set region (Cloud9 doesn't auto-set it from instance profile)
aws configure set region us-east-1

# Verify credentials work
aws sts get-caller-identity
```

You should see your account ID printed. If not, wait 10 seconds and try again.

---

## STEP 3 — Resize the EBS Disk (Cloud9 default is 10GB — too small)

```bash
# Get region and instance ID using IMDSv2
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/region)
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id)

# Get the EBS volume ID
VOLUME_ID=$(aws ec2 describe-volumes \
  --region $REGION \
  --filters "Name=attachment.instance-id,Values=$INSTANCE_ID" \
  --query "Volumes[0].VolumeId" \
  --output text)

echo "Resizing volume: $VOLUME_ID"

# Resize to 20GB
aws ec2 modify-volume --region $REGION --volume-id $VOLUME_ID --size 20
sleep 15

# Extend the partition and filesystem
ROOT_DISK=$(lsblk -no PKNAME $(findmnt -n -o SOURCE /))
sudo growpart /dev/${ROOT_DISK} 1
sudo xfs_growfs /

df -h   # should now show ~20GB
```

---

## STEP 4 — Install Python 3.12

```bash
# Check if already available
python3.12 --version

# If not found, install via dnf
sudo dnf install -y python3.12 python3.12-pip python3.12-devel

python3.12 --version   # should show Python 3.12.x
```

---

## STEP 5 — Copy the Project to Cloud9

```bash
cd ~/environment
git clone https://github.com/YOUR-ORG/finout-rds-review.git
cd finout-rds-review
ls
```

> If not on GitHub yet, create the folder structure:
> ```bash
> mkdir -p ~/environment/finout-rds-review/app/agent/agents
> mkdir -p ~/environment/finout-rds-review/app/streamlit
> ```

---

## STEP 6 — Set Up Python Virtual Environment

```bash
cd ~/environment/finout-rds-review/app/agent
python3.12 -m venv .venv
source .venv/bin/activate
```

Your prompt changes to:
```
(.venv) nct-admin:~/environment/finout-rds-review/app/agent $
```

> Every new terminal: run `source .venv/bin/activate` again.

---

## STEP 7 — Install Packages

```bash
pip install --upgrade pip
pip install -r requirements.txt

# Verify
python -c "import strands; import mcp; import docx; print('Core packages OK')"
```

---

## STEP 8 — Create Your Secrets File

```bash
cp .env.example .env
nano .env
```

Fill in your values:

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

## STEP 9 — Enable Claude in Amazon Bedrock

1. **AWS Console** → **Amazon Bedrock** → **Model access**
2. Click **Manage model access**
3. Enable **Anthropic Claude Sonnet 4**
4. Click **Save changes** — wait 2–3 minutes

---

## STEP 10 — Test Finout Connection

```bash
python list_finout_tools.py
```

Good output: list of 20+ Finout tools printed.
Bad output (`401 Unauthorized`): re-check `.env` credentials.

---

## STEP 11 — Create Reports Folder

```bash
mkdir -p ~/reports
```

---

## STEP 12 — Run CLI Review (Command Line)

```bash
python main.py --local "Full Finout cost review of my RDS/Aurora fleet"
```

Report saved to `~/reports/finout_rds_review_DATE.docx`

**Download from Cloud9:**
- Click **File** menu → **Download** → navigate to `/home/ec2-user/reports/` → select file

---

## STEP 13 — Run Streamlit Frontend (Browser UI)

Install Streamlit in the same venv:

```bash
pip install streamlit
```

Run the app:

```bash
cd ~/environment/finout-rds-review/app/streamlit
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

**Access the UI in your browser:**

Cloud9 does not expose ports directly. Use the **Preview** feature:
1. In Cloud9 → click **Preview** (top menu) → **Preview Running Application**
2. A mini browser opens inside Cloud9
3. Change the port in the URL to `8501`

Or use SSH port forwarding from your laptop:
```bash
ssh -i your-key.pem -L 8501:localhost:8501 ec2-user@YOUR-CLOUD9-EC2-IP
```
Then open `http://localhost:8501` in your laptop browser.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ExpiredToken` | `rm -f ~/.aws/credentials` then retry |
| `(.venv)` missing | `source .venv/bin/activate` |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| `401 Unauthorized` Finout | Re-check `.env` keys |
| Bedrock `AccessDeniedException` | Enable Claude in Bedrock Model access |
| Disk full | Re-run Step 3 resize |

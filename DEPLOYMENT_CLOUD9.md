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
| IAM role with Bedrock + EC2 + Cost Explorer permissions (e.g. `RDS_Agentic_WAR`) | [ ] |

---

## Cloud9 Pre-Requisites — Read Before You Start

Cloud9 has some quirks that will break your work if you don't address them upfront.
Spend 5 minutes on these now to avoid frustration later.

---

### PRE-REQ 1 — Disable Auto-Hibernate

By default Cloud9 shuts down your EC2 instance after 30 minutes of browser
inactivity. Any running jobs (cost review, Streamlit) will be killed.

**Fix — turn off auto-hibernate before doing anything else:**

1. Open your Cloud9 environment
2. Click **Cloud9** (top menu) → **Preferences**
3. Click **EC2 Instance** in the left panel
4. Set **"Stop my environment"** to **Never**
5. Close preferences

---

### PRE-REQ 2 — Disable Managed Temporary Credentials

Cloud9 injects its own temporary AWS credentials into `~/.aws/credentials`.
These expire and cause `ExpiredToken` errors mid-run. Replace them with an
IAM instance profile (permanent, auto-refreshing).

**Fix — done in STEP 2 of this guide.** Just be aware: if you skip STEP 2,
you will hit credential errors during deployment.

---

### PRE-REQ 3 — Plan for Long-Running Jobs (Use nohup)

A full 3-pillar cost review takes 3–8 minutes. If you close the Cloud9 browser
tab mid-run, the process is killed and you lose the output.

**Fix — always run long jobs with `nohup`** (covered in STEP 12):
```bash
nohup python main.py --local "Full review" > ~/reports/review.log 2>&1 &
tail -f ~/reports/review.log
```

---

### PRE-REQ 4 — Know Your Recovery Steps (After Cloud9 Wakes Up)

Every time Cloud9 hibernates and restarts, you need to run these 3 commands:

```bash
rm -f ~/.aws/credentials          # clear stale credentials
aws configure set region us-east-1
cd ~/environment/finout-rds-review/app/agent && source .venv/bin/activate
```

You can automate the venv step permanently (done in STEP 6).

> For the full list of Cloud9 known issues and gotchas, see [SECURITY.md](SECURITY.md).

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

**Auto-activate on every new terminal (do this once — prevents PRE-REQ 4 issue):**
```bash
echo 'cd ~/environment/finout-rds-review/app/agent && source .venv/bin/activate' >> ~/.bashrc
```

After this, every new Cloud9 terminal automatically activates the venv.

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

**Option A — Run in the foreground (simple, loses output if browser closes):**
```bash
python main.py --local "Full Finout cost review of my RDS/Aurora fleet"
```

**Option B — Run in background with nohup (recommended — safe if Cloud9 hibernates):**
```bash
nohup python main.py --local "Full Finout cost review of my RDS/Aurora fleet" \
  > ~/reports/review_log.txt 2>&1 &
echo "Running in background. PID: $!"
tail -f ~/reports/review_log.txt   # watch live output; Ctrl+C to stop watching
```

The review keeps running even if Cloud9 hibernates. When it wakes up, check progress:
```bash
tail -f ~/reports/review_log.txt
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

Run the app on port **8080** — Cloud9 Preview only works on ports 8080, 8081, or 8082:

```bash
cd ~/environment/finout-rds-review/app/streamlit
streamlit run app.py --server.port 8080 --server.address localhost
```

**Access the UI inside Cloud9:**
1. Click **Preview** (top menu) → **Preview Running Application**
2. A mini browser panel opens — Streamlit loads automatically on port 8080

**Keep Streamlit running after you close the terminal (use nohup):**
```bash
nohup streamlit run app.py \
  --server.port 8080 \
  --server.address localhost \
  > ~/reports/streamlit.log 2>&1 &
echo "Streamlit running. PID: $!"
```

Then click **Preview → Preview Running Application** to open the UI.

**Or access from your laptop browser via SSH port forwarding:**
```bash
ssh -i your-key.pem -L 8080:localhost:8080 ec2-user@YOUR-CLOUD9-EC2-IP
```
Then open `http://localhost:8080` in your laptop browser.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ExpiredToken` | `rm -f ~/.aws/credentials` then retry |
| `(.venv)` missing from prompt | `source .venv/bin/activate` |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| `401 Unauthorized` Finout | Re-check `.env` keys |
| Bedrock `AccessDeniedException` | Enable Claude in Bedrock Model access |
| Disk full | Re-run Step 3 resize |
| Cloud9 Preview shows "unable to connect" | Make sure Streamlit runs on port 8080, not 8501 |
| Review job stopped mid-run | Cloud9 hibernated — use `nohup` next time (Step 12 Option B) |
| Cloud9 won't open after browser close | Go to EC2 Console → start the `aws-cloud9-*` instance manually |
| Auto-hibernate keeps killing jobs | Set Cloud9 → Preferences → EC2 Instance → Stop → Never (PRE-REQ 1) |

# Security Considerations — Finout RDS/Aurora Agentic Cost Review
### Securing Data That Travels to the Finout MCP Server

---

## The Core Problem

When this tool runs, your RDS/Aurora cost data travels from your AWS account to
Finout's MCP server at `mcp.finout.io` over the public internet.

Without security layers, that data is exposed to:
- **Eavesdropping** — someone reading the data in transit
- **Impersonation** — a fake Finout server intercepting your calls
- **Credential theft** — your API key being stolen and reused
- **Tampering** — data being modified between you and Finout

This document describes 7 layers of security to protect that data, in order of
priority.

---

## Layer 1 — HTTPS (Already Active)

**What it is:** All traffic to `mcp.finout.io` uses HTTPS — every byte is
encrypted in transit using TLS 1.2+.

**Simple explanation:** Like putting your letter in a locked metal box before
sending it. Only Finout has the key to open it. Even if someone intercepts the
box on the network, they cannot read the contents.

**Status in this project:** Already active — the URL starts with `https://`

```
FINOUT_MCP_URL = "https://mcp.finout.io/mcp"
```

**What it protects against:** Anyone snooping on the network between your EC2
and Finout's server.

---

## Layer 2 — API Key Authentication (Already Active)

**What it is:** Every request to the Finout MCP server includes your
`FINOUT_CLIENT_ID` and `FINOUT_API_KEY` in the request headers.

**Simple explanation:** Like a secret handshake at the door. When your request
arrives at Finout's server, it asks "who are you and prove it." Your client ID
says who you are, and your API key proves it. Without both, Finout refuses the
request.

**Status in this project:** Already active

```python
headers = {
    "x-finout-client-id": FINOUT_CLIENT_ID,    # Who you are
    "Authorization": f"Bearer {FINOUT_API_KEY}" # Proof
}
```

**What it protects against:** Random people on the internet calling Finout
pretending to be you.

**Current risk:** The API key is stored in a plain `.env` text file on disk.
If someone accesses the machine, they can read the key. See Layer 3 for the fix.

---

## Layer 3 — AWS Secrets Manager (Recommended Next Step)

**What it is:** Instead of storing the Finout API key in a `.env` text file,
store it in AWS Secrets Manager — a managed vault that encrypts secrets at rest
and controls who can access them via IAM policies.

**Simple explanation:** Right now the key is under the doormat (`.env` file).
Secrets Manager puts it in a bank vault. Only your EC2 instance (via its IAM
role) can open the vault. No humans need to know the key.

**Why it's better than .env:**
- The key is encrypted at rest using AWS KMS
- Access is controlled by IAM — only your EC2 role can read it
- You can rotate the key without touching any code or files
- AWS logs every access to the secret in CloudTrail
- Eliminates risk of accidentally committing the key to GitHub

### Implementation Steps

**Step 1 — Store the secret:**
```bash
aws secretsmanager create-secret \
  --name "finout/api-credentials" \
  --region us-east-1 \
  --secret-string '{
    "client_id": "YOUR_CLIENT_ID",
    "api_key":   "YOUR_API_KEY"
  }'
```

**Step 2 — Add IAM permission to your EC2 role (`RDS_Agentic_WAR`):**
```json
{
  "Sid": "FinoutSecretAccess",
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue"
  ],
  "Resource": "arn:aws:secretsmanager:us-east-1:062968674300:secret:finout/*"
}
```

**Step 3 — Fetch credentials at runtime (replace .env reads):**
```python
import boto3
import json

def get_finout_credentials() -> tuple[str, str]:
    """Fetch Finout credentials from AWS Secrets Manager at runtime."""
    client = boto3.client("secretsmanager", region_name="us-east-1")
    secret = client.get_secret_value(SecretId="finout/api-credentials")
    creds = json.loads(secret["SecretString"])
    return creds["client_id"], creds["api_key"]

# Usage — replaces os.getenv() calls
client_id, api_key = get_finout_credentials()
```

**Step 4 — Delete the .env file from the server:**
```bash
rm ~/.env  # or shred -u .env for secure deletion
```

**What it protects against:**
- Someone reading your `.env` file if they access the machine
- Credentials accidentally committed to GitHub
- Credentials visible in `ps aux` or environment variable dumps
- Developer or contractor seeing the key when SSHing in

---

## Layer 4 — VPC Private Subnet + NAT Gateway

**What it is:** Move your EC2 instance from a public subnet (visible on the
internet) to a private subnet (no public IP). All outbound traffic routes
through a single NAT Gateway which is logged.

**Simple explanation:** Right now your EC2 is like a house on a public street —
anyone can knock on the door. A private subnet puts your EC2 inside a gated
community with a security guard (NAT Gateway) at the only exit. Everything
going out is recorded.

```
CURRENT:
[EC2 with public IP] ──── internet ────► [mcp.finout.io]
Anyone can reach EC2 directly

IMPROVED:
[EC2, no public IP] ──► [NAT Gateway] ──► internet ──► [mcp.finout.io]
EC2 is invisible from internet. Single logged exit point.
```

### Implementation Steps

**Step 1 — Create a private subnet:**
```
VPC Console → Subnets → Create subnet
Name: finout-review-private
Availability Zone: us-east-1a
CIDR: 10.0.2.0/24
```

**Step 2 — Create NAT Gateway in your existing public subnet:**
```
VPC Console → NAT Gateways → Create
Subnet: your existing public subnet
Elastic IP: Allocate new
```

**Step 3 — Update route table for private subnet:**
```
0.0.0.0/0 → NAT Gateway ID
```

**Step 4 — Move EC2 to private subnet** (stop instance first):
```
EC2 Console → Instance → Actions → Networking → Change subnet
```

**Step 5 — Use EC2 Instance Connect Endpoint to SSH (no public IP needed):**
```bash
aws ec2-instance-connect ssh --instance-id i-xxxxxxxxx --region us-east-1
```

**What it protects against:**
- Direct attacks on your EC2 from the internet
- Port scanning of your machine
- Brute-force SSH attempts

**Cost:** NAT Gateway ~$0.045/hour + $0.045/GB data processed (~$33/month)

---

## Layer 5 — AWS PrivateLink (Secret Tunnel — Future)

**What it is:** Instead of traffic going through the public internet, it travels
entirely within AWS's private backbone network via a VPC Endpoint.

**Simple explanation:** Instead of sending your letter via the public postal
service, you use a private underground tunnel that goes directly from your house
to the post office. The letter never touches a public road.

```
WITHOUT PrivateLink:
[EC2] ──── public internet ────► [mcp.finout.io]

WITH PrivateLink:
[EC2] ──── AWS private network ──► [mcp.finout.io]
Data never leaves AWS backbone
```

**How to enable:**
1. Ask Finout support to enable AWS PrivateLink for your account
2. They provide a VPC Endpoint Service name
3. Create a VPC Interface Endpoint in your VPC pointing to it
4. Update `FINOUT_MCP_URL` to the private DNS name

**What it protects against:**
- Data exposure on the public internet (even encrypted HTTPS data leaves metadata)
- Dependency on public internet availability
- Geographic routing attacks

**Status:** Requires Finout to support it — contact their support team to request.

---

## Layer 6 — TLS Certificate Pinning

**What it is:** Instead of trusting any valid SSL certificate for `mcp.finout.io`,
your code only trusts the specific certificate that Finout uses. If anyone
intercepts the connection with a different certificate (even a valid one), the
connection is rejected.

**Simple explanation:** Normally HTTPS just checks "is this a real post office
with a real license?" Certificate pinning goes further — "is this THE EXACT
post office I always use, not just any licensed one?"

```python
import httpx
import ssl

# Pin to Finout's specific certificate fingerprint
context = ssl.create_default_context()
context.load_verify_locations("finout_ca.pem")  # Finout's CA certificate

# Use this context for all MCP calls
transport = httpx.HTTPSTransport(ssl_context=context)
client = httpx.Client(transport=transport)
```

**How to get Finout's certificate:**
```bash
openssl s_client -connect mcp.finout.io:443 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > finout_cert.pem
```

**What it protects against:**
- Man-in-the-middle attacks using a different valid SSL certificate
- Compromised Certificate Authorities issuing fake Finout certificates

**Tradeoff:** When Finout rotates their certificate, you must update your pinned
cert too — adds operational overhead.

---

## Layer 7 — Audit Logging (CloudTrail + VPC Flow Logs)

**What it is:** Record every AWS API call (CloudTrail) and every network
connection (VPC Flow Logs) so you have a complete audit trail of what happened.

**Simple explanation:** Like installing security cameras in your house AND on
the street outside. Even if something bad happens, you have a recording of
exactly what occurred, when, and from where.

### CloudTrail — Records Every AWS API Call

```bash
# Create a CloudTrail trail
aws cloudtrail create-trail \
  --name finout-review-audit \
  --s3-bucket-name your-audit-logs-bucket \
  --region us-east-1

# Start logging
aws cloudtrail start-logging \
  --name finout-review-audit \
  --region us-east-1
```

This records:
- Every time Secrets Manager is accessed (who got the Finout API key and when)
- Every Bedrock model invocation
- Every IAM action

### VPC Flow Logs — Records Every Network Connection

```bash
# Enable flow logs for your VPC
aws ec2 create-flow-logs \
  --resource-type VPC \
  --resource-ids vpc-xxxxxxxxx \
  --traffic-type ALL \
  --log-destination-type cloud-watch-logs \
  --log-group-name /aws/vpc/finout-review-flowlogs \
  --region us-east-1
```

This records:
- Every outbound connection your EC2 makes to `mcp.finout.io`
- Source IP, destination IP, port, bytes transferred, timestamp
- Any unexpected connections (helps detect if your machine is compromised)

**What it protects against:**
- You won't always prevent attacks but you WILL know when they happen
- Required for compliance in most regulated industries
- Enables forensic investigation if credentials are stolen

---

## Current Risk Assessment

| Risk | Current Status | Severity | Fix |
|------|---------------|----------|-----|
| API key in .env file | Active risk | HIGH | Move to Secrets Manager (Layer 3) |
| EC2 has public IP | Active risk | MEDIUM | Move to private subnet (Layer 4) |
| No audit logging | Active risk | MEDIUM | Enable CloudTrail + Flow Logs (Layer 7) |
| HTTPS not enabled | Not a risk | — | Already done (Layer 1) |
| No API authentication | Not a risk | — | Already done (Layer 2) |
| Data on public internet | Active risk | LOW-MEDIUM | Ask Finout for PrivateLink (Layer 5) |
| Certificate not pinned | Low risk for sandbox | LOW | Consider for production (Layer 6) |

---

## Recommended Implementation Order

### Phase 1 — Do Before Going to Production (1 hour total)

1. **Secrets Manager** (Layer 3) — 15 minutes
   Move API key out of `.env` into AWS vault

2. **CloudTrail** (Layer 7) — 15 minutes
   Turn on audit logging

3. **VPC Flow Logs** (Layer 7) — 10 minutes
   Turn on network logging

### Phase 2 — Do When Hardening for Production (half day)

4. **Private Subnet + NAT Gateway** (Layer 4) — 45 minutes
   Remove public IP from EC2

### Phase 3 — Advanced (contact vendors first)

5. **PrivateLink** (Layer 5) — contact Finout support
   Eliminate public internet dependency

6. **Certificate Pinning** (Layer 6) — 30 minutes
   Lock to Finout's exact certificate

---

## What Is Safe Right Now (Sandbox)

For a **sandbox/demo environment**, the current setup is acceptable because:
- HTTPS encrypts all data in transit (Layer 1) ✓
- API key authentication is active (Layer 2) ✓
- `.gitignore` prevents committing `.env` to GitHub ✓
- IAM role limits what the EC2 machine can do in AWS ✓

**Do NOT use the current setup for production** without at minimum implementing
Layers 3 and 7 (Secrets Manager + Audit Logging).

---

## Questions to Ask Finout Security Team

Before going to production, ask Finout:

1. Do you support **AWS PrivateLink** for the MCP endpoint?
2. What data is **logged on your side** when we call the MCP server?
3. What is your **data retention policy** for API call logs?
4. Do you support **IP allowlisting** so only our EC2's NAT Gateway IP can call the API?
5. What is your **certificate rotation schedule** (for pinning planning)?
6. Do you have a **SOC 2 Type II** report we can review?

---

*This document covers security for the Finout MCP remote connection only.
For AWS-side security (Bedrock, IAM, RDS access), refer to the AWS Well-Architected
Security Pillar guidelines.*

---

## Cloud9 Known Issues and Gotchas

If you are running this tool on AWS Cloud9, there are some important things to know
that can save you a lot of frustration.

---

### Issue 1 — Cloud9 Goes to Sleep After 30 Minutes

**What happens:** If you close the Cloud9 browser tab or walk away for 30 minutes,
Cloud9 hibernates your EC2 instance automatically. When you come back, the browser
tab is blank or stuck loading.

**Simple explanation:** Cloud9 is like a TV that turns itself off when nobody is
watching. The show (your running code) stops completely — not just paused.

**How to stop Cloud9 from hibernating:**

In the Cloud9 IDE menu:
```
Cloud9 (top menu) → Preferences → AWS Settings → Cloud9 Instance Shutdown Behavior
→ Change from "After 30 minutes" to "Never"
```

Or via the EC2 console — just stop and manually manage the instance yourself.

**How to wake it up when it has already hibernated:**
1. Go to **AWS Console → EC2**
2. Find your Cloud9 instance (name starts with `aws-cloud9-...`)
3. Click **Start instance**
4. Wait 1–2 minutes
5. Go back to **AWS Console → Cloud9** → open your environment

---

### Issue 2 — Your Running Code Stops When Cloud9 Hibernates

**What happens:** If a long-running job (like a Finout cost review that takes 5
minutes) is running and Cloud9 hibernates mid-run, everything stops and you lose
the output.

**Fix — use `nohup` to keep it running:**
```bash
nohup python main.py --local "Full review" > ~/reports/review.log 2>&1 &
echo "Running in background. PID: $!"
tail -f ~/reports/review.log   # watch live output
```

Even if Cloud9 hibernates, the process keeps running on the EC2 machine. When you
wake Cloud9 back up, `tail -f` the log to see where it got to.

---

### Issue 3 — Credentials Expire After Cloud9 Restarts

**What happens:** When Cloud9 hibernates and wakes up, the managed temporary
credentials in `~/.aws/credentials` are stale. You will see:

```
An error occurred (ExpiredToken) when calling the... operation
```

**Fix — delete the stale credentials file:**
```bash
rm -f ~/.aws/credentials
```

After this, boto3 falls back to the EC2 instance profile (IAM role), which
auto-refreshes and never expires. This is the correct approach.

**Root cause:** Cloud9's "managed temporary credentials" feature auto-injects a
credentials file that overrides the instance profile. When the session expires,
you get token errors. Deleting the file forces use of the always-fresh IAM role.

---

### Issue 4 — Virtual Environment Deactivates on Reconnect

**What happens:** After Cloud9 wakes up, your terminal prompt no longer shows
`(.venv)`. The virtual environment is not active, so Python commands fail with
`ModuleNotFoundError`.

**Quick fix:**
```bash
cd ~/finout-rds-review/app/agent
source .venv/bin/activate
```

**Permanent fix — auto-activate on every terminal session:**
```bash
echo 'cd ~/finout-rds-review/app/agent && source .venv/bin/activate' >> ~/.bashrc
```

After this, every new terminal in Cloud9 automatically activates your venv.

---

### Issue 5 — Streamlit Stops When Cloud9 Hibernates

**What happens:** If Streamlit was running in a terminal and Cloud9 hibernated,
the Streamlit process is killed. The browser UI shows "connection lost."

**Fix — run Streamlit with nohup:**
```bash
cd ~/finout-rds-review/app/streamlit
nohup streamlit run app.py \
  --server.port 8501 \
  --server.address localhost \
  > ~/reports/streamlit.log 2>&1 &
echo "Streamlit running. PID: $!"
```

After Cloud9 wakes up, re-open the Preview tab in the IDE
(Preview → Preview Running Application).

---

### Issue 6 — Cloud9 Preview Only Works on Port 8080/8081/8082

**What happens:** Cloud9's built-in "Preview Running Application" button only
works on ports 8080, 8081, or 8082. If Streamlit runs on port 8501, the preview
tab shows "unable to connect."

**Fix — run Streamlit on port 8080 for Cloud9 preview:**
```bash
streamlit run app.py --server.port 8080 --server.address localhost
```

Then click: **Preview → Preview Running Application** in the Cloud9 menu.

Alternatively, use SSH port forwarding from your laptop to access port 8501
directly in your local browser (see DEPLOYMENT_CLOUD9.md for details).

---

### Issue 7 — EBS Disk Resize Does Not Persist Across Hibernation

**What is this:** The EBS volume resize you did (from 10 GB to 20 GB) is permanent
— the volume stays at 20 GB even after hibernation and restart. This is not a
problem — just confirming the disk size is fine after waking up.

You can verify after restart:
```bash
df -h /   # should show ~19G total, not 10G
```

---

### Quick Recovery Checklist After Cloud9 Wakes Up

Run these commands every time you reconnect after hibernation:

```bash
# 1. Fix credentials
rm -f ~/.aws/credentials

# 2. Set region (in case it was cleared)
aws configure set region us-east-1

# 3. Re-activate venv
cd ~/finout-rds-review/app/agent && source .venv/bin/activate

# 4. Verify AWS access
aws sts get-caller-identity

# 5. Verify Python packages
python -c "import strands; import mcp; print('Packages OK')"
```

---

### Summary of Cloud9 Quirks vs EC2

| Issue | Cloud9 | EC2 |\n|-------|--------|-----|\n| Auto-hibernates | Yes — 30 min idle | No — runs until you stop it |\n| Credentials expire | Yes — managed creds expire | No — instance profile auto-refreshes |\n| Venv deactivates | Yes — on every reconnect | Only if you didn't add to `.bashrc` |\n| Port for browser preview | 8080/8081/8082 only | Any port (with security group rule) |\n| SSH needed | No — browser IDE | Yes — need .pem key |\n| Cost when idle | Stops billing after hibernate | Keeps billing unless you stop instance |

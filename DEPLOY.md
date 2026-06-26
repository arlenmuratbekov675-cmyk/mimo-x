# MiMo X — Deploy to Hetzner CX22 (beginner-friendly)

Goal: **VPS → Docker → MiMo X → /health OK.** No FRED, no paid data yet.

Server: Hetzner CX22 · Ubuntu 24.04 · 2 vCPU · 4 GB RAM · ~EUR 4.5/mo.
Your machine: Windows (PowerShell). All commands below are copy-paste ready.

---

## Step 1 — Create an SSH key (on YOUR Windows PC)
An SSH key is a password-less, secure way to log into the server.

In PowerShell:
```powershell
ssh-keygen -t ed25519 -C "mimo-x"
```
- Press Enter to accept the default path (`C:\Users\<you>\.ssh\id_ed25519`).
- You may set a passphrase or leave it empty (Enter twice).

Show your PUBLIC key (you'll paste this into Hetzner):
```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```
Copy the whole line (starts with `ssh-ed25519 ...`).

---

## Step 2 — Create the Hetzner server
1. Sign up at https://console.hetzner.cloud
2. **New Project** → name it `mimo`.
3. **Add Server**:
   - Location: closest to you (e.g. Falkenstein/Nuremberg in EU, Ashburn in US).
   - Image: **Ubuntu 24.04**
   - Type: **CX22** (Shared vCPU, x86).
   - **SSH keys**: click *Add SSH key* and paste your PUBLIC key from Step 1.
   - Name: `mimo-x`.
   - Click **Create & Buy now**.
4. Copy the server's **public IPv4** address (e.g. `203.0.113.10`).

---

## Step 3 — First login
In PowerShell (replace with your IP):
```powershell
ssh root@203.0.113.10
```
Type `yes` on the first connection. You should land in a `root@mimo-x:~#` prompt.

---

## Step 4 — Create a non-root user (safer)
Running everything as root is risky. Create a normal user:
```bash
adduser mimo            # set a password when asked, fill name fields = Enter
usermod -aG sudo mimo   # allow admin commands
rsync --archive --chown=mimo:mimo ~/.ssh /home/mimo   # copy SSH access to new user
```
Log out and back in as the new user:
```bash
exit
```
```powershell
ssh mimo@203.0.113.10
```

---

## Step 5 — Firewall (only allow SSH + the app port)
```bash
sudo apt update
sudo apt install -y ufw
sudo ufw allow OpenSSH      # port 22 (don't lock yourself out)
sudo ufw allow 8000/tcp    # MiMo X API
sudo ufw --force enable
sudo ufw status
```

---

## Step 6 — Install Docker + Compose
```bash
# Install Docker from the official convenience script
curl -fsSL https://get.docker.com | sudo sh

# Run docker without sudo (re-login needed after)
sudo usermod -aG docker $USER

# Apply the new group now (or just log out/in)
newgrp docker

# Verify
docker --version
docker compose version
```

---

## Step 7 — Copy the MiMo X project to the server
**Option A — via Git (best, once it's on GitHub):**
```bash
# later, when you push to GitHub:
git clone https://github.com/<you>/mimo-x.git
cd mimo-x
```

**Option B — copy from your Windows PC now (no GitHub yet).**
Run this on YOUR PC (PowerShell), not the server:
```powershell
cd "C:\Users\simular\AppData\Roaming\simular-unified-ui\SimularFiles"
scp -r mimo-x mimo@203.0.113.10:/home/mimo/mimo-x
```
Then back on the server:
```bash
cd ~/mimo-x
```

---

## Step 8 — Configure environment
```bash
cp .env.example .env
# Step 0 needs no keys. You can leave .env as-is for now.
```

---

## Step 9 — Run it (one command)
```bash
docker compose up --build -d     # -d = run in background
docker compose ps                # should show mimo-x-api "running"
docker compose logs -f api       # watch logs (Ctrl+C to stop watching)
```

---

## Step 10 — Check /health
On the server:
```bash
curl http://localhost:8000/health
```
From your own browser (replace IP):
```
http://203.0.113.10:8000/health
http://203.0.113.10:8000/docs
```
Expected:
```json
{ "status": "ok", "app": "MiMo X", "database": "ok", ... }
```

If you see that — **the foundation is live on infrastructure that works.**
Next step after this: **Step 1 — FRED integration.**

---

## Handy commands later
```bash
docker compose down            # stop
docker compose up -d --build   # rebuild + restart after code changes
docker compose logs -f api     # tail logs
```

## Troubleshooting
- **Can't connect via SSH** → check you used the right IP and the key from Step 1.
- **/health works locally but not in browser** → firewall: re-run `sudo ufw allow 8000/tcp`.
- **docker: permission denied** → you skipped `newgrp docker` or need to log out/in.
- **scp not found** → it ships with modern Windows 10/11; otherwise install "OpenSSH Client" in Windows optional features.

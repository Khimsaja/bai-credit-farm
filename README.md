# 🤖 B.AI Credit Farm + Claim

**Farm 500K free credits per account** from [chat.b.ai](https://chat.b.ai) via Google OAuth.

## ⚠️ REQUIREMENTS

### 1. Residential Proxy (WAJIB untuk Claim)

Claim credits **TIDAK BISA** dari IP datacenter. Cloudflare Turnstile memblokir IP VPS.

**Wajib punya residential proxy!** Contoh format:
```
http://username:password@proxy-host:port
```

Proxy dipakai di Phase 2 (claim) saja. Phase 1 (OAuth) jalan tanpa proxy.

### 2. Dependencies
```bash
pip install cloakbrowser playwright geoip2
playwright install chromium
```

### 3. Xvfb (untuk non-headless)
```bash
apt install xvfb
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
```

---

## 🚀 Quick Start

### Step 1: Farm API Keys
```bash
# Single account
python bai-farm.py --email user@domain.com --password mypass

# Batch (creates API keys, 0 balance)
python bai-farm.py --range 1-120 --domain giosin.com --password mypass
```

### Step 2: Claim Credits (needs proxy!)
```bash
# Claim 500K credits for all accounts
python bai-claim.py --range 1-120

# Custom proxy
python bai-claim.py --range 1-120 --proxy-host your-proxy:port --proxy-user user --proxy-pass pass

# Test which accounts need claiming
python bai-claim.py --range 1-120 --test-only
```

---

## 📁 Files

| File | Description |
|------|-------------|
| `bai-farm.py` | Create API keys (no proxy needed) |
| `bai-oauth.py` | Phase 1: Google OAuth → save profile (headless, no proxy) |
| `bai-claim-step2.py` | Phase 2: Claim via proxy (non-headless, Turnstile bypass) |
| `bai-claim.py` | Main claim orchestrator (runs phase 1 + 2 per account) |
| `setup.sh` | Quick dependency install |
| `SKILL.md` | AI agent documentation |

---

## 🔄 How Claiming Works

```
Phase 1 (headless, NO proxy):
  Google OAuth → B.AI login → save persistent browser profile
  
  ⏸️ Kill all chrome processes (free RAM)

Phase 2 (non-headless, WITH residential proxy):
  Load saved profile → B.AI/chat → Click "Claim Free Credits"
  → Cloudflare Turnstile auto-verifies (~30s from residential IP)
  → Click "Claim" button (Playwright click, NOT JS)
  → 500K credits added
```

**Key insights:**
- OAuth tanpa proxy (Google blokir proxy)
- Claim pakai proxy (Turnstile blokir datacenter IP)
- Profile disimpan di `/root/cloakbrowser/profiles/bai_claim_{acct}/`
- Click "Claim" harus pakai Playwright `btn.click()`, bukan JS `dispatchEvent`
- Chrome di-kill antara phase 1 dan 2 untuk hemat RAM

---

## ⚡ CLI Reference

### bai-farm.py
```
--email EMAIL        Single account
--range RANGE        Batch (e.g., 1-120)
--domain DOMAIN      Email domain (default: giosin.com)
--password PASS      Password (required)
--prefix PREFIX      Account prefix (default: kdi)
--delay SECS         Delay between accounts (default: 10)
```

### bai-claim.py
```
--range RANGE        Account range (e.g., 1-120)
--domain DOMAIN      Email domain (default: giosin.com)
--password PASS      Password (default: qwertyui)
--prefix PREFIX      Account prefix (default: kdi)
--delay SECS         Delay between accounts (default: 10)
--proxy-host HOST    Proxy server (default: proxy.wtvconfigs.run.place:8069)
--proxy-user USER    Proxy username
--proxy-pass PASS    Proxy password
--test-only          Only test balance, do not claim
```

---

## 📊 Output

```
bai-keys/
├── kdi1.txt          # sk-xxx API key (35 chars)
├── kdi2.txt
├── ...
├── farm.log          # farming log
└── claim.log         # claiming log
```

---

## 🛡️ Pitfalls

1. **Proxy WAJIB untuk claim** — Turnstile blokir IP datacenter
2. **OAuth TANPA proxy** — Google blokir login dari proxy
3. **Chrome RAM** — kill orphan chromes antar akun
4. **Playwright click** — JS `dispatchEvent` tidak trigger React state
5. **Profile reuse** — phase 1 dan 2 pakai profile dir yang sama
6. **Xvfb** — non-headless butuh display `:99`
7. **geoip2** — `pip install geoip2` untuk proxy geo-detection

---

## 📈 Performance

- **Farm:** ~2-3 min/account, ~98% success
- **Claim:** ~3 min/account (2 min OAuth + 1 min claim)
- **120 accounts:** ~6 hours total
- **Credits per account:** 500,000
- **Total credits:** 120 × 500K = **60,000,000**

---

## 🔑 Using Keys

```bash
curl https://api.b.ai/v1/chat/completions \
  -H "Authorization: Bearer $(cat bai-keys/kdi1.txt)" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v3.2","messages":[{"role":"user","content":"hello"}]}'
```

Available models: `gpt-5.2`, `gpt-5-mini`, `claude-sonnet-4.5`, `deepseek-v3.2`, `gemini-3-flash`, etc.

---

## 📄 License

MIT — use at your own risk.

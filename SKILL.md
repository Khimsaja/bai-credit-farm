---
name: bai-credit-farming
description: "Farm 500K free credits per account from chat.b.ai via Google OAuth + residential proxy for Turnstile bypass"
trigger: "bai farm, b.ai credits, chat.b.ai, bai api key, free credits"
tools: [cloakbrowser, playwright, residential proxy]
---

# B.AI Credit Farming

Farm **500,000 free credits** per account from [chat.b.ai](https://chat.b.ai) using Google OAuth.

## ⚠️ PROXY REQUIRED

**Claim credits REQUIRES residential proxy.** Cloudflare Turnstile blocks datacenter IPs.

Without proxy: API keys created but **balance = 0**.
With proxy: Turnstile auto-solves in ~30s, credits claimed.

Default proxy: `http://1671586399:***@proxy.wtvconfigs.run.place:8069`

## Prerequisites

```bash
pip install cloakbrowser playwright geoip2
playwright install chromium
# Xvfb for non-headless mode
apt install xvfb && Xvfb :99 -screen 0 1920x1080x24 &
```

## Quick Start

```bash
# Step 1: Create API keys (no proxy needed)
python bai-farm.py --range 1-120 --domain giosin.com --password mypass

# Step 2: Claim credits (PROXY REQUIRED)
python bai-claim.py --range 1-120
```

## Architecture

```
bai-farm.py:
  Google OAuth → B.AI → Create API Key → Save sk-xxx
  (headless, no proxy, ~2-3 min/account)

bai-claim.py (orchestrator):
  ├─ Phase 1: bai-oauth.py (headless, NO proxy)
  │   Google OAuth → B.AI login → save persistent profile
  │
  ├─ Kill chrome processes (free RAM)
  │
  └─ Phase 2: bai-claim-step2.py (non-headless, WITH proxy)
      Load profile → B.AI/chat → Click "Claim Free Credits"
      → Turnstile auto-verifies (~30s)
      → Playwright click "Claim" button
      → 500K credits added
```

## Key Pitfalls

1. **Proxy required for claim** — Turnstile blocks datacenter IPs
2. **No proxy for OAuth** — Google blocks proxy logins
3. **Playwright click, not JS** — `btn.click()` works, `dispatchEvent` doesn't trigger React state
4. **Kill chromes between phases** — OOM if both browsers alive
5. **Same profile dir** — Phase 1 & 2 share profile for session continuity
6. **Xvfb required** — Non-headless needs display `:99`
7. **geoip2 package** — `pip install geoip2`

## Scripts

| Script | Purpose | Proxy? |
|--------|---------|--------|
| `bai-farm.py` | Create API keys | No |
| `bai-oauth.py` | Phase 1: OAuth + save profile | No |
| `bai-claim-step2.py` | Phase 2: Claim credits | **YES** |
| `bai-claim.py` | Orchestrator (runs both phases) | Configurable |

## CLI Arguments

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
--test-only          Only test balance
```

## After Farming

```bash
# Count keys
ls bai-keys/*.txt | wc -l

# Test API
curl https://api.b.ai/v1/chat/completions \
  -H "Authorization: Bearer $(cat bai-keys/kdi1.txt)" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v3.2","messages":[{"role":"user","content":"hi"}]}'
```

## Performance

- Farm: ~2-3 min/account
- Claim: ~3 min/account
- 120 accounts: ~6 hours total
- Credits: 500K per account = 60M total for 120 accounts

## For AI Agents

- Run as background: `nohup python -u bai-claim.py --range 1-120 > claim.log 2>&1 &`
- Monitor: check `claim.log` or count `.txt` files
- Auto-skip: accounts with credits already are skipped
- Proxy config via CLI args or edit defaults in script

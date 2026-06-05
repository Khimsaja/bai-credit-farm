# B.AI Credit Claimer

Claim 500K free credits for accounts that already have API keys.

## Problem
API keys created by `bai-farm.py` have **0 balance**. The "Claim Free Credits" button requires Cloudflare Turnstile verification that blocks datacenter IPs.

## Solution
Two-phase approach:
1. **OAuth** via headless browser (no proxy) — fast, reliable
2. **Claim** via non-headless + residential proxy — Turnstile auto-solves in ~30s

## Quick Start

```bash
# Install geoip2 (required)
pip install geoip2

# Claim credits for all accounts
python bai-claim.py --range 1-120

# Test which accounts need claiming
python bai-claim.py --range 1-120 --test-only

# Custom proxy
python bai-claim.py --range 1-120 --proxy http://user:pass@host:port
```

## Requirements

- `cloakbrowser` installed
- `geoip2` installed (`pip install geoip2`)
- Residential proxy (bypasses Turnstile IP check)
- Xvfb display `:99` (for non-headless mode)

## Flow

```
Phase 1 (headless, no proxy):
  Google OAuth → B.AI login → save cookies

Phase 2 (non-headless + residential proxy):
  Load cookies → B.AI/chat → Click "Claim Free Credits"
  → Turnstile auto-verifies (~30s) → Click "Claim"
  → 500K credits added to account
```

## Pitfalls

- OAuth must happen WITHOUT proxy (Google blocks proxy IPs)
- Cookies transfer via `storage_state` → `add_cookies`
- Kill orphan chromium processes between runs
- `DISPLAY=:99` required (Xvfb)

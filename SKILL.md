---
name: bai-credit-farming
description: "Farm B.AI (chat.b.ai) free credits via Google OAuth — extract API keys with 500K credits each"
trigger: "bai farm, b.ai credits, chat.b.ai, bai api key, free credits"
tools: [browser automation, playwright or cloakbrowser]
---

# B.AI Credit Farming

Farm **500,000 free credits** per account from [chat.b.ai](https://chat.b.ai) using Google OAuth login. Each account gets a persistent `sk-xxx` API key compatible with OpenAI API format.

## Prerequisites

```bash
pip install playwright
playwright install chromium
```

Or if using CloakBrowser:
```bash
pip install cloakbrowser
```

## Quick Start

```bash
# Single account
python bai-farm.py --email user@domain.com --password mypass

# Batch 100 accounts (kdi1@domain.com ... kdi100@domain.com)
python bai-farm.py --range 1-100 --domain giosin.com --password mypass

# Custom settings
python bai-farm.py --range 1-50 --prefix acc --domain mail.com --password pass123 --delay 30
```

## CLI Arguments

| Arg | Required | Default | Description |
|-----|----------|---------|-------------|
| `--email` | * | — | Single account email |
| `--range` | * | — | Account range (e.g., `1-100`) |
| `--domain` | No | `giosin.com` | Email domain |
| `--password` | **Yes** | — | Password for all accounts |
| `--prefix` | No | `kdi` | Account name prefix |
| `--delay` | No | `10` | Seconds between accounts |
| `--output` | No | `./bai-keys` | Output directory |

*Provide either `--email` or `--range`

## Output

```
bai-keys/
├── kdi1.txt          # sk-xxx...xxx (35 chars)
├── kdi2.txt
├── ...
├── farm.log          # append-only log
└── summary.json      # run summary
```

Each `.txt` file contains one API key: `sk-` prefix, 35 alphanumeric chars.

## Flow (4 Steps)

### 1. Google Login
- Navigate to Google sign-in
- Fill email → Next → Fill password → Next
- **Pitfall**: Indonesian locale shows TOS "Saya mengerti" as `<input>` element, not `<button>`. Script handles this automatically.

### 2. B.AI OAuth
- Go to `chat.b.ai/key`
- Click "Log in" → "Continue with Google" (triggers popup)
- **CRITICAL**: Must use `ctx.expect_event('page')` BEFORE clicking to capture the popup
- Handle account chooser + consent page
- Wait for popup to redirect to `chat.b.ai`
- **Pitfall**: Main page SPA routing hangs on `goto()`. Always use popup page for subsequent navigation.

### 3. Claim Free Credits
- Click "Claim Free Credits" button in header
- Click inner "Claim" button in modal overlay
- Press Escape to dismiss modal
- **Pitfall**: Modal has z-index layering. Script uses JS dispatch to click through overlays.

### 4. Create API Key
- Click "Create API key" in API keys section
- **Pitfall**: Must use `.type()` not `.fill()` — React state doesn't detect programmatic fill
- Click submit button in modal (force `disabled=false`)
- Poll page for `sk-` key

## After Farming

```bash
# Count keys
ls bai-keys/*.txt | wc -l

# List keys (masked)
for f in bai-keys/*.txt; do echo "$(basename $f .txt): $(head -c 12 $f)..."; done

# Find failed accounts
for n in $(seq 1 100); do f="bai-keys/kdi${n}.txt"; [ ! -f "$f" ] && echo "MISSING: kdi$n"; done
```

## Using Keys

Keys work with OpenAI-compatible API:

```bash
curl https://chat.b.ai/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx...xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

## Pitfalls Reference

1. **Popup won't open** — ~10-20% failure rate. Script retries 3x.
2. **Main page SPA timeout** — B.AI is SPA, `page.goto()` hangs. Use popup page.
3. **React `.fill()` silent fail** — Use `.type()` for keyboard input.
4. **Modal overlay blocks clicks** — Use JS `dispatchEvent` with `bubbles:true`.
5. **TOS button is `<input>`** — Indonesian Google locale, not `<button>`.
6. **Terminal truncates `sk-`** — Display issue only. Full key is in the file.
7. **Fingerprint must be consistent** — `--fingerprint=12345` for all accounts.
8. **Account chooser** — Click by domain prefix if full email doesn't match.

## Success Rate

- **~98%** (118/120 in first production batch)
- Each account: ~2-3 minutes
- 120 accounts: ~4-6 hours
- Total credits: 120 × 500K = **60,000,000**

## For AI Agents

When integrating this into an automation pipeline:

1. **Run as background process**: `nohup python -u bai-farm.py --range 1-100 ... > farm.log 2>&1 &`
2. **Monitor progress**: Check `farm.log` or count `.txt` files in output dir
3. **Extract keys**: Read `.txt` files for API keys
4. **Use keys**: Rotate through keys for API calls to `chat.b.ai/v1/`
5. **Auto-skip**: Script skips accounts that already have valid keys

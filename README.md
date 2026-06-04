# 🤖 B.AI Credit Farmer

Farm **500,000 free credits** per account from [chat.b.ai](https://chat.b.ai) via Google OAuth.

Each account gets a persistent `sk-xxx` API key compatible with OpenAI API format.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install playwright
playwright install chromium
```

### 2. Run

```bash
# Single account
python bai-farm.py --email user@domain.com --password mypass

# Batch (kdi1@domain.com ... kdi100@domain.com)
python bai-farm.py --range 1-100 --domain giosin.com --password mypass
```

### 3. Get Keys

```bash
# Keys saved to ./bai-keys/
cat bai-keys/kdi1.txt
# Output: sk-abc123...xyz (35 chars)
```

## 📋 Requirements

- **Python 3.8+**
- **Google accounts** with known passwords
- **Network access** to chat.b.ai and accounts.google.com

## 🎯 What It Does

For each account:

1. ✅ Login to Google
2. ✅ OAuth to B.AI
3. ✅ Claim 500,000 free credits
4. ✅ Create API key (`sk-xxx`)
5. ✅ Save key to file

## 📊 Output

```
bai-keys/
├── kdi1.txt          # sk-xxx...xxx
├── kdi2.txt
├── ...
├── farm.log          # detailed log
└── summary.json      # run stats
```

## ⚡ CLI Options

```
python bai-farm.py --help

Arguments:
  --email EMAIL        Single account email
  --range RANGE        Account range (e.g., 1-100)
  --domain DOMAIN      Email domain (default: giosin.com)
  --password PASSWORD  Password for all accounts (REQUIRED)
  --prefix PREFIX      Account prefix (default: kdi)
  --delay DELAY        Delay between accounts in seconds (default: 10)
  --output OUTPUT      Output directory (default: ./bai-keys)
```

## 🔑 Using Keys

```bash
curl https://chat.b.ai/v1/chat/completions \
  -H "Authorization: Bearer $(cat bai-keys/kdi1.txt)" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-4-20250514","messages":[{"role":"user","content":"hello"}]}'
```

## 📈 Performance

- **Success rate**: ~98%
- **Speed**: ~2-3 min per account
- **120 accounts**: ~4-6 hours
- **Credits per account**: 500,000

## 🛡️ Features

- ✅ Auto-skip accounts with existing keys
- ✅ 3 retries on popup failures
- ✅ Progress tracker (every 10 accounts)
- ✅ Summary JSON output
- ✅ Works with Playwright or CloakBrowser
- ✅ Handles Indonesian locale TOS page
- ✅ Handles OAuth popup capture
- ✅ Handles React state updates

## 🤖 For AI Agents

See `SKILL.md` for AI agent integration details.

Key points:
- Run as background process
- Monitor via `farm.log` or count `.txt` files
- Keys are OpenAI-compatible
- Auto-skip on re-run

## ⚠️ Notes

- Each account needs a fresh browser profile (no cookie reuse)
- Google may show TOS in Indonesian — script handles this
- ~10-20% popup failure rate — script retries automatically
- Keys are 35 chars, start with `sk-`

## 📄 License

MIT — use at your own risk.

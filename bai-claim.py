#!/usr/bin/env python3
"""
B.AI Credit Claimer — Claim 500K credits for accounts that already have API keys.

Usage:
  python bai-claim.py --range 1-120
  python bai-claim.py --range 1-120 --proxy http://user:pass@host:port

Requires: cloakbrowser, geoip2
"""

import argparse, time, shutil, json, re, sys, os
from pathlib import Path
from cloakbrowser import launch_persistent_context

KEY_DIR = Path('/root/bai-keys')
DEFAULT_PROXY = 'http://1671586399:GKPZqLKZZTUM0U5c@proxy.wtvconfigs.run.place:8069'
DEFAULT_PASSWORD = 'qwertyui'
DEFAULT_DOMAIN = 'giosin.com'
DEFAULT_PREFIX = 'kdi'
MAX_RETRIES = 3


def log(msg, acct=None):
    ts = time.strftime('%H:%M:%S')
    prefix = f'[{ts}] {acct}: ' if acct else f'[{ts}] '
    print(f'{prefix}{msg}', flush=True)


def has_valid_key(acct):
    key_file = KEY_DIR / f'{acct}.txt'
    if key_file.exists():
        k = key_file.read_text().strip()
        return k.startswith('sk-') and len(k) >= 30
    return False


def test_balance(acct):
    """Quick API test to check if account already has credits."""
    import subprocess
    key_file = KEY_DIR / f'{acct}.txt'
    key = key_file.read_text().strip()
    try:
        r = subprocess.run([
            'curl', '-s', '-m', '15', '-X', 'POST',
            'https://api.b.ai/v1/chat/completions',
            '-H', f'Authorization: Bearer {key}',
            '-H', 'Content-Type: application/json',
            '-d', '{"model":"deepseek-v3.2","messages":[{"role":"user","content":"hi"}],"stream":false,"max_tokens":5}'
        ], capture_output=True, text=True, timeout=20)
        d = json.loads(r.stdout)
        if 'choices' in d:
            return True  # Has credits
        err = d.get('error', {}).get('message', '')
        if 'insufficient' in err.lower() or 'balance=0' in err:
            return False  # No credits
        return None  # Unknown
    except:
        return None


def claim_credits(email, password, proxy):
    """OAuth + claim 500K credits. Returns (status, detail)."""
    acct = email.split('@')[0]
    profile_dir = Path(f'/tmp/bai_claim_{acct}_{int(time.time())}')
    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        # === Step 1: OAuth WITHOUT proxy (faster, more reliable) ===
        ctx = launch_persistent_context(str(profile_dir), headless=True,
            args=['--fingerprint=12345', '--no-sandbox'])
        page = ctx.new_page()

        page.goto('https://accounts.google.com/signin/v2/identifier', timeout=30000); time.sleep(2)
        page.locator("input[type='email']").first.fill(email); time.sleep(1)
        page.locator("button:has-text('Next')").first.click(); time.sleep(3)
        page.locator("input[type='password']").first.fill(password); time.sleep(1)
        page.locator("button:has-text('Next')").first.click(); time.sleep(5)

        body_lower = page.locator('body').inner_text().lower()
        if 'selamat datang' in body_lower:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)"); time.sleep(2)
            page.locator('text=Saya mengerti').first.click(); time.sleep(3)

        page.goto('https://chat.b.ai/', timeout=30000); time.sleep(5)
        if 'Log in' in page.locator('body').inner_text():
            page.locator("button:has-text('Log in')").first.click(); time.sleep(3)
            with ctx.expect_event('page', timeout=30000) as pi:
                page.locator('text=Continue with Google').first.click()
            popup = pi.value; time.sleep(5)
            if 'accountchooser' in popup.url:
                popup.locator(f'text={acct}').first.click(); time.sleep(5)
            purl = popup.url
            if 'oauth' in purl or 'consent' in purl:
                popup.evaluate("window.scrollTo(0, document.body.scrollHeight)"); time.sleep(2)
                popup.locator('button').nth(1).click(); time.sleep(3)
            for _ in range(20):
                time.sleep(3)
                if 'chat.b.ai' in popup.url: break
            if 'chat.b.ai' in popup.url: page = popup
            time.sleep(3)

        if 'Log in' in page.locator('body').inner_text():
            ctx.close()
            return 'FAIL', 'OAuth failed'

        storage = ctx.storage_state()
        ctx.close()
        log('OAuth done', acct)

        # === Step 2: WITH proxy + Turnstile ===
        ctx2 = launch_persistent_context(str(profile_dir), headless=False,
            args=['--fingerprint=12345', '--no-sandbox', '--display=:99'],
            proxy=proxy, humanize=True)
        ctx2.add_cookies(storage.get('cookies', []))
        page2 = ctx2.new_page()
        page2.goto('https://chat.b.ai/chat', timeout=60000, wait_until='domcontentloaded')
        time.sleep(15)

        if 'Log in' in page2.locator('body').inner_text():
            ctx2.close()
            return 'FAIL', 'session lost after proxy switch'

        # Click Claim Free Credits
        page2.evaluate("""() => {
            for (const b of document.querySelectorAll('button')) {
                if (b.textContent.trim().includes('Claim Free Credits')) {
                    b.dispatchEvent(new MouseEvent('click', {bubbles:true}));
                }
            }
        }""")
        time.sleep(8)

        # Poll Turnstile for 2 minutes
        for i in range(12):
            time.sleep(10)
            btn = page2.evaluate("""() => {
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent.trim() === 'Claim') return {disabled: b.disabled};
                }
                return 'not_found';
            }""")

            if isinstance(btn, dict) and not btn.get('disabled'):
                page2.evaluate("""() => {
                    for (const b of document.querySelectorAll('button')) {
                        if (b.textContent.trim() === 'Claim') b.click();
                    }
                }""")
                time.sleep(5)
                ctx2.close()
                log('✅ Credits claimed!', acct)
                return 'OK', '500K credits claimed'

            if isinstance(btn, str) and btn == 'not_found':
                # Modal might have closed (already claimed?)
                break

        ctx2.close()
        return 'FAIL', 'Turnstile timeout'

    except Exception as e:
        return 'FAIL', str(e)[:200]
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description='B.AI Credit Claimer')
    parser.add_argument('--range', required=True, help='Account range (e.g., 1-120)')
    parser.add_argument('--domain', default=DEFAULT_DOMAIN)
    parser.add_argument('--password', default=DEFAULT_PASSWORD)
    parser.add_argument('--prefix', default=DEFAULT_PREFIX)
    parser.add_argument('--proxy', default=DEFAULT_PROXY)
    parser.add_argument('--delay', type=int, default=30, help='Delay between accounts (seconds)')
    parser.add_argument('--skip-tested', action='store_true', help='Skip accounts already tested with balance')
    parser.add_argument('--test-only', action='store_true', help='Only test balance, do not claim')

    args = parser.parse_args()

    start, end = args.range.split('-')
    accounts = [f'{args.prefix}{n}@{args.domain}' for n in range(int(start), int(end) + 1)]
    total = len(accounts)

    ok = skip = fail = already = 0
    results = {}

    log(f'🚀 Claiming credits: {total} accounts, {args.delay}s delay')

    for i, email in enumerate(accounts, 1):
        acct = email.split('@')[0]
        log(f'[{i}/{total}] {acct}', acct)

        if not has_valid_key(acct):
            log('⏭️ No API key, skipping', acct)
            skip += 1
            results[acct] = 'SKIP: no key'
            continue

        if args.test_only:
            bal = test_balance(acct)
            if bal is True:
                log('✅ Already has credits', acct)
                already += 1
                results[acct] = 'HAS_CREDITS'
            elif bal is False:
                log('❌ No credits', acct)
                results[acct] = 'NO_CREDITS'
            else:
                log('❓ Unknown', acct)
                results[acct] = 'UNKNOWN'
            continue

        # Check if already has credits
        bal = test_balance(acct)
        if bal is True:
            log('⏭️ Already has credits', acct)
            already += 1
            results[acct] = 'SKIP: has credits'
            continue

        # Claim
        status, detail = claim_credits(email, args.password, args.proxy)
        if status == 'OK':
            ok += 1
            log(f'✅ {detail}', acct)
        else:
            fail += 1
            log(f'❌ {detail[:60]}', acct)

        results[acct] = f'{status}: {detail[:60]}'

        if i < total:
            time.sleep(args.delay)

        if i % 10 == 0:
            print(flush=True)
            log(f'── Progress: {i}/{total} | ✅{ok} ⏭️{skip+already} ❌{fail} ──')
            print(flush=True)

    # Summary
    print(flush=True)
    print('=' * 50)
    log('🏁 CLAIMING COMPLETE')
    print(f'   ✅ Claimed:    {ok}')
    print(f'   ⏭️ Skipped:    {skip + already}')
    print(f'   ❌ Failed:     {fail}')
    print(f'   💰 Credits:    {ok * 500_000:,}')
    print('=' * 50)

    if fail > 0:
        print('\nFailed:')
        for acct, r in results.items():
            if r.startswith('FAIL'):
                print(f'  ❌ {acct}: {r[7:]}')

    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
B.AI Credit Claimer — Claim 500K credits for accounts that already have API keys.

Two-phase approach:
  Phase 1: Google OAuth via headless (no proxy) — fast, reliable
  Phase 2: B.AI claim via non-headless + residential proxy — Turnstile auto-solves

Usage:
  python bai-claim.py --range 1-120
  python bai-claim.py --range 1-120 --proxy http://user:pass@host:port

Requires: cloakbrowser, geoip2
"""

import argparse, time, shutil, json, sys, signal, os
from pathlib import Path

# Force Xvfb display
os.environ['DISPLAY'] = ':99'

from cloakbrowser import launch_persistent_context

KEY_DIR = Path('/root/bai-keys')
DEFAULT_PROXY = 'http://1671586399:GKPZqLKZZTUM0U5c@proxy.wtvconfigs.run.place:8069'
DEFAULT_PASSWORD = 'qwertyui'
DEFAULT_DOMAIN = 'giosin.com'
DEFAULT_PREFIX = 'kdi'


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
    """Quick API test. Returns True (has credits), False (no credits), None (unknown)."""
    import subprocess
    key = (KEY_DIR / f'{acct}.txt').read_text().strip()
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
            return True
        err = d.get('error', {}).get('message', '')
        if 'insufficient' in err.lower() or 'balance=0' in err:
            return False
        return None
    except:
        return None


def safe_close(ctx):
    """Close browser context without crashing on EPIPE."""
    try:
        ctx.close()
    except:
        pass
    # Kill any orphan chromium processes
    try:
        import subprocess
        subprocess.run(['pkill', '-f', 'chromium.*tmp/bai_claim'], 
                       capture_output=True, timeout=5)
    except:
        pass


def oauth_phase(email, password):
    """Phase 1: Google OAuth in headless mode (no proxy). Returns storage_state or None."""
    acct = email.split('@')[0]
    profile_dir = Path(f'/tmp/bai_claim_{acct}')
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
    profile_dir.mkdir(parents=True)

    ctx = None
    try:
        ctx = launch_persistent_context(str(profile_dir), headless=True,
            args=['--fingerprint=12345', '--no-sandbox'])
        page = ctx.new_page()

        # Google login
        page.goto('https://accounts.google.com/signin/v2/identifier', timeout=30000)
        time.sleep(2)
        page.locator("input[type='email']").first.fill(email)
        time.sleep(1)
        page.locator("button:has-text('Next')").first.click()
        time.sleep(3)
        page.locator("input[type='password']").first.fill(password)
        time.sleep(1)
        page.locator("button:has-text('Next')").first.click()
        time.sleep(5)

        # Handle TOS
        try:
            body_lower = page.locator('body').inner_text(timeout=5000).lower()
            if 'selamat datang' in body_lower:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                page.locator('text=Saya mengerti').first.click()
                time.sleep(3)
        except:
            pass

        # B.AI OAuth
        page.goto('https://chat.b.ai/', timeout=30000)
        time.sleep(5)

        body = page.locator('body').inner_text(timeout=5000)
        if 'Log in' in body:
            page.locator("button:has-text('Log in')").first.click()
            time.sleep(3)
            with ctx.expect_event('page', timeout=30000) as pi:
                page.locator('text=Continue with Google').first.click()
            popup = pi.value
            time.sleep(5)

            if 'accountchooser' in popup.url:
                try:
                    popup.locator(f'text={acct}').first.click()
                except:
                    popup.locator('text=kdi').first.click()
                time.sleep(5)

            purl = popup.url
            if 'oauth' in purl or 'consent' in purl:
                popup.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                popup.locator('button').nth(1).click()
                time.sleep(3)

            for _ in range(20):
                time.sleep(3)
                if 'chat.b.ai' in popup.url:
                    break

            if 'chat.b.ai' in popup.url:
                page = popup

        # Verify login
        time.sleep(3)
        body = page.locator('body').inner_text(timeout=5000)
        if 'Log in' in body:
            safe_close(ctx)
            return None, 'OAuth failed - not logged in'

        storage = ctx.storage_state()
        safe_close(ctx)
        return storage, 'ok'

    except Exception as e:
        safe_close(ctx)
        return None, str(e)[:150]


def claim_phase(acct, storage, proxy):
    """Phase 2: Open B.AI with proxy, click Claim, wait for Turnstile. Returns (status, detail)."""
    profile_dir = Path(f'/tmp/bai_claim_{acct}')

    ctx = None
    try:
        ctx = launch_persistent_context(str(profile_dir), headless=False,
            args=['--fingerprint=12345', '--no-sandbox', '--display=:99',
                  '--disable-gpu', '--disable-dev-shm-usage'],
            proxy=proxy, humanize=True)

        # Restore session cookies
        cookies = storage.get('cookies', [])
        if cookies:
            ctx.add_cookies(cookies)

        page = ctx.new_page()

        # Navigate to B.AI
        page.goto('https://chat.b.ai/chat', timeout=60000, wait_until='domcontentloaded')
        time.sleep(15)

        # Verify logged in
        try:
            body = page.locator('body').inner_text(timeout=10000)
        except:
            body = ''
        if 'Log in' in body:
            safe_close(ctx)
            return 'FAIL', 'session lost after proxy switch'

        # Click Claim Free Credits button
        page.evaluate("""() => {
            for (const b of document.querySelectorAll('button')) {
                if (b.textContent.trim().includes('Claim Free Credits')) {
                    b.dispatchEvent(new MouseEvent('click', {bubbles:true}));
                    return true;
                }
            }
            return false;
        }""")
        time.sleep(8)

        # Poll Turnstile for up to 2 minutes
        for i in range(12):
            time.sleep(10)

            try:
                btn = page.evaluate("""() => {
                    for (const b of document.querySelectorAll('button')) {
                        if (b.textContent.trim() === 'Claim') return {disabled: b.disabled};
                    }
                    return 'not_found';
                }""")
            except:
                safe_close(ctx)
                return 'FAIL', 'page crashed during polling'

            if isinstance(btn, dict) and not btn.get('disabled'):
                # Claim button enabled — click it!
                page.evaluate("""() => {
                    for (const b of document.querySelectorAll('button')) {
                        if (b.textContent.trim() === 'Claim') b.click();
                    }
                }""")
                time.sleep(5)
                safe_close(ctx)
                return 'OK', '500K credits claimed'

            if isinstance(btn, str) and btn == 'not_found':
                # Modal gone — maybe already claimed or something else
                safe_close(ctx)
                return 'FAIL', 'claim modal disappeared'

        safe_close(ctx)
        return 'FAIL', 'Turnstile timeout (2min)'

    except Exception as e:
        safe_close(ctx)
        return 'FAIL', str(e)[:150]


def claim_account(email, password, proxy):
    """Full claim flow: OAuth → proxy → claim. Returns (status, detail)."""
    acct = email.split('@')[0]

    # Phase 1: OAuth
    log('Phase 1: OAuth...', acct)
    storage, err = oauth_phase(email, password)
    if storage is None:
        return 'FAIL', f'OAuth: {err}'
    log('OAuth done', acct)

    # Phase 2: Claim with proxy
    log('Phase 2: Claim (proxy)...', acct)
    status, detail = claim_phase(acct, storage, proxy)

    # Cleanup profile
    profile_dir = Path(f'/tmp/bai_claim_{acct}')
    shutil.rmtree(profile_dir, ignore_errors=True)

    return status, detail


def main():
    parser = argparse.ArgumentParser(description='B.AI Credit Claimer')
    parser.add_argument('--range', required=True, help='Account range (e.g., 1-120)')
    parser.add_argument('--domain', default=DEFAULT_DOMAIN)
    parser.add_argument('--password', default=DEFAULT_PASSWORD)
    parser.add_argument('--prefix', default=DEFAULT_PREFIX)
    parser.add_argument('--proxy', default=DEFAULT_PROXY)
    parser.add_argument('--delay', type=int, default=20, help='Delay between accounts (seconds)')
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
            log('⏭️ No API key', acct)
            skip += 1
            results[acct] = 'SKIP: no key'
            continue

        if args.test_only:
            bal = test_balance(acct)
            status_str = 'HAS_CREDITS' if bal else 'NO_CREDITS'
            log(f'{"✅" if bal else "❌"} {status_str}', acct)
            results[acct] = status_str
            if bal:
                already += 1
            continue

        # Check if already has credits
        bal = test_balance(acct)
        if bal is True:
            log('⏭️ Already has credits', acct)
            already += 1
            results[acct] = 'SKIP: has credits'
            continue

        # Claim
        status, detail = claim_account(email, args.password, args.proxy)
        if status == 'OK':
            ok += 1
            log(f'✅ {detail}', acct)
        else:
            fail += 1
            log(f'❌ {detail[:60]}', acct)

        results[acct] = f'{status}: {detail[:60]}'

        # Kill orphan chromes between runs
        try:
            import subprocess
            subprocess.run(['pkill', '-9', '-f', 'chromium.*tmp/bai_claim'],
                           capture_output=True, timeout=5)
            time.sleep(2)
        except:
            pass

        if i < total:
            time.sleep(args.delay)

        # Progress every 10
        if i % 10 == 0:
            print(flush=True)
            log(f'── Progress: {i}/{total} | ✅{ok} ⏭️{skip+already} ❌{fail} ──')
            print(flush=True)

    # Summary
    total_credits = (ok + already) * 500_000
    print(flush=True)
    print('=' * 55)
    log('🏁 CLAIMING COMPLETE')
    print(f'   ✅ Claimed:     {ok}')
    print(f'   ⏭️ Skipped:     {skip + already}')
    print(f'   ❌ Failed:      {fail}')
    print(f'   💰 Total credits: {total_credits:,}')
    print('=' * 55)

    if fail > 0:
        print('\nFailed:')
        for acct, r in results.items():
            if r.startswith('FAIL'):
                print(f'  ❌ {acct}: {r[7:]}')

    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

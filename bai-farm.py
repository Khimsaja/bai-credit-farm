#!/usr/bin/env python3
"""
B.AI Credit Farmer — Farm 500K free credits per Google account.
Extracts sk-xxx API keys from chat.b.ai via Google OAuth.

Usage:
  Single:  python bai-farm.py --email user@domain.com
  Batch:   python bai-farm.py --range 1-120 --domain giosin.com
  Custom:  python bai-farm.py --range 1-50 --domain giosin.com --password mypass --delay 30

Requires: cloakbrowser (pip install cloakbrowser)
Output:   /root/bai-keys/{acct}.txt (one sk-xxx key per file)
"""

import argparse, time, shutil, re, sys
from pathlib import Path
from cloakbrowser import launch_persistent_context

# ── Constants ─────────────────────────────────────────────────────
FINGERPRINT = '12345'
DEFAULT_PASSWORD = 'qwertyui'
DEFAULT_DELAY = 10
MAX_RETRIES = 3
CREDITS_PER_ACCOUNT = 500_000


def log(msg, acct=None):
    ts = time.strftime('%H:%M:%S')
    prefix = f'[{ts}] {acct}: ' if acct else f'[{ts}] '
    print(f'{prefix}{msg}', flush=True)


def is_valid_key(k):
    return k.startswith('sk-') and len(k) >= 30


def save_key(acct, key, key_dir):
    key_dir.mkdir(exist_ok=True)
    (key_dir / f'{acct}.txt').write_text(key)
    with open(key_dir / 'farm.log', 'a') as f:
        f.write(f'{acct}: {key}\n')
    log(f'✅ Key saved: {key[:12]}...', acct)


def already_done(acct, key_dir):
    key_file = key_dir / f'{acct}.txt'
    if key_file.exists():
        return is_valid_key(key_file.read_text().strip())
    return False


def js_click(page, text):
    """Click button containing text via JS (bypasses overlay/z-index)."""
    page.evaluate(f'''() => {{
        for (const b of document.querySelectorAll('button')) {{
            if (b.textContent.trim().includes('{text}') && b.offsetParent) {{
                b.dispatchEvent(new MouseEvent('click', {{bubbles:true, cancelable:true, view:window}}));
                return true;
            }}
        }}
        return false;
    }}''')


def js_click_exact(page, text):
    """Click button with exact text match via JS."""
    page.evaluate(f'''() => {{
        for (const b of document.querySelectorAll('button')) {{
            if (b.textContent.trim() === '{text}' && b.offsetParent) {{
                b.dispatchEvent(new MouseEvent('click', {{bubbles:true, cancelable:true, view:window}}));
                return true;
            }}
        }}
        return false;
    }}''')


def farm_one(email, password, key_dir):
    """Farm a single account. Returns (status, detail)."""
    acct = email.split('@')[0]

    if already_done(acct, key_dir):
        return 'SKIP', 'already has key'

    # Fresh browser profile per account
    profile_dir = Path(f'/tmp/bai_{acct}')
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
    profile_dir.mkdir(parents=True)

    ctx = launch_persistent_context(
        str(profile_dir), headless=True,
        args=[f'--fingerprint={FINGERPRINT}', '--no-sandbox']
    )

    try:
        page = ctx.new_page()

        # ── Step 1: Google Login ──────────────────────────────────
        log('Logging into Google...', acct)
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

        # Handle Indonesian TOS page ("Saya mengerti" is <input>, not <button>)
        body_lower = page.locator('body').inner_text().lower()
        if 'selamat datang' in body_lower:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            page.locator('text=Saya mengerti').first.click()
            time.sleep(3)
            log('TOS accepted', acct)

        log('Google login done', acct)

        # ── Step 2: B.AI OAuth ────────────────────────────────────
        page.goto('https://chat.b.ai/', timeout=30000)
        time.sleep(5)
        page.goto('https://chat.b.ai/key', timeout=30000)
        time.sleep(5)

        body_text = page.locator('body').inner_text()
        if 'Log in' not in body_text:
            log('Already logged in!', acct)
        else:
            # Click "Log in" → capture OAuth popup
            popup = None
            for attempt in range(MAX_RETRIES):
                try:
                    page.locator("button:has-text('Log in')").first.click()
                    time.sleep(3)
                    with ctx.expect_event('page', timeout=30000) as popup_info:
                        page.locator('text=Continue with Google').first.click()
                    popup = popup_info.value
                    log(f'Popup opened (attempt {attempt+1})', acct)
                    break
                except Exception as e:
                    log(f'Popup attempt {attempt+1} failed: {str(e)[:60]}', acct)
                    time.sleep(5)
                    if attempt < MAX_RETRIES - 1:
                        page.reload(timeout=30000)
                        time.sleep(5)

            if popup is None:
                return 'FAIL', 'popup never opened'

            time.sleep(5)

            # Handle account chooser
            if 'accountchooser' in popup.url:
                try:
                    popup.locator(f'text={acct}').first.click()
                    time.sleep(5)
                except:
                    try:
                        popup.locator(f'text={email.split("@")[1][:4]}').first.click()
                        time.sleep(5)
                    except:
                        log('Account chooser click failed', acct)

            # Handle consent/authorization page (scroll + click Continue)
            purl = popup.url
            if 'oauth' in purl or 'consent' in purl or 'authorize' in purl:
                popup.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                popup.locator('button').nth(1).click()
                time.sleep(3)
                log('OAuth consent clicked', acct)

            # Wait for popup to redirect to B.AI domain
            log('Waiting for OAuth redirect...', acct)
            for _ in range(60):
                time.sleep(5)
                if 'chat.b.ai' in popup.url:
                    log('OAuth SUCCESS — popup on B.AI', acct)
                    break
                if popup.url == 'about:blank':
                    break

            # Use popup page (main page SPA routing hangs on goto)
            if 'chat.b.ai' in popup.url:
                page = popup
                log('Using popup page for B.AI', acct)

            try:
                page.goto('https://chat.b.ai/key', timeout=60000, wait_until='domcontentloaded')
            except:
                log('Goto /key timeout, continuing...', acct)
            time.sleep(10)

        # Verify login
        if 'Log in' in page.locator('body').inner_text():
            return 'FAIL', 'not logged in after OAuth'

        log('Logged in to B.AI', acct)

        # ── Step 3: Claim Free Credits (500K) ────────────────────
        body_text = page.locator('body').inner_text()
        if 'Claim Free Credits' in body_text:
            js_click(page, 'Claim Free Credits')
            time.sleep(5)
            js_click_exact(page, 'Claim')
            time.sleep(5)
            page.keyboard.press('Escape')
            time.sleep(2)
            page.keyboard.press('Escape')
            time.sleep(2)
            log('500K credits claimed', acct)

        # ── Step 4: Create API Key ────────────────────────────────
        before_keys = set(re.findall(r'sk-[a-zA-Z0-9]{20,80}', page.content()))

        js_click_exact(page, 'Create API key')
        time.sleep(5)

        visible_input = page.locator('input[placeholder="Please enter the API key name"]')
        if visible_input.count() == 0:
            return 'FAIL', 'no input field found'

        # Use .type() not .fill() — React state doesn't detect programmatic fill
        visible_input.click()
        time.sleep(1)
        visible_input.type('mykey', delay=100)
        time.sleep(2)

        # Submit: last modal → Create button (force enable + click)
        page.evaluate('''() => {
            const modals = document.querySelectorAll('.ant-modal-content');
            const modal = modals[modals.length - 1];
            if (!modal) return;
            for (const btn of modal.querySelectorAll('button')) {
                if (btn.textContent.trim().toLowerCase().includes('create')) {
                    btn.disabled = false;
                    btn.dispatchEvent(new MouseEvent('click', {bubbles:true}));
                    return;
                }
            }
        }''')

        # Poll for new sk- key appearing in page
        for _ in range(15):
            time.sleep(1)
            try:
                after_keys = set(re.findall(r'sk-[a-zA-Z0-9]{20,80}', page.content()))
                new_keys = after_keys - before_keys
                if new_keys:
                    key = list(new_keys)[0]
                    save_key(acct, key, key_dir)
                    return 'OK', key
            except:
                pass

        return 'FAIL', 'no key found after submit'

    except Exception as e:
        return 'FAIL', str(e)[:200]
    finally:
        try:
            ctx.close()
        except:
            pass
        shutil.rmtree(profile_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description='B.AI Credit Farmer — farm 500K credits per Google account',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples:\n'
               '  python bai-farm.py --email user@domain.com\n'
               '  python bai-farm.py --range 1-120 --domain giosin.com\n'
               '  python bai-farm.py --range 1-50 --delay 30 --password mypass\n'
    )
    parser.add_argument('--email', help='Single account email')
    parser.add_argument('--range', help='Account range (e.g., 1-120)')
    parser.add_argument('--domain', default='giosin.com', help='Email domain (default: giosin.com)')
    parser.add_argument('--password', default=DEFAULT_PASSWORD, help='Password for all accounts')
    parser.add_argument('--prefix', default='kdi', help='Account prefix (default: kdi)')
    parser.add_argument('--delay', type=int, default=DEFAULT_DELAY, help='Delay between accounts in seconds')
    parser.add_argument('--output', default='/root/bai-keys', help='Output directory for keys')

    args = parser.parse_args()

    key_dir = Path(args.output)
    key_dir.mkdir(exist_ok=True)

    # Build account list
    accounts = []
    if args.email:
        accounts = [args.email]
    elif args.range:
        start, end = args.range.split('-')
        for n in range(int(start), int(end) + 1):
            accounts.append(f'{args.prefix}{n}@{args.domain}')
    else:
        parser.error('Provide --email or --range')

    total = len(accounts)
    ok_count = skip_count = fail_count = 0
    results = {}

    log(f'🚀 B.AI Farm: {total} accounts, {args.delay}s delay, domain={args.domain}')
    log(f'   Output: {key_dir}')
    print(flush=True)

    for i, email in enumerate(accounts, 1):
        acct = email.split('@')[0]
        log(f'[{i}/{total}] Processing...', acct)

        status, detail = farm_one(email, args.password, key_dir)

        if status == 'OK':
            ok_count += 1
        elif status == 'SKIP':
            skip_count += 1
            log(f'⏭️ Skipped: {detail}', acct)
        else:
            fail_count += 1
            log(f'❌ Failed: {detail[:60]}', acct)

        results[acct] = f'{status}: {detail[:60]}'

        if i < total:
            time.sleep(args.delay)

        # Progress every 10
        if i % 10 == 0:
            print(flush=True)
            log(f'── Progress: {i}/{total} | ✅{ok_count} ⏭️{skip_count} ❌{fail_count} ──')
            print(flush=True)

    # Final summary
    total_credits = (ok_count + skip_count) * CREDITS_PER_ACCOUNT
    print(flush=True)
    print('=' * 50)
    log('🏁 FARMING COMPLETE')
    print(f'   Total accounts: {total}')
    print(f'   ✅ New keys:    {ok_count}')
    print(f'   ⏭️ Skipped:     {skip_count}')
    print(f'   ❌ Failed:      {fail_count}')
    print(f'   💰 Total credits: {total_credits:,}')
    print(f'   📁 Keys saved:   {key_dir}/')
    print('=' * 50)

    if fail_count > 0:
        print('\nFailed accounts:')
        for acct, result in results.items():
            if result.startswith('FAIL'):
                print(f'  ❌ {acct}: {result[7:]}')

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

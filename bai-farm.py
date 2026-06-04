#!/usr/bin/env python3
"""
B.AI Credit Farmer — Farm 500K free credits per Google account from chat.b.ai

Extracts sk-xxx API keys via Google OAuth login.
Each new account gets 500,000 free credits.

Usage:
  Single:  python bai-farm.py --email user@domain.com --password mypass
  Batch:   python bai-farm.py --range 1-100 --domain giosin.com --password mypass

Requirements:
  pip install playwright
  playwright install chromium
"""

import argparse, time, shutil, re, sys, os, json
from pathlib import Path

# ── Try cloakbrowser first, fallback to playwright ────────────────
try:
    from cloakbrowser import launch_persistent_context as _launch
    ENGINE = 'cloakbrowser'
except ImportError:
    from playwright.sync_api import sync_playwright
    ENGINE = 'playwright'

FINGERPRINT = '12345'
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


def create_context(profile_dir, headless=True):
    """Create browser context (cloakbrowser or playwright)."""
    if ENGINE == 'cloakbrowser':
        return _launch(
            str(profile_dir), headless=headless,
            args=[f'--fingerprint={FINGERPRINT}', '--no-sandbox']
        )
    else:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=headless,
            args=[f'--fingerprint={FINGERPRINT}', '--no-sandbox']
        )
        ctx = browser.new_context()
        ctx._pw = pw  # keep reference to stop later
        ctx._browser = browser
        return ctx


def close_context(ctx):
    """Safely close browser context."""
    try:
        if hasattr(ctx, '_browser'):
            ctx._browser.close()
        if hasattr(ctx, '_pw'):
            ctx._pw.stop()
        ctx.close()
    except:
        pass


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
    """
    Farm a single account.
    Returns: (status, detail)
      status: 'OK' | 'SKIP' | 'FAIL'
    """
    acct = email.split('@')[0]

    if already_done(acct, key_dir):
        return 'SKIP', 'already has key'

    # Fresh browser profile per account
    profile_dir = Path(f'/tmp/bai_{acct}_{int(time.time())}')
    profile_dir.mkdir(parents=True, exist_ok=True)

    ctx = create_context(profile_dir)

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
                    log('OAuth SUCCESS', acct)
                    break
                if popup.url == 'about:blank':
                    break

            # Use popup page (main page SPA routing hangs)
            if 'chat.b.ai' in popup.url:
                page = popup
                log('Using popup page', acct)

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
        close_context(ctx)
        shutil.rmtree(profile_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description='B.AI Credit Farmer — farm 500K credits per Google account',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Single account:
    python bai-farm.py --email user@domain.com --password mypass

  Batch 100 accounts:
    python bai-farm.py --range 1-100 --domain giosin.com --password mypass

  Custom prefix and delay:
    python bai-farm.py --range 1-50 --prefix acc --domain mail.com --delay 30

Output:
  Keys saved to ./bai-keys/{acct}.txt (one sk-xxx key per file, 35 chars)
  Log saved to ./bai-keys/farm.log
        '''
    )
    parser.add_argument('--email', help='Single account email')
    parser.add_argument('--range', help='Account range (e.g., 1-100)')
    parser.add_argument('--domain', default='giosin.com', help='Email domain (default: giosin.com)')
    parser.add_argument('--password', required=True, help='Password for all accounts')
    parser.add_argument('--prefix', default='kdi', help='Account prefix (default: kdi)')
    parser.add_argument('--delay', type=int, default=10, help='Delay between accounts in seconds (default: 10)')
    parser.add_argument('--output', default='./bai-keys', help='Output directory (default: ./bai-keys)')

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

    log(f'🚀 B.AI Farm: {total} accounts, {args.delay}s delay, engine={ENGINE}')
    log(f'   Domain: {args.domain}, Prefix: {args.prefix}')
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
    print('=' * 55)
    log('🏁 FARMING COMPLETE')
    print(f'   Total accounts:  {total}')
    print(f'   ✅ New keys:     {ok_count}')
    print(f'   ⏭️ Skipped:      {skip_count}')
    print(f'   ❌ Failed:       {fail_count}')
    print(f'   💰 Total credits: {total_credits:,}')
    print(f'   📁 Keys saved:   {key_dir}/')
    print('=' * 55)

    if fail_count > 0:
        print(f'\nFailed accounts:')
        for acct, result in results.items():
            if result.startswith('FAIL'):
                print(f'  ❌ {acct}: {result[7:]}')

    # Save summary JSON
    summary = {
        'total': total,
        'ok': ok_count,
        'skipped': skip_count,
        'failed': fail_count,
        'total_credits': total_credits,
        'results': results
    }
    with open(key_dir / 'summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

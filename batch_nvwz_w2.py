#!/usr/bin/env python3
"""
B.AI Claim Bonus — Worker 2 with residential proxy.
Range: nvwz126-250 (125 accounts)
Proxy: wtvconfigs residential
"""
import os, time, shutil, json, subprocess, sys, random
from pathlib import Path
os.environ['DISPLAY'] = ':99'
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# === CONFIG ===
CAP_KEY = os.environ.get("B_AI_2CAP_KEY", "your_2captcha_key_here")
SITEKEY = os.environ.get("B_AI_TURNSTILE_SITEKEY", "0x4AAAAAADKhTSXIozuHjOoF")
PASSWORD = os.environ.get("B_AI_EMAIL_PASSWORD", "your_email_password")
DOMAIN = os.environ.get("B_AI_EMAIL_DOMAIN", "yourdomain.com")

# Worker range
WORKER_START = int(os.environ.get("B_AI_WORKER_START", "126"))
WORKER_END = int(os.environ.get("B_AI_WORKER_END", "250"))
SUFFIX = os.environ.get("B_AI_WORKER_SUFFIX", "w2")

RESULTS_FILE = os.environ.get("B_AI_RESULTS_FILE", f"results_{SUFFIX}.json")
LOG_FILE = os.environ.get("B_AI_LOG_FILE", f"claim_{SUFFIX}.log")
KEY_DIR = os.environ.get("B_AI_KEY_DIR", ".")
PROFILE_BASE = os.environ.get("B_AI_PROFILE_BASE", f"/tmp/bai_{SUFFIX}_profile")
ACCOUNT_PREFIX = os.environ.get("B_AI_ACCOUNT_PREFIX", "user")

# (proxy removed — too slow for Google OAuth via Playwright)

# ============

def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

def save_key(account_id, key):
    key_path = f"{KEY_DIR}/{account_id}.txt"
    with open(key_path, 'w') as f:
        f.write(key.strip() + '\n')
    log(f"{account_id}: 💾 Key saved! ({key[:15]}...{key[-4:]})")
    return key

def is_valid_full_key(val):
    if not val or not isinstance(val, str):
        return False
    val = val.strip()
    return val.startswith('sk-') and '...' not in val and '*' not in val and len(val) > 30

def scrape_key_from_modal(page, account_id):
    import re
    # Method 1: input[readonly]
    try:
        readonly = page.locator('input[readonly]').first
        if readonly.is_visible(timeout=2000):
            val = readonly.input_value(timeout=2000)
            if is_valid_full_key(val):
                return save_key(account_id, val)
    except:
        pass
    # Method 2: body text regex
    try:
        body_text = page.locator('body').inner_text(timeout=3000)
        matches = re.findall(r'sk-[a-zA-Z0-9]{32,}', body_text)
        for m in matches:
            if '...' not in m and '*' not in m:
                return save_key(account_id, m)
    except:
        pass
    # Method 3: Click Copy + clipboard
    try:
        copy_btn = page.locator('button:has-text("Copy")').first
        if copy_btn.is_visible(timeout=3000):
            copy_btn.click()
            time.sleep(1)
            intercepted = page.evaluate("window.__bai_full_key || null")
            if is_valid_full_key(intercepted):
                return save_key(account_id, intercepted)
            try:
                val = page.locator('input[readonly]').first.input_value(timeout=2000)
                if is_valid_full_key(val):
                    return save_key(account_id, val)
            except:
                pass
    except:
        pass
    return None

def navigate_to_key_page(page, account_id):
    """Navigate to the /key page using sidebar link (SPA navigation, no reload)."""
    import re
    
    # Close any overlay modal first (claim success modal blocks sidebar)
    try:
        close_btn = page.locator('button:has-text("Claimed"), button:has-text("Close"), dialog button, [class*="close"], [aria-label="Close"]').first
        if close_btn.is_visible(timeout=3000):
            close_btn.click()
            log(f"{account_id}: ✅ Closed overlay modal")
            time.sleep(3)
    except:
        # Also try X button
        try:
            page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.textContent.trim() === '×' || b.textContent.trim() === 'X' || b.getAttribute('aria-label') === 'Close') {
                        b.click(); break;
                    }
                }
            }""")
            time.sleep(2)
        except:
            pass
    
    # Method 1: Click "API" sidebar link (SPA navigation)
    log(f"{account_id}: 🔗 Navigating via sidebar API link...")
    for attempt in range(3):
        try:
            # Wait for page to be stable
            time.sleep(2)
            # Find API link — try multiple selectors
            api_link = page.locator('text=API').first
            if api_link.is_visible(timeout=5000):
                api_link.click()
                time.sleep(5)
                # Check if we navigated
                if 'key' in page.url.lower() or 'api' in page.url.lower():
                    log(f"{account_id}: ✅ Navigated to: {page.url[:60]}")
                    return True
            log(f"{account_id}: ⚠️ API link click attempt {attempt+1}, going to key directly...")
        except:
            log(f"{account_id}: ⚠️ API link click failed (attempt {attempt+1})")
            time.sleep(3)
    
    # Method 2: Fallback — goto /key directly
    log(f"{account_id}: 🔄 Fallback: goto /key directly...")
    try:
        page.goto('https://chat.b.ai/key', timeout=45000, wait_until='networkidle')
        time.sleep(5)
        return True
    except:
        log(f"{account_id}: ⚠️ Fallback goto /key failed")
        return False


def extract_key_via_clipboard(page, account_id):
    import re
    # Step 1: Navigate to key page via sidebar API link (SPA-safe)
    if not navigate_to_key_page(page, account_id):
        log(f"{account_id}: ❌ Could not navigate to key page")
        return None
    
    # Wait for page to become interactive
    try:
        page.wait_for_selector('button, input, h1, h2, [role="button"]', timeout=20000)
        time.sleep(3)
    except:
        log(f"{account_id}: ⚠️ /key page still loading (no interactive elements)")
        time.sleep(8)  # Last resort wait
    
    # Try key extraction with retries
    for attempt in range(3):
        key = scrape_key_from_modal(page, account_id)
        if key:
            log(f"{account_id}: 💾 Got key from pre-existing modal!")
            return key
        
        create_btn = page.locator('button:has-text("Create API key")').first
        if create_btn.is_visible(timeout=10000):
            create_btn.click()
            time.sleep(2)
            
            key = scrape_key_from_modal(page, account_id)
            if key:
                return key
            
            name_input = page.locator('input').first
            if not name_input.is_visible(timeout=3000):
                log(f"{account_id}: ⚠️ Modal input not visible")
                return None
            
            name_input.type(f"key-{account_id}", delay=50)
            time.sleep(1)
            
            create_modal = page.locator('button:has-text("Create")').last
            if create_modal.is_visible(timeout=3000):
                if create_modal.is_disabled():
                    page.evaluate("""() => {
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            if (b.textContent.trim() === 'Create') {
                                b.disabled = false; b.click(); break;
                            }
                        }
                    }""")
                else:
                    create_modal.click()
                time.sleep(4)
            else:
                log(f"{account_id}: ⚠️ No Create button in modal")
                try:
                    page.locator('button').last.click()
                    time.sleep(4)
                except:
                    return None
            
            key = scrape_key_from_modal(page, account_id)
            if key:
                return key
            return None
        
        log(f"{account_id}: ⚠️ No Create API key button (attempt {attempt + 1}/3), waiting {10 * (attempt + 1)}s...")
        # Reload and wait longer each retry
        try:
            page.reload(timeout=45000, wait_until='networkidle')
            time.sleep(8 * (attempt + 1))
        except:
            time.sleep(10 * (attempt + 1))
    
    # Final fallback
    try:
        page.screenshot(path=f'/tmp/bai_keyfail_{SUFFIX}_{account_id}.png', full_page=True)
    except:
        pass
    try:
        body_text = page.locator('body').inner_text(timeout=5000)
        matches = re.findall(r'sk-[a-zA-Z0-9]{32,}', body_text)
        for m in matches:
            if '...' not in m and '*' not in m:
                return save_key(account_id, m)
    except:
        pass
    
    log(f"{account_id}: ❌ All key extraction methods failed after retries")
    return None

def solve_turnstile():
    r = subprocess.run(['curl', '-s', f'https://2captcha.com/in.php?key={CAP_KEY}&method=turnstile&sitekey={SITEKEY}&pageurl=https://chat.b.ai/&json=1'],
                       capture_output=True, text=True, timeout=30)
    data = json.loads(r.stdout)
    if data.get('status') != 1:
        return None, f"2cap create failed: {str(data.get('request', data))[:80]}"
    task_id = data['request']
    for _ in range(60):
        time.sleep(5)
        r = subprocess.run(['curl', '-s', f'https://2captcha.com/res.php?key={CAP_KEY}&action=get&id={task_id}&json=1'],
                           capture_output=True, text=True, timeout=30)
        data = json.loads(r.stdout)
        if data.get('status') == 1:
            return data['request'], None
    return None, "2captcha timeout"

def safe_goto(page, url, timeout=60000, retries=2):
    for attempt in range(retries + 1):
        try:
            page.goto(url, timeout=timeout, wait_until='domcontentloaded')
            time.sleep(3)
            return True
        except PwTimeout:
            log(f"  ⚠️ goto timeout ({timeout}ms), attempt {attempt+1}/{retries+1}")
            if attempt < retries:
                time.sleep(5)
                continue
            return False
        except Exception as e:
            log(f"  ⚠️ goto error: {e}")
            return False
    return False

def claim_account(account_id):
    email = f"{account_id}@{DOMAIN}"
    profile_path = Path(f"{PROFILE_BASE}_{account_id}")
    if profile_path.exists():
        shutil.rmtree(profile_path)
    
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(profile_path), headless=False,
                args=['--no-sandbox', '--disable-gpu', '--disable-popup-blocking',
                      '--disable-dev-shm-usage'],
            )
            page = ctx.new_page()
            
            # Clipboard intercept init
            page.add_init_script("""\
navigator.clipboard.writeText = (function(orig) {
    return async function(text) {
        window.__bai_full_key = text;
        window.__bai_full_key_source = 'clipboard.writeText';
        return orig.call(navigator.clipboard, text);
    };
})(navigator.clipboard.writeText.bind(navigator.clipboard));

var _origExecCommand = document.execCommand.bind(document);
document.execCommand = function(command, ui, value) {
    if (command === 'copy' && value && value.startsWith('sk-')) {
        window.__bai_full_key = value;
        window.__bai_full_key_source = 'execCommand';
    }
    return _origExecCommand(command, ui, value);
};

document.addEventListener('copy', function(e) {
    var text = window.getSelection().toString();
    if (text && text.startsWith('sk-')) {
        window.__bai_full_key = text;
        window.__bai_full_key_source = 'copy_event';
    }
}, true);
""")
            
            # 1️⃣ Google login
            log(f"{account_id}: Google login...")
            if not safe_goto(page, 'https://accounts.google.com/signin/v2/identifier', timeout=60000):
                ctx.close()
                return False, "google_nav_failed", ""
            
            page.locator("input[type='email']").first.fill(email)
            time.sleep(1)
            page.locator("button:has-text('Next')").first.click()
            time.sleep(5)
            
            page.locator("input[type='password']").first.fill(PASSWORD)
            time.sleep(1)
            page.locator("button:has-text('Next')").first.click()
            time.sleep(5)
            
            # Handle Google warning
            try:
                body_text = page.locator('body').inner_text(timeout=5000).lower()
                if 'selamat' in body_text or 'saya mengerti' in body_text or 'i understand' in body_text:
                    page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
                    time.sleep(1)
                    page.locator('text=Saya mengerti').first.click(timeout=5000)
                    time.sleep(3)
                    log(f"{account_id}: Dismissed Google warning")
            except:
                pass
            
            # 2️⃣ B.AI OAuth
            log(f"{account_id}: B.AI OAuth...")
            if not safe_goto(page, 'https://chat.b.ai/', timeout=90000):
                ctx.close()
                return False, "bai_load_failed", ""
            
            current_url = page.url
            log(f"{account_id}: URL after goto: {current_url[:80]}")
            
            if 'accounts.google' in current_url:
                log(f"{account_id}: Already redirecting to Google — waiting...")
                page.wait_for_url('https://chat.b.ai/**', timeout=90000)
                time.sleep(5)
            elif page.locator("button:has-text('Log in')").is_visible(timeout=5000):
                log(f"{account_id}: Login button visible, clicking...")
                try:
                    page.locator("button:has-text('Log in')").first.click()
                except:
                    try:
                        page.locator("button:has-text('Sign in')").first.click()
                    except:
                        pass
                time.sleep(2)
                
                with page.expect_popup(timeout=25000) as popup_info:
                    page.locator('text=Continue with Google').first.click()
                popup = popup_info.value
                time.sleep(4)
                
                try:
                    popup.locator(f'div[role="link"]:has-text("{account_id}")').first.click(timeout=10000)
                    time.sleep(5)
                except:
                    log(f"{account_id}: account link click failed, trying alternative...")
                    try:
                        for el in popup.locator('div[role="link"]').all():
                            t = el.text_content()
                            if account_id in t:
                                el.click()
                                time.sleep(5)
                                break
                    except:
                        ctx.close()
                        return False, "account_click_failed", ""
                
                try:
                    popup.locator('button:has-text("Continue")').first.click(timeout=8000)
                    time.sleep(5)
                except:
                    pass
            else:
                log(f"{account_id}: No login button — may be auto-login")
                time.sleep(8)
            
            time.sleep(2)
            log(f"{account_id}: OAuth done")
            
            # 3️⃣ Navigate to dashboard
            log(f"{account_id}: Loading dashboard...")
            if not safe_goto(page, 'https://chat.b.ai/', timeout=120000, retries=3):
                ctx.close()
                return False, "dashboard_timeout", ""
            
            # 4️⃣ Top-up page
            time.sleep(3)
            if not safe_goto(page, 'https://chat.b.ai/', timeout=60000, retries=2):
                ctx.close()
                return False, "topup_nav_failed", ""
            
            time.sleep(2)
            try:
                page.locator('text=Top-up Bonus').first.click(timeout=15000)
                log(f"{account_id}: Top-up Bonus clicked")
            except:
                try:
                    page.goto('https://chat.b.ai/', timeout=30000)
                    time.sleep(3)
                    page.locator('text=Top-up Bonus').first.click(timeout=15000)
                except:
                    ctx.close()
                    return False, "topup_button_not_found", ""
            
            time.sleep(4)
            
            # Check bonus
            body = page.locator('body').inner_text(timeout=5000)
            credit_info = ""
            for line in body.split('\n'):
                if 'Claim Free Credits' in line:
                    credit_info = line.strip()
                    log(f"{account_id}: {credit_info}")
                    break
            
            # 5️⃣ Solve Turnstile
            log(f"{account_id}: Solving Turnstile...")
            token, err = solve_turnstile()
            if err:
                ctx.close()
                return False, err, credit_info
            log(f"{account_id}: ✅ Turnstile solved")
            
            # 6️⃣ Monkey-patch Turnstile
            page.evaluate(f"""() => {{
                const ourToken = '{token}';
                if (typeof turnstile === 'undefined') window.turnstile = {{}};
                turnstile.render = function(container, params) {{
                    const input = document.querySelector('[name="cf-turnstile-response"]') ||
                        (() => {{ const i = document.createElement('input'); i.name = 'cf-turnstile-response'; document.body.appendChild(i); return i; }})();
                    input.value = ourToken;
                    if (params && params.callback) setTimeout(() => params.callback(ourToken), 50);
                    return 'patched-widget-' + Date.now();
                }};
                turnstile.getResponse = function() {{ return ourToken; }};
                turnstile.execute = function() {{
                    const input = document.querySelector('[name="cf-turnstile-response"]');
                    if (input) input.value = ourToken;
                    return Promise.resolve(ourToken);
                }};
                turnstile.reset = function() {{}};
                window.__turnstileToken = ourToken;
            }}""")
            time.sleep(1)
            
            # 7️⃣ Open bonus modal & claim — with retry
            claim_free_found = False
            for claim_attempt in range(3):
                try:
                    page.locator('button:has-text("Claim Free Credits")').first.click(timeout=10000)
                    time.sleep(5)
                    claim_free_found = True
                    break
                except:
                    url_now = page.url
                    log(f"{account_id}: ⚠️ Claim Free Credits not found (attempt {claim_attempt+1}/3, URL: {url_now})")
                    if claim_attempt < 2:
                        # Try to navigate to top-up directly
                        try:
                            page.goto('https://chat.b.ai/', timeout=30000, wait_until='domcontentloaded')
                            time.sleep(5)
                            page.locator('text=Top-up Bonus').first.click(timeout=15000)
                            time.sleep(6)
                        except:
                            time.sleep(10)
            
            if not claim_free_found:
                log(f"{account_id}: ⚠️ Claim Free Credits not found after retries, skipping key extraction")
                return False, "already_claimed_no_key", ""
            
            # Click Claim
            claim_clicked = False
            try:
                claim_btn = page.locator('button:has-text("Claim")').filter(has_not_text='Free').first
                if claim_btn.is_visible(timeout=5000):
                    if claim_btn.is_disabled():
                        time.sleep(4)
                    if not claim_btn.is_disabled():
                        claim_btn.click(timeout=10000)
                        time.sleep(3)
                        claim_clicked = True
                        log(f"{account_id}: ✅ Claim clicked!")
                    else:
                        page.evaluate("""() => {
                            const btns = document.evaluate("//button[contains(text(),'Claim')]", document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                            for (let i = 0; i < btns.snapshotLength; i++) {
                                const btn = btns.snapshotItem(i);
                                if (btn.textContent.trim() === 'Claim') {
                                    btn.removeAttribute('disabled');
                                    btn.click();
                                }
                            }
                        }""")
                        time.sleep(3)
                        claim_clicked = True
                        log(f"{account_id}: ✅ Claim force-clicked!")
            except:
                pass
            
            # 8️⃣ Check result
            time.sleep(3)
            body2 = page.locator('body').inner_text(timeout=5000)
            
            try:
                page.screenshot(path=f"/tmp/claim_{SUFFIX}_{account_id}.png")
            except:
                pass
            
            has_claimed = 'Free credit claimed' in body2 or 'Claimed' in body2
            has_error = 'Oops' in body2 or 'something went wrong' in body2 or 'Back to Home' in body2
            
            if has_claimed or (has_error and claim_clicked):
                log(f"{account_id}: ✅ 500K claimed! Extracting API key...")
                # Use the same page — keep SPA session intact, navigate via sidebar API link
                key = extract_key_via_clipboard(page, account_id)
                if key:
                    log(f"{account_id}: 💾 Key extracted successfully!")
                else:
                    log(f"{account_id}: ⚠️ Key extraction failed (claim still successful)")
                
                ctx.close()
                return True, "claimed", credit_info
            elif not claim_clicked:
                log(f"{account_id}: ❌ Claim button never worked")
                return False, "claim_button_never_clicked", credit_info
            else:
                log(f"{account_id}: ❌ No success indicator")
                return False, "no_success_indicator", credit_info
    
    except Exception as e:
        err_msg = str(e)[:120]
        log(f"{account_id}: ❌ Exception: {err_msg}")
        return False, f"exception: {err_msg}", ""
    finally:
        if profile_path.exists():
            shutil.rmtree(profile_path)

def main():
    results = {}
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            try:
                results = json.load(f)
            except:
                results = {}
    
    existing_success = sum(1 for v in results.values() if v.get('status') == 'success')
    existing_errors = sum(1 for v in results.values() if v.get('status') == 'error')
    log(f"📊 Worker {SUFFIX}: Existing {len(results)} accounts, ✅{existing_success} ❌{existing_errors}")
    log(f"🔌 No proxy (was using residential, too slow for Playwright Google OAuth)")
    log(f"📋 Range: {ACCOUNT_PREFIX}{WORKER_START} - {ACCOUNT_PREFIX}{WORKER_END}")
    
    for i in range(WORKER_START, WORKER_END + 1):
        acct = f"{ACCOUNT_PREFIX}{i}"
        
        key_path = f"{KEY_DIR}/{acct}.txt"
        has_key = os.path.exists(key_path)
        
        if results.get(acct, {}).get('status') == 'success' and has_key:
            log(f"⏭️ {acct}: Already done (claim ✅ key ✅)")
            continue
        
        if results.get(acct, {}).get('status') == 'success' and not has_key:
            log(f"🔄 {acct}: Re-claiming for key extraction (had claim, no key)")
            delay = random.randint(5, 15) + 20  # +20s offset from W1
        else:
            delay = random.randint(20, 60) + 20  # +20s offset from W1 to avoid collision
        log(f"⏳ Waiting {delay}s before {acct}...")
        time.sleep(delay)
        
        log(f"🚀 {acct}: Starting...")
        t0 = time.time()
        success, detail, credits = claim_account(acct)
        elapsed = int(time.time() - t0)
        
        status = "success" if success else "error"
        results[acct] = {
            "status": status,
            "reason": detail[:100],
            "credits": credits,
            "time_seconds": elapsed,
        }
        
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        if success:
            log(f"✅ {acct}: Claimed ({elapsed}s)")
        else:
            log(f"❌ {acct}: {detail[:80]} ({elapsed}s)")
        
        total = sum(1 for v in results.values() if v.get('status') == 'success')
        err = sum(1 for v in results.values() if v.get('status') == 'error')
        log(f"📊 Worker {SUFFIX}: ✅{total} ❌{err}")
    
    total_ok = sum(1 for v in results.values() if v.get('status') == 'success')
    total_err = sum(1 for v in results.values() if v.get('status') == 'error')
    log(f"🏁 Worker {SUFFIX} DONE: ✅{total_ok} ❌{total_err} | Total: {len(results)}")

if __name__ == '__main__':
    main()

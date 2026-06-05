#!/usr/bin/env python3
"""Phase 1: Google OAuth → save persistent profile."""
import time, json, sys, shutil
from pathlib import Path
from cloakbrowser import launch_persistent_context

email = sys.argv[1]
password = sys.argv[2] if len(sys.argv) > 2 else 'qwertyui'
acct = email.split('@')[0]

profile = Path(f'/root/cloakbrowser/profiles/bai_claim_{acct}')
if profile.exists():
    shutil.rmtree(profile)
profile.mkdir(parents=True)

ctx = launch_persistent_context(str(profile), headless=True, args=['--fingerprint=12345', '--no-sandbox'])
page = ctx.new_page()

# Google login
page.goto('https://accounts.google.com/signin/v2/identifier', timeout=30000); time.sleep(2)
page.locator("input[type='email']").first.fill(email); time.sleep(1)
page.locator("button:has-text('Next')").first.click(); time.sleep(3)
page.locator("input[type='password']").first.fill(password); time.sleep(1)
page.locator("button:has-text('Next')").first.click(); time.sleep(5)

try:
    body = page.locator('body').inner_text(timeout=5000).lower()
    if 'selamat datang' in body:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)"); time.sleep(2)
        page.locator('text=Saya mengerti').first.click(); time.sleep(3)
except: pass

# B.AI OAuth
page.goto('https://chat.b.ai/', timeout=30000); time.sleep(5)
if 'Log in' in page.locator('body').inner_text():
    page.locator("button:has-text('Log in')").first.click(); time.sleep(3)
    with ctx.expect_event('page', timeout=30000) as pi:
        page.locator('text=Continue with Google').first.click()
    popup = pi.value; time.sleep(5)
    if 'accountchooser' in popup.url:
        try: popup.locator(f'text={acct}').first.click()
        except: popup.locator('text=kdi').first.click()
        time.sleep(5)
    purl = popup.url
    if 'oauth' in purl or 'consent' in purl:
        popup.evaluate("window.scrollTo(0, document.body.scrollHeight)"); time.sleep(2)
        popup.locator('button').nth(1).click(); time.sleep(3)
    for _ in range(20):
        time.sleep(3)
        if 'chat.b.ai' in popup.url: break

time.sleep(3)
body = page.locator('body').inner_text(timeout=5000)
if 'Log in' in body:
    print('FAIL: not logged in', flush=True)
    ctx.close(); sys.exit(1)

ctx.close()
print(f'OK: profile saved to {profile}', flush=True)

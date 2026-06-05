#!/usr/bin/env python3
"""
B.AI Credit Claimer — Claim 500K credits for all accounts.

Two-process approach per account:
  Phase 1: bai-oauth.py  (CloakBrowser headless, no proxy) → persistent profile
  Phase 2: bai-claim-step2.py (CloakBrowser non-headless, proxy, same profile) → claim

Usage:
  python bai-claim.py --range 1-120
  python bai-claim.py --range 1-120 --test-only
"""

import argparse, time, json, sys, subprocess
from pathlib import Path

KEY_DIR = Path('/root/bai-keys')
PROFILE_BASE = Path('/root/cloakbrowser/profiles')
PROXY_HOST = 'proxy.wtvconfigs.run.place:8069'
PROXY_USER = '1671586399'
PROXY_PASS = 'GKPZqLKZZTUM0U5c'


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
        return False
    except:
        return None


def kill_chromes():
    try:
        subprocess.run(['pkill', '-9', '-f', 'chromium'], capture_output=True, timeout=5)
        time.sleep(3)
    except:
        pass


def cleanup_profile(acct):
    import shutil
    profile = PROFILE_BASE / f'bai_claim_{acct}'
    shutil.rmtree(profile, ignore_errors=True)


def run_phase1(email, password):
    kill_chromes()
    acct = email.split('@')[0]
    try:
        r = subprocess.run(
            ['python3', '-u', '/root/bai-oauth.py', email, password],
            capture_output=True, text=True, timeout=120
        )
        output = r.stdout.strip()
        if 'OK:' in output:
            log(f'OAuth done', acct)
            return True
        log(f'OAuth FAIL: {output[-80:]}', acct)
        return False
    except subprocess.TimeoutExpired:
        log('OAuth TIMEOUT', acct)
        kill_chromes()
        return False
    except Exception as e:
        log(f'OAuth ERROR: {str(e)[:80]}', acct)
        return False


def run_phase2(acct):
    kill_chromes()
    profile = PROFILE_BASE / f'bai_claim_{acct}'
    try:
        r = subprocess.run(
            ['python3', '-u', '/root/bai-claim-step2.py',
             str(profile), PROXY_HOST, PROXY_USER, PROXY_PASS],
            capture_output=True, text=True, timeout=180
        )
        output = r.stdout.strip()
        if 'OK:' in output:
            return 'OK', '500K credits claimed'
        lines = [l for l in output.split('\n') if l.strip()]
        detail = lines[-1] if lines else 'unknown'
        return 'FAIL', detail[:100]
    except subprocess.TimeoutExpired:
        log('Claim TIMEOUT', acct)
        kill_chromes()
        return 'FAIL', 'timeout'
    except Exception as e:
        return 'FAIL', str(e)[:100]


def main():
    parser = argparse.ArgumentParser(description='B.AI Credit Claimer')
    parser.add_argument('--range', required=True)
    parser.add_argument('--domain', default='giosin.com')
    parser.add_argument('--password', default='qwertyui')
    parser.add_argument('--prefix', default='kdi')
    parser.add_argument('--delay', type=int, default=10)
    parser.add_argument('--test-only', action='store_true')

    args = parser.parse_args()
    start, end = args.range.split('-')
    accounts = [f'{args.prefix}{n}@{args.domain}' for n in range(int(start), int(end) + 1)]
    total = len(accounts)

    ok = skip = fail = already = 0
    results = {}

    log(f'🚀 Claiming: {total} accounts')

    for i, email in enumerate(accounts, 1):
        acct = email.split('@')[0]
        log(f'[{i}/{total}] {acct}', acct)

        if not has_valid_key(acct):
            log('⏭️ No key', acct); skip += 1; continue

        if args.test_only:
            bal = test_balance(acct)
            log(f'{"✅" if bal else "❌"} {"has" if bal else "no"} credits', acct)
            if bal: already += 1
            continue

        if test_balance(acct) is True:
            log('⏭️ Has credits', acct); already += 1; continue

        # Phase 1
        if not run_phase1(email, args.password):
            fail += 1; results[acct] = 'FAIL: OAuth'; continue

        # Phase 2
        status, detail = run_phase2(acct)
        if status == 'OK':
            ok += 1; log(f'✅ {detail}', acct)
        else:
            fail += 1; log(f'❌ {detail}', acct)
        results[acct] = f'{status}: {detail}'

        cleanup_profile(acct)
        kill_chromes()

        if i < total: time.sleep(args.delay)
        if i % 10 == 0:
            print(flush=True)
            log(f'── {i}/{total} | ✅{ok} ⏭️{skip+already} ❌{fail} ──')
            print(flush=True)

    print(flush=True)
    print('=' * 55)
    log('🏁 COMPLETE')
    print(f'   ✅ {ok}  ⏭️ {skip+already}  ❌ {fail}  💰 {(ok+already)*500_000:,}')
    print('=' * 55)

    for acct, r in results.items():
        if r.startswith('FAIL'): print(f'  ❌ {acct}: {r}')

    return 0 if fail == 0 else 1

if __name__ == '__main__':
    sys.exit(main())

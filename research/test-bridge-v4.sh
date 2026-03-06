#!/bin/bash
# Test Oracle bridge with 403 bypass patch
set -e

source ~/camoufox-env/bin/activate
source ~/.nvm/nvm.sh && nvm use 22 >/dev/null 2>&1

COOKIES=~/.oracle/chatgpt-cookies.json
PORT=9222

# Export full cookie set from Playwright context
python3 -c "
from rebrowser_playwright.sync_api import sync_playwright
import json, sys
with open('$COOKIES') as f:
    seed = json.load(f)
pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--remote-debugging-port=$PORT','--remote-allow-origins=*','--disable-blink-features=AutomationControlled'])
ctx = browser.new_context(user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
ctx.add_cookies([{'name':c['name'],'value':c['value'],'domain':c.get('domain','.chatgpt.com'),'path':c.get('path','/'),**({'secure':True} if c.get('secure') else {}),**({'httpOnly':True} if c.get('httpOnly') else {}),**({'sameSite':c['sameSite'].capitalize()} if c.get('sameSite') else {})} for c in seed])
page = ctx.new_page()
page.goto('https://chatgpt.com', timeout=45000)
page.wait_for_load_state('domcontentloaded')
import time; time.sleep(5)
title = page.title()
print(f'BRIDGE_TITLE={title}', file=sys.stderr)
if 'Just a moment' in title:
    print('CF_BLOCKED', file=sys.stderr)
    browser.close(); pw.stop(); sys.exit(1)
# Export full cookies
full = ctx.cookies(['https://chatgpt.com'])
json.dump(full, sys.stdout)
# Keep browser alive (don't close)
import signal
signal.pause()
" > /tmp/full-cookies.json 2>/tmp/bridge-status.log &
BRIDGE_PID=$!

# Wait for bridge to be ready
sleep 15
cat /tmp/bridge-status.log

if grep -q CF_BLOCKED /tmp/bridge-status.log; then
    echo "FAIL: CF blocked"
    kill $BRIDGE_PID 2>/dev/null
    exit 1
fi

echo "Running Oracle..."
ORACLE_REUSE_TAB=1 \
ORACLE_BROWSER_COOKIES_JSON="$(cat /tmp/full-cookies.json)" \
oracle --engine browser --remote-chrome localhost:$PORT \
  --model gpt-4o \
  --prompt "Reply with exactly one word: WORKING" \
  --wait --force -v --timeout 120 2>&1 | tee /tmp/oracle-result.log

echo "=== DONE ==="
kill $BRIDGE_PID 2>/dev/null

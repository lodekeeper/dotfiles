#!/usr/bin/env python3
"""Quick DOM diagnostic: start bridge, submit prompt via Playwright, inspect response DOM."""
from rebrowser_playwright.sync_api import sync_playwright
import json, time, sys

with open('/home/openclaw/.oracle/chatgpt-cookies.json') as f:
    seed = json.load(f)

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=[
    '--remote-debugging-port=9226', '--remote-allow-origins=*',
    '--disable-blink-features=AutomationControlled',
])
ctx = browser.new_context(user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
ctx.add_cookies([{
    'name': c['name'], 'value': c['value'], 'domain': c.get('domain', '.chatgpt.com'),
    'path': c.get('path', '/'),
    **({'secure': True} if c.get('secure') else {}),
    **({'httpOnly': True} if c.get('httpOnly') else {}),
    **({'sameSite': c['sameSite'].capitalize()} if c.get('sameSite') else {}),
} for c in seed])

page = ctx.new_page()
page.goto('https://chatgpt.com', timeout=45000)
page.wait_for_load_state('domcontentloaded')
time.sleep(5)
print(f'Title: {page.title()}')

# Find and fill the prompt textarea
prompt_el = page.query_selector('#prompt-textarea, div[contenteditable="true"]')
if not prompt_el:
    print('ERROR: No prompt textarea found')
    browser.close(); pw.stop(); sys.exit(1)

print(f'Prompt element: {prompt_el.evaluate("el => el.tagName + (el.id ? \"#\"+el.id : \"\")")}')

# Type prompt
prompt_el.click()
page.keyboard.type('Reply with exactly one word: HELLO', delay=30)
time.sleep(1)

# Click send
send_btn = page.query_selector('button[data-testid="send-button"], button[aria-label*="Send"]')
if send_btn:
    send_btn.click()
    print('Send clicked')
else:
    # Try Enter
    page.keyboard.press('Enter')
    print('Enter pressed')

# Wait for response
print('Waiting for response...')
time.sleep(15)

# Inspect DOM for assistant turns
dom_info = page.evaluate("""() => {
    const turns = document.querySelectorAll('[data-testid^="conversation-turn"]');
    const result = [];
    turns.forEach((turn, i) => {
        const role = turn.getAttribute('data-testid');
        const markdown = turn.querySelector('.markdown, .result-streaming, [class*="markdown"]');
        const text = turn.innerText?.substring(0, 200) || '';
        const html = turn.innerHTML?.substring(0, 500) || '';
        result.push({
            index: i,
            testid: role,
            hasMarkdown: !!markdown,
            markdownClass: markdown?.className || null,
            markdownText: markdown?.innerText?.substring(0, 200) || null,
            turnText: text,
            turnHtmlSnippet: html.substring(0, 300),
        });
    });
    return {
        turnCount: turns.length,
        turns: result,
        bodyClasses: document.body.className,
        url: location.href,
    };
}""")
print(f'\nDOM inspection:')
print(json.dumps(dom_info, indent=2))

# Also check what Oracle's snapshot expression would see
oracle_snapshot = page.evaluate("""() => {
    const turns = document.querySelectorAll('[data-testid^="conversation-turn"]');
    const results = [];
    for (const turn of turns) {
        const roleEl = turn.querySelector('[data-message-author-role]');
        const role = roleEl?.getAttribute('data-message-author-role') || null;
        const contentRoot = turn.querySelector('.markdown') || turn.querySelector('[class*="result"]') || roleEl;
        const text = contentRoot?.innerText || contentRoot?.textContent || '';
        results.push({ role, text: text.substring(0, 200), testid: turn.getAttribute('data-testid') });
    }
    return results;
}""")
print(f'\nOracle-style snapshot:')
print(json.dumps(oracle_snapshot, indent=2))

browser.close(); pw.stop()

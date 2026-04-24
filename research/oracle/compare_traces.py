import json
from pathlib import Path

base = Path('/home/openclaw/.openclaw/workspace/research/oracle')
cam = json.loads((base / 'camoufox-trace-current.json').read_text())
ff = json.loads((base / 'firefox-trace-current.json').read_text())

cam_urls = {row['url']: row for row in cam['eventSummary']}
ff_urls = {row['url']: row for row in ff['eventSummary']}
all_urls = sorted(set(cam_urls) | set(ff_urls))

cam_only = []
ff_only = []
status_diff = []

for url in all_urls:
    c = cam_urls.get(url)
    f = ff_urls.get(url)
    if c and not f:
        cam_only.append(url)
    elif f and not c:
        ff_only.append(url)
    else:
        if c['responses'] != f['responses'] or c['failures'] != f['failures'] or c['requests'] != f['requests']:
            status_diff.append({
                'url': url,
                'camoufox': {'requests': c['requests'], 'responses': c['responses'], 'failures': c['failures']},
                'firefox': {'requests': f['requests'], 'responses': f['responses'], 'failures': f['failures']},
            })

interesting = [
    row for row in status_diff
    if ('/backend-api/' in row['url'] or '/backend-anon/' in row['url'] or '/backend/' in row['url'] or '/ces/' in row['url'] or 'ws.chatgpt.com' in row['url'] or '/cdn-cgi/' in row['url'])
]

out = {
    'highLevel': {
        'camoufox': {
            'navigation': cam['navigation'],
            'postSend': cam['postSend'],
            'samples': cam['samples'],
            'websockets': cam['websockets'],
            'pageErrors': cam['pageErrors'],
            'consoleErrorHead': cam['consoleErrors'][:8],
        },
        'firefox': {
            'navigation': ff['navigation'],
            'postSend': ff['postSend'],
            'samples': ff['samples'],
            'websockets': ff['websockets'],
            'pageErrors': ff['pageErrors'],
            'consoleErrorHead': ff['consoleErrors'][:8],
        },
    },
    'counts': {
        'camoufoxUrls': len(cam_urls),
        'firefoxUrls': len(ff_urls),
        'camoufoxOnlyCount': len(cam_only),
        'firefoxOnlyCount': len(ff_only),
        'statusDiffCount': len(status_diff),
        'interestingDiffCount': len(interesting),
    },
    'camoufoxOnlyInteresting': [u for u in cam_only if ('/backend-' in u or '/backend/' in u or '/ces/' in u or 'ws.chatgpt.com' in u or '/cdn-cgi/' in u)][:120],
    'firefoxOnlyInteresting': [u for u in ff_only if ('/backend-' in u or '/backend/' in u or '/ces/' in u or 'ws.chatgpt.com' in u or '/cdn-cgi/' in u)][:120],
    'interestingDiffs': interesting[:200],
}
print(json.dumps(out, indent=2))

#!/usr/bin/env python3
"""Create and publish Substack posts with correct HTML via CDP - FINAL."""
import json
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import websockets

WS_URL = 'ws://127.0.0.1:18800/devtools/page/ECC504EE515D8C004A64C38E3B5FE1B4'
MSG_ID = 0

def next_id():
    global MSG_ID
    MSG_ID += 1
    return MSG_ID

async def run_js(ws, js_code):
    mid = next_id()
    await ws.send(json.dumps({
        'id': mid, 'method': 'Runtime.evaluate',
        'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}
    }))
    resp = json.loads(await ws.recv())
    return resp.get('result', {}).get('result', {}).get('value')

async def main():
    async with websockets.connect(WS_URL, max_size=10**7) as ws:
        # First: clean up test draft
        val = await run_js(ws, '''
            fetch('https://jinilee.substack.com/api/v1/drafts?limit=5', {credentials:'include'})
            .then(r=>r.json())
            .then(d=>JSON.stringify(d.filter(x=>x.draft_title==='TEST').map(x=>x.id)))
        ''')
        print(f'Test drafts to clean: {val}')
        if val:
            for tid in json.loads(val):
                await run_js(ws, f"fetch('https://jinilee.substack.com/api/v1/drafts/{tid}',{{method:'DELETE',credentials:'include'}}).then(r=>r.status)")
                print(f'  Deleted test draft {tid}')

        posts = [
            {
                'html_file': Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_Operating-Notes-2_EN.body.html'),
                'title': 'MAIJINI@openclaw Operating Notes #2 \u2014 Claude Code + MAIBOT + maiupbit: The Full-Stack AI Dev Chain',
                'subtitle': 'How I wired Claude Code into Discord DM via OpenClaw to build a crypto quant CLI, optimize GPU inference, and automate a newsletter pipeline \u2014 all through chat.',
            },
            {
                'html_file': Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_AI-Quant-Letter-3_EN.body.html'),
                'title': 'AI Quant Letter #3 \u2014 All Negative Momentum Scores, ETH Still Leads',
                'subtitle': 'Week of March 15: Dual momentum says hold cash, multi-factor keeps ETH and AVAX at the top.',
            },
        ]

        for post in posts:
            print(f'\n=== {post["title"][:60]}... ===')
            html = post['html_file'].read_text(encoding='utf-8')
            print(f'  HTML: {len(html)} chars')

            # Step 1: Create draft with empty bylines
            create_body = json.dumps({
                'draft_title': post['title'],
                'draft_subtitle': post['subtitle'],
                'type': 'newsletter',
                'audience': 'everyone',
                'draft_bylines': [],
            })
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts', {{
                    method: 'POST', credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: {json.dumps(create_body)}
                }}).then(r=>r.json())
                .then(d=>JSON.stringify({{id:d.id, slug:d.slug}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Created: {val}')
            data = json.loads(val)
            draft_id = data.get('id')
            slug = data.get('slug')
            if not draft_id:
                print('  FAILED to create draft!')
                continue

            # Step 2: Update body with HTML
            update_body = json.dumps({'draft_body': html})
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}', {{
                    method: 'PUT', credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: {json.dumps(update_body)}
                }}).then(r=>r.json())
                .then(d=>JSON.stringify({{body_len:(d.body_html||'').length, starts_with: (d.body_html||'').substring(0,60)}}) )
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Body updated: {val}')

            # Check if body was properly set
            body_data = json.loads(val) if val else {}
            body_len = body_data.get('body_len', 0)
            starts = body_data.get('starts_with', '')
            
            if body_len < 100 or '&lt;' in starts:
                print(f'  WARNING: Body may be escaped! len={body_len}, starts={starts}')
            else:
                print(f'  Body looks good: {body_len} chars, starts with: {starts[:40]}')

            # Step 3: Publish web-only (no email)
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}/publish', {{
                    method: 'PUT', credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{send: false, share_automatically: false}})
                }}).then(r=>r.json())
                .then(d=>JSON.stringify({{ok:true, type:d.type}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Published: {val}')
            print(f'  URL: https://jinilee.substack.com/p/{slug}')

asyncio.run(main())

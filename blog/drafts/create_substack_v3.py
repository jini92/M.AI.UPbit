#!/usr/bin/env python3
"""Create and publish Substack posts with correct HTML via CDP."""
import json
import asyncio
import sys
import time
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
        'id': mid,
        'method': 'Runtime.evaluate',
        'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}
    }))
    resp = json.loads(await ws.recv())
    result = resp.get('result', {}).get('result', {})
    val = result.get('value')
    if result.get('subtype') == 'error':
        return f"JS_ERROR: {result.get('description', 'unknown')}"
    return val


async def main():
    async with websockets.connect(WS_URL, max_size=10**7) as ws:
        # 1. Check auth
        val = await run_js(ws, '''
            fetch('https://jinilee.substack.com/api/v1/subscriber/me', {credentials: 'include'})
            .then(r => r.json())
            .then(d => JSON.stringify({id: d.id, name: d.name}))
            .catch(e => 'ERR:' + e.message)
        ''')
        print(f'Auth: {val}')

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

            # Create draft (no body)
            create_payload = json.dumps({
                'draft_title': post['title'],
                'draft_subtitle': post['subtitle'],
                'type': 'newsletter',
                'audience': 'everyone',
            })
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts', {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: {json.dumps(create_payload)}
                }})
                .then(r => r.text())
                .catch(e => 'ERR:' + e.message)
            ''')
            print(f'  Create response: {str(val)[:200]}')

            try:
                data = json.loads(val)
                if 'errors' in data:
                    print(f'  ERROR: {data["errors"]}')
                    continue
                draft_id = data.get('id')
                slug = data.get('slug')
            except:
                print(f'  Parse error')
                continue

            if not draft_id:
                print('  No draft_id!')
                continue

            print(f'  Draft created: id={draft_id}, slug={slug}')

            # Update body via PUT
            update_payload = json.dumps({'draft_body': html})
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}', {{
                    method: 'PUT',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: {json.dumps(update_payload)}
                }})
                .then(r => r.json())
                .then(d => JSON.stringify({{body_len: (d.body_html||'').length, body_start: (d.body_html||'').substring(0,80)}}))
                .catch(e => 'ERR:' + e.message)
            ''')
            print(f'  Body update: {val}')

            # Publish
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}/publish', {{
                    method: 'PUT',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{send: false, share_automatically: false}})
                }})
                .then(r => r.json())
                .then(d => JSON.stringify({{ok: true, slug: d.slug}}))
                .catch(e => 'ERR:' + e.message)
            ''')
            print(f'  Publish: {val}')
            print(f'  URL: https://jinilee.substack.com/p/{slug}')

asyncio.run(main())

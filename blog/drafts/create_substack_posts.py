#!/usr/bin/env python3
"""Create and publish Substack posts with correct HTML via CDP browser API."""
import json
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import websockets

WS_URL = 'ws://127.0.0.1:18800/devtools/page/ECC504EE515D8C004A64C38E3B5FE1B4'

POSTS = [
    {
        'html_file': Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_Operating-Notes-2_EN.body.html'),
        'title': 'MAIJINI@openclaw Operating Notes #2 — Claude Code + MAIBOT + maiupbit: The Full-Stack AI Dev Chain',
        'subtitle': 'How I wired Claude Code into Discord DM via OpenClaw to build a crypto quant CLI, optimize GPU inference, and automate a newsletter pipeline — all through chat.',
        'type': 'newsletter',
        'audience': 'everyone',
    },
    {
        'html_file': Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_AI-Quant-Letter-3_EN.body.html'),
        'title': 'AI Quant Letter #3 — All Negative Momentum Scores, ETH Still Leads',
        'subtitle': 'Week of March 15: Dual momentum says hold cash, multi-factor keeps ETH and AVAX at the top. What the signals mean when everything is red.',
        'type': 'newsletter',
        'audience': 'everyone',
    },
]


async def run_js(ws, js_code, msg_id=1):
    """Execute JS in browser and return result."""
    await ws.send(json.dumps({
        'id': msg_id,
        'method': 'Runtime.evaluate',
        'params': {
            'expression': js_code,
            'awaitPromise': True,
            'returnByValue': True,
        }
    }))
    resp = json.loads(await ws.recv())
    result = resp.get('result', {}).get('result', {})
    if result.get('type') == 'string':
        return result.get('value')
    return result.get('value', resp)


async def main():
    async with websockets.connect(WS_URL, max_size=10**7) as ws:
        for i, post in enumerate(POSTS):
            print(f'\n=== Creating: {post["title"][:60]}... ===')

            html_content = post['html_file'].read_text(encoding='utf-8')
            print(f'  HTML length: {len(html_content)}')

            # Build the payload as a JSON string for JS
            payload = json.dumps({
                'draft_title': post['title'],
                'draft_subtitle': post['subtitle'],
                'draft_body': html_content,
                'type': post['type'],
                'audience': post['audience'],
            })
            # Escape for embedding in JS template literal
            payload_js = json.dumps(payload)  # double-encode for JS string

            # Step 1: Create draft
            create_js = f'''
            fetch('/api/v1/drafts', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: {payload_js}
            }}).then(r => r.json())
            .then(d => JSON.stringify({{id: d.id, title: d.draft_title, body_len: (d.body_html||'').length, slug: d.slug}}))
            .catch(e => JSON.stringify({{error: e.message}}))
            '''
            result = await run_js(ws, create_js, i * 10 + 1)
            print(f'  Create: {result}')

            try:
                data = json.loads(result)
                draft_id = data.get('id')
                slug = data.get('slug')
                body_len = data.get('body_len', 0)
            except (json.JSONDecodeError, TypeError):
                print(f'  ERROR parsing result: {result}')
                continue

            if not draft_id:
                print(f'  ERROR: no draft_id returned')
                continue

            print(f'  Draft ID: {draft_id}, body_html_len: {body_len}, slug: {slug}')

            if body_len < 100:
                print(f'  WARNING: body seems too short ({body_len}), HTML may not have been accepted')

            # Step 2: Publish (web-only, no email)
            pub_js = f'''
            fetch('/api/v1/drafts/{draft_id}/publish', {{
                method: 'PUT',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{send: false, share_automatically: false}})
            }}).then(r => r.status + ' ' + r.statusText)
            .catch(e => 'ERROR: ' + e.message)
            '''
            result = await run_js(ws, pub_js, i * 10 + 2)
            print(f'  Publish: {result}')

            if slug:
                print(f'  URL: https://jinilee.substack.com/p/{slug}')

asyncio.run(main())

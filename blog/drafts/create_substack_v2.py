#!/usr/bin/env python3
"""Create Substack drafts with proper HTML via CDP - debug version."""
import json
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import websockets

WS_URL = 'ws://127.0.0.1:18800/devtools/page/ECC504EE515D8C004A64C38E3B5FE1B4'


async def run_js(ws, js_code, msg_id=1):
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
    return resp


async def main():
    async with websockets.connect(WS_URL, max_size=10**7) as ws:
        # Step 1: Create a simple draft first to test
        test_js = '''
        fetch('/api/v1/drafts', {
            method: 'POST',
            credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                draft_title: 'TEST POST DELETE ME',
                draft_subtitle: 'test',
                type: 'newsletter',
                audience: 'everyone'
            })
        })
        .then(r => r.text())
        .catch(e => 'ERROR: ' + e.message)
        '''
        resp = await run_js(ws, test_js, 1)
        val = resp.get('result', {}).get('result', {}).get('value', 'NO VALUE')
        # Parse response to find the structure
        try:
            data = json.loads(val)
            print(f'Test draft response keys: {list(data.keys()) if isinstance(data, dict) else "not a dict"}')
            if isinstance(data, dict):
                print(f'  id: {data.get("id")}')
                print(f'  draft_title: {data.get("draft_title")}')
                print(f'  type: {data.get("type")}')
                test_id = data.get('id')
        except (json.JSONDecodeError, TypeError):
            print(f'Raw response: {val[:500]}')
            test_id = None

        if not test_id:
            print('Could not create test draft. Checking auth...')
            # Check if we're logged in
            auth_js = '''
            fetch('/api/v1/me', {credentials: 'include'})
            .then(r => r.json())
            .then(d => JSON.stringify({id: d.id, name: d.name, email: d.email}))
            .catch(e => 'ERROR: ' + e.message)
            '''
            resp = await run_js(ws, auth_js, 2)
            val = resp.get('result', {}).get('result', {}).get('value', 'NO VALUE')
            print(f'Auth check: {val}')
            return

        # Delete test post
        del_js = f'''
        fetch('/api/v1/drafts/{test_id}', {{
            method: 'DELETE',
            credentials: 'include'
        }}).then(r => r.status)
        .catch(e => 'ERROR: ' + e.message)
        '''
        resp = await run_js(ws, del_js, 3)
        val = resp.get('result', {}).get('result', {}).get('value', 'NO VALUE')
        print(f'Deleted test: {val}')

        # Step 2: Now create the real posts with HTML body
        posts = [
            {
                'html_file': r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_Operating-Notes-2_EN.body.html',
                'title': 'MAIJINI@openclaw Operating Notes #2 — Claude Code + MAIBOT + maiupbit: The Full-Stack AI Dev Chain',
                'subtitle': 'How I wired Claude Code into Discord DM via OpenClaw to build a crypto quant CLI, optimize GPU inference, and automate a newsletter pipeline — all through chat.',
            },
            {
                'html_file': r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_AI-Quant-Letter-3_EN.body.html',
                'title': 'AI Quant Letter #3 — All Negative Momentum Scores, ETH Still Leads',
                'subtitle': 'Week of March 15: Dual momentum says hold cash, multi-factor keeps ETH and AVAX at the top.',
            },
        ]

        for i, post in enumerate(posts):
            print(f'\n=== Post {i+1}: {post["title"][:50]}... ===')
            html = Path(post['html_file']).read_text(encoding='utf-8')
            print(f'  HTML length: {len(html)}')
            
            # Create draft WITHOUT body first
            create_js = f'''
            fetch('/api/v1/drafts', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    draft_title: {json.dumps(post['title'])},
                    draft_subtitle: {json.dumps(post['subtitle'])},
                    type: 'newsletter',
                    audience: 'everyone'
                }})
            }})
            .then(r => r.json())
            .then(d => JSON.stringify({{id: d.id, slug: d.slug}}))
            .catch(e => 'ERROR: ' + e.message)
            '''
            resp = await run_js(ws, create_js, 10 + i)
            val = resp.get('result', {}).get('result', {}).get('value', 'NO VALUE')
            print(f'  Created: {val}')
            
            try:
                data = json.loads(val)
                draft_id = data.get('id')
                slug = data.get('slug')
            except:
                print(f'  Could not parse: {val}')
                continue

            if not draft_id:
                continue

            # Now update with body HTML
            # The key: use draft_body in the PUT request
            payload = json.dumps({'draft_body': html})
            
            update_js = f'''
            fetch('/api/v1/drafts/{draft_id}', {{
                method: 'PUT',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: {json.dumps(payload)}
            }})
            .then(r => r.json())
            .then(d => JSON.stringify({{id: d.id, body_len: (d.body_html||'').length}}))
            .catch(e => 'ERROR: ' + e.message)
            '''
            resp = await run_js(ws, update_js, 20 + i)
            val = resp.get('result', {}).get('result', {}).get('value', 'NO VALUE')
            print(f'  Updated body: {val}')

            # Publish web-only
            pub_js = f'''
            fetch('/api/v1/drafts/{draft_id}/publish', {{
                method: 'PUT',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{send: false, share_automatically: false}})
            }})
            .then(r => r.json())
            .then(d => JSON.stringify({{status: 'published', slug: d.slug || '{slug}', id: d.id}}))
            .catch(e => 'ERROR: ' + e.message)
            '''
            resp = await run_js(ws, pub_js, 30 + i)
            val = resp.get('result', {}).get('result', {}).get('value', 'NO VALUE')
            print(f'  Published: {val}')
            print(f'  URL: https://jinilee.substack.com/p/{slug}')

asyncio.run(main())

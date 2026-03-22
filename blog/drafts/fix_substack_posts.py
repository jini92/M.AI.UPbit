#!/usr/bin/env python3
"""Fix Substack posts with escaped HTML via CDP browser API."""
import json
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import websockets

WS_URL = 'ws://127.0.0.1:18800/devtools/page/ECC504EE515D8C004A64C38E3B5FE1B4'

# Post IDs to fix
POSTS = {
    191553433: Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_Operating-Notes-2_EN.body.html'),
    191526011: Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_AI-Quant-Letter-3_EN.body.html'),
}

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
        for post_id, html_file in POSTS.items():
            print(f'\n=== Processing post {post_id} ===')
            
            if not html_file.exists():
                print(f'  HTML file not found: {html_file}')
                continue
                
            html_content = html_file.read_text(encoding='utf-8')
            print(f'  HTML length: {len(html_content)}')
            
            # Escape for JS string
            html_escaped = json.dumps(html_content)
            
            # Step 1: Delete the broken post
            delete_js = f'''
            fetch('/api/v1/drafts/{post_id}', {{
                method: 'DELETE',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}}
            }}).then(r => r.status + ' ' + r.statusText)
            .catch(e => 'ERROR: ' + e.message)
            '''
            result = await run_js(ws, delete_js, post_id)
            print(f'  Delete: {result}')
            
            # If delete didn't work, try unpublishing first
            if '403' in str(result) or '404' in str(result):
                # Try to revert to draft first
                revert_js = f'''
                fetch('/api/v1/drafts/{post_id}', {{
                    method: 'PUT',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{is_published: false}})
                }}).then(r => r.status + ' ' + r.statusText)
                .catch(e => 'ERROR: ' + e.message)
                '''
                result = await run_js(ws, revert_js, post_id + 1000)
                print(f'  Revert to draft: {result}')
                
                # Now try update with correct HTML
                update_js = f'''
                fetch('/api/v1/drafts/{post_id}', {{
                    method: 'PUT',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{draft_body: {html_escaped}}})
                }}).then(r => r.json())
                .then(d => 'Updated: body_html_len=' + (d.body_html||'').length)
                .catch(e => 'ERROR: ' + e.message)
                '''
                result = await run_js(ws, update_js, post_id + 2000)
                print(f'  Update body: {result}')
                
                # Re-publish
                pub_js = f'''
                fetch('/api/v1/drafts/{post_id}/publish', {{
                    method: 'PUT',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{send: false, share_automatically: false}})
                }}).then(r => r.status + ' ' + r.statusText)
                .catch(e => 'ERROR: ' + e.message)
                '''
                result = await run_js(ws, pub_js, post_id + 3000)
                print(f'  Re-publish: {result}')

asyncio.run(main())

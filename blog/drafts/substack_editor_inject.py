#!/usr/bin/env python3
"""Inject HTML content into Substack editor via CDP, then publish."""
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

async def run_js(ws, js_code, timeout=15):
    mid = next_id()
    await ws.send(json.dumps({
        'id': mid, 'method': 'Runtime.evaluate',
        'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}
    }))
    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
    return resp.get('result', {}).get('result', {}).get('value')

async def main():
    async with websockets.connect(WS_URL, max_size=10**7) as ws:
        # Clean up failed drafts first
        val = await run_js(ws, '''
            fetch('https://jinilee.substack.com/api/v1/drafts?limit=10', {credentials:'include'})
            .then(r=>r.json())
            .then(d=>JSON.stringify(d.filter(x=>!x.is_published && x.draft_title!=='How to use the Substack editor').map(x=>({id:x.id,title:x.draft_title}))))
        ''')
        print(f'Drafts: {val}')
        if val:
            for d in json.loads(val):
                await run_js(ws, f"fetch('https://jinilee.substack.com/api/v1/drafts/{d['id']}',{{method:'DELETE',credentials:'include'}}).then(r=>r.status)")
                print(f'  Cleaned: {d["id"]}')

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

            # Step 1: Create empty draft
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
            if not draft_id:
                print('  FAILED!')
                continue

            # Step 2: Navigate to editor page
            editor_url = f'https://jinilee.substack.com/publish/post/{draft_id}'
            val = await run_js(ws, f"window.location.href = '{editor_url}'; 'navigating'")
            print(f'  Navigating to editor...')
            await asyncio.sleep(5)  # Wait for page load

            # Step 3: Wait for editor to be ready and inject HTML
            # Substack uses ProseMirror editor - we need to find the editor view
            val = await run_js(ws, '''
                new Promise((resolve) => {
                    let attempts = 0;
                    const check = () => {
                        attempts++;
                        // Find the ProseMirror editor
                        const editor = document.querySelector('.ProseMirror');
                        if (editor) {
                            resolve('editor_found');
                        } else if (attempts < 20) {
                            setTimeout(check, 500);
                        } else {
                            resolve('editor_not_found_after_' + attempts);
                        }
                    };
                    check();
                })
            ''', timeout=30)
            print(f'  Editor: {val}')

            if val != 'editor_found':
                print(f'  Could not find editor, trying alternate selector...')
                val = await run_js(ws, '''
                    const selectors = ['.ProseMirror', '[contenteditable=true]', '.editor-content', '#editor', '.tiptap'];
                    const found = selectors.filter(s => document.querySelector(s));
                    JSON.stringify(found);
                ''')
                print(f'  Found selectors: {val}')
                
            # Step 4: Inject HTML into ProseMirror
            html_escaped = json.dumps(html)
            val = await run_js(ws, f'''
                const editor = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable=true]');
                if (editor) {{
                    editor.innerHTML = {html_escaped};
                    // Trigger input event to sync ProseMirror state
                    editor.dispatchEvent(new Event('input', {{bubbles: true}}));
                    editor.dispatchEvent(new Event('change', {{bubbles: true}}));
                    'injected_' + editor.innerHTML.length;
                }} else {{
                    'no_editor_element';
                }}
            ''')
            print(f'  Inject: {val}')

            # Step 5: Wait and trigger save
            await asyncio.sleep(3)
            
            # Try to find and click publish button, or save draft
            val = await run_js(ws, '''
                // Try to trigger auto-save by dispatching key event
                const editor = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable=true]');
                if (editor) {
                    editor.dispatchEvent(new KeyboardEvent('keydown', {key: ' ', bubbles: true}));
                    editor.dispatchEvent(new KeyboardEvent('keyup', {key: ' ', bubbles: true}));
                }
                // Check for save status
                const status = document.querySelector('[class*=save], [class*=status], [class*=draft]');
                status ? status.textContent : 'no_status_element';
            ''')
            print(f'  Save status: {val}')

            # Navigate back to publish page
            await asyncio.sleep(2)
            val = await run_js(ws, "window.location.href = 'https://jinilee.substack.com/publish/posts'; 'back'")
            await asyncio.sleep(3)

            # Step 6: Publish via API
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}/publish', {{
                    method: 'PUT', credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{send: false, share_automatically: false}})
                }}).then(r=>r.text())
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Publish response: {str(val)[:200]}')

            # Verify
            await asyncio.sleep(2)
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/posts/{draft_id}', {{credentials:'include'}})
                .then(r=>r.json())
                .then(d=>JSON.stringify({{slug:d.slug, body_len:(d.body_html||'').length, starts:(d.body_html||'').substring(0,80)}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Verify: {val}')

asyncio.run(main())

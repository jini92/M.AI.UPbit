#!/usr/bin/env python3
"""Paste HTML into Substack editor via clipboard paste event (CDP)."""
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

async def run_js(ws, js_code, timeout=30):
    mid = next_id()
    await ws.send(json.dumps({
        'id': mid, 'method': 'Runtime.evaluate',
        'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}
    }))
    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
    return resp.get('result', {}).get('result', {}).get('value')

async def main():
    async with websockets.connect(WS_URL, max_size=10**7) as ws:
        # Clean up any unpublished drafts
        val = await run_js(ws, '''
            fetch('https://jinilee.substack.com/api/v1/drafts?limit=10', {credentials:'include'})
            .then(r=>r.json())
            .then(d=>JSON.stringify(d.filter(x=>!x.is_published && x.draft_title!=='How to use the Substack editor').map(x=>({id:x.id,t:x.draft_title}))))
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
                .then(d=>JSON.stringify({{id:d.id}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            data = json.loads(val)
            draft_id = data.get('id')
            if not draft_id:
                print(f'  Create FAILED: {val}')
                continue
            print(f'  Draft: {draft_id}')

            # Step 2: Navigate to editor
            editor_url = f'https://jinilee.substack.com/publish/post/{draft_id}'
            val = await run_js(ws, f"window.location.href = '{editor_url}'; 'ok'")
            await asyncio.sleep(6)

            # Step 3: Wait for ProseMirror editor
            val = await run_js(ws, '''
                new Promise(resolve => {
                    let n = 0;
                    const check = () => {
                        n++;
                        const pm = document.querySelector('.ProseMirror');
                        if (pm) resolve('ready');
                        else if (n < 30) setTimeout(check, 500);
                        else resolve('timeout');
                    };
                    check();
                })
            ''')
            print(f'  Editor: {val}')
            if val != 'ready':
                continue

            # Step 4: Use clipboard paste to inject HTML into ProseMirror
            html_js = json.dumps(html)
            val = await run_js(ws, f'''
                new Promise(resolve => {{
                    const pm = document.querySelector('.ProseMirror');
                    pm.focus();
                    
                    // Select all existing content first
                    const sel = window.getSelection();
                    sel.selectAllChildren(pm);
                    
                    // Create clipboard data with HTML
                    const dt = new DataTransfer();
                    dt.setData('text/html', {html_js});
                    dt.setData('text/plain', 'content');
                    
                    // Dispatch paste event
                    const pasteEvent = new ClipboardEvent('paste', {{
                        bubbles: true,
                        cancelable: true,
                        clipboardData: dt
                    }});
                    pm.dispatchEvent(pasteEvent);
                    
                    // Wait for ProseMirror to process
                    setTimeout(() => {{
                        const bodyLen = pm.innerHTML.length;
                        const hasContent = bodyLen > 100;
                        resolve(JSON.stringify({{pasted: hasContent, bodyLen: bodyLen, start: pm.innerHTML.substring(0, 80)}}));
                    }}, 2000);
                }})
            ''')
            print(f'  Paste: {val}')

            # Step 5: Wait for auto-save (Substack saves drafts automatically)
            print('  Waiting for auto-save...')
            await asyncio.sleep(8)

            # Step 6: Check if content was saved
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}', {{credentials:'include'}})
                .then(r=>r.json())
                .then(d=>JSON.stringify({{body_len:(d.body_html||'').length, starts:(d.body_html||'').substring(0,80)}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Draft body check: {val}')

            body_data = json.loads(val) if val else {}
            if body_data.get('body_len', 0) < 100:
                print('  Body still empty - trying manual save trigger...')
                # Try Ctrl+S
                val = await run_js(ws, '''
                    document.querySelector('.ProseMirror').dispatchEvent(
                        new KeyboardEvent('keydown', {key: 's', ctrlKey: true, bubbles: true})
                    );
                    'ctrl+s sent'
                ''')
                await asyncio.sleep(5)
                val = await run_js(ws, f'''
                    fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}', {{credentials:'include'}})
                    .then(r=>r.json())
                    .then(d=>JSON.stringify({{body_len:(d.body_html||'').length}}))
                ''')
                print(f'  After Ctrl+S: {val}')

            # Step 7: Navigate back and publish
            val = await run_js(ws, "window.location.href = 'https://jinilee.substack.com/publish/posts'; 'ok'")
            await asyncio.sleep(3)

            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}/publish', {{
                    method: 'PUT', credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{send: false, share_automatically: false}})
                }}).then(r=>r.text())
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Publish: {str(val)[:100]}')

            # Verify final
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/posts/{draft_id}', {{credentials:'include'}})
                .then(r=>r.json())
                .then(d=>JSON.stringify({{slug:d.slug, body_len:(d.body_html||'').length, has_escaped:(d.body_html||'').includes('&lt;')}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Final: {val}')
            try:
                fd = json.loads(val)
                print(f'  URL: https://jinilee.substack.com/p/{fd.get("slug")}')
            except:
                pass

asyncio.run(main())

#!/usr/bin/env python3
"""Use execCommand('insertHTML') + ProseMirror view dispatch to set Substack body."""
import json
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import websockets

MSG_ID = 0
def next_id():
    global MSG_ID; MSG_ID += 1; return MSG_ID

async def run_js(ws, js_code, timeout=30):
    mid = next_id()
    await ws.send(json.dumps({'id': mid, 'method': 'Runtime.evaluate',
        'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}}))
    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
    return resp.get('result', {}).get('result', {}).get('value')

async def cdp_input(ws, text):
    """Use CDP Input.insertText to properly insert text through the browser's input pipeline."""
    mid = next_id()
    await ws.send(json.dumps({'id': mid, 'method': 'Input.insertText', 'params': {'text': text}}))
    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
    return resp

async def main():
    # Get fresh page ID
    import urllib.request
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    substack_page = next((p for p in pages if 'substack.com' in p.get('url', '') and p['type'] == 'page'), None)
    if not substack_page:
        print('No Substack tab found!')
        return
    ws_url = substack_page['webSocketDebuggerUrl']
    print(f'Connecting to: {substack_page["url"]}')

    async with websockets.connect(ws_url, max_size=10**7) as ws:
        # Clean drafts
        val = await run_js(ws, '''
            fetch('https://jinilee.substack.com/api/v1/drafts?limit=10', {credentials:'include'})
            .then(r=>r.json())
            .then(d=>JSON.stringify(d.filter(x=>!x.is_published && x.draft_title!=='How to use the Substack editor').map(x=>({id:x.id,t:x.draft_title}))))
        ''')
        if val:
            for d in json.loads(val):
                await run_js(ws, f"fetch('https://jinilee.substack.com/api/v1/drafts/{d['id']}',{{method:'DELETE',credentials:'include'}}).then(r=>r.status)")
                print(f'Cleaned: {d["id"]}')

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
            print(f'\n=== {post["title"][:55]}... ===')
            html = post['html_file'].read_text(encoding='utf-8')

            # Create draft
            create_body = json.dumps({
                'draft_title': post['title'], 'draft_subtitle': post['subtitle'],
                'type': 'newsletter', 'audience': 'everyone', 'draft_bylines': []})
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts', {{
                    method:'POST', credentials:'include',
                    headers:{{'Content-Type':'application/json'}},
                    body:{json.dumps(create_body)}
                }}).then(r=>r.json()).then(d=>JSON.stringify({{id:d.id}}))
            ''')
            draft_id = json.loads(val).get('id')
            if not draft_id:
                print(f'  Create failed: {val}'); continue
            print(f'  Draft: {draft_id}')

            # Navigate to editor
            await run_js(ws, f"window.location.href='https://jinilee.substack.com/publish/post/{draft_id}'; 'ok'")
            await asyncio.sleep(6)

            # Wait for editor
            val = await run_js(ws, '''
                new Promise(r=>{let n=0;const c=()=>{n++;if(document.querySelector('.ProseMirror'))r('ready');else if(n<30)setTimeout(c,500);else r('timeout')};c()})
            ''')
            if val != 'ready':
                print(f'  Editor not ready: {val}'); continue

            # Method: Access ProseMirror view and use its API to set content
            html_js = json.dumps(html)
            val = await run_js(ws, f'''
                new Promise(resolve => {{
                    const pmEl = document.querySelector('.ProseMirror');
                    pmEl.focus();

                    // Try to find ProseMirror view instance
                    // ProseMirror stores view on the DOM element
                    let view = null;

                    // Method 1: Check pmViewDesc
                    if (pmEl.pmViewDesc && pmEl.pmViewDesc.view) {{
                        view = pmEl.pmViewDesc.view;
                    }}

                    // Method 2: Check __view
                    if (!view && pmEl.__view) {{
                        view = pmEl.__view;
                    }}

                    // Method 3: Walk up to find contentDOM
                    if (!view) {{
                        const nodes = document.querySelectorAll('[class*=ProseMirror]');
                        for (const n of nodes) {{
                            if (n.pmViewDesc) {{ view = n.pmViewDesc.view; break; }}
                        }}
                    }}

                    if (view) {{
                        // We have the ProseMirror view! Use its parser to set HTML content
                        try {{
                            const {{DOMParser}} = window.ProseMirror || {{}};
                            const schema = view.state.schema;
                            
                            // Create a temporary div with the HTML
                            const div = document.createElement('div');
                            div.innerHTML = {html_js};
                            
                            // Parse HTML into ProseMirror doc
                            const parser = view.someProp('clipboardParser') || 
                                          view.someProp('domParser') ||
                                          (schema.marks && schema.nodes ? 
                                              window.require && window.require('prosemirror-model').DOMParser.fromSchema(schema) : null);
                            
                            if (parser) {{
                                const doc = parser.parse(div);
                                const tr = view.state.tr.replaceWith(0, view.state.doc.content.size, doc.content);
                                view.dispatch(tr);
                                resolve('dispatched_via_parser: ' + view.state.doc.content.size);
                            }} else {{
                                // Fallback: use setContent-like approach
                                const slice = view.state.schema.nodeFromJSON ? null : null;
                                
                                // Try execCommand approach with view focused
                                const selection = window.getSelection();
                                selection.selectAllChildren(pmEl);
                                const result = document.execCommand('insertHTML', false, {html_js});
                                resolve('execCommand: ' + result + ', len=' + pmEl.innerHTML.length);
                            }}
                        }} catch(e) {{
                            resolve('view_error: ' + e.message);
                        }}
                    }} else {{
                        // Fallback: execCommand
                        const selection = window.getSelection();
                        selection.selectAllChildren(pmEl);
                        const result = document.execCommand('insertHTML', false, {html_js});
                        resolve('execCommand_fallback: ' + result + ', len=' + pmEl.innerHTML.length);
                    }}
                }})
            ''')
            print(f'  Insert: {val}')

            # Wait for auto-save
            print('  Waiting for auto-save (10s)...')
            await asyncio.sleep(10)

            # Check body
            await run_js(ws, "window.location.href='https://jinilee.substack.com/publish/posts'; 'ok'")
            await asyncio.sleep(3)
            
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}', {{credentials:'include'}})
                .then(r=>r.json())
                .then(d=>JSON.stringify({{body_len:(d.body_html||'').length, starts:(d.body_html||'').substring(0,80), escaped:(d.body_html||'').includes('&lt;')}}))
            ''')
            print(f'  Body check: {val}')

            body_data = json.loads(val) if val else {}
            if body_data.get('body_len', 0) > 100 and not body_data.get('escaped'):
                # Publish
                val = await run_js(ws, f'''
                    fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}/publish', {{
                        method:'PUT', credentials:'include',
                        headers:{{'Content-Type':'application/json'}},
                        body:JSON.stringify({{send:false, share_automatically:false}})
                    }}).then(r=>r.json()).then(d=>JSON.stringify({{slug:d.slug}}))
                ''')
                print(f'  Published: {val}')
                slug = json.loads(val).get('slug') if val else None
                print(f'  URL: https://jinilee.substack.com/p/{slug}')
            else:
                print('  Body still empty/escaped - need manual intervention')
                print(f'  Draft ID {draft_id} is saved, can be edited manually')

asyncio.run(main())

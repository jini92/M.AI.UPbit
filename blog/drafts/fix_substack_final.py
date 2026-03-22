import asyncio, json, websockets, sys

WS_URL = 'ws://127.0.0.1:18800/devtools/page/B93B600459D1C4DECD19E90B8BED171C'

async def step(ws, js_code, step_name, timeout=10):
    """Execute JS and return result."""
    msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}})
    await asyncio.wait_for(ws.send(msg), timeout=3)
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    resp = json.loads(raw)
    val = resp.get('result', {}).get('result', {}).get('value', 'err')
    print(f"[{step_name}] {val}", flush=True)
    return val

async def main():
    async with websockets.connect(WS_URL, max_size=10*1024*1024, open_timeout=5) as ws:
        # Step 1: Navigate to draft 191524718
        nav = json.dumps({'id': 0, 'method': 'Page.navigate', 'params': {'url': 'https://jinilee.substack.com/publish/post/191524718'}})
        await ws.send(nav)
        await ws.recv()
        
        print("[nav] Navigating to draft 191524718...", flush=True)
        await asyncio.sleep(6)
        
        # Step 2: Check editor
        val = await step(ws, """
            const e = document.querySelector('.ProseMirror');
            JSON.stringify({editor: !!e, len: e ? e.innerHTML.length : 0, title: document.title, url: location.href})
        """, "check")
        
        data = json.loads(val)
        if not data.get('editor'):
            print("ERROR: No editor found after navigation", flush=True)
            return
        
        # Step 3: Read HTML and paste it
        with open(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_AI-Quant-Letter-3_EN.body.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        html_escaped = json.dumps(html)
        
        paste_js = f"""
        (async () => {{
            const editor = document.querySelector('.ProseMirror');
            editor.focus();
            
            // Select all
            const sel = window.getSelection();
            sel.selectAllChildren(editor);
            
            // Paste HTML
            const html = {html_escaped};
            const dt = new DataTransfer();
            dt.setData('text/html', html);
            const ev = new ClipboardEvent('paste', {{bubbles: true, cancelable: true, clipboardData: dt}});
            editor.dispatchEvent(ev);
            
            await new Promise(r => setTimeout(r, 2000));
            
            return JSON.stringify({{
                len: editor.innerHTML.length,
                preview: editor.innerHTML.substring(0, 200)
            }});
        }})()
        """
        await step(ws, paste_js, "paste", timeout=15)
        
        # Step 4: Wait for auto-save
        print("[save] Waiting for auto-save...", flush=True)
        await asyncio.sleep(4)
        
        # Step 5: Check draft_body was saved
        val = await step(ws, """
        (async () => {
            const m = location.href.match(/post\\/(\\d+)/);
            if (!m) return JSON.stringify({error: 'no post id in url'});
            const id = m[1];
            const resp = await fetch('/api/v1/drafts/' + id, {credentials: 'include'});
            const data = await resp.json();
            return JSON.stringify({
                id: data.id,
                draft_body_len: data.draft_body ? data.draft_body.length : 0,
                word_count: data.word_count
            });
        })()
        """, "draft_check")
        
        draft_data = json.loads(val)
        if draft_data.get('draft_body_len', 0) < 100:
            print("WARNING: Draft body may not have saved properly", flush=True)
        
        # Step 6: Update should_send_email = false, then publish via API
        val = await step(ws, """
        (async () => {
            const m = location.href.match(/post\\/(\\d+)/);
            const id = m[1];
            
            // Set no email
            await fetch('/api/v1/drafts/' + id, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({should_send_email: false})
            });
            
            // Try publish
            const resp = await fetch('/api/v1/drafts/' + id + '/publish', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({send: false})
            });
            const text = await resp.text();
            return JSON.stringify({status: resp.status, body: text.substring(0, 300)});
        })()
        """, "publish_api", timeout=15)
        
        pub_data = json.loads(val)
        if pub_data.get('status') == 200:
            print("SUCCESS: Post published via API!", flush=True)
        else:
            print(f"API publish returned {pub_data.get('status')}, trying UI button...", flush=True)
            # Step 7: Fall back to clicking UI buttons
            await step(ws, """
            (async () => {
                // Click Continue
                const btns = Array.from(document.querySelectorAll('button'));
                const cont = btns.find(b => b.textContent.trim() === 'Continue');
                if (cont) cont.click();
                await new Promise(r => setTimeout(r, 2000));
                
                // Find publish button
                const btns2 = Array.from(document.querySelectorAll('button'));
                const texts = btns2.map(b => b.textContent.trim()).filter(t => t.length > 0 && t.length < 60);
                return JSON.stringify({buttons: texts});
            })()
            """, "ui_buttons")

asyncio.run(main())

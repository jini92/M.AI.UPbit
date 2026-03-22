import asyncio, json, websockets, time, sys

async def fix_substack():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        # Navigate to draft editor
        nav_msg = json.dumps({'id': 1, 'method': 'Page.navigate', 'params': {'url': 'https://jinilee.substack.com/publish/post/191524718'}})
        await ws.send(nav_msg)
        resp = json.loads(await ws.recv())
        print(f"Navigate response: {resp.get('result', {}).get('frameId', 'ok')}")
        
        # Wait for page to load
        await asyncio.sleep(6)
        
        # Check if editor loaded
        check_js = 'document.querySelector(".ProseMirror") ? "editor found" : "no editor"'
        msg = json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': check_js, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        editor_status = resp.get('result', {}).get('result', {}).get('value', 'unknown')
        print(f"Editor status: {editor_status}")
        
        if editor_status == "no editor":
            await asyncio.sleep(4)
            await ws.send(msg)
            resp = json.loads(await ws.recv())
            editor_status = resp.get('result', {}).get('result', {}).get('value', 'unknown')
            print(f"Editor status (retry): {editor_status}")
        
        # Read the HTML body
        with open(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_AI-Quant-Letter-3_EN.body.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        html_escaped = json.dumps(html)
        
        # Use ProseMirror's clipboard paste to inject HTML content
        # This simulates what happens when you paste HTML into the editor
        paste_js = f"""
        (async () => {{
            const editor = document.querySelector('.ProseMirror');
            if (!editor) return 'no editor found';
            
            // Focus the editor
            editor.focus();
            
            // Select all existing content
            const selection = window.getSelection();
            selection.selectAllChildren(editor);
            
            // Create a paste event with our HTML
            const html = {html_escaped};
            const clipboardData = new DataTransfer();
            clipboardData.setData('text/html', html);
            
            const pasteEvent = new ClipboardEvent('paste', {{
                bubbles: true,
                cancelable: true,
                clipboardData: clipboardData
            }});
            
            editor.dispatchEvent(pasteEvent);
            
            // Wait a bit for ProseMirror to process
            await new Promise(r => setTimeout(r, 2000));
            
            // Check the result
            const newContent = editor.innerHTML;
            return JSON.stringify({{
                success: true,
                content_length: newContent.length,
                preview: newContent.substring(0, 300)
            }});
        }})()
        """
        
        msg = json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': paste_js, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        result = resp.get('result', {}).get('result', {}).get('value', 'no value')
        print(f"Paste result: {result}")

asyncio.run(fix_substack())

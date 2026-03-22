import asyncio, json, websockets

async def save_and_publish():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        # Wait for Substack auto-save to kick in (it auto-saves after edits)
        save_js = """
        (async () => {
            // Trigger a small edit to force auto-save
            const editor = document.querySelector('.ProseMirror');
            if (editor) {
                // Dispatch an input event to trigger auto-save
                editor.dispatchEvent(new Event('input', {bubbles: true}));
            }
            
            // Wait for auto-save
            await new Promise(r => setTimeout(r, 3000));
            
            // Now check if draft_body was updated by fetching the draft
            const resp = await fetch('/api/v1/drafts/191524718', {credentials: 'include'});
            const data = await resp.json();
            return JSON.stringify({
                draft_body_length: data.draft_body ? data.draft_body.length : 0,
                word_count: data.word_count,
                draft_body_preview: data.draft_body ? data.draft_body.substring(0, 200) : 'none'
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': save_js, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        result = resp.get('result', {}).get('result', {}).get('value', 'no value')
        print(f"Save check: {result}")
        
        # If draft_body looks good, publish
        data = json.loads(result)
        if data.get('draft_body_length', 0) > 100:
            publish_js = """
            (async () => {
                try {
                    const resp = await fetch('/api/v1/drafts/191524718/publish', {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        credentials: 'include',
                        body: JSON.stringify({send: false})
                    });
                    const text = await resp.text();
                    return JSON.stringify({status: resp.status, preview: text.substring(0, 300)});
                } catch(e) {
                    return JSON.stringify({error: e.message});
                }
            })()
            """
            msg = json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': publish_js, 'awaitPromise': True, 'returnByValue': True}})
            await ws.send(msg)
            resp = json.loads(await ws.recv())
            result = resp.get('result', {}).get('result', {}).get('value', 'no value')
            print(f"Publish: {result}")
        else:
            print("Draft body not saved yet, waiting more...")
            # Wait more and try manual save via Ctrl+S
            ctrlS_js = """
            (async () => {
                document.dispatchEvent(new KeyboardEvent('keydown', {key: 's', ctrlKey: true, bubbles: true}));
                await new Promise(r => setTimeout(r, 3000));
                const resp = await fetch('/api/v1/drafts/191524718', {credentials: 'include'});
                const data = await resp.json();
                return JSON.stringify({draft_body_length: data.draft_body ? data.draft_body.length : 0});
            })()
            """
            msg = json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': ctrlS_js, 'awaitPromise': True, 'returnByValue': True}})
            await ws.send(msg)
            resp = json.loads(await ws.recv())
            result = resp.get('result', {}).get('result', {}).get('value', 'no value')
            print(f"After Ctrl+S: {result}")

asyncio.run(save_and_publish())

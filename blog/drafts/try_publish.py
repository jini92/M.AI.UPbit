import asyncio, json, websockets

async def try_publish():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        draft_id = 191524718
        
        # Use the Substack UI publish flow - click the "Publish" button
        # First let's find the publish button
        js_code = """
        (async () => {
            // Look for Continue/Publish button
            const buttons = Array.from(document.querySelectorAll('button'));
            const btnTexts = buttons.map(b => b.textContent.trim()).filter(t => t.length > 0 && t.length < 50);
            
            // Also check for the publish menu
            const publishBtn = buttons.find(b => {
                const text = b.textContent.trim().toLowerCase();
                return text.includes('publish') || text.includes('continue');
            });
            
            return JSON.stringify({
                buttons: btnTexts.slice(0, 20),
                publishBtn: publishBtn ? publishBtn.textContent.trim() : 'not found'
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        result = resp.get('result', {}).get('result', {}).get('value', 'no value')
        print(f"Buttons: {result}")

asyncio.run(try_publish())

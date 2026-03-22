import asyncio, json, websockets

async def verify():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/B1E64D25FBFB960DAB642F3F429B4CF0'
    async with websockets.connect(ws_url, max_size=10*1024*1024, open_timeout=5) as ws:
        # Navigate to the public page
        nav = json.dumps({'id': 0, 'method': 'Page.navigate', 'params': {'url': 'https://jinilee.substack.com/p/ai-quant-letter-3-all-negative-momentum'}})
        await ws.send(nav)
        await ws.recv()
        await asyncio.sleep(5)
        
        # Check the rendered content
        js = """
        (async () => {
            // Find the article body
            const body = document.querySelector('.body.markup') || document.querySelector('article') || document.querySelector('.post-content');
            if (!body) {
                return JSON.stringify({error: 'no body found', selectors: document.querySelector('.available-post') ? 'available-post found' : 'none'});
            }
            const text = body.innerText;
            return JSON.stringify({
                bodyLen: text.length,
                preview: text.substring(0, 500),
                hasTable: body.querySelector('table') !== null,
                h2Count: body.querySelectorAll('h2').length
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        raw = await ws.recv()
        resp = json.loads(raw)
        val = resp.get('result', {}).get('result', {}).get('value', 'err')
        print(val)

asyncio.run(verify())

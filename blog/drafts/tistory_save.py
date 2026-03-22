import asyncio, json, websockets

MANAGE_TAB = 'ws://127.0.0.1:18800/devtools/page/0396F91FDA59AFB9C9E3338FD75DB578'

async def main():
    async with websockets.connect(MANAGE_TAB, max_size=10*1024*1024, open_timeout=5) as ws:
        # Click "공개 발행" (Public Publish) button
        js = """
        (async () => {
            const btn = document.querySelector('#publish-btn');
            if (!btn) return JSON.stringify({error: 'no publish-btn'});
            const text = btn.textContent.trim();
            btn.click();
            await new Promise(r => setTimeout(r, 5000));
            return JSON.stringify({clicked: text, newUrl: location.href, newTitle: document.title});
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
        await asyncio.wait_for(ws.send(msg), timeout=3)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            resp = json.loads(raw)
            val = resp.get('result', {}).get('result', {}).get('value', 'err')
            print(f"Result: {val}", flush=True)
        except asyncio.TimeoutError:
            print("Timeout (likely page navigated = success)", flush=True)

asyncio.run(main())

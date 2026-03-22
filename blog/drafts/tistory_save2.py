import asyncio, json, websockets

MANAGE_TAB = 'ws://127.0.0.1:18800/devtools/page/0396F91FDA59AFB9C9E3338FD75DB578'

async def main():
    async with websockets.connect(MANAGE_TAB, max_size=10*1024*1024, open_timeout=5) as ws:
        # Click "완료" to open publish layer
        js1 = """
        (async () => {
            const btn = document.querySelector('#publish-layer-btn');
            if (btn) btn.click();
            await new Promise(r => setTimeout(r, 1500));
            
            // Now check for publish-btn
            const pubBtn = document.querySelector('#publish-btn');
            const visible = pubBtn && pubBtn.offsetParent !== null;
            return JSON.stringify({
                publishLayerClicked: !!btn,
                publishBtnFound: !!pubBtn,
                publishBtnVisible: visible,
                publishBtnText: pubBtn ? pubBtn.textContent.trim() : 'none'
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js1, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        raw = await ws.recv()
        resp = json.loads(raw)
        val = resp.get('result', {}).get('result', {}).get('value')
        print(f"Step 1: {val}", flush=True)
        
        # Now click publish-btn
        js2 = """
        (async () => {
            const btn = document.querySelector('#publish-btn');
            if (!btn) return JSON.stringify({error: 'still no publish-btn'});
            btn.click();
            await new Promise(r => setTimeout(r, 5000));
            return JSON.stringify({clicked: btn.textContent.trim(), url: location.href});
        })()
        """
        msg = json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': js2, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            resp = json.loads(raw)
            val = resp.get('result', {}).get('result', {}).get('value')
            print(f"Step 2: {val}", flush=True)
        except asyncio.TimeoutError:
            print("Step 2: Timeout (page navigated = success)", flush=True)

asyncio.run(main())

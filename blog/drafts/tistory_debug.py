import asyncio, json, websockets

MANAGE_TAB = 'ws://127.0.0.1:18800/devtools/page/0396F91FDA59AFB9C9E3338FD75DB578'

async def main():
    async with websockets.connect(MANAGE_TAB, max_size=10*1024*1024, open_timeout=5) as ws:
        js = """
        JSON.stringify({
            url: location.href,
            title: document.title,
            allBtnIds: Array.from(document.querySelectorAll('button')).map(b => ({id: b.id, text: b.textContent.trim().substring(0, 40), display: getComputedStyle(b).display})).filter(x => x.text.length > 0)
        })
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}})
        await ws.send(msg)
        raw = await ws.recv()
        resp = json.loads(raw)
        val = resp.get('result', {}).get('result', {}).get('value')
        print(val)

asyncio.run(main())

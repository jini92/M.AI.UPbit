import asyncio, json, websockets

async def check():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        js = """
        (async () => {
            const editor = document.querySelector('.ProseMirror');
            if (!editor) return JSON.stringify({editor: false, url: window.location.href, title: document.title});
            const html = editor.innerHTML;
            const buttons = Array.from(document.querySelectorAll('button')).map(b => b.textContent.trim()).filter(t => t.length > 0 && t.length < 60);
            return JSON.stringify({
                editor: true,
                url: window.location.href,
                contentLength: html.length,
                preview: html.substring(0, 300),
                buttons: buttons
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        val = resp.get('result', {}).get('result', {}).get('value', 'err')
        print(val)

asyncio.run(check())

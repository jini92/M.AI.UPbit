import asyncio, json, websockets, sys

WS_URLS = [
    ('191524718', 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'),
    ('191518715', 'ws://127.0.0.1:18800/devtools/page/B93B600459D1C4DECD19E90B8BED171C'),
]

async def check_tab(name, ws_url):
    try:
        async with websockets.connect(ws_url, max_size=10*1024*1024, open_timeout=5, close_timeout=3) as ws:
            js = """document.title + ' | ' + (document.querySelector('.ProseMirror') ? document.querySelector('.ProseMirror').innerHTML.length : 'no-editor')"""
            msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}})
            await asyncio.wait_for(ws.send(msg), timeout=3)
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            resp = json.loads(raw)
            val = resp.get('result', {}).get('result', {}).get('value', 'err')
            print(f"[{name}] {val}", flush=True)
    except Exception as e:
        print(f"[{name}] ERROR: {e}", flush=True)

async def main():
    for name, url in WS_URLS:
        await check_tab(name, url)

asyncio.run(main())

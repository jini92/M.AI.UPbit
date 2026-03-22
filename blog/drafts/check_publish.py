import asyncio, json, websockets

async def main():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/B93B600459D1C4DECD19E90B8BED171C'
    try:
        async with websockets.connect(ws_url, max_size=10*1024*1024, open_timeout=5) as ws:
            js = """JSON.stringify({url: location.href, title: document.title, bodyLen: document.body.innerHTML.length})"""
            msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}})
            await asyncio.wait_for(ws.send(msg), timeout=3)
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            resp = json.loads(raw)
            val = resp.get('result', {}).get('result', {}).get('value', 'err')
            print(f"Tab B: {val}")
    except Exception as e:
        print(f"Tab B error: {e}")
    
    # Try tab A
    ws_url2 = 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'
    try:
        async with websockets.connect(ws_url2, max_size=10*1024*1024, open_timeout=5) as ws:
            js = """JSON.stringify({url: location.href, title: document.title})"""
            msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}})
            await asyncio.wait_for(ws.send(msg), timeout=3)
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            resp = json.loads(raw)
            val = resp.get('result', {}).get('result', {}).get('value', 'err')
            print(f"Tab A: {val}")
    except Exception as e:
        print(f"Tab A error: {e}")

    # Check the draft via the home tab
    ws_url3 = 'ws://127.0.0.1:18800/devtools/page/A64B3471C685898155908C76CB8951D0'
    try:
        async with websockets.connect(ws_url3, max_size=10*1024*1024, open_timeout=5) as ws:
            js = """
            (async () => {
                const resp = await fetch('/api/v1/drafts/191524718', {credentials: 'include'});
                const data = await resp.json();
                return JSON.stringify({
                    is_published: data.is_published,
                    email_sent_at: data.email_sent_at,
                    post_date: data.post_date,
                    draft_body_len: data.draft_body ? data.draft_body.length : 0,
                    body_html_len: data.body_html ? data.body_html.length : 0,
                    title: data.title || data.draft_title
                });
            })()
            """
            msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
            await asyncio.wait_for(ws.send(msg), timeout=3)
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            resp = json.loads(raw)
            val = resp.get('result', {}).get('result', {}).get('value', 'err')
            print(f"Draft status: {val}")
    except Exception as e:
        print(f"Home tab error: {e}")

asyncio.run(main())

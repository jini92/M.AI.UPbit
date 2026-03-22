import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    sp = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    async with websockets.connect(sp['webSocketDebuggerUrl'], max_size=10**7) as ws:
        expr = """
        Promise.all([
          fetch('https://jinilee.substack.com/api/v1/drafts/191555996',{credentials:'include'}).then(r=>r.json()),
          fetch('https://jinilee.substack.com/api/v1/drafts/191556012',{credentials:'include'}).then(r=>r.json())
        ]).then(arr => JSON.stringify(arr.map(d => ({id:d.id, title:d.draft_title, published:d.is_published, slug:d.slug, body_len:(d.body_html||'').length}))))
        """
        await ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':expr,'awaitPromise':True,'returnByValue':True}}))
        resp = json.loads(await ws.recv())
        print(resp.get('result',{}).get('result',{}).get('value',''))

asyncio.run(main())

import json, asyncio, websockets, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    sp = next((p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page'), None)
    async with websockets.connect(sp['webSocketDebuggerUrl'], max_size=10**7) as ws:
        await ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':"""
            fetch('https://jinilee.substack.com/api/v1/posts?limit=5',{credentials:'include'})
            .then(r=>r.json())
            .then(d=>JSON.stringify(d.map(x=>({id:x.id,slug:x.slug,title:x.title,body_len:(x.body_html||'').length,escaped:(x.body_html||'').includes('&lt;')}))))
        """,'awaitPromise':True,'returnByValue':True}}))
        resp = json.loads(await ws.recv())
        val = resp.get('result',{}).get('result',{}).get('value','')
        posts = json.loads(val)
        for p in posts:
            esc = "ESCAPED!" if p['escaped'] else "OK"
            print(f"  {p['id']} | body={p['body_len']} | {esc} | slug={p['slug']} | {p['title'][:70]}")

asyncio.run(main())

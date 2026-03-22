import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets

async def recv_matching(ws, want_id, timeout=30):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get('id') == want_id:
            return msg

CID = 0
async def eval_js(ws, expr, timeout=30):
    global CID; CID += 1
    await ws.send(json.dumps({'id':CID,'method':'Runtime.evaluate','params':{'expression':expr,'awaitPromise':True,'returnByValue':True}}))
    msg = await recv_matching(ws, CID, timeout)
    return msg.get('result',{}).get('result',{}).get('value')

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        # List all drafts
        val = await eval_js(ws, '''
            fetch('https://jinilee.substack.com/api/v1/drafts?limit=30',{credentials:'include'})
            .then(r=>r.json())
            .then(d=>JSON.stringify(d.filter(x=>!x.is_published).map(x=>({id:x.id,title:x.draft_title,body_len:(x.draft_body||'').length}))))
        ''')
        drafts = json.loads(val)
        print(f'Found {len(drafts)} unpublished drafts:')
        # Keep the editor tutorial, delete everything else
        keep_titles = {'How to use the Substack editor'}
        for d in drafts:
            print(f"  {d['id']} | body={d['body_len']} | {d['title'][:60]}")
            if d['title'] not in keep_titles:
                r = await eval_js(ws, f"fetch('https://jinilee.substack.com/api/v1/drafts/{d['id']}',{{method:'DELETE',credentials:'include'}}).then(r=>r.status)")
                print(f"    -> deleted: {r}")

asyncio.run(main())

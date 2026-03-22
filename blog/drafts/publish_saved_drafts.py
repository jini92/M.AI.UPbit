import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets

DRAFTS = [191555996, 191556012]

async def recv_matching(ws, want_id, timeout=30):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get('id') == want_id:
            return msg

async def send_eval(ws, expr, mid, timeout=30):
    await ws.send(json.dumps({'id':mid,'method':'Runtime.evaluate','params':{'expression':expr,'awaitPromise':True,'returnByValue':True}}))
    return await recv_matching(ws, mid, timeout)

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        mid = 1
        for draft_id in DRAFTS:
            print(f'=== Draft {draft_id} ===')
            expr = f"fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}/publish',{{method:'PUT',credentials:'include',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{send:false,share_automatically:false}})}}).then(async r => JSON.stringify({{status:r.status, text: await r.text()}}))"
            resp = await send_eval(ws, expr, mid); mid += 1
            print('publish_resp=', resp.get('result',{}).get('result',{}).get('value'))
            await asyncio.sleep(2)
            expr2 = f"fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}',{{credentials:'include'}}).then(r=>r.json()).then(d=>JSON.stringify({{id:d.id,published:d.is_published,slug:d.slug,draft_body_len:(d.draft_body||'').length}}))"
            resp2 = await send_eval(ws, expr2, mid); mid += 1
            print('status=', resp2.get('result',{}).get('result',{}).get('value'))

asyncio.run(main())

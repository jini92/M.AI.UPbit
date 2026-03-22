import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets
DRAFT_ID = 191555996

async def recv_matching(ws, want_id, timeout=30):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get('id') == want_id:
            return msg

async def eval_js(ws, expr, cid):
    await ws.send(json.dumps({'id':cid,'method':'Runtime.evaluate','params':{'expression':expr,'awaitPromise':True,'returnByValue':True}}))
    msg = await recv_matching(ws,cid,40)
    return msg.get('result',{}).get('result',{}).get('value')

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        val = await eval_js(ws, "(() => { const btn=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Publish on web only'); if(!btn) return 'not-found'; btn.click(); return 'clicked'; })()", 1)
        print('click=', val)
        await asyncio.sleep(8)
        val = await eval_js(ws, f"fetch('https://jinilee.substack.com/api/v1/drafts/{DRAFT_ID}',{{credentials:'include'}}).then(r=>r.json()).then(d=>JSON.stringify({{published:d.is_published,slug:d.slug,draft_body_len:(d.draft_body||'').length}}))", 2)
        print('status=', val)

asyncio.run(main())

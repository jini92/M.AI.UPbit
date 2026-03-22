import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets

DRAFT_ID = 191555996

async def recv_matching(ws, want_id, timeout=40):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get('id') == want_id:
            return msg

class CDP:
    def __init__(self): self.i=0
    async def eval(self, ws, expr, timeout=40):
        self.i += 1
        await ws.send(json.dumps({'id':self.i,'method':'Runtime.evaluate','params':{'expression':expr,'awaitPromise':True,'returnByValue':True}}))
        resp = await recv_matching(ws, self.i, timeout)
        return resp.get('result',{}).get('result',{}).get('value')
    async def nav(self, ws, url, timeout=20):
        self.i += 1
        await ws.send(json.dumps({'id':self.i,'method':'Page.navigate','params':{'url':url}}))
        await recv_matching(ws, self.i, timeout)

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    c = CDP()
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        await c.nav(ws, f'https://jinilee.substack.com/publish/post/{DRAFT_ID}')
        await asyncio.sleep(6)
        val = await c.eval(ws, "(() => { const btn=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Continue'); if(!btn) return 'no-continue'; btn.click(); return 'continue-clicked'; })()")
        print('continue=', val)
        await asyncio.sleep(3)
        val = await c.eval(ws, "(() => { const btn=[...document.querySelectorAll('button')].find(b=>{ const t=b.textContent.trim().toLowerCase(); return t.includes('publish now') || t.includes('send to everyone now') || t==='publish';}); if(!btn) return 'no-publish-btn:' + [...document.querySelectorAll('button')].map(b=>b.textContent.trim()).filter(Boolean).join(' | '); const txt=btn.textContent.trim(); btn.click(); return 'clicked:' + txt; })()")
        print('publish1=', val)
        await asyncio.sleep(4)
        val2 = await c.eval(ws, "(() => { const btn=[...document.querySelectorAll('button')].find(b=>{ const t=b.textContent.trim().toLowerCase(); return t.includes('publish without buttons') || t.includes('send to everyone now') || t.includes('publish now');}); if(!btn) return 'no-second-btn'; const txt=btn.textContent.trim(); btn.click(); return 'clicked2:' + txt; })()")
        print('publish2=', val2)
        await asyncio.sleep(8)
        val = await c.eval(ws, f"fetch('https://jinilee.substack.com/api/v1/drafts/{DRAFT_ID}',{{credentials:'include'}}).then(r=>r.json()).then(d=>JSON.stringify({{published:d.is_published,slug:d.slug,draft_body_len:(d.draft_body||'').length}}))")
        print('status=', val)

asyncio.run(main())

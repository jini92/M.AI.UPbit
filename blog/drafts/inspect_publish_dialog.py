import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets

async def recv_matching(ws, want_id, timeout=30):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get('id') == want_id:
            return msg

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        expr = """(() => JSON.stringify({
            url: location.href,
            buttons: [...document.querySelectorAll('button')].map(b => ({text: b.textContent.trim(), disabled: !!b.disabled})).filter(x => x.text),
            texts: [...document.querySelectorAll('body *')].map(n => n.textContent.trim()).filter(Boolean).filter(t => t.includes('Publish') || t.includes('Send via') || t.includes('without buttons') || t.includes('Delivery')).slice(0,40)
        }))()"""
        await ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':expr,'returnByValue':True}}))
        raw = await recv_matching(ws,1,30)
        val = raw.get('result',{}).get('result',{}).get('value','{}')
        print(json.dumps(json.loads(val), ensure_ascii=False, indent=2))

asyncio.run(main())

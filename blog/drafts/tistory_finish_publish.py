import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets

CID = 0
async def recv_matching(ws, want_id, timeout=30):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get('id') == want_id:
            return msg

async def eval_js(ws, expr, timeout=30):
    global CID; CID += 1
    await ws.send(json.dumps({'id':CID,'method':'Runtime.evaluate','params':{'expression':expr,'awaitPromise':True,'returnByValue':True}}))
    msg = await recv_matching(ws, CID, timeout)
    return msg.get('result',{}).get('result',{}).get('value')

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'tistory' in p.get('url','') and p.get('type')=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        # Inspect the publish dialog
        val = await eval_js(ws, '''
            (() => {
                // Find all visible elements with publish-related text
                const all = [...document.querySelectorAll('*')];
                const relevant = all.filter(el => {
                    const t = el.textContent.trim();
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                           (t.includes('공개') || t.includes('발행') || t.includes('비공개') || 
                            t.includes('보호') || t.includes('완료'));
                }).map(el => ({
                    tag: el.tagName,
                    id: el.id,
                    cls: el.className.toString().slice(0,40),
                    text: el.textContent.trim().slice(0,60),
                    type: el.type || ''
                }));
                return JSON.stringify(relevant.slice(0,30));
            })()
        ''')
        items = json.loads(val)
        for item in items:
            print(f"  {item['tag']} id={item['id']} cls={item['cls'][:30]} type={item['type']} text={item['text'][:50]}")

asyncio.run(main())

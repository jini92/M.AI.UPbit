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
        # Click 완료 button
        val = await eval_js(ws, "document.querySelector('#publish-layer-btn').click(); 'clicked'")
        print(f'완료 clicked: {val}')
        await asyncio.sleep(3)
        
        # Now check for publish dialog
        val = await eval_js(ws, '''
            (() => {
                const all = [...document.querySelectorAll('*')];
                const visible = all.filter(el => {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                });
                const publish = visible.filter(el => {
                    const t = el.textContent.trim();
                    return t === '공개' || t === '비공개' || t === '보호' || t === '공개 발행' || t === '공개발행';
                }).map(el => ({tag:el.tagName, id:el.id, cls:el.className.toString().slice(0,30), text:el.textContent.trim().slice(0,30)}));
                return JSON.stringify(publish);
            })()
        ''')
        print(f'Dialog elements: {val}')
        
        # Try to find and click 공개 radio + final button
        val = await eval_js(ws, '''
            (() => {
                // Find publish layer
                const layer = document.querySelector('#publish-layer, .layer_publish, [class*=publish-layer]');
                if (layer) {
                    const els = [...layer.querySelectorAll('*')];
                    return 'layer-found:' + els.map(e=>e.tagName+'='+e.textContent.trim().slice(0,20)).slice(0,20).join('|');
                }
                // Try finding any modal/overlay
                const modals = [...document.querySelectorAll('[class*=layer], [class*=modal], [class*=popup], [class*=dialog]')];
                const visible = modals.filter(m => {
                    const s = window.getComputedStyle(m);
                    return s.display !== 'none' && s.visibility !== 'hidden';
                });
                return 'modals:' + visible.map(m => m.className.toString().slice(0,30) + '>' + m.textContent.trim().slice(0,40)).join(' || ');
            })()
        ''')
        print(f'Layers: {val}')

asyncio.run(main())

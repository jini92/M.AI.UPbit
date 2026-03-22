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
        val = await eval_js(ws, 'location.href')
        print(f'Current URL: {val}')
        
        # Check if there's a publish confirmation area, or if the post was already saved
        val = await eval_js(ws, '''
            (() => {
                // Check for #publish-layer visibility
                const layer = document.querySelector('.layer_post');
                if (layer) {
                    const style = window.getComputedStyle(layer);
                    return 'layer_post: display=' + style.display + ' content=' + layer.textContent.trim().slice(0,200);
                }
                // Check for any open overlay with 공개
                const overlays = [...document.querySelectorAll('.layer, .popup, .modal, [class*=overlay]')];
                for (const o of overlays) {
                    const s = window.getComputedStyle(o);
                    if (s.display !== 'none') {
                        return 'overlay: cls=' + o.className + ' text=' + o.textContent.trim().slice(0,200);
                    }
                }
                // Maybe post was saved — check manage/posts
                return 'no-dialog-found';
            })()
        ''')
        print(f'Dialog check: {val}')

        # Look at the entire page for any layer/popup
        val = await eval_js(ws, '''
            (() => {
                const html = document.body.innerHTML;
                const hasPublishLayer = html.includes('publish-layer') || html.includes('layer_post') || html.includes('공개 발행');
                const idx = html.indexOf('공개');
                const around = idx > 0 ? html.slice(Math.max(0,idx-100), idx+200) : 'not found';
                return JSON.stringify({hasPublishLayer, around: around.slice(0,300)});
            })()
        ''')
        print(f'HTML check: {val}')

asyncio.run(main())

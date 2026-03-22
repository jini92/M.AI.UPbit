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
    page = next(p for p in pages if 'tistory.com/manage/newpost' in p.get('url','') and p.get('type')=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        # Click 공개 radio
        val = await eval_js(ws, '''
            (() => {
                const radios = [...document.querySelectorAll('input[type=radio]')];
                const publicRadio = radios.find(r => {
                    const label = r.closest('label') || r.parentElement;
                    return label && label.textContent.includes('공개') && !label.textContent.includes('보호') && !label.textContent.includes('비');
                });
                if (publicRadio) { publicRadio.click(); publicRadio.checked = true; return 'public-selected'; }
                return 'radio-not-found:' + radios.map(r => r.value + '=' + r.checked).join(',');
            })()
        ''')
        print(f'Radio: {val}')
        await asyncio.sleep(1)
        
        # Now the button should change from "비공개 발행" to "공개 발행"
        # Click the publish button
        val = await eval_js(ws, '''
            (() => {
                const btns = [...document.querySelectorAll('button')];
                const pubBtn = btns.find(b => b.textContent.includes('발행') && !b.textContent.includes('취소'));
                if (pubBtn) { 
                    const txt = pubBtn.textContent.trim();
                    pubBtn.click(); 
                    return 'clicked:' + txt; 
                }
                return 'no-btn:' + btns.map(b=>b.textContent.trim()).filter(Boolean).join('|');
            })()
        ''')
        print(f'Publish: {val}')
        await asyncio.sleep(5)
        
        val = await eval_js(ws, 'location.href')
        print(f'URL: {val}')

asyncio.run(main())

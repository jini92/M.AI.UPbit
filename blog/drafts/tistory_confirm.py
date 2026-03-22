import asyncio, json, websockets

MANAGE_TAB = 'ws://127.0.0.1:18800/devtools/page/0396F91FDA59AFB9C9E3338FD75DB578'

async def step(ws, js, name, timeout=10):
    msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
    await asyncio.wait_for(ws.send(msg), timeout=3)
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    resp = json.loads(raw)
    val = resp.get('result', {}).get('result', {}).get('value', 'err')
    print(f"[{name}] {val}", flush=True)
    return val

async def main():
    async with websockets.connect(MANAGE_TAB, max_size=10*1024*1024, open_timeout=5) as ws:
        # Check for confirm dialog or publish overlay
        val = await step(ws, """
        (async () => {
            // Check for publish layer/overlay
            const overlay = document.querySelector('#publish-layer') || document.querySelector('.layer_publish');
            const visible = overlay ? (overlay.style.display !== 'none' && overlay.offsetHeight > 0) : false;
            
            // Get all visible buttons
            const buttons = Array.from(document.querySelectorAll('button')).filter(b => b.offsetHeight > 0);
            const btnTexts = buttons.map(b => ({text: b.textContent.trim(), id: b.id})).filter(x => x.text.length > 0 && x.text.length < 50);
            
            return JSON.stringify({
                hasOverlay: !!overlay,
                overlayVisible: visible,
                url: location.href,
                buttons: btnTexts
            });
        })()
        """, "check_overlay")
        
        data = json.loads(val)
        buttons = data.get('buttons', [])
        
        # Look for final publish/save button in the overlay
        val = await step(ws, """
        (async () => {
            // Common Tistory publish layer button IDs/texts
            const publishBtn = document.querySelector('#publish-btn') || 
                              document.querySelector('.btn_ok') ||
                              document.querySelector('.btn-publish');
            
            // Also search by text
            const buttons = Array.from(document.querySelectorAll('button')).filter(b => b.offsetHeight > 0);
            const saveBtn = buttons.find(b => {
                const text = b.textContent.trim();
                return text === '수정' || text === '발행' || text === '저장' || text === '공개 발행';
            });
            
            const target = publishBtn || saveBtn;
            if (target) {
                const text = target.textContent.trim();
                target.click();
                await new Promise(r => setTimeout(r, 3000));
                return JSON.stringify({clicked: text, newUrl: location.href});
            }
            
            // List what's available
            const allBtns = buttons.map(b => ({text: b.textContent.trim(), id: b.id, visible: b.offsetHeight > 0}))
                                   .filter(x => x.text.length > 0 && x.text.length < 50);
            return JSON.stringify({error: 'no publish button', buttons: allBtns});
        })()
        """, "final_publish", timeout=15)

asyncio.run(main())

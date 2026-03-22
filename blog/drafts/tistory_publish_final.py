import asyncio, json, websockets

MANAGE_TAB = 'ws://127.0.0.1:18800/devtools/page/0396F91FDA59AFB9C9E3338FD75DB578'

async def step(ws, js, name, timeout=10):
    msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
    await asyncio.wait_for(ws.send(msg), timeout=3)
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    resp = json.loads(raw)
    ex = resp.get('result', {}).get('exceptionDetails')
    if ex:
        print(f"[{name}] EXCEPTION: {ex.get('text', '')} {ex.get('exception', {}).get('description', '')}", flush=True)
        return 'exception'
    val = resp.get('result', {}).get('result', {}).get('value', 'err')
    print(f"[{name}] {val}", flush=True)
    return val

async def main():
    async with websockets.connect(MANAGE_TAB, max_size=10*1024*1024, open_timeout=5) as ws:
        # Verify TinyMCE content was set
        val = await step(ws, """
        (async () => {
            if (!window.tinymce || !tinymce.activeEditor) return JSON.stringify({error: 'no tinymce'});
            const content = tinymce.activeEditor.getContent();
            return JSON.stringify({len: content.length, preview: content.substring(0, 200)});
        })()
        """, "verify_content")
        
        # Click the 완료 button
        val = await step(ws, """
        (async () => {
            const btn = document.querySelector('#publish-layer-btn');
            if (!btn) return JSON.stringify({error: 'no publish-layer-btn'});
            btn.click();
            await new Promise(r => setTimeout(r, 2000));
            
            // Check if publish layer appeared
            const pubBtn = document.querySelector('#publish-btn');
            if (!pubBtn) {
                // Get all visible buttons
                const btns = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
                return JSON.stringify({error: 'no publish-btn after click', buttons: btns.map(b => ({text: b.textContent.trim().substring(0, 40), id: b.id}))});
            }
            return JSON.stringify({found: 'publish-btn', text: pubBtn.textContent.trim()});
        })()
        """, "open_layer")
        
        data = json.loads(val)
        if data.get('found') == 'publish-btn':
            # Click publish
            val = await step(ws, """
            (async () => {
                const btn = document.querySelector('#publish-btn');
                btn.click();
                await new Promise(r => setTimeout(r, 5000));
                return JSON.stringify({url: location.href, title: document.title});
            })()
            """, "click_publish", timeout=15)
        else:
            # The layer might auto-appear differently. Look for any confirm/submit type button
            print("Looking for alternative save approach...", flush=True)
            val = await step(ws, """
            (async () => {
                // Try submitting the form directly
                const form = document.querySelector('form');
                if (form) {
                    // Use fetch to submit
                    const formData = new FormData(form);
                    return JSON.stringify({hasForm: true, action: form.action});
                }
                
                // Try click on visible publish-like buttons
                const btns = Array.from(document.querySelectorAll('button')).filter(b => {
                    const t = b.textContent.trim();
                    return (t.includes('발행') || t.includes('수정') || t.includes('저장') || t === '완료') && b.offsetParent !== null;
                });
                
                for (const btn of btns) {
                    btn.click();
                    await new Promise(r => setTimeout(r, 2000));
                }
                
                return JSON.stringify({
                    clickedButtons: btns.map(b => b.textContent.trim()),
                    url: location.href
                });
            })()
            """, "alt_save")

asyncio.run(main())

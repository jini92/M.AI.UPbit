import asyncio, json, websockets

MANAGE_TAB = 'ws://127.0.0.1:18800/devtools/page/0396F91FDA59AFB9C9E3338FD75DB578'

async def step(ws, js, name, timeout=10):
    msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
    await asyncio.wait_for(ws.send(msg), timeout=3)
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    resp = json.loads(raw)
    ex = resp.get('result', {}).get('exceptionDetails')
    if ex:
        desc = ex.get('exception', {}).get('description', ex.get('text', ''))
        print(f"[{name}] EXCEPTION: {desc}", flush=True)
        return 'exception'
    val = resp.get('result', {}).get('result', {}).get('value', 'err')
    print(f"[{name}] {val}", flush=True)
    return val

async def main():
    async with websockets.connect(MANAGE_TAB, max_size=10*1024*1024, open_timeout=5) as ws:
        # Navigate to edit post 28
        nav = json.dumps({'id': 0, 'method': 'Page.navigate', 'params': {'url': 'https://greenside.tistory.com/manage/newpost/28'}})
        await ws.send(nav)
        await ws.recv()
        print("[nav] Loading editor...", flush=True)
        await asyncio.sleep(8)
        
        # Read HTML
        with open(r'C:\TEST\M.AI.UPbit\blog\drafts\quant3_kr.html', 'r', encoding='utf-8') as f:
            kr_html = f.read()
        kr_escaped = json.dumps(kr_html)
        
        # Set content via BOTH TinyMCE and the underlying textarea
        val = await step(ws, f"""
        (async () => {{
            const html = {kr_escaped};
            const results = [];
            
            // 1. Set TinyMCE
            if (window.tinymce && tinymce.activeEditor) {{
                tinymce.activeEditor.setContent(html);
                // Force TinyMCE to sync to textarea
                tinymce.activeEditor.save();
                results.push('tinymce: ' + tinymce.activeEditor.getContent().length);
            }}
            
            // 2. Also set the underlying textarea directly
            const textareas = document.querySelectorAll('textarea');
            for (const ta of textareas) {{
                if (ta.id === 'content' || ta.name === 'content' || ta.className.includes('content')) {{
                    ta.value = html;
                    results.push('textarea_content: ' + ta.value.length);
                }}
            }}
            
            // 3. Also set CodeMirror if available
            const cm = document.querySelector('.CodeMirror');
            if (cm && cm.CodeMirror) {{
                cm.CodeMirror.setValue(html);
                results.push('codemirror: ' + cm.CodeMirror.getValue().length);
            }}
            
            // 4. Find ALL textareas and their current content lengths
            const taInfo = Array.from(textareas).map(ta => ({{
                id: ta.id,
                name: ta.name,
                len: ta.value.length,
                preview: ta.value.substring(0, 50)
            }}));
            
            return JSON.stringify({{results, textareas: taInfo}});
        }})()
        """, "set_all", timeout=15)
        
        # Wait a bit for auto-save
        await asyncio.sleep(2)
        
        # Click 완료 to open publish panel
        val = await step(ws, """
        (async () => {
            // First make sure TinyMCE is synced
            if (window.tinymce && tinymce.activeEditor) {
                tinymce.activeEditor.save();
            }
            
            const btn = document.querySelector('#publish-layer-btn');
            if (!btn) return JSON.stringify({error: 'no publish-layer-btn'});
            btn.click();
            await new Promise(r => setTimeout(r, 2000));
            return JSON.stringify({clicked: true});
        })()
        """, "click_done")
        
        # Now click 공개 발행
        val = await step(ws, """
        (async () => {
            const btn = document.querySelector('#publish-btn');
            if (!btn) {
                const btns = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
                return JSON.stringify({error: 'no publish-btn', visible: btns.map(b => ({text: b.textContent.trim().substring(0, 30), id: b.id})).filter(x => x.text.length > 0)});
            }
            btn.click();
            await new Promise(r => setTimeout(r, 5000));
            return JSON.stringify({clicked: true, url: location.href});
        })()
        """, "publish", timeout=15)
        
        # Verify
        await asyncio.sleep(2)
        val = await step(ws, "JSON.stringify({url: location.href, title: document.title})", "after_publish")

asyncio.run(main())

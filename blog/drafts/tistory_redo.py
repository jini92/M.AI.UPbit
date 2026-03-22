import asyncio, json, websockets

# Use the manage tab which is now on the posts list
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
        # Navigate to edit post 28
        nav = json.dumps({'id': 0, 'method': 'Page.navigate', 'params': {'url': 'https://greenside.tistory.com/manage/newpost/28'}})
        await ws.send(nav)
        await ws.recv()
        print("[nav] Going to edit post 28...", flush=True)
        await asyncio.sleep(7)
        
        # Check current state
        val = await step(ws, "JSON.stringify({url: location.href, title: document.title})", "page")
        
        # Check what mode the editor is in (basic vs HTML mode)
        val = await step(ws, """
        (async () => {
            // Check for mode buttons
            const modeBtn = document.querySelector('#editor-mode-layer-btn-open');
            const modeText = modeBtn ? modeBtn.textContent.trim() : 'none';
            
            // Check for TinyMCE editor (visual mode)
            const tinymce = window.tinymce;
            const hasEditor = tinymce && tinymce.activeEditor;
            
            // Check for CodeMirror (HTML mode)
            const cm = document.querySelector('.CodeMirror');
            const hasCM = cm && cm.CodeMirror;
            
            return JSON.stringify({
                currentMode: modeText,
                hasTinyMCE: !!hasEditor,
                hasCodeMirror: !!hasCM,
                tinyContent: hasEditor ? tinymce.activeEditor.getContent().length : 0
            });
        })()
        """, "mode_check")
        
        mode_data = json.loads(val)
        
        # Read the KR HTML
        with open(r'C:\TEST\M.AI.UPbit\blog\drafts\quant3_kr.html', 'r', encoding='utf-8') as f:
            kr_html = f.read()
        kr_escaped = json.dumps(kr_html)
        
        if mode_data.get('hasTinyMCE'):
            # Set content via TinyMCE
            val = await step(ws, f"""
            (async () => {{
                const html = {kr_escaped};
                tinymce.activeEditor.setContent(html);
                return JSON.stringify({{method: 'tinymce', len: tinymce.activeEditor.getContent().length}});
            }})()
            """, "set_tinymce")
        else:
            # Switch to HTML mode first, then set content
            val = await step(ws, """
            (async () => {
                // Click mode button to switch to HTML
                const modeBtn = document.querySelector('#editor-mode-layer-btn-open');
                if (modeBtn) modeBtn.click();
                await new Promise(r => setTimeout(r, 1000));
                
                // Find HTML mode option
                const options = document.querySelectorAll('[data-mode], .layer_editor_mode button, #editor-mode-layer button, .layer button');
                const optTexts = Array.from(options).map(o => ({text: o.textContent.trim(), tag: o.tagName}));
                
                // Click HTML mode
                for (const opt of options) {
                    if (opt.textContent.trim().includes('HTML') || opt.textContent.trim().includes('html')) {
                        opt.click();
                        await new Promise(r => setTimeout(r, 1000));
                        break;
                    }
                }
                
                return JSON.stringify({options: optTexts});
            })()
            """, "switch_html")
            
            # Try CodeMirror again
            val = await step(ws, f"""
            (async () => {{
                const html = {kr_escaped};
                const cm = document.querySelector('.CodeMirror');
                if (cm && cm.CodeMirror) {{
                    cm.CodeMirror.setValue(html);
                    return JSON.stringify({{method: 'codemirror_after_switch', len: html.length}});
                }}
                
                // Try textarea
                const ta = document.querySelector('textarea.html');
                if (ta) {{
                    ta.value = html;
                    ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                    return JSON.stringify({{method: 'textarea', len: html.length}});
                }}
                
                // Also try tinymce if it loaded
                if (window.tinymce && tinymce.activeEditor) {{
                    tinymce.activeEditor.setContent(html);
                    return JSON.stringify({{method: 'tinymce_fallback', len: html.length}});
                }}
                
                return JSON.stringify({{error: 'no editor found'}});
            }})()
            """, "set_html")
        
        # Wait for auto-save
        await asyncio.sleep(3)
        
        # Click 완료 to open publish layer
        val = await step(ws, """
        (async () => {
            const btn = document.querySelector('#publish-layer-btn');
            if (btn) {
                btn.click();
                await new Promise(r => setTimeout(r, 1500));
            }
            
            // Click 공개 발행
            const pubBtn = document.querySelector('#publish-btn');
            if (pubBtn) {
                pubBtn.click();
                await new Promise(r => setTimeout(r, 3000));
                return JSON.stringify({published: true, url: location.href});
            }
            
            return JSON.stringify({error: 'no publish btn'});
        })()
        """, "publish", timeout=15)

asyncio.run(main())

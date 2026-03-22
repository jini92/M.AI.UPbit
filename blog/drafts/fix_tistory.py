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
        # Navigate to edit post #28
        nav = json.dumps({'id': 0, 'method': 'Page.navigate', 'params': {'url': 'https://greenside.tistory.com/manage/newpost/28'}})
        await ws.send(nav)
        await ws.recv()
        
        print("[nav] Navigating to edit post #28...", flush=True)
        await asyncio.sleep(6)
        
        # Check the page
        val = await step(ws, "JSON.stringify({url: location.href, title: document.title})", "page_check")
        
        # Check if editor loaded - Tistory uses different editors
        val = await step(ws, """
        (async () => {
            // Check for HTML mode toggle
            const htmlBtn = document.querySelector('.btn_html') || document.querySelector('[data-mode=html]');
            const editor = document.querySelector('#content') || document.querySelector('.CodeMirror') || document.querySelector('#tinymce') || document.querySelector('.mce-content-body');
            const editorFrame = document.querySelector('iframe');
            
            return JSON.stringify({
                hasHtmlBtn: !!htmlBtn,
                hasEditor: !!editor,
                hasIframe: !!editorFrame,
                editorId: editor ? editor.id : 'none',
                bodyClasses: document.body.className.substring(0, 100)
            });
        })()
        """, "editor_check")
        
        # Read the KR HTML
        with open(r'C:\TEST\M.AI.UPbit\blog\drafts\quant3_kr.html', 'r', encoding='utf-8') as f:
            kr_html = f.read()
        
        kr_escaped = json.dumps(kr_html)
        
        # Try to find and use the editor
        val = await step(ws, f"""
        (async () => {{
            const html = {kr_escaped};
            
            // Try different editor approaches
            // 1. Direct textarea/content element
            const textarea = document.querySelector('#content');
            if (textarea) {{
                textarea.value = html;
                textarea.dispatchEvent(new Event('input', {{bubbles: true}}));
                return JSON.stringify({{method: 'textarea', len: html.length}});
            }}
            
            // 2. CodeMirror
            const cm = document.querySelector('.CodeMirror');
            if (cm && cm.CodeMirror) {{
                cm.CodeMirror.setValue(html);
                return JSON.stringify({{method: 'codemirror', len: html.length}});
            }}
            
            // 3. TinyMCE iframe
            const iframe = document.querySelector('iframe');
            if (iframe && iframe.contentDocument) {{
                const body = iframe.contentDocument.body;
                body.innerHTML = html;
                return JSON.stringify({{method: 'iframe', len: html.length}});
            }}
            
            // 4. Check what we actually have
            const allInputs = document.querySelectorAll('input, textarea, [contenteditable]');
            const inputInfo = Array.from(allInputs).slice(0, 10).map(el => ({{
                tag: el.tagName,
                id: el.id,
                name: el.name,
                type: el.type,
                contentEditable: el.contentEditable
            }}));
            
            return JSON.stringify({{method: 'none', inputs: inputInfo}});
        }})()
        """, "set_content", timeout=15)

asyncio.run(main())

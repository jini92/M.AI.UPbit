import asyncio, json, websockets

async def main():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/B1E64D25FBFB960DAB642F3F429B4CF0'
    async with websockets.connect(ws_url, max_size=10*1024*1024, open_timeout=5) as ws:
        # Step 1: Update draft to disable email sending
        js1 = """
        (async () => {
            const resp = await fetch('/api/v1/drafts/191524718', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({should_send_email: false})
            });
            return JSON.stringify({status: resp.status});
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js1, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        raw = await ws.recv()
        resp = json.loads(raw)
        print(f"Disable email: {resp.get('result', {}).get('result', {}).get('value')}", flush=True)
        
        # Step 2: Try different publish endpoints
        endpoints = [
            ('POST', '/api/v1/drafts/191524718/publish'),
            ('PUT',  '/api/v1/drafts/191524718/publish'),
            ('POST', '/api/v1/drafts/191524718/publish?send=false'),
            ('PUT',  '/api/v1/drafts/191524718/publish?send=false'),
        ]
        
        for method, url in endpoints:
            js = f"""
            (async () => {{
                try {{
                    const resp = await fetch('{url}', {{
                        method: '{method}',
                        headers: {{'Content-Type': 'application/json'}},
                        credentials: 'include',
                        body: JSON.stringify({{send: false}})
                    }});
                    const text = await resp.text();
                    return JSON.stringify({{method: '{method}', url: '{url}', status: resp.status, body: text.substring(0, 300)}});
                }} catch(e) {{
                    return JSON.stringify({{error: e.message}});
                }}
            }})()
            """
            msg = json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
            await ws.send(msg)
            raw = await ws.recv()
            resp = json.loads(raw)
            val = resp.get('result', {}).get('result', {}).get('value', 'err')
            print(f"Try: {val}", flush=True)
            data = json.loads(val)
            if data.get('status') == 200:
                print("Published!", flush=True)
                break
        else:
            # None worked - try navigating to the draft editor and using UI
            print("All API endpoints failed. Trying UI approach...", flush=True)
            
            # Navigate to editor
            nav = json.dumps({'id': 3, 'method': 'Page.navigate', 'params': {'url': 'https://jinilee.substack.com/publish/post/191524718'}})
            await ws.send(nav)
            await ws.recv()
            await asyncio.sleep(6)
            
            # Click Continue
            js_continue = """
            (async () => {
                const btns = Array.from(document.querySelectorAll('button'));
                const cont = btns.find(b => b.textContent.trim() === 'Continue');
                if (cont) {
                    cont.click();
                    await new Promise(r => setTimeout(r, 2000));
                }
                
                // Uncheck email delivery
                const checkboxes = document.querySelectorAll('input[type=checkbox]');
                for (const cb of checkboxes) {
                    const wrapper = cb.closest('label') || cb.parentElement;
                    if (wrapper && wrapper.textContent.includes('Send via email')) {
                        if (cb.checked) {
                            cb.click();
                            await new Promise(r => setTimeout(r, 500));
                        }
                    }
                }
                
                // Also try role=checkbox buttons
                const roleCbs = document.querySelectorAll('[role=checkbox]');
                for (const cb of roleCbs) {
                    const wrapper = cb.closest('label') || cb.parentElement;
                    if (wrapper && wrapper.textContent.includes('Send via email')) {
                        if (cb.getAttribute('aria-checked') === 'true') {
                            cb.click();
                            await new Promise(r => setTimeout(r, 500));
                        }
                    }
                }
                
                await new Promise(r => setTimeout(r, 1000));
                
                const allBtns = Array.from(document.querySelectorAll('button'));
                const texts = allBtns.map(b => b.textContent.trim()).filter(t => t.length > 0 && t.length < 60);
                
                // The button text should change after unchecking email
                return JSON.stringify({buttons: texts});
            })()
            """
            msg = json.dumps({'id': 4, 'method': 'Runtime.evaluate', 'params': {'expression': js_continue, 'awaitPromise': True, 'returnByValue': True}})
            await ws.send(msg)
            raw = await ws.recv()
            resp = json.loads(raw)
            val = resp.get('result', {}).get('result', {}).get('value', 'err')
            print(f"After toggle: {val}", flush=True)
            
            # Find and click the publish button
            data = json.loads(val)
            buttons = data.get('buttons', [])
            
            # After unchecking email, button should say "Publish" instead of "Send to everyone now"
            target = None
            for name in ['Publish', 'Publish now', 'Post without sending', 'Send to everyone now']:
                if name in buttons:
                    target = name
                    break
            
            if target:
                print(f"Clicking: {target}", flush=True)
                target_esc = json.dumps(target)
                js_click = f"""
                (async () => {{
                    const btns = Array.from(document.querySelectorAll('button'));
                    const btn = btns.find(b => b.textContent.trim() === {target_esc});
                    if (btn) {{
                        btn.click();
                        return 'clicked';
                    }}
                    return 'not found';
                }})()
                """
                msg = json.dumps({'id': 5, 'method': 'Runtime.evaluate', 'params': {'expression': js_click, 'awaitPromise': True, 'returnByValue': True}})
                await ws.send(msg)
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=15)
                    resp = json.loads(raw)
                    print(f"Click result: {resp.get('result', {}).get('result', {}).get('value')}", flush=True)
                except asyncio.TimeoutError:
                    print("Click caused page navigation (likely published!)", flush=True)

asyncio.run(main())

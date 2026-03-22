import asyncio, json, websockets

WS_URL = 'ws://127.0.0.1:18800/devtools/page/B93B600459D1C4DECD19E90B8BED171C'

async def step(ws, js_code, name, timeout=10):
    msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}})
    await asyncio.wait_for(ws.send(msg), timeout=3)
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    resp = json.loads(raw)
    val = resp.get('result', {}).get('result', {}).get('value', 'err')
    print(f"[{name}] {val}", flush=True)
    return val

async def main():
    async with websockets.connect(WS_URL, max_size=10*1024*1024, open_timeout=5) as ws:
        # The publish dialog is already open (Continue was clicked)
        # We see "Send to everyone now" - need to find email toggle and uncheck it
        
        # Step 1: Find and click the email toggle to disable it
        val = await step(ws, """
        (async () => {
            // Look for toggle/switch elements near "Send via email"
            const allEls = document.querySelectorAll('*');
            const emailRelated = [];
            for (const el of allEls) {
                const text = el.textContent.trim();
                if ((text.includes('Send via email') || text.includes('send email')) && el.children.length < 3) {
                    emailRelated.push({
                        tag: el.tagName,
                        text: text.substring(0, 80),
                        role: el.getAttribute('role'),
                        className: (el.className || '').substring(0, 80),
                        parentTag: el.parentElement ? el.parentElement.tagName : '',
                        parentRole: el.parentElement ? el.parentElement.getAttribute('role') : ''
                    });
                }
            }
            
            // Also look for switches/toggles
            const switches = document.querySelectorAll('[role=switch], [role=checkbox], input[type=checkbox]');
            const switchInfo = Array.from(switches).map(s => ({
                tag: s.tagName,
                role: s.getAttribute('role'),
                checked: s.checked || s.getAttribute('aria-checked'),
                label: s.getAttribute('aria-label') || s.closest('label')?.textContent?.substring(0, 50) || ''
            }));
            
            return JSON.stringify({emailRelated, switches: switchInfo});
        })()
        """, "find_toggle")
        
        # Step 2: Toggle email off and click publish
        val = await step(ws, """
        (async () => {
            // Find the send toggle - it might be a role=switch or similar
            const switches = document.querySelectorAll('[role=switch]');
            for (const sw of switches) {
                const checked = sw.getAttribute('aria-checked');
                const label = sw.closest('label')?.textContent || sw.parentElement?.textContent || '';
                if (label.includes('email') || label.includes('Send')) {
                    if (checked === 'true') {
                        sw.click();
                        await new Promise(r => setTimeout(r, 500));
                    }
                }
            }
            
            // Also try checkboxes
            const checkboxes = document.querySelectorAll('input[type=checkbox]');
            for (const cb of checkboxes) {
                const wrapper = cb.closest('label') || cb.parentElement;
                const text = wrapper ? wrapper.textContent : '';
                if (text.includes('email') || text.includes('Send via')) {
                    if (cb.checked) {
                        cb.click();
                        await new Promise(r => setTimeout(r, 500));
                    }
                }
            }
            
            await new Promise(r => setTimeout(r, 1000));
            
            // Now check what buttons are available
            const btns = Array.from(document.querySelectorAll('button'));
            const texts = btns.map(b => b.textContent.trim()).filter(t => t.length > 0 && t.length < 60);
            return JSON.stringify({buttonsAfterToggle: texts});
        })()
        """, "toggle_email")
        
        data = json.loads(val)
        buttons = data.get('buttonsAfterToggle', [])
        
        # Step 3: Click whatever publish button is available
        # It might still say "Send to everyone now" or changed to "Publish"
        target_btn = None
        for b in ['Publish now', 'Publish', 'Send to everyone now', 'Post without sending']:
            if b in buttons:
                target_btn = b
                break
        
        if not target_btn:
            # Just click the most likely candidate
            target_btn = 'Send to everyone now'
        
        print(f"[click] Will click: '{target_btn}'", flush=True)
        
        escaped_target = json.dumps(target_btn)
        val = await step(ws, f"""
        (async () => {{
            const target = {escaped_target};
            const btns = Array.from(document.querySelectorAll('button'));
            const btn = btns.find(b => b.textContent.trim() === target);
            if (!btn) return JSON.stringify({{error: 'button not found', target}});
            btn.click();
            await new Promise(r => setTimeout(r, 5000));
            return JSON.stringify({{
                clicked: target,
                newUrl: location.href,
                newTitle: document.title
            }});
        }})()
        """, "publish_click", timeout=20)

asyncio.run(main())

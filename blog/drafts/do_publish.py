import asyncio, json, websockets

async def publish():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        # First update the draft to set should_send_email = false
        js_code = """
        (async () => {
            // Update draft settings
            const updateResp = await fetch('/api/v1/drafts/191524718', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({
                    should_send_email: false
                })
            });
            const updateStatus = updateResp.status;
            
            // Find and uncheck the email toggle in UI
            const spans = Array.from(document.querySelectorAll('span'));
            const emailSpan = spans.find(s => s.textContent.includes('Send via email'));
            if (emailSpan) {
                // Find the closest clickable parent (toggle/checkbox)
                const toggle = emailSpan.closest('label') || emailSpan.closest('[role=switch]') || emailSpan.parentElement;
                if (toggle) {
                    const checkbox = toggle.querySelector('input[type=checkbox]');
                    if (checkbox && checkbox.checked) {
                        checkbox.click();
                        await new Promise(r => setTimeout(r, 500));
                    } else if (!checkbox) {
                        // Might be a custom toggle
                        toggle.click();
                        await new Promise(r => setTimeout(r, 500));
                    }
                }
            }
            
            // Now find and click the primary publish/send button
            // After unchecking email, it should change to "Publish" instead of "Send"
            await new Promise(r => setTimeout(r, 1000));
            
            const buttons = Array.from(document.querySelectorAll('button'));
            const btnTexts = buttons.map(b => ({text: b.textContent.trim(), disabled: b.disabled})).filter(x => x.text.length > 0);
            
            // Look for the main action button
            const publishBtn = buttons.find(b => {
                const text = b.textContent.trim();
                return text === 'Publish' || text === 'Publish now' || text === 'Send to everyone now' || text.includes('Publish');
            });
            
            return JSON.stringify({
                updateStatus,
                buttons: btnTexts.slice(0, 15),
                publishBtnFound: publishBtn ? publishBtn.textContent.trim() : 'not found'
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        result = resp.get('result', {}).get('result', {}).get('value', 'no value')
        print(f"Step 1: {result}")
        
        # Now click the publish button
        js_code2 = """
        (async () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const publishBtn = buttons.find(b => {
                const text = b.textContent.trim();
                return text === 'Publish' || text.includes('Publish') || text === 'Send to everyone now';
            });
            
            if (!publishBtn) return JSON.stringify({error: 'no publish button'});
            
            const btnText = publishBtn.textContent.trim();
            publishBtn.click();
            
            // Wait for publish to complete
            await new Promise(r => setTimeout(r, 5000));
            
            // Check current URL - should redirect to published post
            return JSON.stringify({
                clicked: btnText,
                currentUrl: window.location.href,
                title: document.title
            });
        })()
        """
        msg = json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': js_code2, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        result = resp.get('result', {}).get('result', {}).get('value', 'no value')
        print(f"Step 2: {result}")

asyncio.run(publish())

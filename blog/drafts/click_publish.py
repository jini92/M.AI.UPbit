import asyncio, json, websockets

async def click_publish():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        # Step 1: Click "Continue" button
        js_code = """
        (async () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const continueBtn = buttons.find(b => b.textContent.trim() === 'Continue');
            if (!continueBtn) return 'Continue button not found';
            continueBtn.click();
            await new Promise(r => setTimeout(r, 2000));
            
            // After clicking Continue, a publish dialog should appear
            // Look for the "Publish now" or similar button
            const allButtons = Array.from(document.querySelectorAll('button'));
            const btnTexts = allButtons.map(b => b.textContent.trim()).filter(t => t.length > 0 && t.length < 50);
            
            return JSON.stringify({
                step: 'after_continue',
                buttons: btnTexts
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        result = resp.get('result', {}).get('result', {}).get('value', 'no value')
        print(f"Step 1: {result}")
        
        # Parse the result to find the publish button
        data = json.loads(result)
        buttons = data.get('buttons', [])
        
        # Look for "Publish" or "Publish now" button
        publish_names = ['Publish', 'Publish now', 'Publish Now']
        target = None
        for name in publish_names:
            if name in buttons:
                target = name
                break
        
        if not target:
            print(f"Available buttons: {buttons}")
            # Check for checkbox to uncheck "Send to email subscribers"
            
        # Step 2: Uncheck email sending and click Publish
        js_code2 = """
        (async () => {
            // Look for email checkbox and uncheck it if checked
            const checkboxes = Array.from(document.querySelectorAll('input[type=checkbox]'));
            for (const cb of checkboxes) {
                const label = cb.closest('label');
                if (label && label.textContent.includes('email')) {
                    if (cb.checked) {
                        cb.click();
                        await new Promise(r => setTimeout(r, 500));
                    }
                }
            }
            
            // Find and click Publish button
            const buttons = Array.from(document.querySelectorAll('button'));
            const publishBtn = buttons.find(b => {
                const text = b.textContent.trim().toLowerCase();
                return text === 'publish' || text === 'publish now';
            });
            
            if (!publishBtn) {
                const btnTexts = buttons.map(b => b.textContent.trim()).filter(t => t.length > 0);
                return JSON.stringify({error: 'No publish button', buttons: btnTexts});
            }
            
            publishBtn.click();
            await new Promise(r => setTimeout(r, 3000));
            
            return JSON.stringify({step: 'published', success: true});
        })()
        """
        msg = json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': js_code2, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        result = resp.get('result', {}).get('result', {}).get('value', 'no value')
        print(f"Step 2: {result}")

asyncio.run(click_publish())

import asyncio, json, websockets

async def publish():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/479DB78CF0604B8AEA6E8E33BD5DA5BA'
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        # The publish dialog shows "Send to everyone now"
        # We need to find the option to publish without emailing
        # Look for toggle, dropdown or link like "Publish without sending"
        js_code = """
        (async () => {
            // Get the full dialog content
            const dialog = document.querySelector('[role=dialog]') || document.querySelector('.modal') || document.querySelector('.publish-overlay');
            
            // Get all text in the publish area
            const allElements = document.querySelectorAll('*');
            const texts = [];
            for (const el of allElements) {
                if (el.children.length === 0 && el.textContent.trim().length > 0 && el.textContent.trim().length < 100) {
                    const tag = el.tagName;
                    const text = el.textContent.trim();
                    if (text.includes('email') || text.includes('send') || text.includes('publish') || text.includes('web') || text.includes('only') || text.includes('Publish')) {
                        texts.push({tag, text, type: el.type || ''});
                    }
                }
            }
            
            // Also look for select/dropdown elements
            const selects = document.querySelectorAll('select');
            const selectInfo = Array.from(selects).map(s => ({
                options: Array.from(s.options).map(o => o.textContent),
                value: s.value
            }));
            
            // Look for radio buttons
            const radios = document.querySelectorAll('input[type=radio]');
            const radioInfo = Array.from(radios).map(r => ({
                name: r.name,
                value: r.value,
                checked: r.checked,
                label: r.closest('label')?.textContent || r.nextElementSibling?.textContent || ''
            }));
            
            return JSON.stringify({
                texts: texts.slice(0, 30),
                selects: selectInfo,
                radios: radioInfo
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        resp = json.loads(await ws.recv())
        result = resp.get('result', {}).get('result', {}).get('value', 'no value')
        print(result)

asyncio.run(publish())

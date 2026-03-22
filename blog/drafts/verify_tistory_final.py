import asyncio, json, websockets

# Use the post #28 tab to check
POST_TAB = 'ws://127.0.0.1:18800/devtools/page/A866B7E4C499AFA2632B140D7CBEF878'

async def main():
    async with websockets.connect(POST_TAB, max_size=10*1024*1024, open_timeout=5) as ws:
        # Reload the public page
        nav = json.dumps({'id': 0, 'method': 'Page.navigate', 'params': {'url': 'https://greenside.tistory.com/28'}})
        await ws.send(nav)
        await ws.recv()
        await asyncio.sleep(5)
        
        js = """
        (async () => {
            // Find article content - Tistory uses various selectors
            const selectors = ['.tt_article_useless_p_margin', '.entry-content', '.article_view', '#content', 'article', '.contents_style'];
            let article = null;
            for (const sel of selectors) {
                article = document.querySelector(sel);
                if (article && article.innerText.length > 100) break;
            }
            
            if (!article) {
                // Get all text from the page
                return JSON.stringify({
                    error: 'no article element with content > 100',
                    bodyText: document.body.innerText.substring(0, 1000)
                });
            }
            
            return JSON.stringify({
                selector: article.className || article.id,
                textLen: article.innerText.length,
                htmlLen: article.innerHTML.length,
                preview: article.innerText.substring(0, 500),
                hasH1: !!article.querySelector('h1'),
                hasH2: article.querySelectorAll('h2').length,
                hasTable: !!article.querySelector('table')
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        raw = await ws.recv()
        resp = json.loads(raw)
        val = resp.get('result', {}).get('result', {}).get('value', 'err')
        print(val)

asyncio.run(main())

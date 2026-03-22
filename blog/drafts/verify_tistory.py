import asyncio, json, websockets

# Use a tab to navigate to the public post
POST_TAB = 'ws://127.0.0.1:18800/devtools/page/A866B7E4C499AFA2632B140D7CBEF878'

async def main():
    async with websockets.connect(POST_TAB, max_size=10*1024*1024, open_timeout=5) as ws:
        # Reload the page
        nav = json.dumps({'id': 0, 'method': 'Page.reload', 'params': {'ignoreCache': True}})
        await ws.send(nav)
        await ws.recv()
        await asyncio.sleep(4)
        
        js = """
        (async () => {
            // Find the article content
            const article = document.querySelector('.article_view') || document.querySelector('.entry-content') || 
                           document.querySelector('#content') || document.querySelector('article') ||
                           document.querySelector('.tt_article_useless_p_margin');
            
            if (!article) {
                // Try to find any content area
                const divs = document.querySelectorAll('div');
                const contentDiv = Array.from(divs).find(d => d.innerHTML.length > 500 && !d.querySelector('nav'));
                if (contentDiv) {
                    return JSON.stringify({
                        found: 'fallback div',
                        textLen: contentDiv.innerText.length,
                        preview: contentDiv.innerText.substring(0, 500)
                    });
                }
                return JSON.stringify({error: 'no content found', bodyLen: document.body.innerText.length, bodyPreview: document.body.innerText.substring(0, 300)});
            }
            
            return JSON.stringify({
                found: 'article',
                textLen: article.innerText.length,
                htmlLen: article.innerHTML.length,
                preview: article.innerText.substring(0, 500),
                hasH1: article.querySelector('h1') !== null,
                hasTable: article.querySelector('table') !== null
            });
        })()
        """
        msg = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}})
        await ws.send(msg)
        raw = await ws.recv()
        resp = json.loads(raw)
        val = resp.get('result', {}).get('result', {}).get('value')
        print(val)

asyncio.run(main())

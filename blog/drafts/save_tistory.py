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
        # First verify the content is in the editor
        val = await step(ws, """
        (async () => {
            const cm = document.querySelector('.CodeMirror');
            if (cm && cm.CodeMirror) {
                const val = cm.CodeMirror.getValue();
                return JSON.stringify({len: val.length, preview: val.substring(0, 200)});
            }
            return JSON.stringify({error: 'no codemirror'});
        })()
        """, "verify_content")
        
        # Find the save/publish button
        val = await step(ws, """
        (async () => {
            const buttons = Array.from(document.querySelectorAll('button, input[type=submit], a.btn'));
            const btnTexts = buttons.map(b => ({
                tag: b.tagName,
                text: b.textContent.trim() || b.value || '',
                id: b.id,
                className: (b.className || '').substring(0, 50)
            })).filter(x => x.text.length > 0 && x.text.length < 50);
            return JSON.stringify(btnTexts);
        })()
        """, "find_buttons")
        
        # Click save/update button
        val = await step(ws, """
        (async () => {
            // Look for save button - common Tistory names: "수정", "저장", "발행", "완료"
            const buttons = Array.from(document.querySelectorAll('button, input[type=submit], a'));
            const saveBtn = buttons.find(b => {
                const text = (b.textContent || b.value || '').trim();
                return text === '수정' || text === '저장' || text === '완료' || text === '발행' || 
                       text === 'Save' || text === 'Update' || text === '수정 완료' ||
                       text.includes('수정') || text.includes('저장');
            });
            
            if (!saveBtn) {
                // Try finding by ID
                const saveById = document.querySelector('#save-button') || document.querySelector('#publish-layer-btn') || 
                                 document.querySelector('.btn_save') || document.querySelector('.save');
                if (saveById) {
                    saveById.click();
                    return JSON.stringify({clicked: 'by id: ' + (saveById.id || saveById.className)});
                }
                return JSON.stringify({error: 'no save button found'});
            }
            
            saveBtn.click();
            await new Promise(r => setTimeout(r, 2000));
            return JSON.stringify({clicked: saveBtn.textContent.trim() || saveBtn.value});
        })()
        """, "save_click", timeout=15)

asyncio.run(main())

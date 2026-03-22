import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets

DRAFT_ID = 191555996

async def recv_matching(ws, want_id, timeout=30):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get('id') == want_id:
            return msg

async def send_cmd(ws, method, params=None, timeout=30):
    send_cmd.i += 1
    cid = send_cmd.i
    await ws.send(json.dumps({'id': cid, 'method': method, 'params': params or {}}))
    return await recv_matching(ws, cid, timeout)
send_cmd.i = 0

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        # navigate to draft
        await send_cmd(ws, 'Page.navigate', {'url': f'https://jinilee.substack.com/publish/post/{DRAFT_ID}'})
        await asyncio.sleep(6)
        # focus editor and move caret to end
        expr = '''(() => {
          const root = document.querySelector('.ProseMirror,[contenteditable="true"]');
          if (!root) return 'no-editor';
          root.focus();
          const sel = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(root);
          range.collapse(false);
          sel.removeAllRanges();
          sel.addRange(range);
          return 'focused';
        })()'''
        r = await send_cmd(ws, 'Runtime.evaluate', {'expression': expr, 'returnByValue': True})
        print('focus=', r.get('result',{}).get('result',{}).get('value'))
        # type a space via actual input pipeline, then backspace
        await send_cmd(ws, 'Input.insertText', {'text': ' '})
        await asyncio.sleep(0.5)
        await send_cmd(ws, 'Input.dispatchKeyEvent', {'type':'keyDown','windowsVirtualKeyCode':8,'nativeVirtualKeyCode':8,'key':'Backspace','code':'Backspace'})
        await send_cmd(ws, 'Input.dispatchKeyEvent', {'type':'keyUp','windowsVirtualKeyCode':8,'nativeVirtualKeyCode':8,'key':'Backspace','code':'Backspace'})
        print('typed dirty keystrokes')
        await asyncio.sleep(8)
        # check draft
        expr2 = f'''fetch('https://jinilee.substack.com/api/v1/drafts/{DRAFT_ID}', {{credentials:'include'}})
          .then(r=>r.json())
          .then(d=>JSON.stringify({{body_len:(d.body_html||'').length, slug:d.slug, published:d.is_published}}))'''
        r2 = await send_cmd(ws, 'Runtime.evaluate', {'expression': expr2, 'awaitPromise': True, 'returnByValue': True})
        print(r2.get('result',{}).get('result',{}).get('value'))

asyncio.run(main())

#!/usr/bin/env python3
"""Publish KR blog post to Tistory via CDP + TinyMCE."""
import json, asyncio, sys, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
import websockets

HTML_FILE = Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_Operating-Notes-2_KR.body.html')
TITLE = 'Claude Code × Discord DM으로 암호화폐 퀀트 엔진 개발하기 — MAIJINI 운영 노트 #2'
TISTORY_NEW_POST = 'https://greenside.tistory.com/manage/newpost/?type=post'

CID = 0
async def recv_matching(ws, want_id, timeout=40):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get('id') == want_id:
            return msg

async def eval_js(ws, expr, timeout=40):
    global CID; CID += 1
    await ws.send(json.dumps({'id':CID,'method':'Runtime.evaluate','params':{'expression':expr,'awaitPromise':True,'returnByValue':True}}))
    msg = await recv_matching(ws, CID, timeout)
    return msg.get('result',{}).get('result',{}).get('value')

async def nav(ws, url, timeout=20):
    global CID; CID += 1
    await ws.send(json.dumps({'id':CID,'method':'Page.navigate','params':{'url':url}}))
    await recv_matching(ws, CID, timeout)

async def main():
    # Find tistory tab
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    tistory_pages = [p for p in pages if 'tistory' in p.get('url','') and p.get('type')=='page']
    
    if not tistory_pages:
        # Use substack tab to open tistory
        page = next(p for p in pages if p.get('type')=='page')
    else:
        page = tistory_pages[0]
    
    print(f'Using tab: {page["url"]}')
    html_content = HTML_FILE.read_text(encoding='utf-8')
    print(f'HTML: {len(html_content)} chars')

    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        # Navigate to new post page
        await nav(ws, TISTORY_NEW_POST)
        await asyncio.sleep(6)
        
        # Wait for editor to load
        val = await eval_js(ws, '''
            new Promise(r => {
                let n=0;
                const check = () => {
                    n++;
                    const iframe = document.querySelector('#editor-tistory_ifr');
                    if (iframe) r('editor_ready');
                    else if (n < 30) setTimeout(check, 500);
                    else r('timeout:' + document.title);
                };
                check();
            })
        ''')
        print(f'Editor: {val}')
        
        if val != 'editor_ready':
            print('Editor not found! Checking page state...')
            val = await eval_js(ws, 'document.title + " | " + location.href')
            print(f'Page: {val}')
            return
        
        # Set title
        title_escaped = json.dumps(TITLE)
        val = await eval_js(ws, f'''
            (() => {{
                const titleEl = document.querySelector('#post-title-inp');
                if (!titleEl) return 'no-title-field';
                titleEl.value = {title_escaped};
                titleEl.dispatchEvent(new Event('input', {{bubbles:true}}));
                return 'title-set';
            }})()
        ''')
        print(f'Title: {val}')
        
        # Inject HTML via TinyMCE API (CRITICAL: must use setContent, not innerHTML)
        html_escaped = json.dumps(html_content)
        val = await eval_js(ws, f'''
            (() => {{
                if (typeof tinymce === 'undefined') return 'no-tinymce';
                const editor = tinymce.activeEditor;
                if (!editor) return 'no-active-editor';
                editor.setContent({html_escaped});
                editor.setDirty(true);
                editor.fire('change');
                editor.execCommand('mceInsertContent', false, ' ');
                editor.undoManager.add();
                return 'content-set:' + editor.getContent().length;
            }})()
        ''')
        print(f'Content: {val}')
        
        if not val or not val.startswith('content-set'):
            print('Failed to set content!')
            return
        
        # Wait for auto-save indicator
        await asyncio.sleep(3)
        
        # Click publish button (완료 button)
        val = await eval_js(ws, '''
            (() => {
                // Find the publish/완료 button
                const btns = [...document.querySelectorAll('button, .btn_publish, #publish-layer-btn, .save')];
                const pubBtn = btns.find(b => b.textContent.includes('완료') || b.textContent.includes('발행') || b.id === 'publish-layer-btn');
                if (pubBtn) { pubBtn.click(); return 'publish-clicked:' + pubBtn.textContent.trim(); }
                // Try direct ID
                const direct = document.querySelector('#publish-layer-btn');
                if (direct) { direct.click(); return 'direct-clicked'; }
                return 'no-publish-btn:' + btns.map(b=>b.textContent.trim()).filter(Boolean).slice(0,10).join('|');
            })()
        ''')
        print(f'Publish1: {val}')
        await asyncio.sleep(3)
        
        # In the publish dialog, select "공개" and click final publish
        val = await eval_js(ws, '''
            (() => {
                // Click 공개 radio button
                const radios = [...document.querySelectorAll('input[type=radio], label')];
                const publicRadio = radios.find(r => r.textContent && r.textContent.includes('공개'));
                if (publicRadio) publicRadio.click();
                
                // Click final publish button (공개발행 or 발행)
                const btns = [...document.querySelectorAll('button')];
                const finalBtn = btns.find(b => {
                    const t = b.textContent.trim();
                    return t.includes('공개발행') || t.includes('발행') || t === '공개';
                });
                if (finalBtn) { finalBtn.click(); return 'final-clicked:' + finalBtn.textContent.trim(); }
                return 'no-final:' + btns.map(b=>b.textContent.trim()).filter(Boolean).slice(0,10).join('|');
            })()
        ''')
        print(f'Publish2: {val}')
        await asyncio.sleep(5)
        
        # Check result
        val = await eval_js(ws, 'location.href')
        print(f'Final URL: {val}')

asyncio.run(main())

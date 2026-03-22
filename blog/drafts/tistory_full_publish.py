#!/usr/bin/env python3
"""Full Tistory publish via CDP: navigate, set title, set content via TinyMCE, publish."""
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

async def nav(ws, url):
    global CID; CID += 1
    await ws.send(json.dumps({'id':CID,'method':'Page.navigate','params':{'url':url}}))
    await recv_matching(ws, CID, 20)

async def input_text(ws, text):
    global CID; CID += 1
    await ws.send(json.dumps({'id':CID,'method':'Input.insertText','params':{'text':text}}))
    await recv_matching(ws, CID, 10)

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'tistory' in p.get('url','') and p.get('type')=='page')
    html = HTML_FILE.read_text(encoding='utf-8')
    print(f'HTML: {len(html)} chars')

    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        # Navigate
        await nav(ws, TISTORY_NEW_POST)
        print('Navigating...')
        await asyncio.sleep(7)
        
        # Wait for editor
        val = await eval_js(ws, '''
            new Promise(r => {
                let n=0;
                const c=()=>{n++;
                    if(typeof tinymce!=='undefined' && tinymce.activeEditor) r('ready');
                    else if(n<40) setTimeout(c,500);
                    else r('timeout');
                };c();
            })
        ''')
        print(f'Editor: {val}')
        if val != 'ready':
            return
        
        # Set title via focus + CDP input
        val = await eval_js(ws, '''
            (() => {
                const titleEl = document.querySelector('#post-title-inp');
                if (!titleEl) return 'no-title';
                titleEl.focus();
                titleEl.value = '';
                return 'title-focused';
            })()
        ''')
        print(f'Title focus: {val}')
        await input_text(ws, TITLE)
        print('Title typed')
        
        # Set content via TinyMCE
        html_escaped = json.dumps(html)
        val = await eval_js(ws, f'''
            (() => {{
                const ed = tinymce.activeEditor;
                ed.setContent({html_escaped});
                ed.setDirty(true);
                ed.fire('change');
                ed.undoManager.add();
                return 'set:' + ed.getContent().length;
            }})()
        ''')
        print(f'Content: {val}')
        
        # Wait for autosave
        print('Waiting for autosave...')
        await asyncio.sleep(5)
        
        val = await eval_js(ws, '''
            (() => {
                const status = document.querySelector('.status-text-bar');
                return status ? status.textContent.trim() : 'no-status';
            })()
        ''')
        print(f'Status: {val}')
        
        # Click 완료 (#publish-layer-btn)
        val = await eval_js(ws, '''
            (() => {
                const btn = document.querySelector('#publish-layer-btn');
                if (!btn) return 'no-btn';
                btn.click();
                return 'clicked';
            })()
        ''')
        print(f'완료: {val}')
        await asyncio.sleep(3)
        
        # Check for publish layer/dialog
        val = await eval_js(ws, '''
            (() => {
                // Look for the publish overlay
                const layer = document.querySelector('#publish-layer');
                if (layer) {
                    const style = window.getComputedStyle(layer);
                    if (style.display !== 'none') {
                        return 'layer-visible:' + layer.textContent.trim().slice(0,200);
                    }
                }
                // Check URL — maybe already published
                if (location.href.includes('/manage/posts')) return 'redirected-to-posts';
                if (location.href.match(/\/\d+$/)) return 'published:' + location.href;
                return 'url:' + location.href;
            })()
        ''')
        print(f'After 완료: {val}')
        
        if 'layer-visible' in str(val):
            # Click the 공개 발행 button in the dialog
            val2 = await eval_js(ws, '''
                (() => {
                    const layer = document.querySelector('#publish-layer');
                    // Find radio for 공개
                    const labels = [...layer.querySelectorAll('label')];
                    const publicLabel = labels.find(l => l.textContent.includes('공개'));
                    if (publicLabel) {
                        const radio = publicLabel.querySelector('input') || publicLabel.previousElementSibling;
                        if (radio) radio.click();
                    }
                    // Find and click publish button  
                    const btns = [...layer.querySelectorAll('button')];
                    const pubBtn = btns.find(b => b.textContent.includes('발행') || b.textContent.includes('공개'));
                    if (pubBtn) { pubBtn.click(); return 'published:' + pubBtn.textContent.trim(); }
                    return 'btns:' + btns.map(b=>b.textContent.trim()).join('|');
                })()
            ''')
            print(f'Publish dialog: {val2}')
            await asyncio.sleep(5)
        
        # Final check
        val = await eval_js(ws, 'location.href')
        print(f'Final URL: {val}')

asyncio.run(main())

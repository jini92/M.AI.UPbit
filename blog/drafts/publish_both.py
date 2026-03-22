#!/usr/bin/env python3
"""Publish both Substack drafts via CDP by clicking Continue -> Publish without buttons."""
import json, asyncio, sys, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')
import websockets

async def run_js(ws, js, timeout=30):
    global _mid
    _mid += 1
    await ws.send(json.dumps({'id':_mid,'method':'Runtime.evaluate','params':{'expression':js,'awaitPromise':True,'returnByValue':True}}))
    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
    return resp.get('result',{}).get('result',{}).get('value')

_mid = 0

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    sp = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    
    async with websockets.connect(sp['webSocketDebuggerUrl'], max_size=10**7) as ws:
        drafts = [191555996, 191556012]  # ON#2, QL#3
        
        for draft_id in drafts:
            print(f'\n=== Publishing draft {draft_id} ===')
            
            # Navigate to editor
            await run_js(ws, f"window.location.href='https://jinilee.substack.com/publish/post/{draft_id}'; 'ok'")
            await asyncio.sleep(6)
            
            # Wait for editor ready
            val = await run_js(ws, '''
                new Promise(r=>{let n=0;const c=()=>{n++;
                    const btn=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Continue');
                    if(btn)r('ready');else if(n<30)setTimeout(c,500);else r('timeout')};c()})
            ''')
            print(f'  Editor: {val}')
            
            # Click Continue button
            val = await run_js(ws, '''
                const btn = Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Continue');
                if(btn){btn.click(); 'clicked'} else {'not_found'}
            ''')
            print(f'  Continue: {val}')
            await asyncio.sleep(3)
            
            # Now in publish dialog - uncheck email if possible, then publish
            # First try to uncheck "Send via email"
            val = await run_js(ws, '''
                const labels = Array.from(document.querySelectorAll('label, [role=checkbox], input[type=checkbox]'));
                const emailChk = labels.find(l => l.textContent && l.textContent.includes('Send via email'));
                if (emailChk) { emailChk.click(); 'unchecked_email' }
                else {
                    // Try finding checkbox near "Send via email" text
                    const spans = Array.from(document.querySelectorAll('span, div'));
                    const emailSpan = spans.find(s => s.textContent.includes('Send via email'));
                    if (emailSpan) {
                        const parent = emailSpan.closest('[role=group]') || emailSpan.parentElement;
                        const chk = parent ? parent.querySelector('[role=checkbox], input[type=checkbox]') : null;
                        if (chk) { chk.click(); 'unchecked_via_parent' }
                        else { 'no_checkbox_found' }
                    } else { 'no_email_text_found' }
                }
            ''')
            print(f'  Email toggle: {val}')
            await asyncio.sleep(1)
            
            # Click the publish button (might say "Send to everyone now" or "Publish" or "Publish without buttons")
            val = await run_js(ws, '''
                const buttons = Array.from(document.querySelectorAll('button'));
                const pubBtn = buttons.find(b => {
                    const t = b.textContent.trim().toLowerCase();
                    return t.includes('send to everyone') || t.includes('publish now') || 
                           t.includes('publish without') || (t === 'publish' && !b.disabled);
                });
                if (pubBtn) { pubBtn.click(); 'clicked: ' + pubBtn.textContent.trim() }
                else {
                    const allBtnTexts = buttons.map(b=>b.textContent.trim()).filter(t=>t);
                    'not_found. buttons: ' + allBtnTexts.join(' | ')
                }
            ''')
            print(f'  Publish click: {val}')
            await asyncio.sleep(8)
            
            # Check if "Publish without buttons" appeared
            val = await run_js(ws, '''
                const btns = Array.from(document.querySelectorAll('button'));
                const pwb = btns.find(b => b.textContent.includes('Publish without'));
                if (pwb) { pwb.click(); 'clicked publish without buttons' }
                else { 'no publish-without-buttons found' }
            ''')
            print(f'  Fallback: {val}')
            await asyncio.sleep(5)
            
            # Verify
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}', {{credentials:'include'}})
                .then(r=>r.json())
                .then(d=>JSON.stringify({{published:d.is_published, slug:d.slug, body_len:(d.body_html||'').length}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Status: {val}')

asyncio.run(main())

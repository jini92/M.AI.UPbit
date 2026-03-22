import json, asyncio, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websockets

DRAFT_ID = 191555996

async def main():
    pages = json.loads(urllib.request.urlopen('http://127.0.0.1:18800/json').read())
    page = next(p for p in pages if 'substack.com' in p.get('url','') and p['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10**7) as ws:
        await ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{
            'expression':f"fetch('https://jinilee.substack.com/api/v1/drafts/{DRAFT_ID}',{{credentials:'include'}}).then(r=>r.json()).then(d=>JSON.stringify({{keys:Object.keys(d), body_html_len:(d.body_html||'').length, draft_body_len:(d.draft_body||'').length, has_body:!!d.body, has_body_json:!!d.body_json, has_draft_body:!!d.draft_body, sample_body:(d.draft_body||'').slice(0,80), sample_body_json: JSON.stringify(d.body_json||null).slice(0,120)}}))",
            'awaitPromise':True,'returnByValue':True}}))
        resp = json.loads(await ws.recv())
        print(resp.get('result',{}).get('result',{}).get('value',''))

asyncio.run(main())

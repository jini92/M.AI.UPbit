#!/usr/bin/env python3
"""Create Substack posts using ProseMirror JSON body format via CDP."""
import json
import asyncio
import sys
import re
from pathlib import Path
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8')
import websockets

WS_URL = 'ws://127.0.0.1:18800/devtools/page/ECC504EE515D8C004A64C38E3B5FE1B4'
MSG_ID = 0

def next_id():
    global MSG_ID
    MSG_ID += 1
    return MSG_ID

async def run_js(ws, js_code):
    mid = next_id()
    await ws.send(json.dumps({
        'id': mid, 'method': 'Runtime.evaluate',
        'params': {'expression': js_code, 'awaitPromise': True, 'returnByValue': True}
    }))
    resp = json.loads(await ws.recv())
    return resp.get('result', {}).get('result', {}).get('value')


def html_to_prosemirror(html_content):
    """Convert HTML to Substack ProseMirror JSON document structure."""
    content = []
    
    class PMParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []  # stack of (tag, attrs, children)
            self.current_marks = []
            self.text_buffer = ''
            
        def _flush_text(self):
            if self.text_buffer:
                node = {"type": "text", "text": self.text_buffer}
                if self.current_marks:
                    node["marks"] = list(self.current_marks)
                self.text_buffer = ''
                return node
            return None
        
        def handle_starttag(self, tag, attrs):
            self.stack.append((tag, dict(attrs), []))
            
        def handle_endtag(self, tag):
            if not self.stack:
                return
            stag, sattrs, children = self.stack.pop()
            
            # Flush any remaining text
            text_node = self._flush_text()
            if text_node:
                children.append(text_node)
            
            node = self._tag_to_node(stag, sattrs, children)
            if node:
                if self.stack:
                    self.stack[-1][2].append(node)
                else:
                    content.append(node)
                    
        def handle_data(self, data):
            if data.strip() or data == ' ':
                if self.stack:
                    text_node = {"type": "text", "text": data}
                    self.stack[-1][2].append(text_node)
                else:
                    if data.strip():
                        content.append({"type": "paragraph", "content": [{"type": "text", "text": data.strip()}]})
        
        def _tag_to_node(self, tag, attrs, children):
            tag = tag.lower()
            
            if tag in ('h1', 'h2', 'h3', 'h4'):
                level = int(tag[1])
                node = {"type": "heading", "attrs": {"level": level}}
                if children:
                    node["content"] = children
                return node
                
            elif tag == 'p':
                node = {"type": "paragraph"}
                if children:
                    node["content"] = children
                return node
                
            elif tag == 'hr':
                return {"type": "horizontal_rule"}
                
            elif tag == 'strong' or tag == 'b':
                # Apply bold mark to children
                for c in children:
                    if c.get('type') == 'text':
                        marks = c.get('marks', [])
                        marks.append({"type": "bold"})
                        c['marks'] = marks
                return None  # Children already added to parent
                
            elif tag == 'em' or tag == 'i':
                for c in children:
                    if c.get('type') == 'text':
                        marks = c.get('marks', [])
                        marks.append({"type": "italic"})
                        c['marks'] = marks
                return None
                
            elif tag == 'a':
                href = attrs.get('href', '')
                for c in children:
                    if c.get('type') == 'text':
                        marks = c.get('marks', [])
                        marks.append({"type": "link", "attrs": {"href": href}})
                        c['marks'] = marks
                return None
                
            elif tag == 'code':
                for c in children:
                    if c.get('type') == 'text':
                        marks = c.get('marks', [])
                        marks.append({"type": "code"})
                        c['marks'] = marks
                return None
                
            elif tag == 'pre':
                # Code block
                text = ''
                for c in children:
                    if c.get('type') == 'text':
                        text += c.get('text', '')
                    elif c.get('content'):
                        for cc in c['content']:
                            text += cc.get('text', '')
                return {"type": "codeBlock", "content": [{"type": "text", "text": text}]}
                
            elif tag == 'ul':
                return {"type": "bullet_list", "content": children}
                
            elif tag == 'ol':
                return {"type": "ordered_list", "attrs": {"start": 1}, "content": children}
                
            elif tag == 'li':
                # Wrap in paragraph if needed
                wrapped = []
                for c in children:
                    if c.get('type') in ('paragraph', 'bullet_list', 'ordered_list'):
                        wrapped.append(c)
                    else:
                        wrapped.append({"type": "paragraph", "content": [c]})
                if not wrapped:
                    wrapped = [{"type": "paragraph"}]
                return {"type": "list_item", "content": wrapped}
                
            elif tag == 'table':
                return {"type": "table", "content": children}
            elif tag == 'thead' or tag == 'tbody':
                return None  # Pass through children
            elif tag == 'tr':
                return {"type": "table_row", "content": children}
            elif tag == 'th':
                node = {"type": "table_header"}
                if children:
                    node["content"] = [{"type": "paragraph", "content": children}]
                else:
                    node["content"] = [{"type": "paragraph"}]
                return node
            elif tag == 'td':
                node = {"type": "table_cell"}
                if children:
                    node["content"] = [{"type": "paragraph", "content": children}]
                else:
                    node["content"] = [{"type": "paragraph"}]
                return node
                
            elif tag in ('div', 'span', 'br'):
                if children:
                    return None  # pass through
                if tag == 'br':
                    return {"type": "hard_break"}
                return None
                
            else:
                # Unknown tag - try to pass as paragraph
                if children:
                    return {"type": "paragraph", "content": children}
                return None
    
    parser = PMParser()
    parser.feed(html_content)
    
    # Filter out None values and flatten
    def flatten(nodes):
        result = []
        for n in nodes:
            if n is None:
                continue
            result.append(n)
        return result
    
    content = flatten(content)
    
    return {"type": "doc", "content": content}


async def main():
    async with websockets.connect(WS_URL, max_size=10**7) as ws:
        # Clean up previous failed drafts
        val = await run_js(ws, '''
            fetch('https://jinilee.substack.com/api/v1/drafts?limit=10', {credentials:'include'})
            .then(r=>r.json())
            .then(d=>JSON.stringify(d.filter(x=>!x.is_published && x.draft_title!=='How to use the Substack editor').map(x=>({id:x.id,title:x.draft_title}))))
        ''')
        print(f'Drafts to clean: {val}')
        if val:
            for d in json.loads(val):
                await run_js(ws, f"fetch('https://jinilee.substack.com/api/v1/drafts/{d['id']}',{{method:'DELETE',credentials:'include'}}).then(r=>r.status)")
                print(f'  Deleted: {d["id"]} ({d["title"][:40]})')

        posts = [
            {
                'html_file': Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_Operating-Notes-2_EN.body.html'),
                'title': 'MAIJINI@openclaw Operating Notes #2 \u2014 Claude Code + MAIBOT + maiupbit: The Full-Stack AI Dev Chain',
                'subtitle': 'How I wired Claude Code into Discord DM via OpenClaw to build a crypto quant CLI, optimize GPU inference, and automate a newsletter pipeline \u2014 all through chat.',
            },
            {
                'html_file': Path(r'C:\TEST\M.AI.UPbit\blog\drafts\2026-03-20_AI-Quant-Letter-3_EN.body.html'),
                'title': 'AI Quant Letter #3 \u2014 All Negative Momentum Scores, ETH Still Leads',
                'subtitle': 'Week of March 15: Dual momentum says hold cash, multi-factor keeps ETH and AVAX at the top.',
            },
        ]

        for post in posts:
            print(f'\n=== {post["title"][:60]}... ===')
            html = post['html_file'].read_text(encoding='utf-8')
            pm_doc = html_to_prosemirror(html)
            pm_json = json.dumps(pm_doc)
            print(f'  HTML: {len(html)} chars -> ProseMirror: {len(pm_json)} chars, {len(pm_doc["content"])} top-level nodes')

            # Create draft with body_json (ProseMirror)
            create_body = json.dumps({
                'draft_title': post['title'],
                'draft_subtitle': post['subtitle'],
                'type': 'newsletter',
                'audience': 'everyone',
                'draft_bylines': [],
                'body_json': pm_doc,
            })
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts', {{
                    method: 'POST', credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: {json.dumps(create_body)}
                }}).then(r=>r.json())
                .then(d=>JSON.stringify({{id:d.id, slug:d.slug, body_len:(d.body_html||'').length, body_start:(d.body_html||'').substring(0,100)}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Created: {val}')
            
            try:
                data = json.loads(val)
                draft_id = data.get('id')
                slug = data.get('slug')
                body_len = data.get('body_len', 0)
                body_start = data.get('body_start', '')
            except:
                print(f'  Parse error: {val}')
                continue

            if not draft_id:
                print('  No draft_id!')
                continue
            
            print(f'  Draft {draft_id}: body_html={body_len} chars')
            if '&lt;' in body_start:
                print(f'  WARNING: Still escaped HTML!')
            elif body_len > 100:
                print(f'  Body looks good!')

            # Publish
            val = await run_js(ws, f'''
                fetch('https://jinilee.substack.com/api/v1/drafts/{draft_id}/publish', {{
                    method: 'PUT', credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{send: false, share_automatically: false}})
                }}).then(r=>r.json())
                .then(d=>JSON.stringify({{ok:true, slug:d.slug, type:d.type}}))
                .catch(e=>'ERR:'+e.message)
            ''')
            print(f'  Published: {val}')
            
            try:
                pub_data = json.loads(val)
                final_slug = pub_data.get('slug') or slug
            except:
                final_slug = slug
            print(f'  URL: https://jinilee.substack.com/p/{final_slug}')

asyncio.run(main())

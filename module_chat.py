# 文件名: module_chat.py
import asyncio
import json
import urllib.request
import websockets

CDP_URL = "http://127.0.0.1:9229"
JSON_URL = f"{CDP_URL}/json"

# ==========================================
# 🛠️ CDP 底层通信封装 (防异步干扰)
# ==========================================
async def cdp_call(ws, req_id, method, params=None):
    payload = {"id": req_id, "method": method}
    if params: payload["params"] = params
    await ws.send(json.dumps(payload))
    while True:
        try:
            res_str = await asyncio.wait_for(ws.recv(), timeout=5.0)
            res = json.loads(res_str)
            if res.get("id") == req_id:
                return res
        except asyncio.TimeoutError:
            print(f"  [底层警告] 请求超时 (ID: {req_id})")
            return {}
        except Exception:
            continue

async def process_chat(ai_generate_func):
    """处理当前激活的 WhatsApp 窗口内的聊天"""
    try:
        req = urllib.request.Request(JSON_URL)
        with urllib.request.urlopen(req, timeout=5) as response:
            targets = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"❌ [Chatter] 无法获取 Targets: {e}")
        return False

    active_src = None
    main_ws_url = next((t['webSocketDebuggerUrl'] for t in targets if t.get('title') == 'WADesk' and t.get('type') == 'page'), None)
    if main_ws_url:
        async with websockets.connect(main_ws_url) as ws:
            find_active_js = "Array.from(document.querySelectorAll('webview')).find(wv => window.getComputedStyle(wv).display !== 'none')?.src"
            res = await cdp_call(ws, 1, "Runtime.evaluate", {"expression": find_active_js, "returnByValue": True})
            active_src = res.get("result", {}).get("result", {}).get("value")

    if not active_src: return False

    wa_ws_url = next((t['webSocketDebuggerUrl'] for t in targets if t.get('url') == active_src), None)
    if not wa_ws_url: return False

    print("🔗 [Chatter] 成功潜入当前活动的 WhatsApp 引擎！")

    async with websockets.connect(wa_ws_url, max_size=10_485_760) as ws:
        # --- 步骤 A：点击聊天行红点 (防头像误触版) ---
        print("📍 [Chatter] 正在定位联系人红点...")
        click_js = """
        (() => {
            const paneSide = document.querySelector('#pane-side') || document;
            const rows = paneSide.querySelectorAll('div[role="row"]');
            for (let row of rows) {
                if (row.querySelector('span[aria-label*="未读消息"], span[aria-label*="unread"]')) {
                    row.scrollIntoView({block: 'center', behavior: 'instant'});
                    const rect = row.getBoundingClientRect();
                    return { x: rect.x + rect.width * 0.6, y: rect.y + rect.height / 2 };
                }
            }
            return null;
        })();
        """
        res = await cdp_call(ws, 10, "Runtime.evaluate", {"expression": click_js, "returnByValue": True})
        coords = res.get("result", {}).get("result", {}).get("value")
        
        if not coords:
            print("📭 [Chatter] 页面内未找到红点（可能已被手动点掉）。")
            return False
            
        cx, cy = coords['x'], coords['y']
        
        await cdp_call(ws, 11, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "buttons": 1, "clickCount": 1})
        await asyncio.sleep(0.05)
        await cdp_call(ws, 12, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "buttons": 0, "clickCount": 1})
        await asyncio.sleep(0.2)
        await cdp_call(ws, 13, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "buttons": 1, "clickCount": 1})
        await asyncio.sleep(0.05)
        await cdp_call(ws, 14, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "buttons": 0, "clickCount": 1})
        
        print("🖱️ [Chatter] 联系人已精准点击，预留加载时间...")
        await asyncio.sleep(1.5)

        # --- 步骤 B：提取结构化 JSON 聊天记录 ---
        print("👀 [Chatter] 正在提取结构化上下文...")
        extract_js = """
        (() => {
            const history = [];
            const rows = document.querySelectorAll('#main div[role="row"]');
            
            rows.forEach(row => {
                const isMsgIn = row.querySelector('.message-in') !== null;
                const isMsgOut = row.querySelector('.message-out') !== null;
                
                if (!isMsgIn && !isMsgOut) return; 

                let contentText = "";
                let metaInfo = "";
                let msgTime = "";
                let msgName = "";

                const mediaEls = row.querySelectorAll('img[src^="blob:"]');
                mediaEls.forEach(img => {
                    contentText += `[图片地址: ${img.src}] `;
                });

                const msgNode = row.querySelector('div.copyable-text[data-pre-plain-text]');
                if (msgNode) {
                    metaInfo = msgNode.getAttribute('data-pre-plain-text') || "";
                    
                    if (metaInfo) {
                        const match = metaInfo.trim().match(/^\[(.*?)\]\s*(.*?):\s*$/);
                        if (match) {
                            msgTime = match[1].trim(); 
                            msgName = match[2].trim(); 
                        } else {
                            msgName = metaInfo.trim(); 
                        }
                    }
                    
                    const clone = msgNode.cloneNode(true);
                    
                    const emojis = clone.querySelectorAll('img.emoji');
                    emojis.forEach(emoji => {
                        const altText = emoji.getAttribute('data-plain-text') || emoji.alt || '';
                        const textNode = document.createTextNode(altText);
                        emoji.parentNode.replaceChild(textNode, emoji);
                    });
                    
                    const hiddenElements = clone.querySelectorAll('[aria-hidden="true"]');
                    hiddenElements.forEach(el => el.remove());
                    
                    const text = clone.innerText || clone.textContent;
                    if (text) {
                        contentText += text.trim();
                    }
                }

                if (contentText.trim() !== "") {
                    history.push({
                        role: isMsgIn ? 'user' : 'assistant',
                        time: msgTime,
                        name: msgName,
                        content: contentText.trim()
                    });
                }
            });
            
            return history;
        })();
        """
        
        chat_history = None
        for attempt in range(15):
            res = await cdp_call(ws, 20 + attempt, "Runtime.evaluate", {"expression": extract_js, "returnByValue": True})
            chat_history = res.get("result", {}).get("result", {}).get("value")
            
            if chat_history and len(chat_history) > 0:
                print(f"✅ [Chatter] 成功获取 {len(chat_history)} 条结构化记录！")
                break
                
            print(f"⏳ [Chatter] 聊天记录渲染中 ({attempt+1}/15)...")
            await asyncio.sleep(0.5)

        if not chat_history:
            print("❌ [Chatter] 提取超时，未获取到内容。")
            return False

        # --- 步骤 C：生成回复 ---
        reply_text = await ai_generate_func(chat_history)
        safe_reply_text = json.dumps(reply_text)

        # --- 步骤 D：注入并发送 ---
        print("⌨️ [Chatter] 正在注入回复并发送...")
        inject_js = f"""
        (() => {{
            const inputBox = document.querySelector('#main div[contenteditable="true"][role="textbox"]');
            if (!inputBox) return {{ error: "未找到输入框" }};
            inputBox.focus();
            document.execCommand('insertText', false, {safe_reply_text});
            return {{ success: true }};
        }})();
        """
        await cdp_call(ws, 50, "Runtime.evaluate", {"expression": inject_js, "returnByValue": True})
        await asyncio.sleep(0.8)

        find_btn_js = "(()=>{ const b=document.querySelector('#main button[aria-label=\"发送\"]'); if(!b)return null; const r=b.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2}; })()"
        res = await cdp_call(ws, 51, "Runtime.evaluate", {"expression": find_btn_js, "returnByValue": True})
        btn_coords = res.get("result", {}).get("result", {}).get("value")

        if btn_coords:
            bx, by = btn_coords['x'], btn_coords['y']
            await cdp_call(ws, 52, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": bx, "y": by, "button": "left", "clickCount": 1})
            await cdp_call(ws, 53, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": bx, "y": by, "button": "left", "clickCount": 1})
            print("🎉 [Chatter] 消息已成功发送！")
            return True
        else:
            print("❌ [Chatter] 未找到发送按钮。")
            return False
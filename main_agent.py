# 文件名: main_agent.py
import asyncio
from module_switch import switch_to_unread_account
from module_chat import process_chat
from module_ai import generate_reply

async def agent_loop():
    print("========================================")
    print("🤖 WADesk AI Agent [工程模块化版] 已启动")
    print("👀 正在全天候静默监听未读消息...")
    print("========================================")
    
    while True:
        try:
            # 1. 尝试使用 Playwright 切换账号
            switched = await switch_to_unread_account()
            
            if switched:
                print("🔄 等待 WADesk 界面加载切换动画...")
                await asyncio.sleep(1.5) 
                
                # 2. 如果切换成功，进入内部引擎处理具体聊天
                success = await process_chat(generate_reply)
                
                if success:
                    print("⏳ 闭环完成！防系统封禁冷却中 (3秒)...\n")
                    await asyncio.sleep(3)
                else:
                    print("⚠️ 处理流程中断，返回继续监听...\n")
                    await asyncio.sleep(1)
            else:
                # 3. 如果没发现未读消息，静默轮询
                await asyncio.sleep(2)
                
        except KeyboardInterrupt:
            print("\n🛑 手动停止守护进程。")
            break
        except Exception as e:
            print(f"\n⚠️ 主循环遇到异常: {e}，5秒后重试...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(agent_loop())
    except KeyboardInterrupt:
        print("\n👋 Agent 已退出。")
# 文件名: module_switch.py
import os
os.environ["NODE_NO_WARNINGS"] = "1"  # 屏蔽底层 Node.js 的烦人弃用警告
from playwright.async_api import async_playwright
import asyncio

CDP_URL = "http://127.0.0.1:9229"

async def switch_to_unread_account():
    """扫描 WADesk 主界面，发现未读账号并执行物理切换"""
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            page = browser.contexts[0].pages[0]

            # 核心定位：找到包含可见红点的卡片
            unread_cards = page.locator('.wa-card').filter(
                has=page.locator('sup.el-badge__content:visible')
            )

            unread_count = await unread_cards.count()
            
            if unread_count > 0:
                target_card = unread_cards.first
                badge_text = await target_card.locator('sup.el-badge__content:visible').inner_text()
                print(f"🎯 [Switcher] 锁定目标！发现账号有 {badge_text} 条未读，执行切换...")
                
                await target_card.click()
                await browser.close()
                return True
            else:
                await browser.close()
                return False

        except Exception as e:
            print(f"❌ [Switcher] 账号切换发生错误: {e}")
            return False
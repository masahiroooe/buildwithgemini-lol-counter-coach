import asyncio
import os
import time
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path("/config/.gemini/antigravity/brain/2d93f2be-9cfd-4095-ae35-244a90606da6")
TARGET_URL = "https://frontend-1065249703893.us-central1.run.app"

async def record_demo():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/google-chrome-stable",
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(ARTIFACT_DIR),
            record_video_size={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        print(f"Navigating to {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        input_box = page.locator("#input")
        submit_btn = page.locator(".submit-btn")

        # -------------------------------------------------------------
        # Scene 1: App's Primary Strength (Katakana Matchup Advice + Pro Strategy)
        # -------------------------------------------------------------
        print("Executing Prompt 1: Katakana Counter Advice & Pro Tips...")
        prompt_1 = "ヤスオのカウンター対策とレーニング戦術を教えて"
        await input_box.click()
        await page.wait_for_timeout(500)
        await input_box.fill(prompt_1)
        await page.wait_for_timeout(1000)
        await submit_btn.click()
        
        # Wait for A2UI card to render in response
        print("Waiting for response 1 (A2UI card & Katakana match)...")
        await page.wait_for_selector(".a2card", timeout=45000)
        print("Response 1 rendered successfully! Showcasing cards & splash art...")
        await page.wait_for_timeout(10000) # Showcase rendered A2UI cards & left spotlight splash art

        # -------------------------------------------------------------
        # Scene 2: Detailed Tool Calls, Database Search & Image Generation
        # -------------------------------------------------------------
        print("Executing Prompt 2: Tool Calls & Image Generation...")
        prompt_2 = "ヤスオのアバター画像を生成して、Firestoreデータベースの最新対戦メモも確認して"
        await input_box.click()
        await page.wait_for_timeout(500)
        await input_box.fill(prompt_2)
        await page.wait_for_timeout(1000)
        await submit_btn.click()
        
        # Wait for tool execution (image generation + storage upload + card render)
        print("Waiting for response 2 (Image Generation & Tool Calls)...")
        # Allow time for Gemini Image model generation & GCS bucket upload
        await page.wait_for_timeout(30000)

        await context.close()
        await browser.close()
        
        # Find created video file and rename to demo_recording.webm
        video_files = list(ARTIFACT_DIR.glob("*.webm"))
        if video_files:
            latest_video = max(video_files, key=os.path.getmtime)
            target_path = ARTIFACT_DIR / "demo_recording.webm"
            if latest_video != target_path:
                if target_path.exists():
                    os.remove(target_path)
                os.rename(latest_video, target_path)
            print(f"Successfully saved demo video to {target_path}")
        else:
            print("Warning: No video file was generated.")

if __name__ == "__main__":
    asyncio.run(record_demo())

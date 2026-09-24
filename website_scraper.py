import asyncio
import os
import time
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from playwright.sync_api import sync_playwright
from config import OUTPUTS_PATH, CHROME_PROFILE_PATH

async def _scrape_async(url: str) -> str:
    browser_cfg = BrowserConfig(
        browser_type="chromium", headless=True, java_script_enabled=True)
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, wait_until="domcontentloaded",
        page_timeout=30000, delay_before_return_html=2.0)
    try:
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
        if result.success and result.markdown and len(result.markdown) > 200:
            return result.markdown
    except Exception as e:
        print(f"  Crawl4AI failed: {e}")
    return ""

def _playwright_fallback(url: str) -> str:
    p = browser = None
    try:
        p       = sync_playwright().start()
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_PATH, headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)
        return page.inner_text("body")
    except Exception as e:
        print(f"  Playwright fallback failed: {e}")
        return ""
    finally:
        if browser: browser.close()
        if p:       p.stop()

def scrape(url: str, company_name: str) -> str:
    print(f"  Scraping {company_name}...")
    text = asyncio.run(_scrape_async(url))
    if len(text) < 500:
        print(f"  Low content — trying Playwright fallback...")
        text = _playwright_fallback(url)
    print(f"  Got {len(text)} characters for {company_name}")
    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in company_name).lower()
    with open(f"{OUTPUTS_PATH}/{safe}_scraped.txt", "w", encoding="utf-8") as f:
        f.write(text)
    return text
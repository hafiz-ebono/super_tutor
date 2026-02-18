from app.extraction.trafilatura_extractor import extract_from_html


async def fetch_via_playwright(url: str) -> str | None:
    """Launches headless Chromium, returns extracted text or None."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, timeout=20000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            html = await page.content()
            await browser.close()
        return extract_from_html(html)
    except Exception:
        return None

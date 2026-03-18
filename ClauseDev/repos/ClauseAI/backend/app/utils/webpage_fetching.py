import asyncio
import logging
import requests
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def _extract_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines = (line.strip() for line in soup.get_text(separator="\n").splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)[:20000]

def _sync_fetch_with_requests(url: str, timeout: int = 30000) -> str:
    timeout_seconds = max(timeout / 1000, 1)
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers={"User-Agent": "Mozilla/5.0 ClauseAI/1.0"},
    )
    response.raise_for_status()
    return response.text

async def fetch_webpage_content_with_requests(url: str, timeout: int = 30000) -> Dict[str, Any]:
    try:
        html_content = await asyncio.to_thread(_sync_fetch_with_requests, url, timeout)
        return {"text": _extract_text(html_content)}
    except Exception as e:
        logger.warning(
            "Requests fetch failed",
            extra={"event": "web_fetch_requests_failed", "url": url, "error": str(e)},
        )
        return {"error": str(e)}

async def fetch_webpage_content_with_playwright(
    url: str,
    timeout: int = 30000,
    wait_time: int = 5,
) -> Dict[str, Any]:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=timeout)
            await asyncio.sleep(wait_time)
            html_content = await page.content()
            await browser.close()
        return {"text": _extract_text(html_content)}
    except Exception as e:
        logger.warning(
            "Playwright fetch failed",
            extra={"event": "web_fetch_playwright_failed", "url": url, "error": str(e)},
        )
        return {"error": str(e)}

async def fetch_multiple_webpage_content_with_playwright(
    urls: List[str],
    timeout: int = 30000,
    wait_time: int = 5,
) -> Dict[str, Dict[str, Any]]:
    if not urls:
        return {}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            semaphore = asyncio.Semaphore(min(6, len(urls)))
            results: Dict[str, Dict[str, Any]] = {}

            async def fetch_one(url: str) -> None:
                async with semaphore:
                    page = await browser.new_page()
                    try:
                        await page.goto(url, timeout=timeout)
                        await asyncio.sleep(wait_time)
                        html_content = await page.content()
                        results[url] = {"text": _extract_text(html_content)}
                    except Exception as e:
                        logger.warning(
                            "Playwright batch fetch failed for URL",
                            extra={"event": "web_fetch_playwright_item_failed", "url": url, "error": str(e)},
                        )
                        results[url] = {"error": str(e)}
                    finally:
                        await page.close()

            await asyncio.gather(*[fetch_one(url) for url in urls])
            await browser.close()
            return results
    except Exception as e:
        logger.error(
            "Playwright batch fetch failed",
            extra={"event": "web_fetch_playwright_batch_failed", "error": str(e), "url_count": len(urls)},
        )
        return {url: {"error": str(e)} for url in urls}

async def fetch_webpage_content(url: str, timeout: int = 30000, wait_time: int = 5) -> Dict[str, Any]:
    request_result = await fetch_webpage_content_with_requests(url, timeout)
    if "error" not in request_result and request_result.get("text"):
        return request_result
    return await fetch_webpage_content_with_playwright(url, timeout, wait_time)
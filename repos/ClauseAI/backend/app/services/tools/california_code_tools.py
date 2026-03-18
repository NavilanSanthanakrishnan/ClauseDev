import os
import asyncio
import logging
from typing import Dict, Any, List
from app.core.config import CALIFORNIA_CODE_DIR
from app.services.business_data_repository import business_data_repo
from app.utils.webpage_fetching import (
    fetch_webpage_content,
    fetch_webpage_content_with_requests,
    fetch_multiple_webpage_content_with_playwright,
)

logger = logging.getLogger(__name__)

def _load_master_data(directory: str) -> Dict[str, Any]:
    master_path = os.path.join(directory, "master_expanded.json")
    try:
        return business_data_repo.read_json(master_path)
    except FileNotFoundError:
        return {}

def _resolve_query(codes_db: Dict[str, Any], code: str, division: str, article: str = None) -> Dict[str, Any]:
    matching_code = None
    for key in codes_db.keys():
        if code.upper() in key.upper():
            matching_code = key
            break

    if not matching_code:
        return {"error": f"Code '{code}' not found"}

    code_data = codes_db[matching_code]
    divisions = code_data.get("divisions", {})

    matching_division = None
    for div_key in divisions.keys():
        if division.lower() in div_key.lower():
            matching_division = div_key
            break

    if not matching_division:
        return {"error": f"Division '{division}' not found in {matching_code}"}

    division_data = divisions[matching_division]
    articles = division_data.get("articles", {})

    if not articles:
        return {
            "code": matching_code,
            "division": matching_division,
            "url": division_data.get("url", ""),
            "articles": [],
            "note": "No articles found, returning division URL"
        }

    if not article:
        return {
            "code": matching_code,
            "division": matching_division,
            "articles": list(articles.keys()),
            "note": "No article specified, returning list of articles, choose one to get URL"
        }

    matching_article = None
    for art_key in articles.keys():
        if article.lower() in art_key.lower():
            matching_article = art_key
            break

    if not matching_article:
        return {
            "error": f"Article '{article}' not found in division '{matching_division}' of code '{matching_code}'"
        }

    return {
        "code": matching_code,
        "division": matching_division,
        "article": matching_article,
        "url": articles[matching_article],
        "total_articles": len(articles)
    }

async def query_master_json(code: str, division: str, article: str = None, directory: str = CALIFORNIA_CODE_DIR) -> Dict[str, Any]:
    master_data = _load_master_data(directory)
    if not master_data:
        return {"error": "master_expanded.json not found"}

    try:
        codes_db = master_data.get("codes", {})
        resolved = _resolve_query(codes_db, code, division, article)
        if "error" in resolved or "url" not in resolved or "article" not in resolved:
            return resolved

        article_url = resolved["url"]
        article_content = await fetch_webpage_content(article_url)

        if "error" in article_content:
            return {
                "error": f"Error fetching article content: {article_content['error']}"
            }

        resolved["content"] = article_content["text"]
        return resolved

    except Exception as e:
        logger.exception(
            "California code query failed",
            extra={
                "event": "code_query_failed",
                "code": code,
                "division": division,
                "article": article,
            },
        )
        return {"error": f"Error querying master.json: {str(e)}"}

async def multi_query_master_json(queries: List[Dict[str, str]], directory: str = CALIFORNIA_CODE_DIR) -> Dict[str, Any]:
    results = {}

    master_data = _load_master_data(directory)
    if not master_data:
        return {"error": "master_expanded.json not found"}

    codes_db = master_data.get("codes", {})
    pending = []

    for query in queries:
        code = query.get("code")
        division = query.get("division")
        article = query.get("article", None)

        query_key = f"{code}_{division}_{article if article else 'no_article'}"
        if not code or not division:
            results[query_key] = {"error": "Each query requires code and division"}
            continue

        resolved = _resolve_query(codes_db, code, division, article)
        if "error" in resolved:
            results[query_key] = resolved
            continue

        if "url" in resolved and "article" in resolved:
            pending.append((query_key, resolved["url"], resolved))
            continue

        results[query_key] = resolved

    if not pending:
        return results

    request_tasks = [fetch_webpage_content_with_requests(url) for _, url, _ in pending]
    request_results = await asyncio.gather(*request_tasks)

    failed_entries = []

    for idx, request_result in enumerate(request_results):
        query_key, url, resolved = pending[idx]
        if "error" in request_result or not request_result.get("text"):
            failed_entries.append((query_key, url, resolved))
            continue

        resolved["content"] = request_result["text"]
        results[query_key] = resolved

    if failed_entries:
        playwright_urls = [url for _, url, _ in failed_entries]
        playwright_results = await fetch_multiple_webpage_content_with_playwright(playwright_urls)
        for query_key, url, resolved in failed_entries:
            playwright_result = playwright_results.get(url, {"error": "Playwright fetch failed"})
            if "error" in playwright_result or not playwright_result.get("text"):
                results[query_key] = {
                    "error": f"Error fetching article content: {playwright_result.get('error', 'Unknown fetch error')}"
                }
                continue
            resolved["content"] = playwright_result["text"]
            results[query_key] = resolved

    return results
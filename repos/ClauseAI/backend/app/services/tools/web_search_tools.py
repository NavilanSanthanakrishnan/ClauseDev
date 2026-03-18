import asyncio
import json
import logging
from typing import List, Dict, Any
from ddgs import DDGS
from app.core.config import WEB_SEARCH_MAX_RESULTS

logger = logging.getLogger(__name__)

def _web_search_ddg_result(query: str, max_results: int = WEB_SEARCH_MAX_RESULTS) -> Dict[str, Any]:
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return {
                "query": query,
                "results": [],
                "error": "No results found"
            }

        formatted_results = []
        for idx, result in enumerate(results, 1):
            formatted_results.append({
                "rank": idx,
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", "")
            })

        return {
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results
        }

    except Exception as e:
        logger.warning(
            "Web search failed",
            extra={"event": "web_search_failed", "query": query, "error": str(e)},
        )
        return {
            "query": query,
            "results": [],
            "error": f"Search failed: {str(e)}"
        }

def web_search_ddg(query: str, max_results: int = WEB_SEARCH_MAX_RESULTS) -> str:
    return json.dumps(_web_search_ddg_result(query, max_results))

async def multi_web_search_ddg(queries: List[str], max_results: int = WEB_SEARCH_MAX_RESULTS) -> str:
    tasks = [asyncio.to_thread(_web_search_ddg_result, query, max_results) for query in queries]
    search_results = await asyncio.gather(*tasks)
    aggregated_results = {query: result for query, result in zip(queries, search_results)}
    return json.dumps(aggregated_results)
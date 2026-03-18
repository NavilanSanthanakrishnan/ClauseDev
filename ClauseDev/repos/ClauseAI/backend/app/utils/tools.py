from typing import Dict, Any, List

CALIFORNIA_CODE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "multi_query_master_json",
        "description": "Query the California Code database to get article URLs. Given a list of queries, each with code, division, and optional article, return the content for each query.",
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Code abbreviation (e.g., 'PEN', 'HSC', 'GOV')"
                            },
                            "division": {
                                "type": "string",
                                "description": "Division name within the code"
                            },
                            "article": {
                                "type": "string",
                                "description": "Article name within the division (optional), do this after getting the list of articles given the code and division"
                            }
                        },
                        "required": ["code", "division"]
                    }
                }
            },
            "required": ["queries"]
        }
    }
}

WEB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "multi_web_search_ddg",
        "description": "Search the web using DuckDuckGo to find information about companies, industries, stakeholders, trade associations, lobby groups, and their policy positions. Use this to identify who would oppose/support the bill, find major industry players, and research their stances on similar legislation.",
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of search query strings"
                }
            },
            "required": ["queries"]
        }
    }
}

def get_conflict_analysis_tools() -> List[Dict[str, Any]]:
    return [CALIFORNIA_CODE_TOOL_SCHEMA]

def get_stakeholder_analysis_tools() -> List[Dict[str, Any]]:
    return [WEB_SEARCH_TOOL_SCHEMA]
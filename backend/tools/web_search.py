import os

from backend.schema import WebSearchHit, WebSearchResult


def web_search(query: str, max_results: int = 5) -> WebSearchResult:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return WebSearchResult(query=query, success=False, error="TAVILY_API_KEY not set in .env")

    from tavily import TavilyClient  # imported lazily so the module loads without the dependency installed

    try:
        client = TavilyClient(api_key=api_key)
        resp = client.search(query=query, max_results=max_results)
    except Exception as e:
        return WebSearchResult(query=query, success=False, error=str(e))

    hits = [
        WebSearchHit(title=r.get("title", ""), url=r.get("url", ""), snippet=(r.get("content", "") or "")[:500])
        for r in resp.get("results", [])
    ]
    return WebSearchResult(query=query, success=True, hits=hits)


if __name__ == "__main__":
    import sys

    result = web_search(sys.argv[1] if len(sys.argv) > 1 else "phishtrace hackathon")
    print(result.model_dump_json(indent=2))

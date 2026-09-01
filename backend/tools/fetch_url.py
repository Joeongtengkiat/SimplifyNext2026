import requests
from bs4 import BeautifulSoup

from backend.schema import FetchUrlResult

TEXT_EXCERPT_LIMIT = 5000  # keep tool results small so the agent's context doesn't fill with page dumps


def fetch_url(url: str, timeout: int = 10) -> FetchUrlResult:
    original = url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        resp = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "PhishTrace/0.1 (security research; contact via project README)"},
        )
    except requests.RequestException as e:
        return FetchUrlResult(requested_url=original, success=False, error=str(e))

    redirect_chain = [r.url for r in resp.history]

    # parse raw bytes, not resp.text -- BeautifulSoup's encoding sniffing (meta tags, BOM) is
    # more reliable than requests' guess, which mojibakes pages that omit a charset header
    soup = BeautifulSoup(resp.content, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else None

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())[:TEXT_EXCERPT_LIMIT]

    return FetchUrlResult(
        requested_url=original,
        success=True,
        final_url=resp.url,
        redirect_chain=redirect_chain,
        status_code=resp.status_code,
        title=title,
        text_excerpt=text,
    )


if __name__ == "__main__":
    import sys

    result = fetch_url(sys.argv[1] if len(sys.argv) > 1 else "https://www.wikipedia.org")
    output = result.model_dump_json(indent=2)[:1000]
    sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))

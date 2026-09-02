import tldextract


def registrable_domain(raw: str) -> str:
    """Resolves whatever was passed in (a bare domain, a subdomain, or a full URL with a path)
    down to the actual registrable domain -- e.g. "secure.paypal-verify.tk/login" ->
    "paypal-verify.tk". Shared by check_domain (RDAP lookups fail on anything else) and the
    trust list (so "www.example.com" and "example.com" resolve to the same entry)."""
    ext = tldextract.extract(raw)
    if not ext.domain or not ext.suffix:
        return raw.strip().lower().removeprefix("http://").removeprefix("https://").split("/")[0]
    return f"{ext.domain}.{ext.suffix}"

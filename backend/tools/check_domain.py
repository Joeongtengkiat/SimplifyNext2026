from datetime import datetime, timezone

import requests
import tldextract

from backend.schema import DomainCheckResult

RDAP_URL = "https://rdap.org/domain/{domain}"


def _registrable_domain(raw: str) -> str:
    """Resolves whatever the model passed (a bare domain, a subdomain, or a full URL with a
    path) down to the actual registrable domain -- e.g. "secure.paypal-verify.tk/login" ->
    "paypal-verify.tk". Looking up a subdomain or a URL-with-path against RDAP just fails, so
    this can't be left to the model to get right."""
    ext = tldextract.extract(raw)
    if not ext.domain or not ext.suffix:
        return raw.strip().lower().removeprefix("http://").removeprefix("https://").split("/")[0]
    return f"{ext.domain}.{ext.suffix}"


def check_domain(domain: str) -> DomainCheckResult:
    domain = _registrable_domain(domain)

    try:
        resp = requests.get(
            RDAP_URL.format(domain=domain),
            timeout=10,
            headers={"Accept": "application/rdap+json"},
        )
    except requests.RequestException as e:
        return DomainCheckResult(domain=domain, found=False, error=str(e))

    if resp.status_code != 200:
        return DomainCheckResult(
            domain=domain,
            found=False,
            error=f"RDAP lookup returned status {resp.status_code}",
        )

    data = resp.json()

    registration_date = next(
        (e.get("eventDate") for e in data.get("events", []) if e.get("eventAction") == "registration"),
        None,
    )

    age_days = None
    if registration_date:
        try:
            reg_dt = datetime.fromisoformat(registration_date.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - reg_dt).days
        except ValueError:
            pass

    registrar = None
    for entity in data.get("entities", []):
        if "registrar" not in entity.get("roles", []):
            continue
        vcard = entity.get("vcardArray")
        if not vcard or len(vcard) < 2:
            continue
        for field in vcard[1]:
            if field[0] == "fn":
                registrar = field[3]
                break

    return DomainCheckResult(
        domain=domain,
        found=True,
        registration_date=registration_date,
        age_days=age_days,
        registrar=registrar,
    )


if __name__ == "__main__":
    import sys

    result = check_domain(sys.argv[1] if len(sys.argv) > 1 else "wikipedia.org")
    print(result.model_dump_json(indent=2))

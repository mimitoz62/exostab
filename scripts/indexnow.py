"""Send the URLs of the documentation site to IndexNow (used by the docs workflow).

    python3 scripts/indexnow.py sitemap.xml

IndexNow (https://www.indexnow.org/documentation) lets search engines that take part learn of new and changed pages,
with no account. An engine checks the key against a file on the site: docs/<KEY>.txt, which mkdocs copies to the site
and which holds the key and nothing else. GitHub Pages serves this project under /exostab/, and nothing is served at
the root of the host, so each request names the file in keyLocation. Such a key covers only the URLs under its own
directory, and this script refuses a sitemap with any other URL.

The protocol asks for URLs that were added, updated or deleted. A weekly catalog changes all the system pages, because
each gives the catalog's date. The other pages go with them, although most weeks they have not changed, because a push
that changes one sends nothing.

HTTP 200 and 202 (key validation pending) confirm receipt and nothing more: each engine decides whether to crawl a
page. A failed call is not retried: the next run sends every URL again. The workflow runs this in a job of its own once
the site is deployed, so a failed call cannot fail the deployment. Standard library only, since that job installs
nothing.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HOST = "mimitoz62.github.io"
SITE = f"https://{HOST}/exostab/"  # site_url in mkdocs.yml
KEY = "0534dfea2baa48bbac28136a47286b49"  # not a secret: the site serves it
ENDPOINT = "https://api.indexnow.org/indexnow"  # shares what it receives with the engines that take part
BATCH = 10_000  # the protocol's limit for one POST
LOC = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"


def site_urls(sitemap: Path) -> list[str]:
    urls = [(loc.text or "").strip() for loc in ET.parse(sitemap).iter(LOC)]
    if not urls:
        raise SystemExit(f"No URLs in {sitemap}.")
    outside = [url for url in urls if not url.startswith(SITE)]
    if outside:
        raise SystemExit(f"{len(outside)} URLs in {sitemap} are not under {SITE}, for example {outside[0]}.")
    return urls


def submit(urls: list[str]) -> int:
    """POST one batch and return the HTTP status. Anything but a 200 or 202 from the endpoint stops the script."""
    payload = {"host": HOST, "key": KEY, "keyLocation": f"{SITE}{KEY}.txt", "urlList": urls}
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "exostab docs workflow (https://github.com/mimitoz62/exostab)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            status, url = int(response.status), response.geturl()
    except urllib.error.HTTPError as error:
        with error:
            body = error.read(500).decode("utf-8", "replace")
        raise SystemExit(f"POST {ENDPOINT} -> HTTP {error.code}: {body}") from error
    # urllib follows a 301, 302 or 303 with a GET that has no body, so the URLs would not have arrived.
    if status not in (200, 202) or url != ENDPOINT:
        raise SystemExit(f"POST {ENDPOINT} -> HTTP {status} from {url}: not a receipt.")
    return status


def main() -> None:
    urls = site_urls(Path(sys.argv[1]))
    for start in range(0, len(urls), BATCH):
        batch = urls[start : start + BATCH]
        print(f"IndexNow received {len(batch):,} URLs (HTTP {submit(batch)})")


if __name__ == "__main__":
    main()

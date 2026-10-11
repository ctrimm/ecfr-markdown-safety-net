"""Minimal client for the eCFR versioner API (https://www.ecfr.gov/developers/documentation/api/v1).

Standard library only. The full-text endpoint requires a compressed response,
so every request asks for gzip and decompresses it here.
"""
from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.ecfr.gov/api/versioner/v1"
DEFAULT_UA = "ecfr-markdown (https://github.com/ctrimm/ecfr-markdown)"


class Client:
    def __init__(self, user_agent: str = DEFAULT_UA, retries: int = 4, pause: float = 0.5):
        self.user_agent, self.retries, self.pause = user_agent, retries, pause

    def _get(self, path: str, params: dict | None = None, accept: str = "application/json") -> bytes:
        url = f"{API}/{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": accept,
                                                   "Accept-Encoding": "gzip"})
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        data = gzip.decompress(data)
                    time.sleep(self.pause)  # be polite to the public API
                    return data
            except urllib.error.HTTPError as e:
                if e.code in (400, 404) or attempt == self.retries - 1:
                    raise
            except urllib.error.URLError:
                if attempt == self.retries - 1:
                    raise
            time.sleep(2 * (attempt + 1))
        raise RuntimeError("unreachable")

    def titles(self) -> list[dict]:
        return json.loads(self._get("titles.json"))["titles"]

    def latest_date(self, title: int | str) -> str:
        """The date the title is up to date as of (use it for 'current')."""
        for t in self.titles():
            if str(t["number"]) == str(title):
                return t["up_to_date_as_of"]
        raise KeyError(f"title {title} not found")

    def versions(self, title: int | str, part: str) -> list[dict]:
        """Every amendment of every section in the part: [{identifier, date, ...}]."""
        return json.loads(self._get(f"versions/title-{title}.json", {"part": part}))["content_versions"]

    def full_xml(self, title: int | str, date: str, part: str) -> bytes:
        """The part's full text as eCFR XML on `date` (YYYY-MM-DD)."""
        return self._get(f"full/{date}/title-{title}.xml", {"part": part}, accept="application/xml")

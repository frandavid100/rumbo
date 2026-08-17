from __future__ import annotations

import time
from urllib.error import HTTPError

import compare_aesan_2022_current_evidence as comparison

_original_fetch_off = comparison.fetch_off_product


def _rate_limited_fetch_off(gtin: str, *, timeout: float = 15.0):
    # OFF is intentionally queried gently: this validation has only 33 GTINs and
    # accuracy matters more than speed. Retry 429 without changing evidence rules.
    time.sleep(0.8)
    for attempt in range(4):
        try:
            return _original_fetch_off(gtin, timeout=timeout)
        except HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


comparison.fetch_off_product = _rate_limited_fetch_off

if __name__ == "__main__":
    raise SystemExit(comparison.main())

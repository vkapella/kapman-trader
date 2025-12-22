from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import date
from typing import Any, AsyncIterator, Awaitable, Callable, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from core.ingestion.options.normalizer import NormalizedOptionContract, normalize_unicorn_contracts

logger = logging.getLogger(__name__)

_SAFE_FIELDS = (
    "contract,underlying_symbol,exp_date,type,strike,bid,ask,last,volume,open_interest,"
    "volatility,delta,gamma,theta,vega,tradetime,bid_date,ask_date,dte"
)


def _safe_url_for_logs(url: str) -> str:
    parsed = urlparse(url)
    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        redacted = "REDACTED" if key.lower() in {"api_token", "apikey", "token"} else value
        query_pairs.append((key, redacted))
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query_pairs),
            parsed.fragment,
        )
    )


class UnicornOptionsProvider:
    name = "unicorn"

    def __init__(
        self,
        api_token: Optional[str] = None,
        base_url: str = "https://eodhd.com/api/mp/unicornbay",
        max_retries: int = 3,
        request_timeout: float = 20.0,
        page_limit: int = 1000,
    ) -> None:
        self.api_token = api_token or os.getenv("UNICORN_API_TOKEN") or os.getenv("UNICORN_API_KEY") or os.getenv("EODHD_API_TOKEN")
        if not self.api_token:
            raise RuntimeError("UNICORN_API_TOKEN is not set")

        self.base_url = base_url.rstrip("/")
        self.max_retries = max(1, int(max_retries))
        self.request_timeout = float(request_timeout)
        self.page_limit = 1000

    def normalize_results(
        self,
        raw_results: list[dict[str, Any]],
        *,
        snapshot_date: date,
    ) -> list[NormalizedOptionContract]:
        return normalize_unicorn_contracts(raw_results, snapshot_date=snapshot_date)

    async def fetch_options_snapshot_chain(
        self,
        underlying: str,
        *,
        snapshot_date: date,
        client: Optional[httpx.AsyncClient] = None,
        on_page: Callable[[int], Awaitable[None]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        symbol = str(underlying).strip().upper()
        if not symbol:
            raise ValueError("underlying symbol must be non-empty")

        url = f"{self.base_url}/options/contracts"
        params = {
            "filter[underlying_symbol]": symbol,
            "filter[exp_date_from]": snapshot_date.isoformat(),
            "page[limit]": self.page_limit,
            "page[offset]": 0,
            "fields[options-contracts]": _SAFE_FIELDS,
            "api_token": self.api_token,
        }

        logger.info(
            "Unicorn options fetch started",
            extra={
                "stage": "provider",
                "symbol": symbol,
                "url": url,
                "page_limit": self.page_limit,
            },
        )

        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=self.request_timeout)
        assert client is not None

        page = 0
        total_results = 0
        next_url: str | None = None

        try:
            while True:
                request_url = next_url or url
                query = None if next_url else params

                attempts = 0
                while True:
                    attempts += 1
                    try:
                        response = await client.get(request_url, params=query)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:  # pragma: no cover - surfaced upstream
                        logger.error(
                            "Unicorn options request failed",
                            extra={
                                "stage": "provider",
                                "symbol": symbol,
                                "page": page + 1,
                                "url": request_url,
                                "root_cause": type(exc).__name__,
                            },
                        )
                        raise

                    status = int(response.status_code)
                    if status in (429,) or status >= 500:
                        will_retry = attempts < self.max_retries
                        logger.warning(
                            "Unicorn options request retrying",
                            extra={
                                "stage": "provider",
                                "symbol": symbol,
                                "page": page + 1,
                                "url": _safe_url_for_logs(str(response.request.url)),
                                "status_code": status,
                                "attempt": attempts,
                                "will_retry": will_retry,
                            },
                        )
                        if not will_retry:
                            response.raise_for_status()
                        backoff = min(30.0, 0.5 * (2 ** (attempts - 1))) + random.uniform(0, 0.25)
                        await asyncio.sleep(backoff)
                        continue

                    if status >= 400:
                        logger.error(
                            "Unicorn options request failed",
                            extra={
                                "stage": "provider",
                                "symbol": symbol,
                                "page": page + 1,
                                "url": _safe_url_for_logs(str(response.request.url)),
                                "status_code": status,
                                "root_cause": f"http_{status}",
                            },
                        )
                        response.raise_for_status()

                    try:
                        payload: Any = response.json()
                    except ValueError as exc:  # pragma: no cover - defensive
                        logger.error(
                            "Unicorn options response not JSON",
                            extra={
                                "stage": "provider",
                                "symbol": symbol,
                                "page": page + 1,
                                "url": _safe_url_for_logs(str(response.request.url)),
                                "status_code": status,
                            },
                        )
                        raise

                    if not isinstance(payload, dict):
                        logger.error(
                            "Unicorn options response schema invalid",
                            extra={
                                "stage": "provider",
                                "symbol": symbol,
                                "page": page + 1,
                                "url": _safe_url_for_logs(str(response.request.url)),
                                "status_code": status,
                                "root_cause": "invalid_schema",
                            },
                        )
                        raise ValueError("Unicorn options response schema invalid")

                    data = payload.get("data") if isinstance(payload.get("data"), list) else []
                    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
                    links = payload.get("links") if isinstance(payload.get("links"), dict) else {}

                    page += 1
                    logger.debug(
                        "Unicorn options page received",
                        extra={
                            "stage": "provider",
                            "symbol": symbol,
                            "page": page,
                            "url": _safe_url_for_logs(str(response.request.url)),
                            "results_count": len(data),
                            "total": meta.get("total"),
                            "offset": meta.get("offset"),
                        },
                    )

                    valid_rows = [r for r in data if isinstance(r, dict)]
                    total_results += len(valid_rows)

                    if on_page is not None:
                        await on_page(len(valid_rows))

                    for row in valid_rows:
                        yield row

                    next_link = links.get("next")
                    if next_link:
                        parsed = httpx.URL(str(next_link))
                        params_next = dict(parsed.params)
                        params_next["api_token"] = self.api_token
                        params_next["page[limit]"] = self.page_limit
                        next_url = str(parsed.copy_with(params=params_next))
                        break

                    next_url = None
                    break

                if not next_url:
                    break
        finally:
            if owns_client:
                await client.aclose()

        logger.info(
            "Unicorn options pagination complete",
            extra={
                "stage": "provider",
                "symbol": symbol,
                "pages": page,
                "results_total": total_results,
                "url": url,
            },
        )

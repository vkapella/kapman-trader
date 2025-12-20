from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, AsyncIterator, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

_API_KEY_RE = re.compile(r"(?i)(apikey|api_key|access_token|token)=([^&\\s]+)")


def _redact_secrets(value: str) -> str:
    return _API_KEY_RE.sub(lambda m: f"{m.group(1)}=REDACTED", value)


def _strip_query(url: str) -> str:
    return url.split("?", 1)[0]


def _append_api_key_if_missing(url: str, api_key: str) -> str:
    if re.search(r"(?i)(^|[?&])apikey=", url):
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}apiKey={api_key}"


def _safe_url_for_logs(url: str) -> str:
    return _redact_secrets(_strip_query(str(url)))


def _extract_request_id(response: httpx.Response, payload: Any | None) -> str | None:
    for header in ("x-request-id", "x-request_id", "request-id", "request_id"):
        value = response.headers.get(header)
        if value:
            return str(value)
    if isinstance(payload, dict):
        req = payload.get("request_id") or payload.get("requestId")
        if req:
            return str(req)
    return None


class PolygonOptionsProvider:
    def __init__(
        self,
        api_key: Optional[str] = None,
        snapshots_base_url: str = "https://api.polygon.io/v3/snapshot/options",
        max_retries: int = 3,
        request_timeout: float = 15.0,
    ) -> None:
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise RuntimeError("POLYGON_API_KEY is not set")

        self.snapshots_base_url = snapshots_base_url.rstrip("/")
        self.max_retries = int(max_retries)
        self.request_timeout = float(request_timeout)

    async def fetch_options_snapshot_chain(
        self,
        underlying: str,
        *,
        limit: int = 250,
        client: Optional[httpx.AsyncClient] = None,
    ) -> AsyncIterator[dict]:
        underlying = str(underlying).strip().upper()
        if not underlying:
            raise ValueError("underlying symbol must be non-empty")

        base_url = f"{self.snapshots_base_url}/{underlying}"
        origin = urlunsplit((urlsplit(self.snapshots_base_url).scheme, urlsplit(self.snapshots_base_url).netloc, "", "", ""))

        logger.info(
            "Polygon snapshot fetch started",
            extra={
                "stage": "provider",
                "symbol": underlying,
                "url": _safe_url_for_logs(base_url),
                "limit": int(limit),
            },
        )

        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=self.request_timeout)
        assert client is not None

        page = 0
        total_results = 0
        first_page_logged = False
        next_url: str | None = base_url

        try:
            while next_url:
                page += 1
                request_url = next_url
                if request_url != base_url:
                    request_url = urljoin(origin + "/", request_url)
                    request_url = _append_api_key_if_missing(request_url, self.api_key)

                params = {"apiKey": self.api_key, "limit": int(limit)} if request_url == base_url else None

                attempts = 0
                while True:
                    attempts += 1
                    try:
                        response = await client.get(request_url, params=params)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.error(
                            "Polygon snapshot request failed",
                            extra={
                                "stage": "provider",
                                "symbol": underlying,
                                "page": page,
                                "url": _safe_url_for_logs(request_url),
                                "root_cause": type(exc).__name__,
                            },
                        )
                        raise

                    status = int(response.status_code)
                    payload: Any | None = None
                    request_id: str | None = None

                    is_json = "application/json" in (response.headers.get("content-type") or "").lower()
                    if is_json:
                        try:
                            payload = response.json()
                        except ValueError:
                            payload = None
                    request_id = _extract_request_id(response, payload)

                    if status == 401 or status == 403:
                        logger.error(
                            "Polygon snapshot request rejected",
                            extra={
                                "stage": "provider",
                                "symbol": underlying,
                                "page": page,
                                "url": _safe_url_for_logs(request_url),
                                "status_code": status,
                                "request_id": request_id,
                                "root_cause": f"http_{status}",
                            },
                        )
                        response.raise_for_status()

                    if status == 429 or status >= 500:
                        will_retry = attempts < max(1, self.max_retries)
                        logger.warning(
                            "Polygon snapshot request failed (retryable)",
                            extra={
                                "stage": "provider",
                                "symbol": underlying,
                                "page": page,
                                "url": _safe_url_for_logs(request_url),
                                "status_code": status,
                                "request_id": request_id,
                                "attempt": attempts,
                                "will_retry": will_retry,
                                "root_cause": f"http_{status}",
                            },
                        )
                        if not will_retry:
                            response.raise_for_status()
                        await asyncio.sleep(min(10.0, 0.5 * (2 ** (attempts - 1))))
                        continue

                    if status >= 400:
                        logger.error(
                            "Polygon snapshot request failed",
                            extra={
                                "stage": "provider",
                                "symbol": underlying,
                                "page": page,
                                "url": _safe_url_for_logs(request_url),
                                "status_code": status,
                                "request_id": request_id,
                                "root_cause": f"http_{status}",
                            },
                        )
                        response.raise_for_status()

                    if not isinstance(payload, dict):
                        logger.error(
                            "Polygon snapshot response schema invalid",
                            extra={
                                "stage": "provider",
                                "symbol": underlying,
                                "page": page,
                                "url": _safe_url_for_logs(request_url),
                                "status_code": status,
                                "request_id": request_id,
                                "root_cause": "invalid_schema",
                            },
                        )
                        raise ValueError("Polygon snapshot response schema invalid: expected JSON object")

                    results = payload.get("results")
                    if results is None:
                        results = []
                    if not isinstance(results, list):
                        logger.error(
                            "Polygon snapshot response schema invalid",
                            extra={
                                "stage": "provider",
                                "symbol": underlying,
                                "page": page,
                                "url": _safe_url_for_logs(request_url),
                                "status_code": status,
                                "request_id": request_id,
                                "root_cause": "invalid_schema",
                            },
                        )
                        raise ValueError("Polygon snapshot response schema invalid: results must be a list")

                    if not first_page_logged:
                        first_page_logged = True
                        logger.info(
                            "Polygon snapshot first page received",
                            extra={
                                "stage": "provider",
                                "symbol": underlying,
                                "page": page,
                                "url": _safe_url_for_logs(request_url),
                                "status_code": status,
                                "request_id": request_id,
                                "results_count": len(results),
                            },
                        )

                    valid_rows = [r for r in results if isinstance(r, dict)]
                    total_results += len(valid_rows)

                    logger.debug(
                        "Polygon snapshot page received",
                        extra={
                            "stage": "provider",
                            "symbol": underlying,
                            "page": page,
                            "url": _safe_url_for_logs(request_url),
                            "status_code": status,
                            "request_id": request_id,
                            "results_count": len(valid_rows),
                            "total_results": total_results,
                        },
                    )

                    for row in valid_rows:
                        yield row

                    next_value = payload.get("next_url")
                    next_url = str(next_value).strip() if next_value else None
                    break

        finally:
            if owns_client:
                await client.aclose()

        logger.info(
            "Polygon snapshot pagination complete",
            extra={
                "stage": "provider",
                "symbol": underlying,
                "pages": page,
                "results_total": total_results,
                "url": _safe_url_for_logs(base_url),
            },
        )


import asyncio
import logging
import os
from datetime import date
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class PolygonOptionsProvider:
    """
    Lightweight Polygon REST client focused on fetching raw options chain data.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.polygon.io/v3/snapshot/options",
        max_retries: int = 3,
        request_timeout: int = 15,
    ):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise RuntimeError("POLYGON_API_KEY is not set")
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.request_timeout = request_timeout

    async def _fetch_page(
        self, client: httpx.AsyncClient, url: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        attempts = 0
        while True:
            attempts += 1
            try:
                response = await client.get(url, params=params)
                if response.status_code in (429,) or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "Transient error", request=response.request, response=response
                    )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as exc:
                should_retry = attempts < self.max_retries
                logger.warning(
                    "Polygon options request failed",
                    extra={
                        "stage": "provider",
                        "symbol": params.get("underlying_ticker") or params.get("symbol"),
                        "status": "timeout",
                        "error_type": "timeout",
                        "error_message": str(exc),
                        "attempt": attempts,
                        "will_retry": should_retry,
                    },
                )
                if not should_retry:
                    raise
                await asyncio.sleep(1 * attempts)
            except httpx.HTTPStatusError as exc:
                should_retry = attempts < self.max_retries
                logger.warning(
                    "Polygon options request failed",
                    extra={
                        "stage": "provider",
                        "symbol": params.get("underlying_ticker") or params.get("symbol"),
                        "status": exc.response.status_code,
                        "error_type": "http_error",
                        "error_message": str(exc),
                        "attempt": attempts,
                        "will_retry": should_retry,
                    },
                )
                if not should_retry:
                    raise
                await asyncio.sleep(1 * attempts)

    async def get_options_chain(
        self, symbol: str, as_of_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the full options chain for a symbol from Polygon REST.
        Returns raw payload rows without transformation.
        """
        params: Dict[str, Any] = {
            "underlying_ticker": symbol,
            "apiKey": self.api_key,
        }
        if as_of_date:
            params["as_of"] = as_of_date.isoformat()

        results: List[Dict[str, Any]] = []
        next_url: Optional[str] = f"{self.base_url}/{symbol}"
        request_count = 0

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            while next_url:
                request_count += 1
                page = await self._fetch_page(client, next_url, params)
                page_results = page.get("results") or []
                results.extend(page_results)

                logger.info(
                    "Fetched Polygon options page",
                    extra={
                        "stage": "provider",
                        "symbol": symbol,
                        "request_count": request_count,
                        "pagination_progress": len(results),
                    },
                )

                # Polygon pagination typically returns next_url when more data exists
                next_url = page.get("next_url")
                # When next_url is present, Polygon expects apiKey in the next request as well
                if next_url and "apiKey" not in next_url:
                    params["cursor"] = page.get("cursor")
                else:
                    params.pop("cursor", None)

        return results

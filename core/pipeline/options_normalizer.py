import logging
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


def _parse_expiration(raw: Dict[str, Any]) -> Optional[date]:
    exp = (
        raw.get("expiration_date")
        or raw.get("expirationDate")
        or raw.get("exp_date")
        or raw.get("expiration")
    )
    if not exp:
        return None
    try:
        return date.fromisoformat(str(exp))
    except ValueError:
        return None


def _parse_strike(raw: Dict[str, Any]) -> Optional[Decimal]:
    strike = raw.get("strike_price") or raw.get("strikePrice") or raw.get("strike")
    if strike is None:
        return None
    try:
        return Decimal(str(strike))
    except (InvalidOperation, ValueError):
        return None


def _classify_option_type(raw: Dict[str, Any]) -> Optional[str]:
    explicit = raw.get("option_type") or raw.get("type") or raw.get("contract_type")
    if explicit:
        lowered = str(explicit).lower()
        if lowered.startswith("c"):
            return "call"
        if lowered.startswith("p"):
            return "put"

    contract_symbol = raw.get("symbol") or raw.get("ticker")
    if contract_symbol:
        if "C" in contract_symbol and not explicit:
            return "call"
        if "P" in contract_symbol and not explicit:
            return "put"
    return None


def _extract_numeric(raw: Dict[str, Any], key: str) -> Optional[Decimal]:
    if key in raw:
        try:
            return Decimal(str(raw[key]))
        except (InvalidOperation, ValueError):
            return None
    return None


def _normalize_row(raw: Dict[str, Any], symbol: str, as_of: date) -> Optional[Dict[str, Any]]:
    expiration = _parse_expiration(raw)
    strike = _parse_strike(raw)
    option_type = _classify_option_type(raw)

    if not expiration or strike is None or not option_type:
        return None

    as_of_ts = datetime.combine(as_of, time.min, tzinfo=timezone.utc)

    return {
        "symbol": symbol,
        "time": as_of_ts,
        "expiration_date": expiration,
        "strike_price": strike,
        "option_type": option_type,
        "bid": _extract_numeric(raw, "bid"),
        "ask": _extract_numeric(raw, "ask"),
        "last": _extract_numeric(raw, "last"),
        "volume": raw.get("volume"),
        "open_interest": raw.get("open_interest") or raw.get("openInterest"),
        "implied_volatility": _extract_numeric(raw, "implied_volatility")
        or _extract_numeric(raw, "impliedVolatility"),
        "delta": _extract_numeric(raw, "delta"),
        "gamma": _extract_numeric(raw, "gamma"),
        "theta": _extract_numeric(raw, "theta"),
        "vega": _extract_numeric(raw, "vega"),
        "oi_change": raw.get("oi_change"),
        "volume_oi_ratio": _extract_numeric(raw, "volume_oi_ratio"),
        "moneyness": raw.get("moneyness"),
    }


def normalize_contracts(
    raw_contracts: Iterable[Dict[str, Any]], symbol: str, as_of: date
) -> List[Dict[str, Any]]:
    """
    Normalize raw Polygon contracts into the internal options chain shape.
    """
    normalized: List[Dict[str, Any]] = []
    dropped = 0
    raw_list = list(raw_contracts)

    for raw in raw_list:
        mapped = _normalize_row(raw, symbol, as_of)
        if mapped:
            normalized.append(mapped)
        else:
            dropped += 1

    logger.info(
        "Normalized options contracts",
        extra={
            "stage": "normalize",
            "symbol": symbol,
            "raw": len(raw_list),
            "normalized": len(normalized),
            "dropped": dropped,
        },
    )
    return normalized

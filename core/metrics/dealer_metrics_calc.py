from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


# Defaults aligned with the authoritative research input
DEFAULT_WALLS_TOP_N = 3
DEFAULT_GEX_SLOPE_RANGE_PCT = 0.02
DEFAULT_MAX_MONEYNESS = 0.2


@lru_cache(maxsize=1)
def _authoritative_dealer_module():
    """
    Dynamically import the authoritative dealer metrics reference from
    docs/research_inputs/dealer_metrics.py.
    """
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "docs" / "research_inputs" / "dealer_metrics.py"
    spec = importlib.util.spec_from_file_location("kapman_dealer_metrics_ref", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to import dealer metrics reference at {mod_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def build_option_contract(
    *,
    strike: float,
    option_type: str,
    gamma: Optional[float],
    delta: Optional[float],
    open_interest: int,
    volume: int,
    iv: Optional[float],
    dte: int,
):
    module = _authoritative_dealer_module()
    return module.OptionContract(
        strike=float(strike),
        contract_type=option_type.lower(),
        gamma=gamma,
        delta=delta,
        open_interest=int(open_interest),
        volume=int(volume),
        iv=iv,
        dte=int(dte),
    )


@dataclass(frozen=True)
class DealerComputationResult:
    gex_total: Optional[float]
    gex_net: Optional[float]
    gamma_flip: Optional[float]
    call_walls: List[Dict[str, Any]]
    put_walls: List[Dict[str, Any]]
    gex_slope: Optional[float]
    dgpi: Optional[float]
    position: str
    confidence: str
    strike_gex: Dict[float, float]


def calculate_metrics(
    contracts: Sequence[Any],
    *,
    spot: float,
    walls_top_n: int = DEFAULT_WALLS_TOP_N,
    gex_slope_range_pct: float = DEFAULT_GEX_SLOPE_RANGE_PCT,
    max_moneyness: float = DEFAULT_MAX_MONEYNESS,
    iv_rank: Optional[float] = None,
) -> DealerComputationResult:
    """
    Compute dealer metrics using the authoritative reference functions.
    """
    module = _authoritative_dealer_module()

    if not contracts or spot is None or spot <= 0:
        return DealerComputationResult(
            gex_total=None,
            gex_net=None,
            gamma_flip=None,
            call_walls=[],
            put_walls=[],
            gex_slope=None,
            dgpi=None,
            position="unknown",
            confidence="invalid",
            strike_gex={},
        )

    strike_gex = module.calculate_strike_gex(list(contracts), spot)
    if not strike_gex:
        return DealerComputationResult(
            gex_total=None,
            gex_net=None,
            gamma_flip=None,
            call_walls=[],
            put_walls=[],
            gex_slope=None,
            dgpi=None,
            position="unknown",
            confidence="invalid",
            strike_gex={},
        )

    gex_total = sum(abs(v) for v in strike_gex.values())
    gex_net = sum(strike_gex.values())

    gamma_flip = module.find_gamma_flip(strike_gex)
    call_walls = module.find_walls(
        list(contracts),
        "call",
        spot,
        top_n=walls_top_n,
        max_moneyness=max_moneyness,
    )
    put_walls = module.find_walls(
        list(contracts),
        "put",
        spot,
        top_n=walls_top_n,
        max_moneyness=max_moneyness,
    )
    gex_slope = module.calculate_gex_slope(strike_gex, spot, range_pct=gex_slope_range_pct)
    dgpi = module.calculate_dgpi(gex_net, gex_slope, iv_rank)
    position = module.determine_position(gex_net)
    confidence = module.determine_confidence(list(contracts))

    return DealerComputationResult(
        gex_total=round(gex_total, 2) if gex_total or gex_total == 0 else None,
        gex_net=round(gex_net, 2) if gex_net or gex_net == 0 else None,
        gamma_flip=gamma_flip,
        call_walls=call_walls,
        put_walls=put_walls,
        gex_slope=gex_slope,
        dgpi=dgpi,
        position=position,
        confidence=confidence,
        strike_gex=strike_gex,
    )


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize objects for JSON serialization (no NaN/inf).
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, (int, str, bool)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return float(obj)
    try:
        if hasattr(obj, "item"):
            return sanitize_for_json(obj.item())
    except Exception:
        pass
    return obj

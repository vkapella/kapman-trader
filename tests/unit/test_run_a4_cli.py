from datetime import date

from core.metrics.a4_volatility_metrics_job import _should_emit_heartbeat
from scripts.run_a4_volatility_metrics import _resolve_verbosity, build_parser


def test_date_flag_takes_precedence_over_range() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--date",
            "2025-01-01",
            "--start-date",
            "2024-12-01",
            "--end-date",
            "2024-12-31",
        ]
    )
    assert args.date == date(2025, 1, 1)
    assert args.start_date == date(2024, 12, 1)
    assert args.end_date == date(2024, 12, 31)


def test_resolve_verbosity_debug_implies_verbose() -> None:
    debug, verbose = _resolve_verbosity(verbose_flag=False, debug_flag=True, quiet_flag=False)
    assert debug is True
    assert verbose is True


def test_resolve_verbosity_quiet_suppresses_levels() -> None:
    debug, verbose = _resolve_verbosity(verbose_flag=True, debug_flag=True, quiet_flag=True)
    assert debug is False
    assert verbose is False


def test_heartbeat_helper_triggers_at_interval() -> None:
    assert _should_emit_heartbeat(processed=3, heartbeat_every=3) is True
    assert _should_emit_heartbeat(processed=2, heartbeat_every=3) is False

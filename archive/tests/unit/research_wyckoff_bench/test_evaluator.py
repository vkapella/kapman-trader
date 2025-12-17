import pandas as pd

from research.wyckoff_bench.harness import evaluator


def test_evaluator_computes_forward_returns():
    price_df = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 10,
            "time": pd.date_range("2023-01-01", periods=10, freq="D"),
            "open": [10 + i for i in range(10)],
            "high": [10.5 + i for i in range(10)],
            "low": [9.5 + i for i in range(10)],
            "close": [10 + i for i in range(10)],
            "volume": [1_000_000 + i * 1000 for i in range(10)],
        }
    )
    signals_df = pd.DataFrame(
        [
            {
                "impl": "stub",
                "symbol": "AAPL",
                "time": price_df.loc[1, "time"],
                "event_sc": False,
                "event_ar": False,
                "event_st": False,
                "event_spring": False,
                "event_test": False,
                "event_sos": True,
                "event_bc": False,
                "event_sow": False,
                "bc_score": 10.0,
                "spring_score": 0.0,
                "composite_score": 5.0,
            }
        ]
    )

    evaluated_df, summary_df, directional_summary_df = evaluator.evaluate_signals(signals_df, price_df, horizons=(2,))
    assert not evaluated_df.empty
    row = evaluated_df.iloc[0]
    assert row["event"] == "SOS"
    assert row["direction"] == "UP"
    assert row["horizon"] == 2
    assert summary_df.iloc[0]["count"] == 1
    assert summary_df.iloc[0]["mean_return"] > 0
    assert directional_summary_df.iloc[0]["signal_count"] == 1

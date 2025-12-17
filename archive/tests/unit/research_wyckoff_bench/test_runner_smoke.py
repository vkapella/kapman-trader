from datetime import datetime

import pandas as pd

from research.wyckoff_bench.harness import runner
from research.wyckoff_bench.harness.contract import EventCode, ScoreName, WyckoffSignal


class StubImpl:
    name = "stub_impl"

    def analyze(self, df_symbol, cfg):
        when = pd.to_datetime(df_symbol.iloc[-1]["time"]).to_pydatetime()
        return [
            WyckoffSignal(
                symbol=df_symbol.iloc[-1]["symbol"],
                time=when,
                events={EventCode.SC: True},
                scores={ScoreName.SPRING_SCORE: 10.0, ScoreName.COMPOSITE_SCORE: 10.0},
                debug={"note": "stub"},
            )
        ]


def test_runner_smoke(monkeypatch, tmp_path):
    price_df = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 5,
            "time": pd.date_range("2023-01-01", periods=5, freq="D"),
            "open": [10, 11, 12, 13, 14],
            "high": [10.5, 11.5, 12.5, 13.5, 14.5],
            "low": [9.5, 10.5, 11.5, 12.5, 13.5],
            "close": [10, 11, 12, 13, 14],
            "volume": [1_000_000] * 5,
        }
    )

    monkeypatch.setattr(runner, "load_ohlcv", lambda *a, **k: price_df)
    monkeypatch.setattr(runner, "select_implementations", lambda names: [StubImpl()])
    monkeypatch.setattr(
        runner,
        "evaluator",
        type(
            "EvalStub",
            (),
            {
                "evaluate_signals": lambda signals_df, price_df, **kwargs: (
                    pd.DataFrame({"impl": ["stub"], "event": ["SC"]}),
                    pd.DataFrame(),
                    pd.DataFrame(),
                )
            },
        ),
    )

    signals_df, price_df_out, signals_path, summary_path, comparison_path = runner.run_benchmark(
        ["AAPL"], impl_names=["stub_impl"], output_dir=tmp_path, run_id="test"
    )

    assert signals_path.exists()
    assert summary_path.exists()
    assert comparison_path.exists()
    assert not signals_df.empty
    assert len(price_df_out) == len(price_df)

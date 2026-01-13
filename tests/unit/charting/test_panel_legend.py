import pytest

from scripts.util.generate_ohlcv_ta_chart_pack import _apply_panel_legend


def test_panel_scoped_legend_generation() -> None:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([0, 1], [1, 2], label="Line A")
    ax.plot([0, 1], [2, 1], label="Line B")
    ax.plot([0, 1], [0, 0], label="Line A")

    _apply_panel_legend(ax)
    legend = ax.get_legend()
    assert legend is not None
    labels = [text.get_text() for text in legend.get_texts()]
    assert labels == ["Line A", "Line B"]
    plt.close(fig)

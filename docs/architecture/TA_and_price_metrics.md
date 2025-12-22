# TA and Price Metrics

## Overview
KapMan A2 writes price metrics (`price_metrics_json`) and technical indicators (`technical_indicators_json`) into `daily_snapshots` for each ticker/date. These metrics are consumed by Wyckoff logic, dashboards, and downstream scoring to contextualize trend, momentum, volatility, and volume. Outputs are deterministic: every key is emitted with `null` when unavailable.

## Price Metrics (price_metrics_json)
- `rvol` (float | null): Relative volume = latest volume divided by prior-window mean volume; unitless ratio. Source: OHLCV history up to the snapshot date. Missing when insufficient history or volume is zero/NaN.
- `vsi` (float | null): Volume Surprise Index = (latest volume − prior-window mean) / prior-window std; unitless z-score. Source: same OHLCV window as `rvol`. Missing when prior std is zero/invalid or history is insufficient.
- `hv` (float | null): Historical volatility = std of log returns over the window annualized by sqrt(252); units: annualized volatility. Source: OHLCV closes. Missing when close history is insufficient or std is invalid.

## Technical Analysis Metrics (technical_indicators_json)
Values are grouped by category; each indicator emits the listed JSON keys. Outputs are floats unless noted; `null` denotes insufficient data or computation failure. Interpretation is standard for each indicator (higher/lower reflects stronger/weaker signal as described).

### Momentum
- `awesome_oscillator.awesome_oscillator`: Midpoint momentum; positive = upward momentum, negative = downward.
- `kama.kama`: Kaufman adaptive moving average; tracks price with volatility sensitivity.
- `ppo.{ppo, ppo_signal, ppo_hist}`: Percentage Price Oscillator and signal/histogram; above/below zero shows bullish/bearish momentum; histogram divergence indicates momentum shifts.
- `pvo.{pvo, pvo_signal, pvo_hist}`: Percentage Volume Oscillator equivalents on volume; gauges volume momentum; histogram divergence shows volume trend shifts.
- `roc.roc`: Rate of change (%); positive rising momentum, negative declining.
- `rsi.rsi`: RSI 0-100; higher = overbought pressure, lower = oversold pressure.
- `stochrsi.{stochrsi, stochrsi_k, stochrsi_d}`: Stochastic RSI 0-1; higher = stronger upside momentum relative to RSI range.
- `stoch.{stoch, stoch_signal}`: Stochastic oscillator (%K/%D); values near 0/100 show closes near range lows/highs.
- `tsi.tsi`: True Strength Index; positive = bullish momentum, negative = bearish; magnitude shows strength.
- `ultimate_oscillator.ultimate_oscillator`: Multi-horizon momentum 0-100; higher values favor bullish pressure.
- `williams_r.williams_r`: Williams %R (-100 to 0); closer to 0 = overbought, closer to -100 = oversold.

### Volatility
- `atr.average_true_range`: Average true range; absolute volatility measure in price units.
- `bbands.{bollinger_hband, bollinger_lband, bollinger_mavg, bollinger_pband, bollinger_wband, bollinger_hband_indicator, bollinger_lband_indicator}`: Bollinger Bands; `pband` shows relative position (0-1), `wband` is width %, indicators flag closes above/below bands.
- `donchian.{donchian_channel_hband, donchian_channel_lband, donchian_channel_mband, donchian_channel_pband, donchian_channel_wband}`: Donchian channels; bands capture recent high/low range, `pband`/`wband` express position/width.
- `keltner.{keltner_channel_hband, keltner_channel_lband, keltner_channel_mband, keltner_channel_pband, keltner_channel_wband, keltner_channel_hband_indicator, keltner_channel_lband_indicator}`: Keltner channels using ATR; `pband`/`wband` analogous to Bollinger; indicators flag closes outside envelopes.
- `ulcer_index.ulcer_index`: Downside-risk volatility metric; higher = deeper/more frequent drawdowns.

### Trend
- `adx.{adx, adx_pos, adx_neg}`: ADX and directional components; ADX higher = stronger trend; pos/neg indicate direction.
- `aroon.{aroon_up, aroon_down, aroon_indicator}`: Aroon oscillators; up vs down shows trend direction and recency of highs/lows.
- `cci.cci`: Commodity Channel Index; positive = price above typical level, negative = below; magnitude reflects deviation.
- `dpo.dpo`: Detrended Price Oscillator; oscillates around zero to reveal cycles without trend.
- `ema.ema_indicator`: Exponential moving average (14); smoother trend level.
- `ichimoku.{ichimoku_conversion_line, ichimoku_base_line, ichimoku_a, ichimoku_b}`: Ichimoku components; relative positions describe support/resistance clouds.
- `kst.{kst, kst_sig, kst_diff}`: Know Sure Thing and signal/diff; positive diff suggests bullish momentum.
- `macd.{macd, macd_signal, macd_diff}`: MACD line/signal/histogram; diff shows momentum shifts around zero.
- `mass_index.mass_index`: Mass Index; rising toward common thresholds (~27) can flag potential reversals.
- `psar.{psar, psar_up, psar_down, psar_up_indicator, psar_down_indicator}`: Parabolic SAR levels and flags; indicators show active SAR direction.
- `sma.{sma_14, sma_20, sma_50, sma_200}`: Simple moving averages; longer windows show higher-level trend.
- `stc.stc`: Schaff Trend Cycle; oscillates 0-100; higher values = bullish phase.
- `trix.trix`: Triple EMA ROC (%); above zero bullish, below bearish; magnitude shows momentum.
- `vortex.{vortex_indicator_pos, vortex_indicator_neg, vortex_indicator_diff}`: Vortex components; pos>neg implies bullish trend; diff magnitude shows strength.
- `wma.wma`: Weighted moving average (9); emphasizes recent prices for short-term trend.

### Volume
- `adi.acc_dist_index`: Accumulation/Distribution Index; rising with price suggests accumulation.
- `cmf.chaikin_money_flow`: Chaikin Money Flow; positive = buy pressure, negative = sell pressure.
- `eom.{ease_of_movement, sma_ease_of_movement}`: Ease of Movement and smoothed value; higher positive = price advancing on lower volume effort.
- `fi.force_index`: Force Index; combines price change and volume; sign indicates direction, magnitude indicates strength.
- `mfi.money_flow_index`: MFI (0-100); higher = positive money flow, lower = negative; thresholds similar to RSI.
- `nvi.negative_volume_index`: Negative Volume Index; tracks price changes on low-volume days; trend indicates smart money bias.
- `obv.on_balance_volume`: On-Balance Volume; cumulative volume flow; slope aligns with price/volume confirmation.
- `vpt.volume_price_trend`: Volume Price Trend; cumulative volume weighted by price change; direction aligns with demand.
- `vwap.volume_weighted_average_price`: VWAP over window; price-relative benchmark; price above/below indicates intraday bias.

### Others
- `cr.cumulative_return`: Cumulative simple return over series; unitless ratio.
- `dlr.daily_log_return`: Latest log return; unitless.
- `dr.daily_return`: Latest simple return; unitless.

### Pattern Recognition
- `pattern_recognition` (object of ints | nulls): TA-Lib candlestick pattern outputs (latest value per function). Keys: `cdl2crows`, `cdl3blackcrows`, `cdl3inside`, `cdl3linestrike`, `cdl3outside`, `cdl3starsinsouth`, `cdl3whitesoldiers`, `cdlabandonedbaby`, `cdladvanceblock`, `cdlbelthold`, `cdlbreakaway`, `cdlclosingmarubozu`, `cdlconcealbabyswall`, `cdlcounterattack`, `cdldarkcloudcover`, `cdldoji`, `cdldojistar`, `cdldragonflydoji`, `cdlengulfing`, `cdleveningdojistar`, `cdleveningstar`, `cdlgapsidesidewhite`, `cdlgravestonedoji`, `cdlhammer`, `cdlhangingman`, `cdlharami`, `cdlharamicross`, `cdlhighwave`, `cdlhikkake`, `cdlhikkakemod`, `cdlhomingpigeon`, `cdlidentical3crows`, `cdlinneck`, `cdlinvertedhammer`, `cdlkicking`, `cdlkickingbylength`, `cdlladderbottom`, `cdllongleggeddoji`, `cdllongline`, `cdlmarubozu`, `cdlmatchinglow`, `cdlmathold`, `cdlmorningdojistar`, `cdlmorningstar`, `cdlonneck`, `cdlpiercing`, `cdlrickshawman`, `cdlrisefall3methods`, `cdlseparatinglines`, `cdlshootingstar`, `cdlshortline`, `cdlspinningtop`, `cdlstalledpattern`, `cdlsticksandwich`, `cdltakuri`, `cdltasukigap`, `cdlthrusting`, `cdltristar`, `cdlunique3river`, `cdlupsidegap2crows`, `cdlxsidgap3methods`. Values are integer pattern scores (positive/negative) or null when not computed or backend unavailable.

## Absence & Fallback Rules
- All keys are emitted; `null` indicates insufficient history, missing inputs, or computation failure (including TA-Lib availability for patterns).
- Price metrics return `null` when the required window cannot be formed or when denominator terms are zero/invalid.
- Technical indicators return `null` per-output on invalid data or errors; pattern recognition returns `null` for every pattern when TA-Lib is unavailable or inputs are missing.
- Missing TA or price metrics do not imply system failure; consumers should treat `null` as “not computed/insufficient data” rather than an error signal.

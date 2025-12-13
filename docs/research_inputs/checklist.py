"""
Wyckoff 9-Step Checklist Engine (v2.0.0)
Each function implements a specific Wyckoff accumulation/distribution signal.
"""
import pandas as pd


def detect_defined_support(df, lookback=20, threshold=0.01):
    """Step 1: Detect Defined Support Level"""
    if df is None or df.empty or 'close' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'support_level': 0.0}
    
    support_level = df['low'].rolling(window=lookback, min_periods=1).min()
    distance_from_support = (df['close'] - support_level) / support_level
    signal = distance_from_support <= threshold
    
    valid_distances = distance_from_support[distance_from_support >= 0]
    if len(valid_distances) > 0 and valid_distances.iloc[-1] <= threshold:
        score = float(max(0, 1 - (valid_distances.iloc[-1] / threshold)))
    else:
        score = 0.0
    
    return {
        'signal': signal,
        'score': score,
        'support_level': float(support_level.iloc[-1]) if len(support_level) > 0 else 0.0
    }


def detect_climax_volume_spike(df, lookback=20, volume_spike_factor=2.0):
    """Step 2: Detect Preliminary Support / Climax Volume Spike"""
    if df is None or df.empty or 'volume' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'avg_volume': 0.0}
    
    avg_volume = df['volume'].rolling(window=lookback, min_periods=1).mean()
    volume_spike = df['volume'] > (avg_volume * volume_spike_factor)
    
    bullish_reversal = (df['close'] > df['close'].shift(1)) & (df['low'] < df['low'].shift(1))
    
    signal = volume_spike & bullish_reversal
    
    if len(df) > 0 and avg_volume.iloc[-1] > 0:
        volume_ratio = df['volume'].iloc[-1] / avg_volume.iloc[-1]
        score = float(min(1.0, (volume_ratio - 1) / volume_spike_factor))
        score = score if signal.iloc[-1] else 0.0
    else:
        score = 0.0
    
    return {
        'signal': signal,
        'score': score,
        'avg_volume': float(avg_volume.iloc[-1]) if len(avg_volume) > 0 else 0.0
    }


def detect_rally_on_increasing_volume(df, lookback=10):
    """Step 3: Detect Rally on Increasing Volume"""
    if df is None or df.empty or 'volume' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'rally_pct': 0.0}
    
    avg_volume = df['volume'].rolling(window=lookback, min_periods=1).mean()
    price_rising = df['close'] > df['close'].shift(1)
    volume_increasing = df['volume'] > avg_volume
    
    signal = price_rising & volume_increasing
    
    if len(df) > 1:
        rally_pct = float(((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100)
        score = float(min(1.0, abs(rally_pct) / 5.0)) if signal.iloc[-1] else 0.0
    else:
        rally_pct = 0.0
        score = 0.0
    
    return {
        'signal': signal,
        'score': score,
        'rally_pct': rally_pct
    }


def detect_pullback_low_volume(df, lookback=10):
    """Step 4: Detect Pullback on Low Volume (Secondary Test)"""
    if df is None or df.empty or 'volume' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'volume_ratio': 0.0}
    
    avg_volume = df['volume'].rolling(window=lookback, min_periods=1).mean()
    price_declining = df['close'] < df['close'].shift(1)
    volume_declining = df['volume'] < avg_volume
    
    signal = price_declining & volume_declining
    
    if len(df) > 0 and avg_volume.iloc[-1] > 0:
        volume_ratio = float(df['volume'].iloc[-1] / avg_volume.iloc[-1])
        score = float(max(0, 1 - volume_ratio)) if signal.iloc[-1] else 0.0
    else:
        volume_ratio = 0.0
        score = 0.0
    
    return {
        'signal': signal,
        'score': score,
        'volume_ratio': volume_ratio
    }


def detect_higher_swing_lows(df, lookback=3):
    """Step 5: Detect Higher Swing Lows (Sign of Strength)"""
    if df is None or df.empty or 'low' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'consecutive_higher_lows': 0}
    
    higher_lows = df['low'] > df['low'].shift(1)
    
    consecutive = 0
    for i in range(len(higher_lows) - 1, max(0, len(higher_lows) - lookback - 1), -1):
        if higher_lows.iloc[i]:
            consecutive += 1
        else:
            break
    
    signal = pd.Series([consecutive >= 2] * len(df), index=df.index)
    score = float(min(1.0, consecutive / lookback))
    
    return {
        'signal': signal,
        'score': score,
        'consecutive_higher_lows': consecutive
    }


def detect_downtrend_break(df, lookback=20):
    """Step 6: Detect Breaking of Downtrend Resistance"""
    if df is None or df.empty or 'close' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'resistance_level': 0.0}
    
    resistance = df['high'].rolling(window=lookback, min_periods=1).max()
    downtrend_broken = df['close'] > resistance.shift(1)
    
    if len(df) > 1 and resistance.shift(1).iloc[-1] > 0:
        breakout_pct = float(((df['close'].iloc[-1] - resistance.shift(1).iloc[-1]) / resistance.shift(1).iloc[-1]) * 100)
        score = float(min(1.0, max(0, breakout_pct / 3.0))) if downtrend_broken.iloc[-1] else 0.0
    else:
        score = 0.0
    
    return {
        'signal': downtrend_broken,
        'score': score,
        'resistance_level': float(resistance.iloc[-1]) if len(resistance) > 0 else 0.0
    }


def detect_relative_strength(df, benchmark_df, lookback=20):
    """Step 7: Detect Relative Strength vs Benchmark"""
    if df is None or df.empty or 'close' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'relative_return': 0.0}
    
    asset_return = df['close'].pct_change(periods=lookback) * 100
    
    if benchmark_df is not None and not benchmark_df.empty and 'close' in benchmark_df.columns:
        benchmark_aligned = benchmark_df.reindex(df.index, method='ffill')
        benchmark_return = benchmark_aligned['close'].pct_change(periods=lookback) * 100
        
        signal = asset_return > benchmark_return
        relative_return = asset_return - benchmark_return
        
        if len(relative_return) > 0 and not pd.isna(relative_return.iloc[-1]):
            score = float(min(1.0, max(0, relative_return.iloc[-1] / 10.0)))
        else:
            score = 0.0
        
        rel_ret_val = float(relative_return.iloc[-1]) if len(relative_return) > 0 and not pd.isna(relative_return.iloc[-1]) else 0.0
    else:
        signal = asset_return > 0
        score = float(min(1.0, max(0, asset_return.iloc[-1] / 10.0))) if len(asset_return) > 0 and not pd.isna(asset_return.iloc[-1]) else 0.0
        rel_ret_val = float(asset_return.iloc[-1]) if len(asset_return) > 0 and not pd.isna(asset_return.iloc[-1]) else 0.0
    
    return {
        'signal': signal,
        'score': score,
        'relative_return': rel_ret_val
    }


def detect_horizontal_base(df, lookback=20, volatility_threshold=0.02):
    """Step 8: Detect Horizontal Price Base Formation"""
    if df is None or df.empty or 'close' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'base_volatility': 0.0}
    
    rolling_std = df['close'].rolling(window=lookback, min_periods=1).std()
    rolling_mean = df['close'].rolling(window=lookback, min_periods=1).mean()
    base_volatility_pct = (rolling_std / rolling_mean) * 100
    
    signal = base_volatility_pct < (volatility_threshold * 100)
    
    if len(base_volatility_pct) > 0 and not pd.isna(base_volatility_pct.iloc[-1]):
        normalized_vol = base_volatility_pct.iloc[-1] / (volatility_threshold * 100)
        score = float(max(0, 1 - normalized_vol)) if signal.iloc[-1] else 0.0
        vol_val = float(base_volatility_pct.iloc[-1])
    else:
        score = 0.0
        vol_val = 0.0
    
    return {
        'signal': signal,
        'score': score,
        'base_volatility': vol_val
    }


def detect_favorable_risk_reward(df, lookback=20, min_ratio=3.0):
    """Step 9: Detect Favorable Reward-to-Risk Ratio
    
    Calculates risk/reward based on actual support and resistance levels
    detected in the price action, not fixed percentages.
    """
    if df is None or df.empty or 'close' not in df.columns:
        return {'signal': pd.Series([False]), 'score': 0.0, 'risk_reward_ratio': 0.0}
    
    current_price = df['close'].iloc[-1] if len(df) > 0 else 0
    
    if current_price <= 0:
        return {'signal': pd.Series([False]), 'score': 0.0, 'risk_reward_ratio': 0.0}
    
    # Calculate actual support and resistance from price action
    support_level = df['low'].rolling(window=lookback, min_periods=1).min().iloc[-1]
    resistance_level = df['high'].rolling(window=lookback, min_periods=1).max().iloc[-1]
    
    # Risk is distance from current price to support
    # Reward is distance from current price to resistance
    potential_risk = current_price - support_level
    potential_reward = resistance_level - current_price
    
    if potential_risk > 0 and potential_reward > 0:
        risk_reward_ratio = potential_reward / potential_risk
    else:
        risk_reward_ratio = 0.0
    
    signal = pd.Series([risk_reward_ratio >= min_ratio] * len(df), index=df.index)
    
    if risk_reward_ratio >= min_ratio:
        score = float(min(1.0, (risk_reward_ratio - min_ratio) / min_ratio))
    else:
        score = 0.0
    
    return {
        'signal': signal,
        'score': score,
        'risk_reward_ratio': float(risk_reward_ratio)
    }


def run_wyckoff_checklist(df, benchmark_df=None, config=None):
    """
    Run all 9 Wyckoff checklist steps and return comprehensive diagnostics.
    
    Args:
        df (pd.DataFrame): Asset OHLCV DataFrame
        benchmark_df (pd.DataFrame): Optional benchmark for relative strength
        config (dict): Optional configuration with custom parameters
    
    Returns:
        dict: Complete checklist results with all 9 steps, scores, and summary
    """
    default_config = {
        'lookback_short': 10,
        'lookback_medium': 20,
        'lookback_long': 50,
        'volume_spike_factor': 2.0,
        'support_threshold': 0.01,
        'base_volatility_threshold': 0.02,
        'min_risk_reward': 3.0
    }
    
    cfg = {**default_config, **(config or {})}
    
    step1 = detect_defined_support(df, lookback=cfg['lookback_medium'], threshold=cfg['support_threshold'])
    step2 = detect_climax_volume_spike(df, lookback=cfg['lookback_medium'], volume_spike_factor=cfg['volume_spike_factor'])
    step3 = detect_rally_on_increasing_volume(df, lookback=cfg['lookback_short'])
    step4 = detect_pullback_low_volume(df, lookback=cfg['lookback_short'])
    step5 = detect_higher_swing_lows(df, lookback=3)
    step6 = detect_downtrend_break(df, lookback=cfg['lookback_medium'])
    step7 = detect_relative_strength(df, benchmark_df, lookback=cfg['lookback_medium'])
    step8 = detect_horizontal_base(df, lookback=cfg['lookback_medium'], volatility_threshold=cfg['base_volatility_threshold'])
    step9 = detect_favorable_risk_reward(df, lookback=cfg['lookback_medium'], min_ratio=cfg['min_risk_reward'])
    
    steps = [
        ('step_1_defined_support', step1, 'support_level', 'Price at/near support level'),
        ('step_2_climax_volume', step2, 'avg_volume', 'High-volume selling climax with reversal'),
        ('step_3_rally_volume', step3, 'rally_pct', 'Rally on increasing volume'),
        ('step_4_pullback_low_volume', step4, 'volume_ratio', 'Pullback on declining volume'),
        ('step_5_higher_lows', step5, 'consecutive_higher_lows', 'Series of higher swing lows'),
        ('step_6_downtrend_break', step6, 'resistance_level', 'Breaking downtrend resistance'),
        ('step_7_relative_strength', step7, 'relative_return', 'Outperforming benchmark'),
        ('step_8_horizontal_base', step8, 'base_volatility', 'Tight horizontal consolidation'),
        ('step_9_risk_reward', step9, 'risk_reward_ratio', 'Favorable reward-to-risk ratio')
    ]
    
    checklist = {}
    all_scores = []
    all_passed = []
    
    for step_name, step_result, detail_key, description in steps:
        passed = bool(step_result['signal'].iloc[-1]) if len(step_result['signal']) > 0 else False
        score = step_result['score']
        
        checklist[step_name] = {
            'passed': passed,
            'score': score,
            detail_key: step_result[detail_key],
            'description': description
        }
        
        all_scores.append(score)
        all_passed.append(passed)
    
    checklist['summary'] = {
        'total_passed': sum(all_passed),
        'average_score': sum(all_scores) / 9.0 if all_scores else 0.0,
        'config_used': cfg
    }
    
    return checklist

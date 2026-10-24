from .ema_trend import EmaTrendStrategy
from .rsi_reversion import RsiMeanReversionStrategy
from .donchian_breakout import DonchianBreakoutStrategy
from .supertrend import SupertrendStrategy
from .adx_macd import AdxMacdStrategy
from .price_volume_momentum import PriceVolumeMomentumStrategy
from .orb import OpeningRangeBreakoutStrategy
from .bollinger_reversion import BollingerReversionStrategy
from .swing_pullback import SwingPullbackStrategy
from .options_spread import OptionsVerticalSpreadStrategy
from .ml_regime_filter import MlRegimeFilterStrategy

# Candidate Strategies from Advanced Indicator Engine
from .ema200_macd import Ema200MacdStrategy
from .bollinger_squeeze_breakout import BollingerSqueezeBreakoutStrategy
from .adx_trend_continuation import AdxTrendContinuationStrategy
from .rsi_bollinger_range import RsiBollingerRangeStrategy
from .vwap_volume_intraday import VwapVolumeIntradayStrategy
from .atr_breakout_exit import AtrBreakoutExitStrategy
from .mtf_swing import MultiTimeframeSwingStrategy

STRATEGIES = {
    # Baseline Starter Strategies (Preserved for compatibility)
    "ema_trend": EmaTrendStrategy(),
    "rsi_mean_reversion": RsiMeanReversionStrategy(),
    "donchian_breakout": DonchianBreakoutStrategy(),
    # Multi-Strategy Expansion
    "supertrend": SupertrendStrategy(),
    "adx_macd": AdxMacdStrategy(),
    "price_volume_momentum": PriceVolumeMomentumStrategy(),
    "orb_breakout": OpeningRangeBreakoutStrategy(),
    "bollinger_reversion": BollingerReversionStrategy(),
    "swing_pullback": SwingPullbackStrategy(),
    "options_vertical_spread": OptionsVerticalSpreadStrategy(),
    "ml_regime_classifier": MlRegimeFilterStrategy(),
    # Candidate Indicator Engine Strategies
    "ema200_macd_trend": Ema200MacdStrategy(),
    "bollinger_squeeze_breakout": BollingerSqueezeBreakoutStrategy(),
    "adx_trend_continuation": AdxTrendContinuationStrategy(),
    "rsi_bollinger_range": RsiBollingerRangeStrategy(),
    "vwap_volume_intraday": VwapVolumeIntradayStrategy(),
    "atr_breakout_exit": AtrBreakoutExitStrategy(),
    "mtf_swing_trading": MultiTimeframeSwingStrategy(),
}


def list_strategies(include_candidates: bool = True) -> list[dict]:
    if include_candidates:
        return [s.metadata() for s in STRATEGIES.values()]
    return [s.metadata() for k, s in STRATEGIES.items() if k in {"ema_trend", "rsi_mean_reversion", "donchian_breakout"}]

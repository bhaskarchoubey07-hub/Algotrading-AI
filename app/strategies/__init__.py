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

STRATEGIES = {
    "ema_trend": EmaTrendStrategy(),
    "rsi_mean_reversion": RsiMeanReversionStrategy(),
    "donchian_breakout": DonchianBreakoutStrategy(),
    "supertrend": SupertrendStrategy(),
    "adx_macd": AdxMacdStrategy(),
    "price_volume_momentum": PriceVolumeMomentumStrategy(),
    "orb_breakout": OpeningRangeBreakoutStrategy(),
    "bollinger_reversion": BollingerReversionStrategy(),
    "swing_pullback": SwingPullbackStrategy(),
    "options_vertical_spread": OptionsVerticalSpreadStrategy(),
    "ml_regime_classifier": MlRegimeFilterStrategy(),
}


def list_strategies() -> list[dict]:
    return [s.metadata() for s in STRATEGIES.values()]

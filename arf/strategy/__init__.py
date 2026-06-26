from .base import BaseStrategy
from .ma import MaStrategy
from .macross import MaCrossStrategy
from .technical_score import TechnicalScoreStrategy, TechnicalPandasData

# Dictionary mapping display names to strategy classes
STRATEGIES = {
    "MA 策略 (单均线)": MaStrategy,
    "MACross 策略 (双均线交叉)": MaCrossStrategy,
    "TechnicalScore 策略 (智能技术评分)": TechnicalScoreStrategy,
}

__all__ = [
    "BaseStrategy",
    "MaStrategy",
    "MaCrossStrategy",
    "TechnicalScoreStrategy",
    "TechnicalPandasData",
    "STRATEGIES",
]

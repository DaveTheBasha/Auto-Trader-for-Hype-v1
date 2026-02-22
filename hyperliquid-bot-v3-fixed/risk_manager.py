"""
Risk Management Module
Handles position sizing, risk limits, and trade validation
"""
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select, func

from models import Trade, TradeStatus, TradingSignal, TraderPerformance, Database
from config import config


class RiskManager:
    """Manages trading risk and position sizing"""

    def __init__(self, db: Database):
        self.db = db

    async def get_open_trades_count(self) -> int:
        """Get count of currently open trades"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(func.count(Trade.id)).where(Trade.status == TradeStatus.OPEN)
            )
            return result.scalar() or 0

    async def get_open_position_for_asset(self, asset: str) -> Optional[Trade]:
        """Check if there's an open position for a specific asset"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Trade).where(
                    Trade.asset == asset,
                    Trade.status == TradeStatus.OPEN
                )
            )
            return result.scalar_one_or_none()

    async def get_trader_weight(self, username: str) -> float:
        """Get performance-based weight for a trader"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TraderPerformance).where(TraderPerformance.username == username)
            )
            perf = result.scalar_one_or_none()

            if perf and perf.executed_trades >= config.learning.min_trades_for_weighting:
                return perf.weight_score
            return 1.0  # Default weight for new traders

    async def calculate_position_size(
        self,
        signal: TradingSignal,
        account_balance: float,
        trader_weight: float = 1.0
    ) -> float:
        """Calculate position size based on risk parameters"""
        # Base position size from risk config
        risk_amount = account_balance * (config.risk.risk_per_trade_percent / 100)

        # Apply maximum position limit
        base_size = min(risk_amount, config.risk.max_position_usd)

        # Scale by signal confidence
        confidence_multiplier = signal.confidence_score

        # Scale by trader performance weight (if learning enabled)
        if config.learning.weight_by_win_rate:
            base_size *= trader_weight

        # Final position size
        position_size = base_size * confidence_multiplier

        # Apply minimum trade size
        if position_size < config.trading.min_trade_size_usd:
            logger.warning(
                f"Position size ${position_size:.2f} below minimum "
                f"${config.trading.min_trade_size_usd}"
            )
            return 0.0

        logger.info(
            f"Calculated position size: ${position_size:.2f} "
            f"(confidence: {confidence_multiplier:.2f}, trader_weight: {trader_weight:.2f})"
        )

        return position_size

    def calculate_leverage(self, signal: TradingSignal) -> int:
        """Calculate appropriate leverage based on signal and config"""
        # Use signal leverage if provided and within limits
        if signal.leverage and signal.leverage <= config.risk.max_leverage:
            return signal.leverage

        # Default leverage based on confidence
        if signal.confidence_score >= 0.8:
            return min(config.risk.max_leverage, 10)
        elif signal.confidence_score >= 0.6:
            return min(config.risk.max_leverage, 7)
        else:
            return min(config.risk.max_leverage, 5)

    async def validate_trade(
        self,
        signal: TradingSignal,
        account_balance: Dict[str, float]
    ) -> Dict[str, any]:
        """Validate if a trade should be executed"""
        validation_result = {
            "valid": True,
            "reasons": [],
            "position_size": 0.0,
            "leverage": 1
        }

        # Check if max positions reached
        open_count = await self.get_open_trades_count()
        if open_count >= config.risk.max_open_positions:
            validation_result["valid"] = False
            validation_result["reasons"].append(
                f"Max open positions reached ({config.risk.max_open_positions})"
            )
            return validation_result

        # Check if already have position in this asset
        existing_position = await self.get_open_position_for_asset(signal.asset)
        if existing_position:
            validation_result["valid"] = False
            validation_result["reasons"].append(
                f"Already have open position in {signal.asset}"
            )
            return validation_result

        # Check confidence score
        if signal.confidence_score < config.risk.min_confidence_score:
            validation_result["valid"] = False
            validation_result["reasons"].append(
                f"Confidence score {signal.confidence_score:.2f} below minimum "
                f"{config.risk.min_confidence_score}"
            )
            return validation_result

        # Check available margin
        available_margin = account_balance.get("available_margin", 0)
        if available_margin < config.trading.min_trade_size_usd:
            validation_result["valid"] = False
            validation_result["reasons"].append(
                f"Insufficient margin: ${available_margin:.2f}"
            )
            return validation_result

        # Calculate position size
        equity = account_balance.get("equity", 0)
        trader_weight = await self.get_trader_weight(signal.trader_username)
        position_size = await self.calculate_position_size(signal, equity, trader_weight)

        if position_size == 0:
            validation_result["valid"] = False
            validation_result["reasons"].append("Position size too small")
            return validation_result

        # Calculate leverage
        leverage = self.calculate_leverage(signal)

        validation_result["position_size"] = position_size
        validation_result["leverage"] = leverage

        logger.info(
            f"Trade validated: {signal.signal_type.value} {signal.asset} "
            f"size=${position_size:.2f} leverage={leverage}x"
        )

        return validation_result

    async def check_stop_loss_take_profit(
        self,
        trade: Trade,
        current_price: float
    ) -> Optional[str]:
        """Check if trade should be closed due to SL/TP"""
        if trade.status != TradeStatus.OPEN:
            return None

        # For long positions
        if trade.signal_type.value == "long":
            if current_price <= trade.stop_loss:
                return "stop_loss"
            if current_price >= trade.take_profit:
                return "take_profit"

        # For short positions
        else:
            if current_price >= trade.stop_loss:
                return "stop_loss"
            if current_price <= trade.take_profit:
                return "take_profit"

        return None

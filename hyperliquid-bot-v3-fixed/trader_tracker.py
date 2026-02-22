"""
Trader Performance Tracker
Tracks and learns from trader performance to optimize signal weighting
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
from sqlalchemy import select, func, and_

from models import Trade, TradeStatus, TraderPerformance, TradingSignal, Database
from config import config


class TraderTracker:
    """Tracks trader performance and calculates weights for position sizing"""

    def __init__(self, db: Database):
        self.db = db

    async def initialize_trader(self, username: str):
        """Initialize a trader in the performance table if not exists"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TraderPerformance).where(TraderPerformance.username == username)
            )
            existing = result.scalar_one_or_none()

            if not existing:
                perf = TraderPerformance(
                    username=username,
                    total_signals=0,
                    executed_trades=0,
                    winning_trades=0,
                    losing_trades=0,
                    total_pnl_usd=0.0,
                    win_rate=0.0,
                    avg_pnl_percent=0.0,
                    weight_score=1.0
                )
                session.add(perf)
                await session.commit()
                logger.info(f"Initialized trader profile: @{username}")

    async def update_trader_stats(self, username: str):
        """Update aggregated statistics for a trader"""
        async with self.db.get_session() as session:
            # Get trader performance record
            result = await session.execute(
                select(TraderPerformance).where(TraderPerformance.username == username)
            )
            perf = result.scalar_one_or_none()

            if not perf:
                await self.initialize_trader(username)
                result = await session.execute(
                    select(TraderPerformance).where(TraderPerformance.username == username)
                )
                perf = result.scalar_one_or_none()

            # Calculate lookback period
            lookback_date = datetime.utcnow() - timedelta(days=config.learning.performance_lookback_days)

            # Get total signals from this trader
            signal_count = await session.execute(
                select(func.count(TradingSignal.id)).where(
                    TradingSignal.trader_username == username
                )
            )
            perf.total_signals = signal_count.scalar() or 0

            # Get closed trades within lookback period
            trades_result = await session.execute(
                select(Trade).where(
                    and_(
                        Trade.trader_username == username,
                        Trade.status == TradeStatus.CLOSED,
                        Trade.closed_at >= lookback_date
                    )
                )
            )
            closed_trades = list(trades_result.scalars().all())

            # Calculate statistics
            perf.executed_trades = len(closed_trades)

            if perf.executed_trades > 0:
                perf.winning_trades = sum(1 for t in closed_trades if t.pnl_usd and t.pnl_usd > 0)
                perf.losing_trades = sum(1 for t in closed_trades if t.pnl_usd and t.pnl_usd <= 0)
                perf.total_pnl_usd = sum(t.pnl_usd or 0 for t in closed_trades)
                perf.win_rate = perf.winning_trades / perf.executed_trades

                pnl_percents = [t.pnl_percent for t in closed_trades if t.pnl_percent is not None]
                perf.avg_pnl_percent = sum(pnl_percents) / len(pnl_percents) if pnl_percents else 0.0

                # Calculate weight score
                perf.weight_score = self._calculate_weight_score(perf)
            else:
                perf.winning_trades = 0
                perf.losing_trades = 0
                perf.total_pnl_usd = 0.0
                perf.win_rate = 0.0
                perf.avg_pnl_percent = 0.0
                perf.weight_score = 1.0

            perf.last_updated = datetime.utcnow()
            await session.commit()

            logger.info(
                f"Updated stats for @{username}: "
                f"trades={perf.executed_trades}, win_rate={perf.win_rate:.1%}, "
                f"PnL=${perf.total_pnl_usd:.2f}, weight={perf.weight_score:.2f}"
            )

    def _calculate_weight_score(self, perf: TraderPerformance) -> float:
        """Calculate weight score based on performance"""
        if perf.executed_trades < config.learning.min_trades_for_weighting:
            return 1.0  # Neutral weight for insufficient data

        weight = 1.0

        # Weight by win rate (0.3 - 1.5 range)
        if config.learning.weight_by_win_rate:
            # Win rate contribution: 50% win rate = 1.0, 70% = 1.4, 30% = 0.6
            win_rate_factor = 0.3 + (perf.win_rate * 1.2)
            weight *= win_rate_factor

        # Weight by PnL (0.5 - 2.0 range)
        if config.learning.weight_by_pnl:
            if perf.avg_pnl_percent > 0:
                # Positive PnL: boost weight (cap at 2x)
                pnl_factor = min(1 + (perf.avg_pnl_percent / 50), 2.0)
            else:
                # Negative PnL: reduce weight (floor at 0.5x)
                pnl_factor = max(1 + (perf.avg_pnl_percent / 100), 0.5)
            weight *= pnl_factor

        # Normalize to reasonable range (0.3 - 2.5)
        return max(0.3, min(weight, 2.5))

    async def get_all_trader_stats(self) -> List[Dict]:
        """Get performance stats for all tracked traders"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TraderPerformance).order_by(TraderPerformance.weight_score.desc())
            )
            traders = list(result.scalars().all())

            return [
                {
                    "username": t.username,
                    "total_signals": t.total_signals,
                    "executed_trades": t.executed_trades,
                    "winning_trades": t.winning_trades,
                    "losing_trades": t.losing_trades,
                    "win_rate": t.win_rate,
                    "total_pnl_usd": t.total_pnl_usd,
                    "avg_pnl_percent": t.avg_pnl_percent,
                    "weight_score": t.weight_score,
                    "last_updated": t.last_updated.isoformat() if t.last_updated else None
                }
                for t in traders
            ]

    async def get_trader_ranking(self) -> List[str]:
        """Get traders ranked by performance"""
        stats = await self.get_all_trader_stats()
        return [t["username"] for t in sorted(stats, key=lambda x: x["weight_score"], reverse=True)]

    async def record_trade_result(self, trade: Trade):
        """Record a trade result and update trader stats"""
        await self.update_trader_stats(trade.trader_username)

    async def update_all_traders(self):
        """Update stats for all tracked traders"""
        for username in config.twitter.tracked_accounts:
            await self.update_trader_stats(username)

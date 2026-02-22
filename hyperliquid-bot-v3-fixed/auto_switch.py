"""
Auto Switch Module
Automatically adjusts which traders to follow based on performance
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Set
from loguru import logger
from sqlalchemy import select, func

from models import Database, Trade, TradeStatus, TraderPerformance
from config import config, TRADER_PRESETS


class AutoSwitch:
    """
    Automatically manages which traders to follow based on their
    real-time performance. Promotes good performers and demotes bad ones.
    """

    def __init__(self, db: Database):
        self.db = db
        self.active_traders: Set[str] = set(config.twitter.tracked_accounts)
        self.blacklisted: Set[str] = set()  # Temporarily removed due to poor performance
        self.promoted: Set[str] = set()  # Added due to good performance

        # Thresholds
        self.min_trades_to_evaluate = 5
        self.min_win_rate = 0.40  # Below this = demote
        self.good_win_rate = 0.55  # Above this = promote
        self.max_losing_streak = 3  # Consecutive losses before demotion
        self.blacklist_duration_hours = 24
        self.evaluation_period_days = 7

    async def evaluate_trader(self, username: str) -> Dict:
        """Evaluate a trader's recent performance"""
        async with self.db.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=self.evaluation_period_days)

            # Get recent trades
            result = await session.execute(
                select(Trade).where(
                    Trade.trader_username == username,
                    Trade.status == TradeStatus.CLOSED,
                    Trade.closed_at >= cutoff_date
                ).order_by(Trade.closed_at.desc())
            )
            trades = list(result.scalars().all())

            if len(trades) < self.min_trades_to_evaluate:
                return {
                    "username": username,
                    "status": "insufficient_data",
                    "trades": len(trades),
                    "action": "none"
                }

            # Calculate metrics
            wins = sum(1 for t in trades if t.pnl_usd and t.pnl_usd > 0)
            losses = sum(1 for t in trades if t.pnl_usd and t.pnl_usd <= 0)
            total_pnl = sum(t.pnl_usd or 0 for t in trades)
            win_rate = wins / len(trades)

            # Check for losing streak
            losing_streak = 0
            for trade in trades:  # Already sorted by date desc
                if trade.pnl_usd and trade.pnl_usd <= 0:
                    losing_streak += 1
                else:
                    break

            # Determine action
            action = "none"
            reason = ""

            if losing_streak >= self.max_losing_streak:
                action = "demote"
                reason = f"Losing streak of {losing_streak}"
            elif win_rate < self.min_win_rate and len(trades) >= self.min_trades_to_evaluate:
                action = "demote"
                reason = f"Win rate {win_rate:.1%} below threshold"
            elif win_rate >= self.good_win_rate and total_pnl > 0:
                action = "promote"
                reason = f"Strong performance: {win_rate:.1%} win rate, ${total_pnl:.2f} PnL"

            return {
                "username": username,
                "trades": len(trades),
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "losing_streak": losing_streak,
                "action": action,
                "reason": reason
            }

    async def demote_trader(self, username: str, reason: str):
        """Temporarily remove a trader from active list"""
        if username in self.active_traders:
            self.active_traders.remove(username)
            self.blacklisted.add(username)
            logger.warning(f"DEMOTED @{username}: {reason}")

            # Log demotion
            async with self.db.get_session() as session:
                perf = await session.execute(
                    select(TraderPerformance).where(TraderPerformance.username == username)
                )
                trader = perf.scalar_one_or_none()
                if trader:
                    trader.weight_score = max(trader.weight_score * 0.5, 0.1)
                    await session.commit()

    async def promote_trader(self, username: str, reason: str):
        """Add a new trader to active list based on good performance"""
        if username not in self.active_traders and username not in self.blacklisted:
            self.active_traders.add(username)
            self.promoted.add(username)
            logger.info(f"PROMOTED @{username}: {reason}")

            # Boost weight
            async with self.db.get_session() as session:
                perf = await session.execute(
                    select(TraderPerformance).where(TraderPerformance.username == username)
                )
                trader = perf.scalar_one_or_none()
                if trader:
                    trader.weight_score = min(trader.weight_score * 1.5, 2.5)
                    await session.commit()

    async def check_blacklist_expiry(self):
        """Restore traders whose blacklist period has expired"""
        # In a real implementation, you'd track blacklist timestamps
        # For now, we'll just log
        pass

    async def run_evaluation_cycle(self):
        """Run a full evaluation cycle on all traders"""
        logger.info("Running auto-switch evaluation cycle...")

        all_traders = list(self.active_traders) + list(self.blacklisted)

        for username in all_traders:
            eval_result = await self.evaluate_trader(username)

            if eval_result["action"] == "demote":
                await self.demote_trader(username, eval_result["reason"])
            elif eval_result["action"] == "promote":
                await self.promote_trader(username, eval_result["reason"])

        # Also check candidates from presets
        for preset_name, traders in TRADER_PRESETS.items():
            for trader in traders:
                if trader not in self.active_traders and trader not in self.blacklisted:
                    eval_result = await self.evaluate_trader(trader)
                    if eval_result["action"] == "promote":
                        await self.promote_trader(trader, eval_result["reason"])

        logger.info(f"Active traders: {len(self.active_traders)}, Blacklisted: {len(self.blacklisted)}")

    async def start_auto_switch_loop(self, interval_minutes: int = 60):
        """Run continuous auto-switch evaluation"""
        while True:
            try:
                await self.run_evaluation_cycle()
                await self.check_blacklist_expiry()
            except Exception as e:
                logger.error(f"Auto-switch error: {e}")

            await asyncio.sleep(interval_minutes * 60)

    def get_active_traders(self) -> List[str]:
        """Get current list of active traders"""
        return list(self.active_traders)

    def get_status(self) -> Dict:
        """Get auto-switch status"""
        return {
            "active_traders": list(self.active_traders),
            "blacklisted": list(self.blacklisted),
            "promoted": list(self.promoted),
            "thresholds": {
                "min_win_rate": self.min_win_rate,
                "good_win_rate": self.good_win_rate,
                "max_losing_streak": self.max_losing_streak
            }
        }

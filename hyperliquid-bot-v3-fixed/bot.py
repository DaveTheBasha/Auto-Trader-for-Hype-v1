"""
Main Trading Bot Orchestration
Coordinates all components for automated trading
"""
import asyncio
from typing import List, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy import select

from config import config
from models import Database, Tweet, TradingSignal, Trade, TradeStatus
from twitter_monitor import TwitterMonitor
from signal_parser import SignalParser
from hyperliquid_trader import HyperliquidTrader
from risk_manager import RiskManager
from trader_tracker import TraderTracker


class TradingBot:
    """Main trading bot that orchestrates all components"""

    def __init__(self):
        self.db = Database(config.db_path)
        self.twitter_monitor: Optional[TwitterMonitor] = None
        self.signal_parser: Optional[SignalParser] = None
        self.trader: Optional[HyperliquidTrader] = None
        self.risk_manager: Optional[RiskManager] = None
        self.tracker: Optional[TraderTracker] = None
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._position_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize all bot components"""
        logger.info("Initializing trading bot...")

        # Initialize database
        await self.db.initialize()
        logger.info("Database initialized")

        # Initialize components
        self.twitter_monitor = TwitterMonitor(self.db)
        self.signal_parser = SignalParser(self.db)
        self.trader = HyperliquidTrader(self.db)
        self.risk_manager = RiskManager(self.db)
        self.tracker = TraderTracker(self.db)

        # Initialize Twitter connection
        await self.twitter_monitor.initialize()

        # Initialize Hyperliquid connection
        await self.trader.initialize()

        # Initialize tracker for all traders
        for username in config.twitter.tracked_accounts:
            await self.tracker.initialize_trader(username)

        logger.info("All components initialized successfully")

    async def process_new_tweets(self, tweets: List[Tweet]):
        """Process new tweets for trading signals"""
        logger.info(f"Processing {len(tweets)} new tweets...")

        for tweet in tweets:
            try:
                # Parse signal from tweet
                parsed_signal = self.signal_parser.parse_tweet(tweet)

                if parsed_signal and parsed_signal.confidence_score >= config.risk.min_confidence_score:
                    # Store signal in database
                    signal = await self.signal_parser.store_signal(tweet, parsed_signal)

                    # Mark tweet as processed with signal
                    await self.twitter_monitor.mark_tweet_processed(tweet.id, has_signal=True)

                    # Attempt to execute trade
                    await self.execute_trade(signal)
                else:
                    # Mark tweet as processed without signal
                    await self.twitter_monitor.mark_tweet_processed(tweet.id, has_signal=False)

            except Exception as e:
                logger.error(f"Error processing tweet {tweet.id}: {e}")
                await self.twitter_monitor.mark_tweet_processed(tweet.id, has_signal=False)

    async def execute_trade(self, signal: TradingSignal):
        """Validate and execute a trading signal"""
        logger.info(f"Evaluating signal: {signal.signal_type.value} {signal.asset}")

        try:
            # Get account balance
            account_balance = await self.trader.get_account_balance()

            # Validate trade
            validation = await self.risk_manager.validate_trade(signal, account_balance)

            if not validation["valid"]:
                logger.warning(f"Trade not validated: {validation['reasons']}")
                return

            # Execute trade
            trade = await self.trader.execute_signal(
                signal=signal,
                position_size_usd=validation["position_size"],
                leverage=validation["leverage"]
            )

            if trade:
                # Mark signal as executed
                async with self.db.get_session() as session:
                    signal.executed = True
                    session.add(signal)
                    await session.commit()

                logger.info(f"Trade executed successfully: #{trade.id}")

        except Exception as e:
            logger.error(f"Error executing trade for signal {signal.id}: {e}")

    async def monitor_positions(self):
        """Monitor open positions for SL/TP"""
        logger.info("Starting position monitor...")

        while self._running:
            try:
                # Get all open trades
                async with self.db.get_session() as session:
                    result = await session.execute(
                        select(Trade).where(Trade.status == TradeStatus.OPEN)
                    )
                    open_trades = list(result.scalars().all())

                for trade in open_trades:
                    # Get current price
                    current_price = await self.trader.get_market_price(trade.asset)
                    if not current_price:
                        continue

                    # Check SL/TP
                    close_reason = await self.risk_manager.check_stop_loss_take_profit(
                        trade, current_price
                    )

                    if close_reason:
                        logger.info(f"Closing trade #{trade.id} due to {close_reason}")
                        success = await self.trader.close_trade(trade, close_reason)

                        if success:
                            # Update trader stats
                            await self.tracker.record_trade_result(trade)

                # Check every 10 seconds
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in position monitor: {e}")
                await asyncio.sleep(10)

    async def start(self):
        """Start the trading bot"""
        logger.info("Starting trading bot...")
        self._running = True

        # Start position monitor in background
        self._position_task = asyncio.create_task(self.monitor_positions())

        # Start Twitter polling with callback
        self._monitor_task = asyncio.create_task(
            self.twitter_monitor.poll_loop(callback=self.process_new_tweets)
        )

        logger.info("Trading bot is now running")

        # Wait for tasks
        try:
            await asyncio.gather(self._monitor_task, self._position_task)
        except asyncio.CancelledError:
            logger.info("Bot tasks cancelled")

    async def stop(self):
        """Stop the trading bot"""
        logger.info("Stopping trading bot...")
        self._running = False

        if self.twitter_monitor:
            self.twitter_monitor.stop()

        if self._monitor_task:
            self._monitor_task.cancel()
        if self._position_task:
            self._position_task.cancel()

        logger.info("Trading bot stopped")

    async def get_status(self) -> dict:
        """Get current bot status"""
        account_balance = await self.trader.get_account_balance() if self.trader else {}
        open_positions = await self.trader.get_open_positions() if self.trader else []
        trader_stats = await self.tracker.get_all_trader_stats() if self.tracker else []

        async with self.db.get_session() as session:
            # Get trade statistics
            from sqlalchemy import func
            result = await session.execute(
                select(func.count(Trade.id)).where(Trade.status == TradeStatus.CLOSED)
            )
            total_trades = result.scalar() or 0

            result = await session.execute(
                select(func.sum(Trade.pnl_usd)).where(Trade.status == TradeStatus.CLOSED)
            )
            total_pnl = result.scalar() or 0.0

        return {
            "running": self._running,
            "account": account_balance,
            "open_positions": len(open_positions),
            "positions": open_positions,
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "tracked_traders": trader_stats,
            "config": {
                "testnet": config.hyperliquid.testnet,
                "max_position_usd": config.risk.max_position_usd,
                "max_leverage": config.risk.max_leverage,
                "risk_per_trade": config.risk.risk_per_trade_percent
            }
        }

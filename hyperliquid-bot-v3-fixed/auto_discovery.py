"""
Auto Discovery Module
Automatically finds and ranks good trading channels and traders
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger
from sqlalchemy import select, func

from models import Database, TradingSignal, Trade, TradeStatus, TraderPerformance
from signal_parser import SignalParser
from config import config


@dataclass
class ChannelScore:
    """Score for a trading channel/trader"""
    name: str
    source: str  # "twitter" or "telegram"
    total_signals: int = 0
    valid_signals: int = 0  # Signals that had clear entry/exit
    winning_signals: int = 0
    total_pnl_percent: float = 0.0
    avg_confidence: float = 0.0
    signal_frequency: float = 0.0  # Signals per day
    win_rate: float = 0.0
    score: float = 0.0  # Combined score 0-100
    last_updated: datetime = field(default_factory=datetime.utcnow)


class AutoDiscovery:
    """
    Automatically discovers and ranks trading channels/traders
    based on signal quality and performance
    """

    # Known good trading channels to seed discovery
    SEED_TWITTER_ACCOUNTS = [
        "SmartContracter", "Pentoshi", "CryptoKaleo", "DonAlt",
        "Ansem", "HsakaTrades", "EmperorBTC", "CryptoCred",
        "blaborade", "MacnBTC", "lightcrypto", "DegenSpartan"
    ]

    SEED_TELEGRAM_CHANNELS = [
        "WhaleTrades", "CryptoSignalsOrg", "Binance_Killers",
        "FatPigSignals", "CryptoInnerCircle"
    ]

    def __init__(self, db: Database):
        self.db = db
        self.channel_scores: Dict[str, ChannelScore] = {}
        self.parser = SignalParser(db)

    async def analyze_twitter_account(self, username: str, tweets: List[Dict]) -> ChannelScore:
        """Analyze a Twitter account's signal quality"""
        score = ChannelScore(name=username, source="twitter")

        valid_signals = 0
        total_confidence = 0.0

        for tweet in tweets:
            # Mock tweet object for parser
            class MockTweet:
                def __init__(self, text):
                    self.text = text
                    self.id = str(hash(text))
                    self.author_username = username

            parsed = self.parser.parse_tweet(MockTweet(tweet.get("text", "")))

            if parsed:
                score.total_signals += 1
                total_confidence += parsed.confidence_score

                if parsed.entry_price and (parsed.stop_loss or parsed.take_profit):
                    valid_signals += 1

        score.valid_signals = valid_signals
        score.avg_confidence = total_confidence / max(score.total_signals, 1)

        # Calculate score (0-100)
        score.score = self._calculate_score(score)

        return score

    async def analyze_telegram_channel(self, channel: str, messages: List[Dict]) -> ChannelScore:
        """Analyze a Telegram channel's signal quality"""
        score = ChannelScore(name=channel, source="telegram")

        valid_signals = 0
        total_confidence = 0.0

        for msg in messages:
            class MockTweet:
                def __init__(self, text, channel):
                    self.text = text
                    self.id = str(hash(text))
                    self.author_username = channel

            parsed = self.parser.parse_tweet(MockTweet(msg.get("text", ""), channel))

            if parsed:
                score.total_signals += 1
                total_confidence += parsed.confidence_score

                if parsed.entry_price and (parsed.stop_loss or parsed.take_profit):
                    valid_signals += 1

        score.valid_signals = valid_signals
        score.avg_confidence = total_confidence / max(score.total_signals, 1)
        score.score = self._calculate_score(score)

        return score

    def _calculate_score(self, channel: ChannelScore) -> float:
        """Calculate overall score for a channel (0-100)"""
        score = 0.0

        # Signal quality (0-40 points)
        if channel.total_signals > 0:
            quality_ratio = channel.valid_signals / channel.total_signals
            score += quality_ratio * 40

        # Average confidence (0-30 points)
        score += channel.avg_confidence * 30

        # Win rate bonus (0-30 points)
        score += channel.win_rate * 30

        return min(score, 100.0)

    async def get_performance_from_db(self, username: str) -> Optional[TraderPerformance]:
        """Get trader performance from database"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TraderPerformance).where(TraderPerformance.username == username)
            )
            return result.scalar_one_or_none()

    async def update_scores_from_trades(self):
        """Update channel scores based on actual trade results"""
        async with self.db.get_session() as session:
            # Get all traders with closed trades
            result = await session.execute(
                select(Trade.trader_username,
                       func.count(Trade.id).label('total'),
                       func.sum(func.cast(Trade.pnl_usd > 0, int)).label('wins'),
                       func.avg(Trade.pnl_percent).label('avg_pnl'))
                .where(Trade.status == TradeStatus.CLOSED)
                .group_by(Trade.trader_username)
            )

            for row in result:
                username = row[0]
                total = row[1] or 0
                wins = row[2] or 0
                avg_pnl = row[3] or 0

                if username in self.channel_scores:
                    self.channel_scores[username].winning_signals = wins
                    self.channel_scores[username].win_rate = wins / max(total, 1)
                    self.channel_scores[username].total_pnl_percent = avg_pnl * total
                    self.channel_scores[username].score = self._calculate_score(
                        self.channel_scores[username]
                    )

    async def get_top_channels(self, n: int = 10, source: str = None) -> List[ChannelScore]:
        """Get top ranked channels"""
        await self.update_scores_from_trades()

        channels = list(self.channel_scores.values())

        if source:
            channels = [c for c in channels if c.source == source]

        return sorted(channels, key=lambda x: x.score, reverse=True)[:n]

    async def discover_new_channels(self, twitter_monitor=None, telegram_monitor=None):
        """
        Discover new potentially good channels by analyzing
        mentions and references from known good traders
        """
        discovered = []

        # This would analyze tweets/messages for mentions of other traders
        # and add them to the discovery queue
        logger.info("Channel discovery running...")

        return discovered

    def get_recommended_traders(self, min_score: float = 50.0) -> List[str]:
        """Get list of recommended trader usernames above score threshold"""
        return [
            c.name for c in self.channel_scores.values()
            if c.score >= min_score and c.source == "twitter"
        ]

    def get_recommended_channels(self, min_score: float = 50.0) -> List[str]:
        """Get list of recommended Telegram channels above score threshold"""
        return [
            c.name for c in self.channel_scores.values()
            if c.score >= min_score and c.source == "telegram"
        ]

"""
Database Models for Trading Bot
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Enum as SQLEnum, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
import enum

Base = declarative_base()


class SignalType(enum.Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Tweet(Base):
    """Stored tweets from tracked accounts"""
    __tablename__ = "tweets"

    id = Column(String, primary_key=True)
    author_username = Column(String, index=True)
    author_id = Column(String)
    text = Column(String)
    created_at = Column(DateTime)
    processed = Column(Boolean, default=False)
    has_signal = Column(Boolean, default=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class TradingSignal(Base):
    """Extracted trading signals"""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tweet_id = Column(String, index=True)
    trader_username = Column(String, index=True)
    asset = Column(String)
    signal_type = Column(SQLEnum(SignalType))
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    leverage = Column(Integer, nullable=True)
    confidence_score = Column(Float)  # 0.0 - 1.0
    raw_text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    executed = Column(Boolean, default=False)


class Trade(Base):
    """Executed trades"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, index=True)
    trader_username = Column(String, index=True)
    asset = Column(String)
    signal_type = Column(SQLEnum(SignalType))
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    size_usd = Column(Float)
    leverage = Column(Integer)
    status = Column(SQLEnum(TradeStatus), default=TradeStatus.PENDING)
    pnl_usd = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    hyperliquid_order_id = Column(String, nullable=True)
    notes = Column(String, nullable=True)


class TraderPerformance(Base):
    """Aggregated trader performance for learning"""
    __tablename__ = "trader_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True)
    total_signals = Column(Integer, default=0)
    executed_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl_usd = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    avg_pnl_percent = Column(Float, default=0.0)
    weight_score = Column(Float, default=1.0)  # Used for position sizing
    last_updated = Column(DateTime, default=datetime.utcnow)


class Database:
    """Database manager"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.engine = None
        self.async_engine = None
        self.Session = None

    async def initialize(self):
        """Initialize database"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Async engine for main operations
        self.async_engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.db_path}",
            echo=False
        )

        # Sync engine for table creation
        sync_engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(sync_engine)

        self.Session = sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    def get_session(self) -> AsyncSession:
        """Get a new database session"""
        return self.Session()

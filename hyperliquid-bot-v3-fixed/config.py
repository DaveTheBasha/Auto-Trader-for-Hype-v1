"""
Configuration for Hyperliquid Twitter Trading Bot

Trader Presets:
  - CONSERVATIVE: Proven traders, lower frequency (SmartContracter, Pentoshi, etc.)
  - BALANCED: Mix of established and rising traders
  - AGGRESSIVE: High frequency traders, higher risk/reward
  - CUSTOM: Your own selection

To change preset, set TRADER_PRESET env var or modify tracked_accounts below.
See recommended_traders.py for full trader database.
"""
import os
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# TRADER PRESETS - Choose your risk appetite
# =============================================================================

TRADER_PRESETS = {
    # Proven multi-year track records, quality over quantity
    "CONSERVATIVE": [
        "SmartContracter",   # Called 2018 BTC bottom, elite TA
        "Pentoshi",          # Called 2021 top, excellent charts
        "CryptoCred",        # Trading educator, frameworks
        "lightcrypto",       # Professional, disciplined
        "DonAlt",            # Direct commentary, no BS
    ],

    # Balanced mix of established and active traders
    "BALANCED": [
        "SmartContracter",
        "Pentoshi",
        "DonAlt",
        "CryptoKaleo",       # Active, charts + equities
        "HsakaTrades",       # Derivatives specialist
        "EmperorBTC",        # Education + TA
    ],

    # High frequency, aggressive style - higher risk/reward
    "AGGRESSIVE": [
        "CryptoKaleo",
        "Ansem",             # SOL/memecoin specialist
        "HsakaTrades",
        "blaborade",         # Altcoin rotation
        "ColdBloodShill",    # Active altcoin trader
        "DegenSpartan",      # DeFi specialist
    ],

    # Your original selection
    "ORIGINAL": [
        "IncomeSharks",
        "astronomer_zero",
        "DonAlt",
    ],

    # SOL ecosystem focused
    "SOLANA": [
        "Ansem",
        "blaborade",
        "ColdBloodShill",
    ],

    # BTC focused
    "BITCOIN": [
        "SmartContracter",
        "Pentoshi",
        "MacnBTC",
        "EmperorBTC",
    ],
}

# Select preset via environment variable or default to BALANCED
ACTIVE_PRESET = os.getenv("TRADER_PRESET", "BALANCED")


class TwitterConfig(BaseModel):
    """Twitter API Configuration"""
    bearer_token: str = os.getenv("TWITTER_BEARER_TOKEN", "")
    # Use preset or custom list
    tracked_accounts: List[str] = TRADER_PRESETS.get(ACTIVE_PRESET, TRADER_PRESETS["BALANCED"])
    poll_interval_seconds: int = 30  # How often to check for new tweets


class HyperliquidConfig(BaseModel):
    """Hyperliquid API Configuration"""
    private_key: str = os.getenv("HYPERLIQUID_PRIVATE_KEY", "")
    wallet_address: str = os.getenv("HYPERLIQUID_WALLET_ADDRESS", "")
    testnet: bool = os.getenv("HYPERLIQUID_TESTNET", "true").lower() == "true"


class RiskConfig(BaseModel):
    """Risk Management Configuration"""
    max_position_usd: float = 1000.0
    risk_per_trade_percent: float = 7.5  # Aggressive: 5-10%
    max_leverage: int = 10
    default_stop_loss_percent: float = 5.0
    default_take_profit_percent: float = 15.0
    max_open_positions: int = 5
    min_confidence_score: float = 0.6  # Minimum signal confidence to trade


class TradingConfig(BaseModel):
    """Trading Parameters"""
    supported_assets: List[str] = [
        "BTC", "ETH", "SOL", "ARB", "DOGE", "AVAX", "LINK",
        "MATIC", "OP", "APT", "SUI", "INJ", "TIA", "SEI",
        "PEPE", "WIF", "BONK", "JTO", "PYTH", "JUP"
    ]
    min_trade_size_usd: float = 10.0
    slippage_tolerance_percent: float = 0.5


class LearningConfig(BaseModel):
    """Learning/Tracking Configuration"""
    track_performance: bool = True
    min_trades_for_weighting: int = 10
    performance_lookback_days: int = 30
    weight_by_win_rate: bool = True
    weight_by_pnl: bool = True


class TelegramConfig(BaseModel):
    """Telegram Monitoring Configuration"""
    enabled: bool = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
    api_id: str = os.getenv("TELEGRAM_API_ID", "")
    api_hash: str = os.getenv("TELEGRAM_API_HASH", "")
    # Channels to monitor (add your own)
    tracked_channels: List[str] = [
        "WhaleTrades",
        "CryptoSignalsOrg",
        "Binance_Killers",
    ]


class WalletCopyConfig(BaseModel):
    """Wallet Copy Trading Configuration"""
    enabled: bool = os.getenv("WALLET_COPY_ENABLED", "false").lower() == "true"
    min_pnl_to_track: float = 10000.0  # Min 30d PnL to track a wallet
    min_win_rate: float = 0.50
    copy_size_percent: float = 0.5  # Copy at 50% of their trade size
    max_wallets: int = 20
    # Manually add wallet addresses to track
    tracked_wallets: List[str] = []


class AutoSwitchConfig(BaseModel):
    """Auto Switch Configuration"""
    enabled: bool = os.getenv("AUTO_SWITCH_ENABLED", "true").lower() == "true"
    evaluation_interval_minutes: int = 60
    min_trades_to_evaluate: int = 5
    min_win_rate: float = 0.40  # Below this = demote
    good_win_rate: float = 0.55  # Above this = promote
    max_losing_streak: int = 3


class NotificationsConfig(BaseModel):
    """Telegram Notifications Configuration"""
    enabled: bool = os.getenv("NOTIFICATIONS_ENABLED", "false").lower() == "true"
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    notify_on_signal: bool = True
    notify_on_trade_open: bool = True
    notify_on_trade_close: bool = True
    notify_on_stop_loss: bool = True
    notify_on_take_profit: bool = True
    daily_summary: bool = True
    daily_summary_hour: int = 20  # 8 PM UTC


class DashboardConfig(BaseModel):
    """Web Dashboard Configuration"""
    enabled: bool = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"
    host: str = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port: int = int(os.getenv("DASHBOARD_PORT", "5000"))


class BotConfig(BaseModel):
    """Main Bot Configuration"""
    twitter: TwitterConfig = TwitterConfig()
    hyperliquid: HyperliquidConfig = HyperliquidConfig()
    risk: RiskConfig = RiskConfig()
    trading: TradingConfig = TradingConfig()
    learning: LearningConfig = LearningConfig()
    telegram: TelegramConfig = TelegramConfig()
    wallet_copy: WalletCopyConfig = WalletCopyConfig()
    auto_switch: AutoSwitchConfig = AutoSwitchConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    dashboard: DashboardConfig = DashboardConfig()

    # Database
    db_path: str = "data/trading_bot.db"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"


# Global config instance
config = BotConfig()

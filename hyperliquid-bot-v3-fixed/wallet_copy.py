"""
Wallet Copy Trading Module
Monitors and copies trades from successful on-chain traders
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from loguru import logger

from models import Database, SignalType
from config import config


@dataclass
class TrackedWallet:
    """A wallet being tracked for copy trading"""
    address: str
    label: str  # Human readable name
    source: str  # Where we found this wallet
    pnl_30d: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    avg_trade_size: float = 0.0
    is_active: bool = True
    added_at: datetime = field(default_factory=datetime.utcnow)
    last_trade: Optional[datetime] = None


@dataclass
class WalletTrade:
    """A trade detected from a tracked wallet"""
    wallet: str
    asset: str
    direction: SignalType  # LONG or SHORT
    size_usd: float
    entry_price: float
    leverage: int
    timestamp: datetime
    tx_hash: str


class WalletCopyTrader:
    """
    Monitors on-chain activity of successful traders and copies their positions.
    Uses Hyperliquid API and blockchain explorers to track wallet activity.
    """

    # Known profitable traders' wallets (example addresses)
    SEED_WALLETS = [
        {
            "address": "0x1234...example",  # Replace with real addresses
            "label": "Top Trader 1",
            "source": "leaderboard"
        }
    ]

    # APIs for wallet tracking
    HYPERLIQUID_API = "https://api.hyperliquid.xyz/info"
    ARKHAM_API = "https://api.arkhamintelligence.com"  # For wallet labeling
    DEBANK_API = "https://pro-openapi.debank.com"

    def __init__(self, db: Database):
        self.db = db
        self.tracked_wallets: Dict[str, TrackedWallet] = {}
        self.recent_trades: List[WalletTrade] = []
        self.processed_txs: Set[str] = set()
        self._running = False

        # Copy trading settings
        self.min_pnl_to_track = 10000  # Minimum 30d PnL to track
        self.min_win_rate = 0.50
        self.max_copy_delay_seconds = 30  # Max delay before copying
        self.copy_size_percent = 0.5  # Copy at 50% of their size

    async def initialize(self):
        """Initialize wallet tracker"""
        logger.info("Initializing wallet copy trader...")

        # Load seed wallets
        for wallet_data in self.SEED_WALLETS:
            wallet = TrackedWallet(**wallet_data)
            self.tracked_wallets[wallet.address] = wallet

        # Discover top traders from Hyperliquid leaderboard
        await self.discover_top_traders()

        logger.info(f"Tracking {len(self.tracked_wallets)} wallets")

    async def discover_top_traders(self):
        """Discover top traders from Hyperliquid leaderboard"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get leaderboard
                async with session.post(
                    self.HYPERLIQUID_API,
                    json={"type": "leaderboard", "timeWindow": "month"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        await self._process_leaderboard(data)
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")

    async def _process_leaderboard(self, data: Dict):
        """Process leaderboard data to find wallets to track"""
        # Extract top performers
        if not isinstance(data, list):
            return

        for entry in data[:50]:  # Top 50
            try:
                address = entry.get("address", "")
                pnl = float(entry.get("pnl", 0))
                win_rate = float(entry.get("winRate", 0))

                if pnl >= self.min_pnl_to_track and win_rate >= self.min_win_rate:
                    if address not in self.tracked_wallets:
                        wallet = TrackedWallet(
                            address=address,
                            label=f"Leaderboard #{len(self.tracked_wallets) + 1}",
                            source="hyperliquid_leaderboard",
                            pnl_30d=pnl,
                            win_rate=win_rate
                        )
                        self.tracked_wallets[address] = wallet
                        logger.info(f"Discovered top trader: {address[:10]}... (PnL: ${pnl:,.0f})")

            except (KeyError, ValueError) as e:
                continue

    async def get_wallet_positions(self, address: str) -> List[Dict]:
        """Get current positions for a wallet"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.HYPERLIQUID_API,
                    json={"type": "clearinghouseState", "user": address}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("assetPositions", [])
        except Exception as e:
            logger.error(f"Error fetching positions for {address}: {e}")
        return []

    async def get_wallet_trades(self, address: str, limit: int = 20) -> List[Dict]:
        """Get recent trades for a wallet"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.HYPERLIQUID_API,
                    json={"type": "userFills", "user": address}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data[:limit] if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Error fetching trades for {address}: {e}")
        return []

    async def detect_new_positions(self, address: str) -> List[WalletTrade]:
        """Detect new positions opened by a wallet"""
        detected = []
        trades = await self.get_wallet_trades(address, limit=10)

        for trade in trades:
            try:
                tx_hash = trade.get("hash", trade.get("tid", str(hash(str(trade)))))

                if tx_hash in self.processed_txs:
                    continue

                self.processed_txs.add(tx_hash)

                # Parse trade
                asset = trade.get("coin", "")
                side = trade.get("side", "")
                size = abs(float(trade.get("sz", 0)))
                price = float(trade.get("px", 0))

                if not asset or not side:
                    continue

                wallet_trade = WalletTrade(
                    wallet=address,
                    asset=asset,
                    direction=SignalType.LONG if side.lower() == "b" else SignalType.SHORT,
                    size_usd=size * price,
                    entry_price=price,
                    leverage=1,  # Would need additional call to get leverage
                    timestamp=datetime.utcnow(),
                    tx_hash=tx_hash
                )

                detected.append(wallet_trade)
                logger.info(
                    f"Detected trade from {address[:10]}: "
                    f"{wallet_trade.direction.value} {asset} ${wallet_trade.size_usd:,.0f}"
                )

            except (KeyError, ValueError) as e:
                continue

        return detected

    async def monitor_loop(self, callback=None):
        """Main monitoring loop for wallet activity"""
        self._running = True
        logger.info("Starting wallet copy trading monitor...")

        while self._running:
            try:
                for address, wallet in self.tracked_wallets.items():
                    if not wallet.is_active:
                        continue

                    # Check for new trades
                    new_trades = await self.detect_new_positions(address)

                    for trade in new_trades:
                        self.recent_trades.append(trade)

                        if callback:
                            # Convert to signal format for the trading bot
                            signal_data = {
                                "asset": trade.asset,
                                "direction": trade.direction,
                                "entry_price": trade.entry_price,
                                "size_usd": trade.size_usd * self.copy_size_percent,
                                "source": f"wallet_copy:{wallet.label}",
                                "confidence": wallet.win_rate
                            }
                            await callback(signal_data)

                    # Small delay between wallets
                    await asyncio.sleep(1)

                # Poll interval
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in wallet monitor loop: {e}")
                await asyncio.sleep(10)

    async def stop(self):
        """Stop the monitor"""
        self._running = False
        logger.info("Wallet copy trader stopped")

    def add_wallet(self, address: str, label: str = ""):
        """Manually add a wallet to track"""
        if address not in self.tracked_wallets:
            wallet = TrackedWallet(
                address=address,
                label=label or f"Manual {len(self.tracked_wallets) + 1}",
                source="manual"
            )
            self.tracked_wallets[address] = wallet
            logger.info(f"Added wallet to track: {address}")

    def remove_wallet(self, address: str):
        """Remove a wallet from tracking"""
        if address in self.tracked_wallets:
            del self.tracked_wallets[address]
            logger.info(f"Removed wallet: {address}")

    async def get_wallet_stats(self, address: str) -> Dict:
        """Get detailed stats for a tracked wallet"""
        wallet = self.tracked_wallets.get(address)
        if not wallet:
            return {}

        positions = await self.get_wallet_positions(address)

        return {
            "address": address,
            "label": wallet.label,
            "pnl_30d": wallet.pnl_30d,
            "win_rate": wallet.win_rate,
            "is_active": wallet.is_active,
            "current_positions": len(positions),
            "positions": positions
        }

    def get_status(self) -> Dict:
        """Get copy trader status"""
        return {
            "tracked_wallets": len(self.tracked_wallets),
            "active_wallets": sum(1 for w in self.tracked_wallets.values() if w.is_active),
            "recent_trades": len(self.recent_trades),
            "wallets": [
                {
                    "address": w.address[:10] + "...",
                    "label": w.label,
                    "pnl": w.pnl_30d,
                    "win_rate": w.win_rate
                }
                for w in list(self.tracked_wallets.values())[:10]
            ]
        }

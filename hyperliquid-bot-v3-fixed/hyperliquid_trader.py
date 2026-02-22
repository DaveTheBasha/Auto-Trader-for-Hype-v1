"""
Hyperliquid Trading Module
Executes trades on Hyperliquid perpetuals exchange
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
import eth_account
from eth_account.signers.local import LocalAccount
from loguru import logger

from models import TradingSignal, Trade, TradeStatus, SignalType, Database
from config import config

# Hyperliquid SDK imports
try:
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants
    HYPERLIQUID_AVAILABLE = True
except ImportError:
    HYPERLIQUID_AVAILABLE = False
    logger.warning("Hyperliquid SDK not installed. Trading will be simulated.")


class HyperliquidTrader:
    """Handles trading operations on Hyperliquid"""

    def __init__(self, db: Database):
        self.db = db
        self.account: Optional[LocalAccount] = None
        self.info: Optional[Info] = None
        self.exchange: Optional[Exchange] = None
        self.is_testnet = config.hyperliquid.testnet
        self._initialized = False

    async def initialize(self):
        """Initialize Hyperliquid connection"""
        if not HYPERLIQUID_AVAILABLE:
            logger.warning("Running in SIMULATION mode - no real trades will be executed")
            self._initialized = True
            return

        if not config.hyperliquid.private_key:
            raise ValueError("HYPERLIQUID_PRIVATE_KEY not set in environment")

        try:
            # Create account from private key
            self.account = eth_account.Account.from_key(config.hyperliquid.private_key)
            logger.info(f"Wallet address: {self.account.address}")

            # Set API URL based on testnet/mainnet
            base_url = constants.TESTNET_API_URL if self.is_testnet else constants.MAINNET_API_URL

            # Initialize Info client for market data
            self.info = Info(base_url, skip_ws=True)

            # Initialize Exchange client for trading
            self.exchange = Exchange(
                self.account,
                base_url,
                account_address=config.hyperliquid.wallet_address or self.account.address
            )

            self._initialized = True
            mode = "TESTNET" if self.is_testnet else "MAINNET"
            logger.info(f"Hyperliquid trader initialized on {mode}")

        except Exception as e:
            logger.error(f"Failed to initialize Hyperliquid: {e}")
            raise

    async def get_market_price(self, asset: str) -> Optional[float]:
        """Get current market price for an asset"""
        if not self._initialized:
            raise RuntimeError("Trader not initialized")

        if not HYPERLIQUID_AVAILABLE or not self.info:
            # Simulation mode - return mock price
            mock_prices = {
                "BTC": 95000, "ETH": 3500, "SOL": 180, "ARB": 1.2,
                "DOGE": 0.35, "AVAX": 40, "LINK": 25, "OP": 3.5
            }
            return mock_prices.get(asset, 100.0)

        try:
            # Get all mids (mid prices)
            all_mids = self.info.all_mids()
            symbol = f"{asset}-USD"

            if symbol in all_mids:
                return float(all_mids[symbol])
            else:
                logger.warning(f"No price found for {symbol}")
                return None

        except Exception as e:
            logger.error(f"Error fetching price for {asset}: {e}")
            return None

    async def get_account_balance(self) -> Dict[str, float]:
        """Get account balance and margin info"""
        if not self._initialized:
            raise RuntimeError("Trader not initialized")

        if not HYPERLIQUID_AVAILABLE or not self.info:
            # Simulation mode
            return {
                "equity": 10000.0,
                "available_margin": 8000.0,
                "margin_used": 2000.0
            }

        try:
            address = config.hyperliquid.wallet_address or self.account.address
            user_state = self.info.user_state(address)

            return {
                "equity": float(user_state.get("marginSummary", {}).get("accountValue", 0)),
                "available_margin": float(user_state.get("withdrawable", 0)),
                "margin_used": float(user_state.get("marginSummary", {}).get("totalMarginUsed", 0))
            }

        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return {}

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        if not self._initialized:
            raise RuntimeError("Trader not initialized")

        if not HYPERLIQUID_AVAILABLE or not self.info:
            return []

        try:
            address = config.hyperliquid.wallet_address or self.account.address
            user_state = self.info.user_state(address)

            positions = []
            for pos in user_state.get("assetPositions", []):
                position_data = pos.get("position", {})
                if float(position_data.get("szi", 0)) != 0:
                    positions.append({
                        "asset": position_data.get("coin", ""),
                        "size": float(position_data.get("szi", 0)),
                        "entry_price": float(position_data.get("entryPx", 0)),
                        "unrealized_pnl": float(position_data.get("unrealizedPnl", 0)),
                        "leverage": int(position_data.get("leverage", {}).get("value", 1))
                    })

            return positions

        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    async def place_order(
        self,
        asset: str,
        is_buy: bool,
        size: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
        order_type: str = "market"
    ) -> Optional[Dict[str, Any]]:
        """Place an order on Hyperliquid"""
        if not self._initialized:
            raise RuntimeError("Trader not initialized")

        if not HYPERLIQUID_AVAILABLE or not self.exchange:
            # Simulation mode
            logger.info(f"[SIMULATION] {'BUY' if is_buy else 'SELL'} {size} {asset}")
            return {
                "status": "simulated",
                "filled": True,
                "order_id": f"sim_{datetime.utcnow().timestamp()}"
            }

        try:
            symbol = f"{asset}"

            if order_type == "market":
                # Market order
                result = self.exchange.market_open(
                    symbol,
                    is_buy,
                    size,
                    None,  # No slippage for market
                    reduce_only=reduce_only
                )
            else:
                # Limit order
                if price is None:
                    raise ValueError("Price required for limit order")
                result = self.exchange.order(
                    symbol,
                    is_buy,
                    size,
                    price,
                    {"limit": {"tif": "Gtc"}},
                    reduce_only=reduce_only
                )

            logger.info(f"Order result: {result}")
            return result

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    async def set_leverage(self, asset: str, leverage: int) -> bool:
        """Set leverage for an asset"""
        if not self._initialized:
            raise RuntimeError("Trader not initialized")

        if not HYPERLIQUID_AVAILABLE or not self.exchange:
            logger.info(f"[SIMULATION] Set leverage for {asset} to {leverage}x")
            return True

        try:
            result = self.exchange.update_leverage(leverage, asset)
            logger.info(f"Leverage set for {asset}: {leverage}x")
            return True
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            return False

    async def execute_signal(
        self,
        signal: TradingSignal,
        position_size_usd: float,
        leverage: int
    ) -> Optional[Trade]:
        """Execute a trading signal"""
        logger.info(f"Executing signal: {signal.signal_type.value} {signal.asset}")

        # Get current price
        current_price = await self.get_market_price(signal.asset)
        if not current_price:
            logger.error(f"Could not get price for {signal.asset}")
            return None

        # Calculate position size in asset units
        size = position_size_usd / current_price

        # Set leverage
        await self.set_leverage(signal.asset, leverage)

        # Determine order direction
        is_buy = signal.signal_type == SignalType.LONG

        # Place order
        result = await self.place_order(
            asset=signal.asset,
            is_buy=is_buy,
            size=size,
            order_type="market"
        )

        if not result:
            logger.error("Order execution failed")
            return None

        # Calculate SL/TP if not provided
        entry_price = signal.entry_price or current_price

        if signal.stop_loss:
            stop_loss = signal.stop_loss
        else:
            sl_pct = config.risk.default_stop_loss_percent / 100
            if is_buy:
                stop_loss = entry_price * (1 - sl_pct)
            else:
                stop_loss = entry_price * (1 + sl_pct)

        if signal.take_profit:
            take_profit = signal.take_profit
        else:
            tp_pct = config.risk.default_take_profit_percent / 100
            if is_buy:
                take_profit = entry_price * (1 + tp_pct)
            else:
                take_profit = entry_price * (1 - tp_pct)

        # Create trade record
        async with self.db.get_session() as session:
            trade = Trade(
                signal_id=signal.id,
                trader_username=signal.trader_username,
                asset=signal.asset,
                signal_type=signal.signal_type,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                size_usd=position_size_usd,
                leverage=leverage,
                status=TradeStatus.OPEN,
                opened_at=datetime.utcnow(),
                hyperliquid_order_id=result.get("order_id") or str(result)
            )

            session.add(trade)
            await session.commit()
            await session.refresh(trade)

            logger.info(
                f"Trade opened: #{trade.id} {signal.signal_type.value} {signal.asset} "
                f"@ {entry_price:.4f}, SL: {stop_loss:.4f}, TP: {take_profit:.4f}"
            )

            return trade

    async def close_trade(self, trade: Trade, reason: str = "manual") -> bool:
        """Close an open trade"""
        if trade.status != TradeStatus.OPEN:
            logger.warning(f"Trade #{trade.id} is not open")
            return False

        # Get current price
        current_price = await self.get_market_price(trade.asset)
        if not current_price:
            return False

        # Close position (opposite direction)
        is_buy = trade.signal_type == SignalType.SHORT  # Opposite to close
        size = trade.size_usd / trade.entry_price

        result = await self.place_order(
            asset=trade.asset,
            is_buy=is_buy,
            size=size,
            order_type="market",
            reduce_only=True
        )

        if not result:
            return False

        # Calculate PnL
        if trade.signal_type == SignalType.LONG:
            pnl_percent = ((current_price - trade.entry_price) / trade.entry_price) * 100 * trade.leverage
        else:
            pnl_percent = ((trade.entry_price - current_price) / trade.entry_price) * 100 * trade.leverage

        pnl_usd = trade.size_usd * (pnl_percent / 100)

        # Update trade record
        async with self.db.get_session() as session:
            trade.exit_price = current_price
            trade.pnl_usd = pnl_usd
            trade.pnl_percent = pnl_percent
            trade.status = TradeStatus.CLOSED
            trade.closed_at = datetime.utcnow()
            trade.notes = f"Closed: {reason}"

            session.add(trade)
            await session.commit()

            logger.info(
                f"Trade closed: #{trade.id} {trade.asset} "
                f"PnL: ${pnl_usd:.2f} ({pnl_percent:.2f}%)"
            )

        return True

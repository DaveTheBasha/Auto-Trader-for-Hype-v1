"""
Telegram Notifications Bot
Sends trade alerts to your Telegram chat
"""
import asyncio
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

import aiohttp
from loguru import logger


@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    bot_token: str
    chat_id: str
    enabled: bool = True


class TelegramNotifier:
    """
    Sends trading notifications to Telegram.

    Setup:
    1. Create a bot via @BotFather on Telegram
    2. Get the bot token
    3. Start a chat with your bot
    4. Get your chat_id via https://api.telegram.org/bot<TOKEN>/getUpdates
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.enabled = bool(bot_token and chat_id)

        if not self.enabled:
            logger.warning("Telegram notifications disabled (missing bot_token or chat_id)")

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        if not self.enabled:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                }

                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.debug("Telegram notification sent")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Telegram error: {error}")
                        return False

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def notify_trade_opened(
        self,
        asset: str,
        signal_type: str,
        size_usd: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trader: Optional[str] = None,
        leverage: Optional[float] = None
    ):
        """Notify when a trade is opened"""
        emoji = "📈" if signal_type.lower() == "long" else "📉"
        direction = "LONG" if signal_type.lower() == "long" else "SHORT"

        message = f"""
{emoji} <b>NEW TRADE OPENED</b>

<b>Asset:</b> {asset}
<b>Direction:</b> {direction}
<b>Size:</b> ${size_usd:,.2f}
<b>Entry:</b> ${entry_price:,.4f}
"""

        if leverage:
            message += f"<b>Leverage:</b> {leverage}x\n"

        if stop_loss:
            sl_pct = abs((stop_loss - entry_price) / entry_price * 100)
            message += f"<b>Stop Loss:</b> ${stop_loss:,.4f} (-{sl_pct:.1f}%)\n"

        if take_profit:
            tp_pct = abs((take_profit - entry_price) / entry_price * 100)
            message += f"<b>Take Profit:</b> ${take_profit:,.4f} (+{tp_pct:.1f}%)\n"

        if trader:
            message += f"\n<i>Signal from @{trader}</i>"

        message += f"\n\n<code>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</code>"

        await self.send_message(message)

    async def notify_trade_closed(
        self,
        asset: str,
        signal_type: str,
        size_usd: float,
        entry_price: float,
        exit_price: float,
        pnl_usd: float,
        pnl_percent: float,
        reason: str = "Manual"
    ):
        """Notify when a trade is closed"""
        is_profit = pnl_usd >= 0
        emoji = "💰" if is_profit else "💸"
        result = "PROFIT" if is_profit else "LOSS"
        direction = "LONG" if signal_type.lower() == "long" else "SHORT"

        pnl_emoji = "🟢" if is_profit else "🔴"

        message = f"""
{emoji} <b>TRADE CLOSED - {result}</b>

<b>Asset:</b> {asset}
<b>Direction:</b> {direction}
<b>Size:</b> ${size_usd:,.2f}

<b>Entry:</b> ${entry_price:,.4f}
<b>Exit:</b> ${exit_price:,.4f}

{pnl_emoji} <b>PnL:</b> ${pnl_usd:+,.2f} ({pnl_percent:+.2f}%)

<b>Reason:</b> {reason}

<code>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</code>
"""

        await self.send_message(message)

    async def notify_signal_detected(
        self,
        trader: str,
        asset: str,
        signal_type: str,
        confidence: float,
        tweet_text: str
    ):
        """Notify when a trading signal is detected"""
        emoji = "🔔"
        direction = "LONG" if signal_type.lower() == "long" else "SHORT"

        # Truncate tweet if too long
        if len(tweet_text) > 200:
            tweet_text = tweet_text[:200] + "..."

        message = f"""
{emoji} <b>SIGNAL DETECTED</b>

<b>Trader:</b> @{trader}
<b>Asset:</b> {asset}
<b>Signal:</b> {direction}
<b>Confidence:</b> {confidence:.0%}

<i>"{tweet_text}"</i>

<code>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</code>
"""

        await self.send_message(message)

    async def notify_stop_loss_hit(
        self,
        asset: str,
        signal_type: str,
        loss_usd: float,
        entry_price: float,
        stop_price: float
    ):
        """Notify when stop loss is triggered"""
        direction = "LONG" if signal_type.lower() == "long" else "SHORT"

        message = f"""
🛑 <b>STOP LOSS TRIGGERED</b>

<b>Asset:</b> {asset}
<b>Direction:</b> {direction}
<b>Entry:</b> ${entry_price:,.4f}
<b>Stop:</b> ${stop_price:,.4f}

🔴 <b>Loss:</b> ${abs(loss_usd):,.2f}

<code>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</code>
"""

        await self.send_message(message)

    async def notify_take_profit_hit(
        self,
        asset: str,
        signal_type: str,
        profit_usd: float,
        entry_price: float,
        tp_price: float
    ):
        """Notify when take profit is triggered"""
        direction = "LONG" if signal_type.lower() == "long" else "SHORT"

        message = f"""
🎯 <b>TAKE PROFIT HIT</b>

<b>Asset:</b> {asset}
<b>Direction:</b> {direction}
<b>Entry:</b> ${entry_price:,.4f}
<b>Target:</b> ${tp_price:,.4f}

🟢 <b>Profit:</b> ${profit_usd:,.2f}

<code>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</code>
"""

        await self.send_message(message)

    async def notify_daily_summary(
        self,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
        best_trade: Optional[dict] = None,
        worst_trade: Optional[dict] = None
    ):
        """Send daily trading summary"""
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        emoji = "📊"
        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"

        message = f"""
{emoji} <b>DAILY SUMMARY</b>

<b>Trades:</b> {total_trades}
<b>Wins:</b> {wins} | <b>Losses:</b> {losses}
<b>Win Rate:</b> {win_rate:.1f}%

{pnl_emoji} <b>Total PnL:</b> ${total_pnl:+,.2f}
"""

        if best_trade:
            message += f"\n<b>Best:</b> {best_trade['asset']} +${best_trade['pnl']:,.2f}"

        if worst_trade:
            message += f"\n<b>Worst:</b> {worst_trade['asset']} ${worst_trade['pnl']:,.2f}"

        message += f"\n\n<code>{datetime.utcnow().strftime('%Y-%m-%d')} UTC</code>"

        await self.send_message(message)

    async def notify_error(self, error_message: str, context: str = ""):
        """Notify about an error"""
        message = f"""
⚠️ <b>BOT ERROR</b>

<b>Context:</b> {context or 'Unknown'}
<b>Error:</b> {error_message[:500]}

<code>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</code>
"""

        await self.send_message(message)

    async def notify_bot_started(self, mode: str = "Unknown"):
        """Notify that the bot has started"""
        message = f"""
🚀 <b>BOT STARTED</b>

<b>Mode:</b> {mode}
<b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

Bot is now monitoring for trading signals.
"""

        await self.send_message(message)

    async def notify_bot_stopped(self, reason: str = "Manual shutdown"):
        """Notify that the bot has stopped"""
        message = f"""
🛑 <b>BOT STOPPED</b>

<b>Reason:</b> {reason}
<b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""

        await self.send_message(message)

    async def test_connection(self) -> bool:
        """Test the Telegram connection"""
        if not self.enabled:
            logger.warning("Telegram not configured")
            return False

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/getMe"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_name = data.get('result', {}).get('username', 'Unknown')
                        logger.info(f"Telegram connected: @{bot_name}")
                        return True
                    else:
                        logger.error(f"Telegram connection failed: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Telegram test failed: {e}")
            return False


# Global notifier instance
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> Optional[TelegramNotifier]:
    """Get the global notifier instance"""
    return _notifier


def init_notifier(bot_token: str, chat_id: str) -> TelegramNotifier:
    """Initialize the global notifier"""
    global _notifier
    _notifier = TelegramNotifier(bot_token, chat_id)
    return _notifier


async def test_telegram():
    """Test function for Telegram notifications"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

    if not bot_token or not chat_id:
        print("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        print("\nHow to get these:")
        print("1. Message @BotFather on Telegram")
        print("2. Send /newbot and follow instructions")
        print("3. Copy the bot token")
        print("4. Start a chat with your new bot")
        print("5. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates")
        print("6. Send a message to the bot, then refresh the URL")
        print("7. Find 'chat':{'id': XXXXX} - that's your chat_id")
        return

    notifier = TelegramNotifier(bot_token, chat_id)

    # Test connection
    if await notifier.test_connection():
        print("Connection successful!")

        # Send test message
        await notifier.send_message("🧪 <b>Test notification</b>\n\nYour Hyperliquid bot notifications are working!")
        print("Test message sent!")
    else:
        print("Connection failed. Check your credentials.")


if __name__ == '__main__':
    asyncio.run(test_telegram())

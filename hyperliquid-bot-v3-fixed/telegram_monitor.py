"""
Telegram Monitoring Module
Monitors Telegram channels for trading signals
"""
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable
from loguru import logger

try:
    from telethon import TelegramClient, events
    from telethon.tl.types import Channel, Chat
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.warning("Telethon not installed. Run: pip install telethon")

from models import Database


class TelegramMonitor:
    """Monitors Telegram channels for trading signals"""

    # Popular crypto trading channels (public)
    DEFAULT_CHANNELS = [
        "WhaleTrades",           # Whale movements
        "CryptoSignalsOrg",      # Trading signals
        "Binance_Killers",       # Binance signals
        "WallStreetBetsCrypto",  # WSB crypto
        "FatPigSignals",         # Free signals
        "CryptoInnerCircle",     # Trading calls
    ]

    def __init__(self, db: Database, api_id: str = "", api_hash: str = ""):
        self.db = db
        self.api_id = api_id
        self.api_hash = api_hash
        self.client: Optional[TelegramClient] = None
        self.tracked_channels: List[str] = self.DEFAULT_CHANNELS.copy()
        self._running = False
        self._message_callback: Optional[Callable] = None

    async def initialize(self):
        """Initialize Telegram client"""
        if not TELETHON_AVAILABLE:
            logger.error("Telethon not installed. Telegram monitoring disabled.")
            return False

        if not self.api_id or not self.api_hash:
            logger.warning("Telegram API credentials not set. Get them from https://my.telegram.org")
            return False

        try:
            self.client = TelegramClient('trading_bot_session', self.api_id, self.api_hash)
            await self.client.start()
            logger.info("Telegram client initialized")

            # Get info about tracked channels
            for channel in self.tracked_channels:
                try:
                    entity = await self.client.get_entity(channel)
                    logger.info(f"Tracking Telegram channel: {channel}")
                except Exception as e:
                    logger.warning(f"Could not find channel {channel}: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize Telegram: {e}")
            return False

    def add_channel(self, channel: str):
        """Add a channel to track"""
        if channel not in self.tracked_channels:
            self.tracked_channels.append(channel)
            logger.info(f"Added Telegram channel: {channel}")

    def remove_channel(self, channel: str):
        """Remove a channel from tracking"""
        if channel in self.tracked_channels:
            self.tracked_channels.remove(channel)
            logger.info(f"Removed Telegram channel: {channel}")

    async def start_monitoring(self, callback: Callable):
        """Start monitoring channels for messages"""
        if not self.client:
            logger.error("Telegram client not initialized")
            return

        self._message_callback = callback
        self._running = True

        @self.client.on(events.NewMessage(chats=self.tracked_channels))
        async def handler(event):
            if not self._running:
                return

            message_data = {
                "id": event.id,
                "text": event.text,
                "channel": event.chat.title if hasattr(event.chat, 'title') else str(event.chat_id),
                "channel_id": event.chat_id,
                "date": event.date,
                "source": "telegram"
            }

            logger.info(f"New message from {message_data['channel']}: {event.text[:50]}...")

            if self._message_callback:
                await self._message_callback(message_data)

        logger.info(f"Monitoring {len(self.tracked_channels)} Telegram channels...")
        await self.client.run_until_disconnected()

    async def stop(self):
        """Stop monitoring"""
        self._running = False
        if self.client:
            await self.client.disconnect()
        logger.info("Telegram monitor stopped")

    async def search_channels(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for trading channels"""
        if not self.client:
            return []

        results = []
        try:
            async for dialog in self.client.iter_dialogs():
                if query.lower() in dialog.name.lower():
                    results.append({
                        "name": dialog.name,
                        "id": dialog.id,
                        "type": "channel" if dialog.is_channel else "group"
                    })
                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.error(f"Error searching channels: {e}")

        return results

    async def get_channel_history(self, channel: str, limit: int = 100) -> List[Dict]:
        """Get recent messages from a channel for analysis"""
        if not self.client:
            return []

        messages = []
        try:
            entity = await self.client.get_entity(channel)
            async for message in self.client.iter_messages(entity, limit=limit):
                if message.text:
                    messages.append({
                        "id": message.id,
                        "text": message.text,
                        "date": message.date,
                        "views": message.views or 0
                    })
        except Exception as e:
            logger.error(f"Error getting channel history: {e}")

        return messages

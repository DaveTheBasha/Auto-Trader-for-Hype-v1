"""
Twitter Monitoring Module
Fetches and processes tweets from tracked trading accounts
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import tweepy
from tweepy import Client
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Tweet, Database
from config import config


class TwitterMonitor:
    """Monitors Twitter for trading signals from specified accounts"""

    def __init__(self, db: Database):
        self.db = db
        self.client: Optional[Client] = None
        self.tracked_users: Dict[str, str] = {}  # username -> user_id mapping
        self._running = False

    async def initialize(self):
        """Initialize Twitter client and fetch user IDs"""
        if not config.twitter.bearer_token:
            logger.warning("TWITTER_BEARER_TOKEN not set - Twitter monitoring disabled")
            logger.info("Using Telegram and/or Wallet Copy Trading instead")
            return  # Skip Twitter, don't crash

        self.client = Client(bearer_token=config.twitter.bearer_token)

        # Get user IDs for tracked accounts
        for username in config.twitter.tracked_accounts:
            try:
                user = self.client.get_user(username=username)
                if user.data:
                    self.tracked_users[username] = user.data.id
                    logger.info(f"Tracking @{username} (ID: {user.data.id})")
                else:
                    logger.warning(f"Could not find user @{username}")
            except Exception as e:
                logger.error(f"Error fetching user @{username}: {e}")

        logger.info(f"Twitter monitor initialized with {len(self.tracked_users)} accounts")

    async def fetch_recent_tweets(self, username: str, since_minutes: int = 60) -> List[Dict[str, Any]]:
        """Fetch recent tweets from a specific user"""
        if username not in self.tracked_users:
            logger.warning(f"User @{username} not in tracked list")
            return []

        user_id = self.tracked_users[username]
        tweets_data = []

        try:
            # Calculate start time
            start_time = datetime.utcnow() - timedelta(minutes=since_minutes)

            # Fetch tweets
            response = self.client.get_users_tweets(
                id=user_id,
                start_time=start_time,
                max_results=10,
                tweet_fields=["created_at", "text", "author_id"],
                exclude=["retweets", "replies"]
            )

            if response.data:
                for tweet in response.data:
                    tweets_data.append({
                        "id": tweet.id,
                        "text": tweet.text,
                        "author_id": tweet.author_id,
                        "author_username": username,
                        "created_at": tweet.created_at
                    })
                logger.debug(f"Fetched {len(tweets_data)} tweets from @{username}")

        except Exception as e:
            logger.error(f"Error fetching tweets from @{username}: {e}")

        return tweets_data

    async def fetch_all_tracked_tweets(self, since_minutes: int = 60) -> List[Dict[str, Any]]:
        """Fetch tweets from all tracked accounts"""
        all_tweets = []

        for username in self.tracked_users:
            tweets = await self.fetch_recent_tweets(username, since_minutes)
            all_tweets.extend(tweets)

        return all_tweets

    async def store_tweet(self, tweet_data: Dict[str, Any]) -> Optional[Tweet]:
        """Store a tweet in the database if not already exists"""
        async with self.db.get_session() as session:
            # Check if tweet already exists
            result = await session.execute(
                select(Tweet).where(Tweet.id == str(tweet_data["id"]))
            )
            existing = result.scalar_one_or_none()

            if existing:
                return None  # Already processed

            # Create new tweet record
            tweet = Tweet(
                id=str(tweet_data["id"]),
                author_username=tweet_data["author_username"],
                author_id=str(tweet_data["author_id"]),
                text=tweet_data["text"],
                created_at=tweet_data["created_at"],
                processed=False,
                has_signal=False
            )

            session.add(tweet)
            await session.commit()
            logger.info(f"Stored new tweet from @{tweet_data['author_username']}: {tweet_data['text'][:50]}...")

            return tweet

    async def get_unprocessed_tweets(self) -> List[Tweet]:
        """Get all unprocessed tweets from database"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Tweet).where(Tweet.processed == False).order_by(Tweet.created_at)
            )
            return list(result.scalars().all())

    async def mark_tweet_processed(self, tweet_id: str, has_signal: bool = False):
        """Mark a tweet as processed"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Tweet).where(Tweet.id == tweet_id)
            )
            tweet = result.scalar_one_or_none()
            if tweet:
                tweet.processed = True
                tweet.has_signal = has_signal
                await session.commit()

    async def poll_loop(self, callback=None):
        """Main polling loop for fetching new tweets"""
        self._running = True
        logger.info("Starting Twitter polling loop...")

        while self._running:
            try:
                # Fetch recent tweets
                tweets = await self.fetch_all_tracked_tweets(since_minutes=5)

                # Store new tweets
                new_tweets = []
                for tweet_data in tweets:
                    stored = await self.store_tweet(tweet_data)
                    if stored:
                        new_tweets.append(stored)

                # Process new tweets via callback
                if new_tweets and callback:
                    await callback(new_tweets)

                # Wait before next poll
                await asyncio.sleep(config.twitter.poll_interval_seconds)

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(config.twitter.poll_interval_seconds)

    def stop(self):
        """Stop the polling loop"""
        self._running = False
        logger.info("Twitter monitor stopped")

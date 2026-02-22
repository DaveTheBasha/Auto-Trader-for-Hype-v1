"""
Signal Parser Module
Extracts trading signals from tweets using NLP and pattern matching
"""
import re
from typing import Optional, List, Tuple
from dataclasses import dataclass
from loguru import logger

from models import Tweet, TradingSignal, SignalType, Database
from config import config


@dataclass
class ParsedSignal:
    """Parsed trading signal from tweet"""
    asset: str
    signal_type: SignalType
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: Optional[int] = None
    confidence_score: float = 0.0
    raw_text: str = ""


class SignalParser:
    """Parses trading signals from tweet text"""

    # Keywords indicating long positions
    LONG_KEYWORDS = [
        r'\blong\b', r'\bbuy\b', r'\blonging\b', r'\bbullish\b',
        r'\blong\s+entry\b', r'\bentered\s+long\b', r'\bgoing\s+long\b',
        r'\bbid\b', r'\bbuying\b', r'\baccumulating\b', r'\bacquiring\b',
        r'🟢', r'📈', r'\bape\s+in\b', r'\baped\b'
    ]

    # Keywords indicating short positions
    SHORT_KEYWORDS = [
        r'\bshort\b', r'\bsell\b', r'\bshorting\b', r'\bbearish\b',
        r'\bshort\s+entry\b', r'\bentered\s+short\b', r'\bgoing\s+short\b',
        r'\bshorting\b', r'\bfading\b', r'🔴', r'📉'
    ]

    # Price patterns
    PRICE_PATTERNS = [
        r'\$?([\d,]+\.?\d*)\s*(?:k|K)?',  # $50000 or 50k
        r'@\s*\$?([\d,]+\.?\d*)',  # @ 50000
    ]

    # Entry price patterns
    ENTRY_PATTERNS = [
        r'(?:entry|entered|enter|at|@|bought|longed|shorted)\s*:?\s*\$?([\d,]+\.?\d*)',
        r'(?:entry|price)\s*:?\s*\$?([\d,]+\.?\d*)',
    ]

    # Stop loss patterns
    SL_PATTERNS = [
        r'(?:sl|stop\s*loss|stop|stoploss)\s*:?\s*\$?([\d,]+\.?\d*)',
        r'(?:invalidation|invalid)\s*:?\s*\$?([\d,]+\.?\d*)',
    ]

    # Take profit patterns
    TP_PATTERNS = [
        r'(?:tp|take\s*profit|target|tgt)\s*:?\s*\$?([\d,]+\.?\d*)',
        r'(?:tp|target)\s*\d?\s*:?\s*\$?([\d,]+\.?\d*)',
    ]

    # Leverage patterns
    LEVERAGE_PATTERNS = [
        r'(\d+)\s*x\b',
        r'(?:leverage|lev)\s*:?\s*(\d+)',
    ]

    def __init__(self, db: Database):
        self.db = db
        self.supported_assets = set(config.trading.supported_assets)
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        # Build asset pattern dynamically
        asset_pattern = r'\b(' + '|'.join(self.supported_assets) + r')\b'
        self.asset_regex = re.compile(asset_pattern, re.IGNORECASE)

        # Compile signal direction patterns
        self.long_patterns = [re.compile(p, re.IGNORECASE) for p in self.LONG_KEYWORDS]
        self.short_patterns = [re.compile(p, re.IGNORECASE) for p in self.SHORT_KEYWORDS]

        # Compile price extraction patterns
        self.entry_regexes = [re.compile(p, re.IGNORECASE) for p in self.ENTRY_PATTERNS]
        self.sl_regexes = [re.compile(p, re.IGNORECASE) for p in self.SL_PATTERNS]
        self.tp_regexes = [re.compile(p, re.IGNORECASE) for p in self.TP_PATTERNS]
        self.leverage_regexes = [re.compile(p, re.IGNORECASE) for p in self.LEVERAGE_PATTERNS]

    def _extract_asset(self, text: str) -> Optional[str]:
        """Extract cryptocurrency asset from text"""
        # Look for explicit mentions
        matches = self.asset_regex.findall(text)
        if matches:
            return matches[0].upper()

        # Check for $ASSET pattern
        ticker_match = re.search(r'\$([A-Za-z]+)', text)
        if ticker_match:
            ticker = ticker_match.group(1).upper()
            if ticker in self.supported_assets:
                return ticker

        # Check for common variations
        variations = {
            'BITCOIN': 'BTC', 'ETHEREUM': 'ETH', 'SOLANA': 'SOL',
            'DOGECOIN': 'DOGE', 'ARBITRUM': 'ARB', 'AVALANCHE': 'AVAX'
        }
        text_upper = text.upper()
        for name, symbol in variations.items():
            if name in text_upper:
                return symbol

        return None

    def _detect_signal_type(self, text: str) -> Tuple[Optional[SignalType], float]:
        """Detect if the tweet indicates a long or short position"""
        long_score = 0
        short_score = 0

        # Check for long keywords
        for pattern in self.long_patterns:
            if pattern.search(text):
                long_score += 1

        # Check for short keywords
        for pattern in self.short_patterns:
            if pattern.search(text):
                short_score += 1

        # Determine direction
        if long_score > short_score and long_score > 0:
            confidence = min(long_score / 3, 1.0)  # Normalize to 0-1
            return SignalType.LONG, confidence
        elif short_score > long_score and short_score > 0:
            confidence = min(short_score / 3, 1.0)
            return SignalType.SHORT, confidence

        return None, 0.0

    def _parse_price(self, price_str: str) -> Optional[float]:
        """Parse price string to float"""
        try:
            # Remove commas and handle k notation
            price_str = price_str.replace(',', '')
            if 'k' in price_str.lower():
                price_str = price_str.lower().replace('k', '')
                return float(price_str) * 1000
            return float(price_str)
        except ValueError:
            return None

    def _extract_price(self, text: str, patterns: List[re.Pattern]) -> Optional[float]:
        """Extract price using multiple patterns"""
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                price = self._parse_price(match.group(1))
                if price and price > 0:
                    return price
        return None

    def _extract_leverage(self, text: str) -> Optional[int]:
        """Extract leverage from text"""
        for pattern in self.leverage_regexes:
            match = pattern.search(text)
            if match:
                lev = int(match.group(1))
                if 1 <= lev <= 100:  # Reasonable leverage range
                    return lev
        return None

    def _calculate_confidence(
        self,
        has_asset: bool,
        signal_confidence: float,
        has_entry: bool,
        has_sl: bool,
        has_tp: bool
    ) -> float:
        """Calculate overall signal confidence score"""
        score = 0.0

        if has_asset:
            score += 0.3
        score += signal_confidence * 0.3

        if has_entry:
            score += 0.15
        if has_sl:
            score += 0.15
        if has_tp:
            score += 0.1

        return min(score, 1.0)

    def parse_tweet(self, tweet: Tweet) -> Optional[ParsedSignal]:
        """Parse a tweet and extract trading signal if present"""
        text = tweet.text
        logger.debug(f"Parsing tweet: {text[:100]}...")

        # Extract asset
        asset = self._extract_asset(text)
        if not asset:
            logger.debug("No supported asset found in tweet")
            return None

        # Detect signal type
        signal_type, signal_confidence = self._detect_signal_type(text)
        if not signal_type:
            logger.debug("No clear signal direction in tweet")
            return None

        # Extract price levels
        entry_price = self._extract_price(text, self.entry_regexes)
        stop_loss = self._extract_price(text, self.sl_regexes)
        take_profit = self._extract_price(text, self.tp_regexes)
        leverage = self._extract_leverage(text)

        # Calculate confidence
        confidence = self._calculate_confidence(
            has_asset=True,
            signal_confidence=signal_confidence,
            has_entry=entry_price is not None,
            has_sl=stop_loss is not None,
            has_tp=take_profit is not None
        )

        signal = ParsedSignal(
            asset=asset,
            signal_type=signal_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            leverage=leverage,
            confidence_score=confidence,
            raw_text=text
        )

        logger.info(
            f"Parsed signal: {signal.signal_type.value.upper()} {signal.asset} "
            f"(confidence: {confidence:.2f})"
        )

        return signal

    async def store_signal(self, tweet: Tweet, signal: ParsedSignal) -> TradingSignal:
        """Store a parsed signal in the database"""
        async with self.db.get_session() as session:
            db_signal = TradingSignal(
                tweet_id=tweet.id,
                trader_username=tweet.author_username,
                asset=signal.asset,
                signal_type=signal.signal_type,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                leverage=signal.leverage,
                confidence_score=signal.confidence_score,
                raw_text=signal.raw_text,
                executed=False
            )

            session.add(db_signal)
            await session.commit()
            await session.refresh(db_signal)

            logger.info(f"Stored signal #{db_signal.id} from @{tweet.author_username}")
            return db_signal

    async def process_tweets(self, tweets: List[Tweet]) -> List[TradingSignal]:
        """Process multiple tweets and extract signals"""
        signals = []

        for tweet in tweets:
            parsed = self.parse_tweet(tweet)

            if parsed and parsed.confidence_score >= config.risk.min_confidence_score:
                db_signal = await self.store_signal(tweet, parsed)
                signals.append(db_signal)

        return signals

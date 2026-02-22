"""
Recommended Traders Database
Curated list of reputable crypto traders with proven track records

Updated: February 2025
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class TraderTier(Enum):
    """Trader reputation tiers"""
    ELITE = "elite"          # Proven multi-year track record, major calls
    ESTABLISHED = "established"  # Consistent performance, large following
    RISING = "rising"        # Up-and-coming, showing promise
    SPECIALIST = "specialist"  # Niche expertise (e.g., specific coins, derivatives)


@dataclass
class RecommendedTrader:
    """Recommended trader profile"""
    username: str           # Twitter/X handle (without @)
    name: str              # Display name
    tier: TraderTier
    followers: str         # Approximate follower count
    specialty: str         # What they're known for
    notable_calls: List[str]  # Famous accurate predictions
    risk_level: str        # conservative/moderate/aggressive
    signal_frequency: str  # low/medium/high
    notes: str             # Additional context
    active: bool = True    # Currently active


# =============================================================================
# ELITE TIER - Proven multi-year track records with major accurate calls
# =============================================================================

ELITE_TRADERS = [
    RecommendedTrader(
        username="SmartContracter",
        name="Smart Contracter",
        tier=TraderTier.ELITE,
        followers="200K+",
        specialty="Technical analysis, macro calls",
        notable_calls=[
            "Called BTC $3,200 capitulation bottom 6 months early (2018)",
            "Multiple accurate cycle top/bottom calls"
        ],
        risk_level="moderate",
        signal_frequency="low",
        notes="No paid signals. Quality over quantity. Highly respected in CT.",
        active=True
    ),
    RecommendedTrader(
        username="Pentoshi",
        name="Pentoshi",
        tier=TraderTier.ELITE,
        followers="533K+",
        specialty="Chart analysis, swing trading",
        notable_calls=[
            "Called BTC $64K top in April 2021",
            "Accurate altcoin cycle predictions"
        ],
        risk_level="moderate",
        signal_frequency="medium",
        notes="No Telegram/YouTube monetization. Pure trading focus.",
        active=True
    ),
    RecommendedTrader(
        username="CryptoKaleo",
        name="Crypto Kaleo",
        tier=TraderTier.ELITE,
        followers="476K+",
        specialty="Charts, crypto & equities crossover",
        notable_calls=[
            "Multiple accurate BTC/ETH swing calls",
            "Strong altcoin timing"
        ],
        risk_level="aggressive",
        signal_frequency="high",
        notes="Very active poster. Co-founded LedgerArt NFT initiative.",
        active=True
    ),
]

# =============================================================================
# ESTABLISHED TIER - Consistent performance, respected in community
# =============================================================================

ESTABLISHED_TRADERS = [
    RecommendedTrader(
        username="DonAlt",
        name="DonAlt",
        tier=TraderTier.ESTABLISHED,
        followers="392K+",
        specialty="Direct market commentary, no BS",
        notable_calls=[
            "Consistent swing trade calls",
            "Good risk management examples"
        ],
        risk_level="moderate",
        signal_frequency="medium",
        notes="Co-hosts Technical Roundup on YouTube. No promotional tie-ins.",
        active=True
    ),
    RecommendedTrader(
        username="CryptoCred",
        name="CryptoCred",
        tier=TraderTier.ESTABLISHED,
        followers="454K+",
        specialty="Trading education, frameworks",
        notable_calls=[
            "Educational threads on market structure",
            "Risk management frameworks"
        ],
        risk_level="conservative",
        signal_frequency="low",
        notes="Best for learning. Free lessons and trading frameworks.",
        active=True
    ),
    RecommendedTrader(
        username="HsakaTrades",
        name="Hsaka",
        tier=TraderTier.ESTABLISHED,
        followers="280K+",
        specialty="Derivatives, funding rates, liquidations",
        notable_calls=[
            "Funding rate arbitrage plays",
            "Liquidation cascade predictions"
        ],
        risk_level="aggressive",
        signal_frequency="high",
        notes="Deep derivatives expertise. Great for perps trading.",
        active=True
    ),
    RecommendedTrader(
        username="lightcrypto",
        name="Light",
        tier=TraderTier.ESTABLISHED,
        followers="150K+",
        specialty="Professional trading, risk management",
        notable_calls=[
            "Consistent profitable trading",
            "Strong position sizing examples"
        ],
        risk_level="conservative",
        signal_frequency="medium",
        notes="Former traditional finance. Very disciplined approach.",
        active=True
    ),
    RecommendedTrader(
        username="EmperorBTC",
        name="Emperor",
        tier=TraderTier.ESTABLISHED,
        followers="320K+",
        specialty="Trading education, technical analysis",
        notable_calls=[
            "BTC macro cycle analysis",
            "Educational trading threads"
        ],
        risk_level="moderate",
        signal_frequency="medium",
        notes="Great educational content. Teaches trading concepts clearly.",
        active=True
    ),
]

# =============================================================================
# RISING TIER - Up-and-coming traders showing strong promise
# =============================================================================

RISING_TRADERS = [
    RecommendedTrader(
        username="Ansem",
        name="Ansem",
        tier=TraderTier.RISING,
        followers="500K+",
        specialty="SOL ecosystem, memecoins, narratives",
        notable_calls=[
            "Early SOL ecosystem calls",
            "Memecoin timing (WIF, BONK early)"
        ],
        risk_level="aggressive",
        signal_frequency="high",
        notes="Best for SOL/memecoin plays. High risk, high reward style.",
        active=True
    ),
    RecommendedTrader(
        username="blaborade",
        name="Blabro",
        tier=TraderTier.RISING,
        followers="150K+",
        specialty="Altcoin trading, narrative plays",
        notable_calls=[
            "Multiple 10x altcoin calls",
            "Strong narrative identification"
        ],
        risk_level="aggressive",
        signal_frequency="high",
        notes="Good at catching rotating narratives early.",
        active=True
    ),
    RecommendedTrader(
        username="Route2FI",
        name="Route 2 FI",
        tier=TraderTier.RISING,
        followers="200K+",
        specialty="DeFi yields, airdrops, farming",
        notable_calls=[
            "Multiple profitable airdrop strategies",
            "DeFi yield optimization"
        ],
        risk_level="moderate",
        signal_frequency="medium",
        notes="Best for DeFi strategies beyond just trading.",
        active=True
    ),
    RecommendedTrader(
        username="ColdBloodShill",
        name="ColdBloodedShill",
        tier=TraderTier.RISING,
        followers="180K+",
        specialty="Altcoin trading, CT meta",
        notable_calls=[
            "Strong altcoin rotation plays",
            "Good entry/exit timing"
        ],
        risk_level="aggressive",
        signal_frequency="high",
        notes="Active trader with transparent P&L sharing.",
        active=True
    ),
    RecommendedTrader(
        username="MacnBTC",
        name="MacnBTC",
        tier=TraderTier.RISING,
        followers="120K+",
        specialty="BTC technical analysis, swing trading",
        notable_calls=[
            "Accurate BTC range predictions",
            "Clean technical setups"
        ],
        risk_level="moderate",
        signal_frequency="medium",
        notes="Focuses primarily on BTC. Clear chart analysis.",
        active=True
    ),
]

# =============================================================================
# SPECIALIST TIER - Niche expertise in specific areas
# =============================================================================

SPECIALIST_TRADERS = [
    RecommendedTrader(
        username="DegenSpartan",
        name="Degen Spartan",
        tier=TraderTier.SPECIALIST,
        followers="250K+",
        specialty="DeFi, on-chain analysis, yield farming",
        notable_calls=[
            "Early DeFi summer plays (2020)",
            "Protocol analysis and risks"
        ],
        risk_level="aggressive",
        signal_frequency="medium",
        notes="Deep DeFi expertise. Good for protocol-level analysis.",
        active=True
    ),
    RecommendedTrader(
        username="loomdart",
        name="Loomdart",
        tier=TraderTier.SPECIALIST,
        followers="100K+",
        specialty="Macro analysis, cross-market",
        notable_calls=[
            "Macro-crypto correlation plays",
            "Risk-on/risk-off timing"
        ],
        risk_level="moderate",
        signal_frequency="low",
        notes="Good macro perspective. Less frequent but insightful.",
        active=True
    ),
    RecommendedTrader(
        username="coaborado",
        name="Cobie",
        tier=TraderTier.SPECIALIST,
        followers="700K+",
        specialty="VC/insider perspective, macro",
        notable_calls=[
            "Early warning on FTX concerns",
            "Cycle timing insights"
        ],
        risk_level="conservative",
        signal_frequency="low",
        notes="More macro/industry commentary than direct signals.",
        active=True
    ),
    RecommendedTrader(
        username="inversebrah",
        name="inversebrah",
        tier=TraderTier.SPECIALIST,
        followers="200K+",
        specialty="Humor + contrarian market analysis",
        notable_calls=[
            "Sentiment indicator via memes",
            "Contrarian timing signals"
        ],
        risk_level="moderate",
        signal_frequency="medium",
        notes="Use as sentiment gauge. Memes often signal tops/bottoms.",
        active=True
    ),
]


# =============================================================================
# COMBINED LISTS & UTILITIES
# =============================================================================

ALL_RECOMMENDED_TRADERS = (
    ELITE_TRADERS +
    ESTABLISHED_TRADERS +
    RISING_TRADERS +
    SPECIALIST_TRADERS
)

def get_traders_by_tier(tier: TraderTier) -> List[RecommendedTrader]:
    """Get all traders of a specific tier"""
    return [t for t in ALL_RECOMMENDED_TRADERS if t.tier == tier]

def get_traders_by_risk(risk_level: str) -> List[RecommendedTrader]:
    """Get traders matching a risk level"""
    return [t for t in ALL_RECOMMENDED_TRADERS if t.risk_level == risk_level]

def get_high_frequency_traders() -> List[RecommendedTrader]:
    """Get traders who post signals frequently"""
    return [t for t in ALL_RECOMMENDED_TRADERS if t.signal_frequency == "high"]

def get_trader_usernames(traders: List[RecommendedTrader] = None) -> List[str]:
    """Get list of usernames for config"""
    if traders is None:
        traders = ALL_RECOMMENDED_TRADERS
    return [t.username for t in traders if t.active]


# =============================================================================
# PRESET CONFIGURATIONS
# =============================================================================

# Conservative setup - proven traders, lower frequency
CONSERVATIVE_PRESET = [
    "SmartContracter",
    "Pentoshi",
    "CryptoCred",
    "lightcrypto",
    "DonAlt"
]

# Balanced setup - mix of styles
BALANCED_PRESET = [
    "SmartContracter",
    "Pentoshi",
    "DonAlt",
    "CryptoKaleo",
    "HsakaTrades",
    "EmperorBTC"
]

# Aggressive setup - high frequency, higher risk
AGGRESSIVE_PRESET = [
    "CryptoKaleo",
    "Ansem",
    "HsakaTrades",
    "blaborade",
    "ColdBloodShill",
    "DegenSpartan"
]

# SOL/Memecoin focused
SOLANA_PRESET = [
    "Ansem",
    "blaborade",
    "ColdBloodShill"
]

# BTC focused
BITCOIN_PRESET = [
    "SmartContracter",
    "Pentoshi",
    "MacnBTC",
    "EmperorBTC"
]


def print_trader_table():
    """Print a formatted table of all recommended traders"""
    print("\n" + "=" * 100)
    print("RECOMMENDED CRYPTO TRADERS - CURATED LIST")
    print("=" * 100)

    for tier in TraderTier:
        traders = get_traders_by_tier(tier)
        if not traders:
            continue

        print(f"\n{'─' * 100}")
        print(f"  {tier.value.upper()} TIER")
        print(f"{'─' * 100}")
        print(f"{'Username':<20} {'Followers':<12} {'Risk':<12} {'Specialty':<40}")
        print(f"{'─' * 20} {'─' * 12} {'─' * 12} {'─' * 40}")

        for t in traders:
            print(f"@{t.username:<19} {t.followers:<12} {t.risk_level:<12} {t.specialty[:40]}")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    print_trader_table()

    print("\n\nPRESET CONFIGURATIONS:")
    print(f"Conservative: {CONSERVATIVE_PRESET}")
    print(f"Balanced:     {BALANCED_PRESET}")
    print(f"Aggressive:   {AGGRESSIVE_PRESET}")

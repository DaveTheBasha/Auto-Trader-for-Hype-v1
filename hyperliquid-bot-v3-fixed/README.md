# Hyperliquid Twitter Trading Bot 🤖

An automated trading bot that monitors Twitter/X for trading signals from popular traders and executes trades on Hyperliquid perpetuals exchange.

## ⚠️ Risk Warning

**This bot trades with REAL money.** Trading based on social media signals is extremely risky. You can lose your entire investment. Only trade what you can afford to lose.

- Past performance of traders does not guarantee future results
- Signals may be delayed, inaccurate, or manipulated
- Market conditions can change rapidly
- Always start with testnet before using real funds

## Features

- **Twitter Monitoring**: Polls specified trader accounts for new tweets
- **Signal Parsing**: NLP-based extraction of trading signals (long/short, entry, SL, TP)
- **Risk Management**: Position sizing, leverage limits, max positions
- **Trade Execution**: Automated order placement on Hyperliquid
- **Performance Learning**: Tracks trader success rates to optimize position sizing
- **Position Monitoring**: Auto-closes trades at stop loss/take profit

## Tracked Traders

Currently configured to follow:
- @IncomeSharks
- @astronomer_zero
- @DonAlt

## Configuration

### Risk Settings (in `config.py`)
| Setting | Default | Description |
|---------|---------|-------------|
| `max_position_usd` | $1,000 | Maximum position size |
| `risk_per_trade_percent` | 7.5% | Risk per trade (aggressive) |
| `max_leverage` | 10x | Maximum allowed leverage |
| `max_open_positions` | 5 | Max concurrent positions |
| `default_stop_loss_percent` | 5% | Default SL if not specified |
| `default_take_profit_percent` | 15% | Default TP if not specified |

## Installation

```bash
# Clone or navigate to the bot directory
cd hyperliquid-twitter-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.template .env
# Edit .env with your API credentials
```

## API Setup

### Twitter/X API
1. Go to [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a project and app
3. Generate a Bearer Token
4. Add to `.env` as `TWITTER_BEARER_TOKEN`

### Hyperliquid API
1. Create a wallet (or use existing)
2. Fund with USDC on Arbitrum
3. Export private key
4. Add to `.env` as `HYPERLIQUID_PRIVATE_KEY`

## Usage

```bash
# Test the signal parser (no API needed)
python main.py test

# Check current status
python main.py status

# View trader performance
python main.py traders

# Start the bot
python main.py run
```

## How It Works

### 1. Signal Detection
The bot parses tweets looking for:
- **Direction keywords**: "long", "short", "buy", "sell", "bullish", "bearish"
- **Asset mentions**: $BTC, ETH, SOL, etc.
- **Price levels**: Entry, stop loss (SL), take profit (TP)
- **Leverage**: "5x", "10x leverage"

### 2. Confidence Scoring
Each signal receives a confidence score (0-1) based on:
- Clear direction keyword (+0.3)
- Valid asset detected (+0.3)
- Entry price specified (+0.15)
- Stop loss specified (+0.15)
- Take profit specified (+0.1)

### 3. Trade Validation
Before executing, the bot checks:
- Confidence score ≥ minimum threshold
- Not already in position for that asset
- Max positions not exceeded
- Sufficient margin available

### 4. Performance Learning
The bot tracks each trader's:
- Win rate
- Average PnL
- Total signals vs executed trades

Traders with better track records get larger position sizes.

## Project Structure

```
hyperliquid-twitter-bot/
├── main.py              # CLI entry point
├── bot.py               # Main orchestration
├── config.py            # Configuration
├── models.py            # Database models
├── twitter_monitor.py   # Twitter polling
├── signal_parser.py     # NLP signal extraction
├── hyperliquid_trader.py# Trade execution
├── risk_manager.py      # Position sizing
├── trader_tracker.py    # Performance tracking
├── requirements.txt     # Dependencies
├── .env.template        # Environment template
└── data/                # SQLite database
```

## Example Signal Parsing

```
Tweet: "Long $BTC here at 95k, SL: 93k, TP: 100k 🚀 5x leverage"

Parsed Signal:
├── Type: LONG
├── Asset: BTC
├── Entry: $95,000
├── Stop Loss: $93,000
├── Take Profit: $100,000
├── Leverage: 5x
└── Confidence: 0.85
```

## Customization

### Add More Traders
Edit `config.py`:
```python
tracked_accounts: List[str] = [
    "IncomeSharks",
    "astronomer_zero",
    "DonAlt",
    "NewTrader123",  # Add new trader
]
```

### Adjust Risk Parameters
Edit `config.py`:
```python
class RiskConfig(BaseModel):
    max_position_usd: float = 500.0      # Lower max position
    risk_per_trade_percent: float = 3.0  # More conservative
    max_leverage: int = 5                 # Lower leverage
```

## Logs & Data

- **Logs**: `logs/bot.log` (rotated daily, 7-day retention)
- **Database**: `data/trading_bot.db` (SQLite)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Bearer token invalid" | Regenerate Twitter token |
| "Insufficient margin" | Deposit more USDC |
| "No signals detected" | Check tracked traders are posting |
| "Rate limited" | Increase poll interval |

## Disclaimer

This software is provided "as-is" without warranty. The authors are not responsible for any financial losses. Trading cryptocurrencies involves significant risk. Always do your own research and never invest more than you can afford to lose.

## License

MIT License - Use at your own risk.

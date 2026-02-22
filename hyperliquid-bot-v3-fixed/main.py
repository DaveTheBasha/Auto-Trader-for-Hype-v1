#!/usr/bin/env python3
"""
Hyperliquid Twitter Trading Bot
Command Line Interface

Usage:
    python main.py run        - Start the trading bot
    python main.py status     - Get current status
    python main.py balance    - Show wallet balance
    python main.py traders    - Show trader performance
    python main.py tax        - Generate UK tax report
    python main.py dashboard  - Start web dashboard only
    python main.py test       - Run in test mode (parse sample tweets)
"""
import asyncio
import sys
import os
import signal
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich import box

from config import config
from bot import TradingBot

# Setup logging
os.makedirs("logs", exist_ok=True)
logger.add(
    config.log_file,
    rotation="1 day",
    retention="7 days",
    level=config.log_level
)

console = Console()
bot: TradingBot = None


def print_banner():
    """Print startup banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║     HYPERLIQUID TWITTER TRADING BOT                           ║
║     Follows signals from: @IncomeSharks @astronomer_zero      ║
║                           @DonAlt                             ║
╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


async def run_bot():
    """Run the trading bot"""
    global bot

    print_banner()

    console.print("\n[yellow]⚠️  RISK WARNING[/yellow]")
    console.print("This bot trades with REAL funds (unless in testnet mode).")
    console.print("Trading based on social media signals is EXTREMELY RISKY.")
    console.print("Only trade what you can afford to lose.\n")

    # Show configuration
    table = Table(title="Configuration", box=box.ROUNDED)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Mode", "TESTNET" if config.hyperliquid.testnet else "⚠️ MAINNET")
    table.add_row("Max Position", f"${config.risk.max_position_usd:,.2f}")
    table.add_row("Risk per Trade", f"{config.risk.risk_per_trade_percent}%")
    table.add_row("Max Leverage", f"{config.risk.max_leverage}x")
    table.add_row("Max Open Positions", str(config.risk.max_open_positions))
    table.add_row("Min Confidence", f"{config.risk.min_confidence_score}")
    table.add_row("Poll Interval", f"{config.twitter.poll_interval_seconds}s")

    console.print(table)
    console.print()

    # Initialize and start bot
    bot = TradingBot()

    try:
        await bot.initialize()

        console.print("[green]✓ Bot initialized successfully[/green]")
        console.print("[cyan]Starting trading loop... Press Ctrl+C to stop[/cyan]\n")

        await bot.start()

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Bot error")
    finally:
        if bot:
            await bot.stop()


async def show_status():
    """Show current bot status"""
    print_banner()

    bot = TradingBot()
    await bot.initialize()

    status = await bot.get_status()

    # Account info
    console.print(Panel.fit(
        f"Equity: ${status['account'].get('equity', 0):,.2f}\n"
        f"Available Margin: ${status['account'].get('available_margin', 0):,.2f}\n"
        f"Margin Used: ${status['account'].get('margin_used', 0):,.2f}",
        title="Account Balance"
    ))

    # Positions
    if status['positions']:
        pos_table = Table(title="Open Positions", box=box.ROUNDED)
        pos_table.add_column("Asset")
        pos_table.add_column("Size")
        pos_table.add_column("Entry")
        pos_table.add_column("PnL")

        for pos in status['positions']:
            pos_table.add_row(
                pos['asset'],
                f"{pos['size']:.4f}",
                f"${pos['entry_price']:,.2f}",
                f"${pos['unrealized_pnl']:,.2f}"
            )
        console.print(pos_table)
    else:
        console.print("[dim]No open positions[/dim]")

    # Statistics
    console.print(f"\n[cyan]Total Closed Trades:[/cyan] {status['total_trades']}")
    console.print(f"[cyan]Total PnL:[/cyan] ${status['total_pnl']:,.2f}")


async def show_traders():
    """Show trader performance"""
    print_banner()

    bot = TradingBot()
    await bot.initialize()
    await bot.tracker.update_all_traders()

    status = await bot.get_status()

    table = Table(title="Trader Performance", box=box.ROUNDED)
    table.add_column("Trader", style="cyan")
    table.add_column("Signals")
    table.add_column("Trades")
    table.add_column("Win Rate", style="green")
    table.add_column("PnL", style="yellow")
    table.add_column("Weight", style="magenta")

    for trader in status['tracked_traders']:
        win_rate = f"{trader['win_rate']:.1%}" if trader['executed_trades'] > 0 else "N/A"
        pnl_color = "green" if trader['total_pnl_usd'] >= 0 else "red"

        table.add_row(
            f"@{trader['username']}",
            str(trader['total_signals']),
            str(trader['executed_trades']),
            win_rate,
            f"[{pnl_color}]${trader['total_pnl_usd']:,.2f}[/{pnl_color}]",
            f"{trader['weight_score']:.2f}"
        )

    console.print(table)


async def test_parser():
    """Test the signal parser with sample tweets"""
    print_banner()

    from models import Tweet
    from signal_parser import SignalParser, ParsedSignal

    # Sample tweets for testing
    sample_tweets = [
        ("IncomeSharks", "Long $BTC here at 95k, SL: 93k, TP: 100k 🚀 5x leverage"),
        ("astronomer_zero", "Shorting ETH from 3500. Stop loss at 3600, target 3200. Looks bearish 📉"),
        ("DonAlt", "Entered a long on SOL @ 180. Looking for 200+"),
        ("IncomeSharks", "Just bought some ARB, bullish on the ecosystem"),
        ("astronomer_zero", "Taking profit on my BTC long here. Great trade! +15%"),
        ("DonAlt", "Not trading today, just watching"),
    ]

    console.print("[cyan]Testing Signal Parser[/cyan]\n")

    parser = SignalParser(None)  # No DB needed for testing

    table = Table(title="Signal Parsing Results", box=box.ROUNDED)
    table.add_column("Trader", style="cyan")
    table.add_column("Tweet", max_width=40)
    table.add_column("Signal?", style="yellow")
    table.add_column("Details", style="green")

    for username, text in sample_tweets:
        tweet = Tweet(
            id=str(hash(text)),
            author_username=username,
            author_id="test",
            text=text,
            created_at=datetime.utcnow()
        )

        signal = parser.parse_tweet(tweet)

        if signal:
            details = (
                f"{signal.signal_type.value.upper()} {signal.asset}\n"
                f"Entry: {signal.entry_price or 'N/A'}\n"
                f"SL: {signal.stop_loss or 'N/A'}\n"
                f"TP: {signal.take_profit or 'N/A'}\n"
                f"Confidence: {signal.confidence_score:.2f}"
            )
            table.add_row(f"@{username}", text[:40] + "...", "✓", details)
        else:
            table.add_row(f"@{username}", text[:40] + "...", "✗", "No signal detected")

    console.print(table)


async def show_balance():
    """Show detailed wallet balance"""
    print_banner()

    from hyperliquid_trader import HyperliquidTrader
    from models import Database

    db = Database(config.db_path)
    await db.initialize()

    trader = HyperliquidTrader(db)
    await trader.initialize()

    # Get balance
    balance = await trader.get_account_balance()
    positions = await trader.get_open_positions()

    # Display balance
    console.print("\n")
    console.print(Panel.fit(
        f"[bold green]💰 WALLET BALANCE[/bold green]\n\n"
        f"[cyan]Equity:[/cyan]           ${balance.get('equity', 0):>12,.2f}\n"
        f"[cyan]Available Margin:[/cyan] ${balance.get('available_margin', 0):>12,.2f}\n"
        f"[cyan]Margin Used:[/cyan]      ${balance.get('margin_used', 0):>12,.2f}\n\n"
        f"[dim]Wallet: {trader.account.address if trader.account else 'N/A'}[/dim]",
        title="Hyperliquid Account",
        border_style="green"
    ))

    # Show positions if any
    if positions:
        total_unrealized = sum(p.get('unrealized_pnl', 0) for p in positions)

        pos_table = Table(title="Open Positions", box=box.ROUNDED)
        pos_table.add_column("Asset", style="cyan")
        pos_table.add_column("Side", style="yellow")
        pos_table.add_column("Size")
        pos_table.add_column("Entry Price")
        pos_table.add_column("Unrealized PnL")

        for pos in positions:
            size = pos.get('size', 0)
            side = "LONG" if size > 0 else "SHORT"
            side_color = "green" if size > 0 else "red"
            pnl = pos.get('unrealized_pnl', 0)
            pnl_color = "green" if pnl >= 0 else "red"

            pos_table.add_row(
                pos.get('asset', 'N/A'),
                f"[{side_color}]{side}[/{side_color}]",
                f"{abs(size):.4f}",
                f"${pos.get('entry_price', 0):,.2f}",
                f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"
            )

        console.print(pos_table)
        pnl_color = "green" if total_unrealized >= 0 else "red"
        console.print(f"\n[{pnl_color}]Total Unrealized PnL: ${total_unrealized:,.2f}[/{pnl_color}]")
    else:
        console.print("\n[dim]No open positions[/dim]")

    # Mode indicator
    mode = "🧪 TESTNET" if config.hyperliquid.testnet else "⚠️ MAINNET (REAL FUNDS)"
    console.print(f"\n[yellow]Mode: {mode}[/yellow]")


async def show_tax_report():
    """Generate and display UK tax report"""
    print_banner()

    from models import Database
    from uk_tax_report import UKTaxReporter

    db = Database(config.db_path)
    await db.initialize()

    reporter = UKTaxReporter(db)

    # Get tax year from args or use current
    tax_year = sys.argv[2] if len(sys.argv) > 2 else None

    console.print("[cyan]Generating UK Tax Report...[/cyan]\n")

    report = await reporter.generate_report(tax_year)

    # Print summary
    reporter.print_report(report)

    # Export files
    csv_file = await reporter.export_csv(report)
    json_file = await reporter.export_json(report)

    console.print(f"\n[green]✓ Reports exported:[/green]")
    console.print(f"  CSV:  {csv_file}")
    console.print(f"  JSON: {json_file}")

    console.print("\n[dim]Use these files for your Self Assessment tax return.[/dim]")
    console.print("[dim]Note: This is for guidance only. Consult a tax professional.[/dim]")


def run_dashboard():
    """Run the web dashboard"""
    print_banner()

    console.print("[cyan]Starting Web Dashboard...[/cyan]\n")

    from web_dashboard import run_dashboard as start_dashboard

    host = config.dashboard.host
    port = config.dashboard.port

    console.print(f"[green]✓ Dashboard running at:[/green] http://{host}:{port}")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        start_dashboard(host=host, port=port)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        console.print("[yellow]Usage:[/yellow]")
        console.print("  python main.py run       - Start the bot")
        console.print("  python main.py status    - Show status")
        console.print("  python main.py balance   - Show wallet balance")
        console.print("  python main.py traders   - Show trader stats")
        console.print("  python main.py tax       - Generate UK tax report")
        console.print("  python main.py tax 2024-25  - Tax report for specific year")
        console.print("  python main.py dashboard - Start web dashboard")
        console.print("  python main.py test      - Test signal parser")
        return

    command = sys.argv[1].lower()

    if command == "run":
        asyncio.run(run_bot())
    elif command == "status":
        asyncio.run(show_status())
    elif command == "balance":
        asyncio.run(show_balance())
    elif command == "traders":
        asyncio.run(show_traders())
    elif command == "tax":
        asyncio.run(show_tax_report())
    elif command == "dashboard":
        run_dashboard()
    elif command == "test":
        asyncio.run(test_parser())
    else:
        console.print(f"[red]Unknown command: {command}[/red]")


if __name__ == "__main__":
    main()

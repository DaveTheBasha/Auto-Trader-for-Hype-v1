"""
Web Dashboard for Hyperliquid Trading Bot
Real-time monitoring via browser interface
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
from threading import Thread

from flask import Flask, render_template_string, jsonify, request
from loguru import logger

from config import config
from models import Database, Trade, TradeStatus, TraderPerformance
from sqlalchemy import select, func


app = Flask(__name__)
db: Optional[Database] = None


# HTML Template with embedded CSS and JS
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hyperliquid Trading Bot Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e4e4e4;
            min-height: 100vh;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid #2a2a4a;
            margin-bottom: 30px;
        }

        .logo {
            font-size: 24px;
            font-weight: bold;
            color: #00d4ff;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(0, 212, 255, 0.1);
            border-radius: 20px;
            font-size: 14px;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff88;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }

        .card-title {
            font-size: 14px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }

        .card-value {
            font-size: 32px;
            font-weight: bold;
            color: #fff;
        }

        .card-value.positive { color: #00ff88; }
        .card-value.negative { color: #ff4757; }

        .card-subtitle {
            font-size: 13px;
            color: #666;
            margin-top: 8px;
        }

        .section {
            margin-bottom: 30px;
        }

        .section-title {
            font-size: 20px;
            margin-bottom: 20px;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            overflow: hidden;
        }

        th, td {
            padding: 16px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        th {
            background: rgba(255, 255, 255, 0.05);
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 1px;
        }

        tr:hover {
            background: rgba(255, 255, 255, 0.02);
        }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .badge-long {
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
        }

        .badge-short {
            background: rgba(255, 71, 87, 0.2);
            color: #ff4757;
        }

        .badge-open {
            background: rgba(0, 212, 255, 0.2);
            color: #00d4ff;
        }

        .badge-closed {
            background: rgba(136, 136, 136, 0.2);
            color: #888;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            border-radius: 4px;
            transition: width 0.3s ease;
        }

        .trader-card {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 16px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            margin-bottom: 12px;
        }

        .trader-avatar {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: linear-gradient(135deg, #00d4ff, #00ff88);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 18px;
        }

        .trader-info {
            flex: 1;
        }

        .trader-name {
            font-weight: 600;
            color: #fff;
        }

        .trader-stats {
            font-size: 13px;
            color: #888;
            margin-top: 4px;
        }

        .trader-pnl {
            font-size: 18px;
            font-weight: bold;
        }

        .refresh-btn {
            background: rgba(0, 212, 255, 0.2);
            border: none;
            color: #00d4ff;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }

        .refresh-btn:hover {
            background: rgba(0, 212, 255, 0.3);
        }

        .mode-indicator {
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
        }

        .mode-testnet {
            background: rgba(255, 193, 7, 0.2);
            color: #ffc107;
        }

        .mode-mainnet {
            background: rgba(255, 71, 87, 0.2);
            color: #ff4757;
        }

        .empty-state {
            text-align: center;
            padding: 40px;
            color: #666;
        }

        .last-updated {
            font-size: 12px;
            color: #666;
        }

        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }

            .card-value {
                font-size: 24px;
            }

            table {
                font-size: 14px;
            }

            th, td {
                padding: 12px 8px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">Hyperliquid Bot</div>
            <div style="display: flex; gap: 16px; align-items: center;">
                <span class="mode-indicator {{ 'mode-testnet' if testnet else 'mode-mainnet' }}">
                    {{ 'TESTNET' if testnet else 'MAINNET' }}
                </span>
                <div class="status-badge">
                    <div class="status-dot"></div>
                    <span>Live</span>
                </div>
                <button class="refresh-btn" onclick="refreshData()">Refresh</button>
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <div class="card-title">Portfolio Value</div>
                <div class="card-value" id="equity">$0.00</div>
                <div class="card-subtitle">Available: <span id="available">$0.00</span></div>
            </div>

            <div class="card">
                <div class="card-title">Today's PnL</div>
                <div class="card-value" id="todayPnl">$0.00</div>
                <div class="card-subtitle" id="todayTrades">0 trades today</div>
            </div>

            <div class="card">
                <div class="card-title">Total PnL</div>
                <div class="card-value" id="totalPnl">$0.00</div>
                <div class="card-subtitle" id="totalTrades">0 total trades</div>
            </div>

            <div class="card">
                <div class="card-title">Win Rate</div>
                <div class="card-value" id="winRate">0%</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="winRateBar" style="width: 0%"></div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">
                Open Positions
                <span style="font-size: 14px; color: #666;" id="positionCount">(0)</span>
            </div>
            <table id="positionsTable">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Side</th>
                        <th>Size</th>
                        <th>Entry</th>
                        <th>Current</th>
                        <th>PnL</th>
                    </tr>
                </thead>
                <tbody id="positionsBody">
                    <tr><td colspan="6" class="empty-state">No open positions</td></tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <div class="section-title">Tracked Traders</div>
            <div id="tradersContainer">
                <div class="empty-state">No traders tracked yet</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Recent Trades</div>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Asset</th>
                        <th>Type</th>
                        <th>Size</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>PnL</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="tradesBody">
                    <tr><td colspan="8" class="empty-state">No trades yet</td></tr>
                </tbody>
            </table>
        </div>

        <div class="last-updated">
            Last updated: <span id="lastUpdated">-</span>
        </div>
    </div>

    <script>
        async function refreshData() {
            try {
                const response = await fetch('/api/dashboard');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        function updateDashboard(data) {
            // Update account info
            document.getElementById('equity').textContent = formatCurrency(data.account.equity);
            document.getElementById('available').textContent = formatCurrency(data.account.available_margin);

            // Today's PnL
            const todayPnl = document.getElementById('todayPnl');
            todayPnl.textContent = formatCurrency(data.stats.today_pnl);
            todayPnl.className = 'card-value ' + (data.stats.today_pnl >= 0 ? 'positive' : 'negative');
            document.getElementById('todayTrades').textContent = `${data.stats.today_trades} trades today`;

            // Total PnL
            const totalPnl = document.getElementById('totalPnl');
            totalPnl.textContent = formatCurrency(data.stats.total_pnl);
            totalPnl.className = 'card-value ' + (data.stats.total_pnl >= 0 ? 'positive' : 'negative');
            document.getElementById('totalTrades').textContent = `${data.stats.total_trades} total trades`;

            // Win rate
            const winRate = data.stats.win_rate;
            document.getElementById('winRate').textContent = winRate.toFixed(1) + '%';
            document.getElementById('winRateBar').style.width = winRate + '%';

            // Positions
            updatePositions(data.positions);

            // Traders
            updateTraders(data.traders);

            // Recent trades
            updateTrades(data.recent_trades);

            // Last updated
            document.getElementById('lastUpdated').textContent = new Date().toLocaleString();
        }

        function updatePositions(positions) {
            const tbody = document.getElementById('positionsBody');
            document.getElementById('positionCount').textContent = `(${positions.length})`;

            if (positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No open positions</td></tr>';
                return;
            }

            tbody.innerHTML = positions.map(pos => `
                <tr>
                    <td><strong>${pos.asset}</strong></td>
                    <td><span class="badge ${pos.size > 0 ? 'badge-long' : 'badge-short'}">${pos.size > 0 ? 'LONG' : 'SHORT'}</span></td>
                    <td>${Math.abs(pos.size).toFixed(4)}</td>
                    <td>${formatCurrency(pos.entry_price)}</td>
                    <td>${formatCurrency(pos.mark_price || pos.entry_price)}</td>
                    <td class="${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}">${formatCurrency(pos.unrealized_pnl)}</td>
                </tr>
            `).join('');
        }

        function updateTraders(traders) {
            const container = document.getElementById('tradersContainer');

            if (traders.length === 0) {
                container.innerHTML = '<div class="empty-state">No traders tracked yet</div>';
                return;
            }

            container.innerHTML = traders.map(trader => `
                <div class="trader-card">
                    <div class="trader-avatar">${trader.username.charAt(0).toUpperCase()}</div>
                    <div class="trader-info">
                        <div class="trader-name">@${trader.username}</div>
                        <div class="trader-stats">${trader.executed_trades} trades | ${(trader.win_rate * 100).toFixed(0)}% win rate | Weight: ${trader.weight_score.toFixed(2)}</div>
                    </div>
                    <div class="trader-pnl ${trader.total_pnl_usd >= 0 ? 'positive' : 'negative'}">
                        ${formatCurrency(trader.total_pnl_usd)}
                    </div>
                </div>
            `).join('');
        }

        function updateTrades(trades) {
            const tbody = document.getElementById('tradesBody');

            if (trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No trades yet</td></tr>';
                return;
            }

            tbody.innerHTML = trades.map(trade => `
                <tr>
                    <td>${formatTime(trade.created_at)}</td>
                    <td><strong>${trade.asset}</strong></td>
                    <td><span class="badge ${trade.signal_type === 'long' ? 'badge-long' : 'badge-short'}">${trade.signal_type.toUpperCase()}</span></td>
                    <td>${formatCurrency(trade.size_usd)}</td>
                    <td>${trade.entry_price ? formatCurrency(trade.entry_price) : '-'}</td>
                    <td>${trade.exit_price ? formatCurrency(trade.exit_price) : '-'}</td>
                    <td class="${(trade.pnl_usd || 0) >= 0 ? 'positive' : 'negative'}">${trade.pnl_usd ? formatCurrency(trade.pnl_usd) : '-'}</td>
                    <td><span class="badge ${trade.status === 'open' ? 'badge-open' : 'badge-closed'}">${trade.status.toUpperCase()}</span></td>
                </tr>
            `).join('');
        }

        function formatCurrency(value) {
            if (value === null || value === undefined) return '$0.00';
            const num = parseFloat(value);
            return (num >= 0 ? '' : '-') + '$' + Math.abs(num).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }

        function formatTime(isoString) {
            if (!isoString) return '-';
            const date = new Date(isoString);
            return date.toLocaleString('en-US', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});
        }

        // Initial load and auto-refresh
        refreshData();
        setInterval(refreshData, 30000); // Refresh every 30 seconds
    </script>
</body>
</html>
"""


@app.route('/')
def dashboard():
    """Render dashboard page"""
    return render_template_string(
        DASHBOARD_HTML,
        testnet=config.hyperliquid.testnet
    )


@app.route('/api/dashboard')
def api_dashboard():
    """API endpoint for dashboard data"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        data = loop.run_until_complete(get_dashboard_data())
        return jsonify(data)
    finally:
        loop.close()


async def get_dashboard_data():
    """Get all dashboard data"""
    global db

    if db is None:
        db = Database(config.db_path)
        await db.initialize()

    # Get account balance from Hyperliquid
    account_data = {"equity": 0, "available_margin": 0, "margin_used": 0}
    positions = []

    try:
        from hyperliquid_trader import HyperliquidTrader
        trader = HyperliquidTrader(db)
        await trader.initialize()
        account_data = await trader.get_account_balance()
        positions = await trader.get_open_positions()
    except Exception as e:
        logger.error(f"Error getting Hyperliquid data: {e}")

    # Get trades from database
    async with db.get_session() as session:
        # Recent trades
        result = await session.execute(
            select(Trade).order_by(Trade.created_at.desc()).limit(20)
        )
        trades = result.scalars().all()

        # Total stats
        total_result = await session.execute(
            select(
                func.count(Trade.id).label('total'),
                func.sum(Trade.pnl_usd).label('total_pnl')
            ).where(Trade.status == TradeStatus.CLOSED)
        )
        total_row = total_result.first()
        total_trades = total_row.total or 0
        total_pnl = total_row.total_pnl or 0

        # Win count
        win_result = await session.execute(
            select(func.count(Trade.id)).where(
                Trade.status == TradeStatus.CLOSED,
                Trade.pnl_usd > 0
            )
        )
        wins = win_result.scalar() or 0

        # Today's stats
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await session.execute(
            select(
                func.count(Trade.id).label('count'),
                func.sum(Trade.pnl_usd).label('pnl')
            ).where(
                Trade.status == TradeStatus.CLOSED,
                Trade.closed_at >= today
            )
        )
        today_row = today_result.first()
        today_trades = today_row.count or 0
        today_pnl = today_row.pnl or 0

        # Traders
        trader_result = await session.execute(
            select(TraderPerformance).order_by(TraderPerformance.weight_score.desc())
        )
        traders = trader_result.scalars().all()

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    return {
        "account": account_data,
        "positions": positions,
        "stats": {
            "total_trades": total_trades,
            "total_pnl": float(total_pnl),
            "today_trades": today_trades,
            "today_pnl": float(today_pnl),
            "win_rate": win_rate
        },
        "traders": [
            {
                "username": t.username,
                "total_signals": t.total_signals,
                "executed_trades": t.executed_trades,
                "win_rate": t.win_rate,
                "total_pnl_usd": t.total_pnl_usd,
                "weight_score": t.weight_score
            }
            for t in traders
        ],
        "recent_trades": [
            {
                "id": t.id,
                "asset": t.asset,
                "signal_type": t.signal_type.value,
                "size_usd": t.size_usd,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_usd": t.pnl_usd,
                "status": t.status.value,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in trades
        ]
    }


def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """Run the dashboard server"""
    logger.info(f"Starting dashboard at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)


def start_dashboard_background(port=5000):
    """Start dashboard in background thread"""
    thread = Thread(target=run_dashboard, kwargs={'port': port}, daemon=True)
    thread.start()
    return thread


if __name__ == '__main__':
    run_dashboard(debug=True)

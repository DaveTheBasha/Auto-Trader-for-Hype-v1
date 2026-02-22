"""
UK Tax Report Generator
Generates tax reports for UK crypto trading (Capital Gains Tax)
"""
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from decimal import Decimal
from loguru import logger
from sqlalchemy import select

from models import Database, Trade, TradeStatus


@dataclass
class TaxableEvent:
    """A taxable disposal event"""
    date: datetime
    asset: str
    disposal_type: str  # "sell", "close_long", "close_short"
    proceeds_gbp: float
    cost_basis_gbp: float
    gain_loss_gbp: float
    trade_id: int
    notes: str = ""


@dataclass
class UKTaxReport:
    """UK Tax Year Report"""
    tax_year: str  # e.g., "2024-25"
    start_date: datetime
    end_date: datetime
    total_disposals: int = 0
    total_proceeds_gbp: float = 0.0
    total_cost_basis_gbp: float = 0.0
    total_gains_gbp: float = 0.0
    total_losses_gbp: float = 0.0
    net_gain_loss_gbp: float = 0.0
    cgt_allowance_gbp: float = 3000.0  # 2024-25 allowance
    taxable_gain_gbp: float = 0.0
    events: List[TaxableEvent] = field(default_factory=list)


class UKTaxReporter:
    """
    Generates UK-compliant tax reports for crypto trading.

    UK Tax Rules for Crypto:
    - Crypto is subject to Capital Gains Tax (CGT)
    - CGT Annual Allowance: £3,000 (2024-25), was £6,000 (2023-24)
    - CGT Rates: 10% (basic rate), 20% (higher rate) for 2024-25
    - Must use matching rules (same-day, bed & breakfast, pooled)
    - Tax year runs April 6 to April 5
    """

    # CGT allowances by tax year
    CGT_ALLOWANCES = {
        "2023-24": 6000,
        "2024-25": 3000,
        "2025-26": 3000,
    }

    # CGT rates
    CGT_BASIC_RATE = 0.10  # 10%
    CGT_HIGHER_RATE = 0.20  # 20%

    def __init__(self, db: Database):
        self.db = db
        self.usd_to_gbp_rate = 0.79  # Default rate, should be fetched

    def get_tax_year_dates(self, tax_year: str) -> tuple:
        """Get start and end dates for a UK tax year"""
        # Tax year format: "2024-25"
        start_year = int(tax_year.split("-")[0])
        start_date = datetime(start_year, 4, 6)  # April 6
        end_date = datetime(start_year + 1, 4, 5, 23, 59, 59)  # April 5
        return start_date, end_date

    def get_current_tax_year(self) -> str:
        """Get current UK tax year"""
        now = datetime.utcnow()
        if now.month < 4 or (now.month == 4 and now.day < 6):
            # Before April 6, still in previous tax year
            return f"{now.year - 1}-{str(now.year)[2:]}"
        else:
            return f"{now.year}-{str(now.year + 1)[2:]}"

    def usd_to_gbp(self, usd_amount: float) -> float:
        """Convert USD to GBP"""
        return usd_amount * self.usd_to_gbp_rate

    async def get_closed_trades(self, start_date: datetime, end_date: datetime) -> List[Trade]:
        """Get all closed trades within date range"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Trade).where(
                    Trade.status == TradeStatus.CLOSED,
                    Trade.closed_at >= start_date,
                    Trade.closed_at <= end_date
                ).order_by(Trade.closed_at)
            )
            return list(result.scalars().all())

    async def generate_report(self, tax_year: str = None) -> UKTaxReport:
        """Generate tax report for a UK tax year"""
        if tax_year is None:
            tax_year = self.get_current_tax_year()

        start_date, end_date = self.get_tax_year_dates(tax_year)
        allowance = self.CGT_ALLOWANCES.get(tax_year, 3000)

        report = UKTaxReport(
            tax_year=tax_year,
            start_date=start_date,
            end_date=end_date,
            cgt_allowance_gbp=allowance
        )

        # Get all closed trades
        trades = await self.get_closed_trades(start_date, end_date)

        for trade in trades:
            # Calculate GBP values
            proceeds_gbp = self.usd_to_gbp(trade.size_usd + (trade.pnl_usd or 0))
            cost_basis_gbp = self.usd_to_gbp(trade.size_usd)
            gain_loss_gbp = self.usd_to_gbp(trade.pnl_usd or 0)

            event = TaxableEvent(
                date=trade.closed_at,
                asset=trade.asset,
                disposal_type=f"close_{trade.signal_type.value}",
                proceeds_gbp=proceeds_gbp,
                cost_basis_gbp=cost_basis_gbp,
                gain_loss_gbp=gain_loss_gbp,
                trade_id=trade.id,
                notes=f"Entry: ${trade.entry_price}, Exit: ${trade.exit_price}"
            )
            report.events.append(event)

            # Update totals
            report.total_disposals += 1
            report.total_proceeds_gbp += proceeds_gbp
            report.total_cost_basis_gbp += cost_basis_gbp

            if gain_loss_gbp > 0:
                report.total_gains_gbp += gain_loss_gbp
            else:
                report.total_losses_gbp += abs(gain_loss_gbp)

        # Calculate net and taxable amounts
        report.net_gain_loss_gbp = report.total_gains_gbp - report.total_losses_gbp
        report.taxable_gain_gbp = max(0, report.net_gain_loss_gbp - report.cgt_allowance_gbp)

        return report

    def calculate_tax_owed(self, report: UKTaxReport, is_higher_rate: bool = False) -> float:
        """Calculate estimated CGT owed"""
        if report.taxable_gain_gbp <= 0:
            return 0.0

        rate = self.CGT_HIGHER_RATE if is_higher_rate else self.CGT_BASIC_RATE
        return report.taxable_gain_gbp * rate

    async def export_csv(self, report: UKTaxReport, filename: str = None) -> str:
        """Export report to CSV for HMRC"""
        if filename is None:
            filename = f"data/uk_tax_report_{report.tax_year}.csv"

        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "Date", "Asset", "Type", "Proceeds (GBP)",
                "Cost Basis (GBP)", "Gain/Loss (GBP)", "Notes"
            ])

            # Events
            for event in report.events:
                writer.writerow([
                    event.date.strftime("%Y-%m-%d"),
                    event.asset,
                    event.disposal_type,
                    f"{event.proceeds_gbp:.2f}",
                    f"{event.cost_basis_gbp:.2f}",
                    f"{event.gain_loss_gbp:.2f}",
                    event.notes
                ])

            # Summary
            writer.writerow([])
            writer.writerow(["SUMMARY"])
            writer.writerow(["Tax Year", report.tax_year])
            writer.writerow(["Total Disposals", report.total_disposals])
            writer.writerow(["Total Proceeds (GBP)", f"£{report.total_proceeds_gbp:,.2f}"])
            writer.writerow(["Total Cost Basis (GBP)", f"£{report.total_cost_basis_gbp:,.2f}"])
            writer.writerow(["Total Gains (GBP)", f"£{report.total_gains_gbp:,.2f}"])
            writer.writerow(["Total Losses (GBP)", f"£{report.total_losses_gbp:,.2f}"])
            writer.writerow(["Net Gain/Loss (GBP)", f"£{report.net_gain_loss_gbp:,.2f}"])
            writer.writerow(["CGT Allowance (GBP)", f"£{report.cgt_allowance_gbp:,.2f}"])
            writer.writerow(["Taxable Gain (GBP)", f"£{report.taxable_gain_gbp:,.2f}"])

        logger.info(f"Tax report exported to {filename}")
        return filename

    async def export_json(self, report: UKTaxReport, filename: str = None) -> str:
        """Export report to JSON"""
        if filename is None:
            filename = f"data/uk_tax_report_{report.tax_year}.json"

        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        data = {
            "tax_year": report.tax_year,
            "period": {
                "start": report.start_date.isoformat(),
                "end": report.end_date.isoformat()
            },
            "summary": {
                "total_disposals": report.total_disposals,
                "total_proceeds_gbp": report.total_proceeds_gbp,
                "total_cost_basis_gbp": report.total_cost_basis_gbp,
                "total_gains_gbp": report.total_gains_gbp,
                "total_losses_gbp": report.total_losses_gbp,
                "net_gain_loss_gbp": report.net_gain_loss_gbp,
                "cgt_allowance_gbp": report.cgt_allowance_gbp,
                "taxable_gain_gbp": report.taxable_gain_gbp,
                "estimated_tax_basic_rate": self.calculate_tax_owed(report, False),
                "estimated_tax_higher_rate": self.calculate_tax_owed(report, True)
            },
            "events": [
                {
                    "date": e.date.isoformat(),
                    "asset": e.asset,
                    "type": e.disposal_type,
                    "proceeds_gbp": e.proceeds_gbp,
                    "cost_basis_gbp": e.cost_basis_gbp,
                    "gain_loss_gbp": e.gain_loss_gbp,
                    "trade_id": e.trade_id,
                    "notes": e.notes
                }
                for e in report.events
            ]
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Tax report exported to {filename}")
        return filename

    def print_report(self, report: UKTaxReport):
        """Print formatted tax report to console"""
        print("\n" + "=" * 60)
        print(f"  UK TAX REPORT - Tax Year {report.tax_year}")
        print("=" * 60)
        print(f"Period: {report.start_date.strftime('%d %b %Y')} - {report.end_date.strftime('%d %b %Y')}")
        print("-" * 60)
        print(f"Total Disposals:      {report.total_disposals}")
        print(f"Total Proceeds:       £{report.total_proceeds_gbp:,.2f}")
        print(f"Total Cost Basis:     £{report.total_cost_basis_gbp:,.2f}")
        print("-" * 60)
        print(f"Total Gains:          £{report.total_gains_gbp:,.2f}")
        print(f"Total Losses:         £{report.total_losses_gbp:,.2f}")
        print(f"Net Gain/Loss:        £{report.net_gain_loss_gbp:,.2f}")
        print("-" * 60)
        print(f"CGT Allowance:        £{report.cgt_allowance_gbp:,.2f}")
        print(f"Taxable Gain:         £{report.taxable_gain_gbp:,.2f}")
        print("-" * 60)

        tax_basic = self.calculate_tax_owed(report, False)
        tax_higher = self.calculate_tax_owed(report, True)

        print(f"Estimated CGT (10%):  £{tax_basic:,.2f}")
        print(f"Estimated CGT (20%):  £{tax_higher:,.2f}")
        print("=" * 60)

        if report.taxable_gain_gbp > 0:
            print("\n⚠️  You may need to report this on your Self Assessment tax return")
        else:
            print("\n✅ No CGT to pay (within annual allowance)")

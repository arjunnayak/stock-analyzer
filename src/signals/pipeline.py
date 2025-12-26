"""
Signal evaluation pipeline for material change detection.

Main orchestrator that:
1. Fetches price data for watched tickers
2. Computes technical signals
3. Detects state changes
4. Generates alerts
"""

from datetime import date, datetime, timedelta
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from src.config import config
from src.email.delivery import EmailDeliveryService
from src.reader import TimeSeriesReader
from src.signals.alerts import Alert, AlertGenerator, AlertRepository
from src.signals.state_tracker import StateChange, StateTracker
from src.signals.technical import TechnicalSignals
from src.signals.valuation import ValuationSignals


class SignalPipeline:
    """Main signal evaluation pipeline."""

    def __init__(self, enable_email: bool = True):
        """
        Initialize pipeline components.

        Args:
            enable_email: Whether to send emails (default: True)
        """
        self.reader = TimeSeriesReader()
        self.state_tracker = StateTracker()
        self.alert_repo = AlertRepository()
        self.db_conn = psycopg2.connect(config.database_url)

        # Email delivery (optional)
        self.enable_email = enable_email
        self.email_service = None
        if enable_email:
            try:
                self.email_service = EmailDeliveryService()
                print("✓ Email delivery enabled")
            except ValueError as e:
                print(f"⚠️  Email delivery disabled: {e}")
                self.enable_email = False

    def close(self):
        """Close all connections."""
        self.state_tracker.close()
        self.alert_repo.close()
        if self.email_service:
            self.email_service.close()
        if self.db_conn:
            self.db_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_active_watchlists(self) -> list[dict]:
        """
        Get all active user watchlists.

        Returns:
            List of dicts with user_id, entity_id, ticker, email
        """
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    w.user_id,
                    w.entity_id,
                    e.ticker,
                    u.email,
                    u.alerts_enabled AS user_alerts_enabled,
                    w.alerts_enabled AS watchlist_alerts_enabled
                FROM watchlists w
                JOIN users u ON w.user_id = u.id
                JOIN entities e ON w.entity_id = e.id
                WHERE u.alerts_enabled = true
                  AND w.alerts_enabled = true
                """
            )

            return [dict(row) for row in cur.fetchall()]

    def evaluate_ticker_for_user(
        self, user_id: str, entity_id: str, ticker: str, lookback_days: int = 365
    ) -> list[Alert]:
        """
        Evaluate a single ticker for a user and detect material changes.

        Evaluates both technical and valuation signals:
        - Technical: 200-day MA crossovers (trend breaks)
        - Valuation: Regime transitions (cheap/normal/expensive zones)

        Args:
            user_id: User UUID
            entity_id: Entity UUID
            ticker: Stock ticker
            lookback_days: Days of historical data to fetch (default: 365)

        Returns:
            List of Alert objects (may be empty)
        """
        alerts = []

        # Fetch price data
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        df = self.reader.get_prices(ticker, start_date, end_date)

        if df.empty:
            print(f"  ⚠️  No price data for {ticker}")
            return alerts

        # Compute technical signals
        df = TechnicalSignals.compute_all_technical_signals(df)

        # Get latest technical signals
        latest = TechnicalSignals.get_latest_signals(df)

        if not latest:
            print(f"  ⚠️  No signals computed for {ticker}")
            return alerts

        # Get previous state
        previous_state = self.state_tracker.get_state(user_id, entity_id, ticker)

        # === Technical Signal Evaluation ===
        # Detect trend changes
        if latest.get("trend_position"):
            change = self.state_tracker.detect_trend_change(
                previous_state, latest["trend_position"], latest["close"]
            )

            if change and change.should_alert:
                print(f"  ✓ Trend break detected: {change.old_value} → {change.new_value}")

                # Generate alert
                alert = AlertGenerator.generate_trend_break_alert(
                    ticker=ticker,
                    change=change,
                    current_price=latest["close"],
                    sma_200=latest["sma_200"],
                    previous_price=previous_state.last_price_close,
                )

                alerts.append(alert)

                # Save alert to database
                alert_id = self.alert_repo.save_alert(user_id, entity_id, alert)
                print(f"  ✓ Alert saved: {alert_id}")

                # Send email if enabled
                if self.enable_email and self.email_service:
                    user_email = self._get_user_email(user_id)
                    if user_email:
                        self.email_service.send_alert_email(
                            user_id=user_id,
                            entity_id=entity_id,
                            user_email=user_email,
                            alert=alert,
                            alert_id=alert_id,
                        )

        # === Valuation Signal Evaluation ===
        # Fetch valuation data (use longer history for percentile calculation)
        valuation_start = end_date - timedelta(days=10 * 365)  # 10 years
        valuation_df = self.reader.r2.get_timeseries("signals_valuation", ticker, valuation_start, end_date)

        if not valuation_df.empty:
            # Compute valuation signals
            valuation_result = ValuationSignals.compute_valuation_signals(valuation_df, lookback_years=10)

            if valuation_result['success']:
                current_regime = valuation_result['regime']
                current_percentile = valuation_result['current_percentile']
                current_multiple = valuation_result['current_multiple']
                metric_type = valuation_result['metric_type']

                # Detect valuation regime change
                change = self.state_tracker.detect_valuation_regime_change(
                    previous_state,
                    current_percentile,
                    cheap_threshold=ValuationSignals.CHEAP_THRESHOLD,
                    expensive_threshold=ValuationSignals.EXPENSIVE_THRESHOLD,
                )

                if change and change.should_alert:
                    print(f"  ✓ Valuation regime change detected: {change.old_value} → {change.new_value}")

                    # Generate alert
                    alert = AlertGenerator.generate_valuation_regime_alert(
                        ticker=ticker,
                        change=change,
                        current_percentile=current_percentile,
                        current_metric_value=current_multiple,
                        metric_type=metric_type,
                        previous_percentile=previous_state.last_valuation_percentile,
                        previous_metric_value=None,  # Could store this in state if needed
                    )

                    alerts.append(alert)

                    # Save alert to database
                    alert_id = self.alert_repo.save_alert(user_id, entity_id, alert)
                    print(f"  ✓ Alert saved: {alert_id}")

                    # Send email if enabled
                    if self.enable_email and self.email_service:
                        user_email = self._get_user_email(user_id)
                        if user_email:
                            self.email_service.send_alert_email(
                                user_id=user_id,
                                entity_id=entity_id,
                                user_email=user_email,
                                alert=alert,
                                alert_id=alert_id,
                            )

                # Update valuation state
                self.state_tracker.update_state(
                    user_id=user_id,
                    entity_id=entity_id,
                    valuation_regime=current_regime,
                    valuation_percentile=current_percentile,
                )
            else:
                print(f"  ⚠️  Valuation computation failed: {valuation_result.get('error')}")

        # Update technical state
        self.state_tracker.update_state(
            user_id=user_id,
            entity_id=entity_id,
            trend_position=latest.get("trend_position"),
            price_close=latest.get("close"),
        )

        return alerts

    def _get_user_email(self, user_id: str) -> Optional[str]:
        """
        Get user email from database.

        Args:
            user_id: User UUID

        Returns:
            Email address or None
        """
        with self.db_conn.cursor() as cur:
            cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None

    def run_daily_evaluation(self) -> dict:
        """
        Run daily signal evaluation for all active watchlists.

        This is the main batch job that would run daily.

        Returns:
            Summary statistics
        """
        print("=" * 70)
        print("DAILY SIGNAL EVALUATION")
        print("=" * 70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        watchlists = self.get_active_watchlists()
        print(f"Processing {len(watchlists)} active watchlist items\n")

        total_alerts = 0
        results = []

        for item in watchlists:
            print(f"Evaluating {item['ticker']} for {item['email']}...")

            try:
                alerts = self.evaluate_ticker_for_user(
                    user_id=item["user_id"], entity_id=item["entity_id"], ticker=item["ticker"]
                )

                results.append(
                    {
                        "ticker": item["ticker"],
                        "email": item["email"],
                        "alerts_generated": len(alerts),
                        "status": "success",
                    }
                )

                total_alerts += len(alerts)

                if alerts:
                    print(f"  → {len(alerts)} alert(s) generated")
                else:
                    print(f"  → No material changes")

            except Exception as e:
                print(f"  ✗ Error: {e}")
                results.append(
                    {
                        "ticker": item["ticker"],
                        "email": item["email"],
                        "alerts_generated": 0,
                        "status": "error",
                        "error": str(e),
                    }
                )

            print()

        # Summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "watchlists_processed": len(watchlists),
            "total_alerts": total_alerts,
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "error"),
            "results": results,
        }

        print("=" * 70)
        print("EVALUATION SUMMARY")
        print("=" * 70)
        print(f"Watchlists processed: {summary['watchlists_processed']}")
        print(f"Total alerts generated: {summary['total_alerts']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return summary


if __name__ == "__main__":
    # Run daily evaluation
    with SignalPipeline() as pipeline:
        summary = pipeline.run_daily_evaluation()

        # Show alerts generated
        if summary["total_alerts"] > 0:
            print("\n" + "=" * 70)
            print("ALERTS DETAILS")
            print("=" * 70)

            for result in summary["results"]:
                if result["alerts_generated"] > 0:
                    print(f"\n{result['ticker']} ({result['email']}): {result['alerts_generated']} alert(s)")

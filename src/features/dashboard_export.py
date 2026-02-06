"""
Dashboard JSON export for the valuation dashboard.

Generates JSON files in R2 that the Cloudflare Worker serves to the Next.js frontend:
- dashboard/v1/overview.json: Latest values for all tickers + active triggers
- dashboard/v1/{TICKER}.json: Per-ticker historical time-series
"""

import json
from datetime import date
from typing import Optional

import pandas as pd

from src.storage.r2_client import R2Client


class DashboardExporter:
    """Exports dashboard JSON files to R2 after daily pipeline runs."""

    OVERVIEW_KEY = "dashboard/v1/overview.json"
    TICKER_KEY_TEMPLATE = "dashboard/v1/{ticker}.json"

    # Keep 5 years of valuation history, 1 year of technical
    MAX_VALUATION_DAYS = 1260  # ~5 years trading days
    MAX_TECHNICAL_DAYS = 252   # ~1 year trading days

    def __init__(self, r2_client: Optional[R2Client] = None):
        self.r2 = r2_client or R2Client()

    def export_dashboard(
        self,
        features_df: pd.DataFrame,
        triggers_df: pd.DataFrame,
        run_date: date,
    ) -> dict:
        """
        Export dashboard JSON files after daily pipeline run.

        Args:
            features_df: Today's features (from step 2, already in memory)
            triggers_df: Today's triggers (from step 3, already in memory). Can be empty DataFrame.
            run_date: Pipeline run date

        Returns:
            Summary dict
        """
        print(f"\n{'=' * 70}")
        print("STEP 3.5: DASHBOARD JSON EXPORT")
        print(f"{'=' * 70}")

        # Export overview
        self._export_overview(features_df, triggers_df, run_date)

        # Export per-ticker histories
        tickers_exported = self._export_ticker_histories(features_df, run_date)

        summary = {
            "status": "success",
            "tickers_exported": tickers_exported,
            "overview_key": self.OVERVIEW_KEY,
        }
        print(f"\nDashboard export complete: {tickers_exported} tickers")
        return summary

    def _export_overview(
        self,
        features_df: pd.DataFrame,
        triggers_df: pd.DataFrame,
        run_date: date,
    ):
        """Write overview.json with latest values + active triggers."""
        tickers_data = []

        for _, row in features_df.iterrows():
            ticker = row["ticker"]

            # Get triggers for this ticker
            ticker_triggers = []
            if not triggers_df.empty and "ticker" in triggers_df.columns:
                t_rows = triggers_df[triggers_df["ticker"] == ticker]
                for _, t_row in t_rows.iterrows():
                    ticker_triggers.append({
                        "id": t_row.get("template_id", ""),
                        "name": t_row.get("template_name", ""),
                        "strength": float(t_row.get("trigger_strength", 0)),
                    })

            tickers_data.append({
                "ticker": ticker,
                "sector": row.get("sector"),
                "close": _safe_float(row.get("close")),
                "ema_200": _safe_float(row.get("ema_200")),
                "ema_50": _safe_float(row.get("ema_50")),
                "ev_ebit": _safe_float(row.get("ev_ebit")),
                "triggers": ticker_triggers,
            })

        overview = {
            "updated_at": run_date.isoformat(),
            "tickers": tickers_data,
        }

        self.r2.put_json(self.OVERVIEW_KEY, overview)
        print(f"  Wrote overview for {len(tickers_data)} tickers")

    def _export_ticker_histories(
        self,
        features_df: pd.DataFrame,
        run_date: date,
    ) -> int:
        """
        For each ticker, read existing history JSON, append today's row, trim, write back.
        """
        count = 0

        for _, row in features_df.iterrows():
            ticker = row["ticker"]
            key = self.TICKER_KEY_TEMPLATE.format(ticker=ticker)

            # Read existing history
            existing = self.r2.get_json(key)

            if existing and "history" in existing:
                history = existing["history"]
            else:
                history = []

            # Build today's data point
            today = {
                "date": run_date.isoformat(),
                "close": _safe_float(row.get("close")),
                "ema_200": _safe_float(row.get("ema_200")),
                "ema_50": _safe_float(row.get("ema_50")),
                "ev_ebit": _safe_float(row.get("ev_ebit")),
            }

            # Remove any existing entry for today (idempotent)
            history = [h for h in history if h.get("date") != run_date.isoformat()]

            # Append today
            history.append(today)

            # Sort by date
            history.sort(key=lambda x: x.get("date", ""))

            # Trim to max length (keep most recent)
            if len(history) > self.MAX_VALUATION_DAYS:
                history = history[-self.MAX_VALUATION_DAYS:]

            # Write back
            ticker_data = {
                "ticker": ticker,
                "updated_at": run_date.isoformat(),
                "history": history,
            }

            self.r2.put_json(key, ticker_data)
            count += 1

        return count


def _safe_float(val) -> Optional[float]:
    """Convert to float, handling NaN and None."""
    if val is None:
        return None
    try:
        import math
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (ValueError, TypeError):
        return None

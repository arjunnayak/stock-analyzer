"""
Daily pipeline orchestrator for feature computation and template evaluation.

Runs after price ingestion:
1. Step 2: Compute daily features for all active tickers
2. Step 3: Evaluate hardcoded templates using latest features + valuation stats
"""

import argparse
from datetime import date, datetime
from typing import Optional

import pandas as pd

from src.features.features_compute import FeaturesComputer
from src.features.templates import (
    ALL_TEMPLATES,
    BASIC_TEMPLATES,
    STATS_TEMPLATES,
    evaluate_all_templates,
)
from src.storage.r2_client import R2Client
from src.storage.supabase_db import SupabaseDB


class DailyPipeline:
    """Orchestrates the daily feature computation and template evaluation pipeline."""

    def __init__(
        self,
        r2_client: Optional[R2Client] = None,
        db: Optional[SupabaseDB] = None,
    ):
        """
        Initialize pipeline components.

        Args:
            r2_client: R2 storage client
            db: Supabase database client
        """
        self.r2 = r2_client or R2Client()
        self.db = db or SupabaseDB()
        self.features_computer = FeaturesComputer(
            r2_client=self.r2,
            db=self.db,
        )

    def close(self):
        """Close all connections."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def run(
        self,
        run_date: date,
        tickers: Optional[list[str]] = None,
        skip_features: bool = False,
        skip_templates: bool = False,
        skip_stats_templates: bool = False,
        dry_run: bool = False,
    ) -> dict:
        """
        Run the full daily pipeline.

        Args:
            run_date: Date of the pipeline run
            tickers: Optional list of tickers (defaults to all active)
            skip_features: Skip Step 2 (feature computation)
            skip_templates: Skip Step 3 (template evaluation)
            skip_stats_templates: Skip templates that require valuation stats
            dry_run: Don't write to R2 or Supabase

        Returns:
            Summary dict with results from each step
        """
        print("\n" + "=" * 70)
        print(f"DAILY PIPELINE - {run_date}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        results = {
            "run_date": run_date.isoformat(),
            "started_at": datetime.now().isoformat(),
            "step2_features": None,
            "step3_templates": None,
            "status": "pending",
        }

        # =====================================================================
        # Step 2: Feature Computation
        # =====================================================================
        if not skip_features:
            print("\n" + "=" * 70)
            print("STEP 2: FEATURE COMPUTATION")
            print("=" * 70)

            step2_result = self.features_computer.compute_daily_features(
                run_date=run_date,
                tickers=tickers,
                dry_run=dry_run,
            )

            results["step2_features"] = step2_result

            if step2_result["status"] not in ("success", "dry_run"):
                print(f"\nStep 2 failed: {step2_result['status']}")
                results["status"] = "failed_step2"
                return results

        # =====================================================================
        # Step 3: Template Evaluation
        # =====================================================================
        if not skip_templates:
            print("\n" + "=" * 70)
            print("STEP 3: TEMPLATE EVALUATION")
            print("=" * 70)

            step3_result = self._evaluate_templates(
                run_date=run_date,
                skip_stats_templates=skip_stats_templates,
                dry_run=dry_run,
            )

            results["step3_templates"] = step3_result

        # =====================================================================
        # Summary
        # =====================================================================
        results["status"] = "success"
        results["completed_at"] = datetime.now().isoformat()

        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)
        print(f"Status: {results['status']}")
        if results["step2_features"]:
            print(f"Features: {results['step2_features'].get('tickers_processed', 0)} tickers")
        if results["step3_templates"]:
            print(f"Templates: {results['step3_templates'].get('total_triggers', 0)} total triggers")

        return results

    def _evaluate_templates(
        self,
        run_date: date,
        skip_stats_templates: bool = False,
        dry_run: bool = False,
    ) -> dict:
        """
        Evaluate all templates on the latest features.

        Args:
            run_date: Date of evaluation
            skip_stats_templates: Skip templates that require valuation stats
            dry_run: Don't write results to R2

        Returns:
            Summary dict with template evaluation results
        """
        # Load latest features
        features_df = self.r2.get_features_latest()

        if features_df is None or features_df.empty:
            print("No features data available. Skipping template evaluation.")
            return {
                "status": "no_features",
                "total_triggers": 0,
            }

        print(f"Loaded features for {len(features_df)} tickers")

        # Get run_date from features if not explicitly set
        if "date" in features_df.columns:
            features_date = features_df["date"].iloc[0]
            if isinstance(features_date, str):
                features_date = date.fromisoformat(features_date)
            elif hasattr(features_date, "date"):
                features_date = features_date.date()
            print(f"Features date: {features_date}")

        # Determine which templates to run
        if skip_stats_templates:
            templates = BASIC_TEMPLATES
            print(f"Running {len(templates)} basic templates (skipping stats templates)")
        else:
            templates = ALL_TEMPLATES
            print(f"Running {len(templates)} templates")

            # Load and join valuation stats
            features_df = self._join_valuation_stats(features_df)

        # Evaluate all templates
        print("\nEvaluating templates...")
        triggers_df = evaluate_all_templates(features_df, templates)

        # Add date column
        triggers_df["date"] = run_date

        # Reorder columns
        if not triggers_df.empty:
            triggers_df = triggers_df[
                ["date", "ticker", "template_id", "template_name", "trigger_strength", "reasons_json"]
            ]

        print(f"\nTotal triggers: {len(triggers_df)}")

        # Show summary by template
        if not triggers_df.empty:
            print("\nTriggers by template:")
            summary = triggers_df.groupby(["template_id", "template_name"]).size()
            for (tid, name), count in summary.items():
                print(f"  [{tid}] {name}: {count}")

        # Write to R2
        if not dry_run and not triggers_df.empty:
            key = self.r2.put_triggers(run_date, triggers_df)
            print(f"\nWrote triggers to: {key}")
        elif dry_run:
            print("\n[DRY RUN] Skipping write to R2")

        return {
            "status": "success",
            "total_triggers": len(triggers_df),
            "triggers_by_template": (
                triggers_df.groupby("template_id").size().to_dict() if not triggers_df.empty else {}
            ),
        }

    def _join_valuation_stats(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Join valuation stats to features DataFrame.

        Adds columns like ev_ebitda_p20, ev_ebitda_p50, ev_ebitda_p80.

        Args:
            features_df: Features DataFrame

        Returns:
            Features DataFrame with valuation stats columns added
        """
        tickers = features_df["ticker"].unique().tolist()

        # Fetch stats for ev_ebitda metric
        stats_df = self.db.fetch_valuation_stats(
            tickers=tickers,
            metric="ev_ebitda",
            window_days=1260,  # ~5 years
        )

        if stats_df.empty:
            print("No valuation stats available. Stats templates may not trigger.")
            return features_df

        print(f"Loaded valuation stats for {len(stats_df)} tickers")

        # Select and rename columns for join
        stats_join = stats_df[["ticker", "p10", "p20", "p50", "p80", "p90"]].copy()
        stats_join = stats_join.rename(
            columns={
                "p10": "ev_ebitda_p10",
                "p20": "ev_ebitda_p20",
                "p50": "ev_ebitda_p50",
                "p80": "ev_ebitda_p80",
                "p90": "ev_ebitda_p90",
            }
        )

        # Left join to features
        features_df = features_df.merge(stats_join, on="ticker", how="left")

        # Log coverage
        stats_coverage = features_df["ev_ebitda_p20"].notna().sum()
        print(f"Valuation stats coverage: {stats_coverage}/{len(features_df)} tickers")

        return features_df


def main():
    """Main entry point for the daily pipeline."""
    parser = argparse.ArgumentParser(
        description="Run daily feature computation and template evaluation pipeline"
    )
    parser.add_argument(
        "--run-date",
        type=str,
        help="Date to run pipeline for (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        help="Specific tickers to process (default: all active)",
    )
    parser.add_argument(
        "--skip-features",
        action="store_true",
        help="Skip feature computation (Step 2)",
    )
    parser.add_argument(
        "--skip-templates",
        action="store_true",
        help="Skip template evaluation (Step 3)",
    )
    parser.add_argument(
        "--skip-stats-templates",
        action="store_true",
        help="Skip templates that require valuation stats",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write to R2 or Supabase",
    )

    args = parser.parse_args()

    # Parse run date
    if args.run_date:
        run_date = date.fromisoformat(args.run_date)
    else:
        run_date = date.today()

    # Run pipeline
    with DailyPipeline() as pipeline:
        result = pipeline.run(
            run_date=run_date,
            tickers=args.tickers,
            skip_features=args.skip_features,
            skip_templates=args.skip_templates,
            skip_stats_templates=args.skip_stats_templates,
            dry_run=args.dry_run,
        )

        # Exit with non-zero if failed
        if result["status"] not in ("success", "dry_run"):
            exit(1)


if __name__ == "__main__":
    main()

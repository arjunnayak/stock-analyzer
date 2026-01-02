-- Add operating_income_ttm column to fundamentals_latest
-- This provides EBIT (Earnings Before Interest and Taxes) with quarterly granularity
-- Used for EV/EBIT valuation metric which is more accurate than EV/EBITDA

ALTER TABLE fundamentals_latest
ADD COLUMN IF NOT EXISTS operating_income_ttm DOUBLE PRECISION;

COMMENT ON COLUMN fundamentals_latest.operating_income_ttm IS 'Trailing 12-month operating income (EBIT) - sum of last 4 quarters';

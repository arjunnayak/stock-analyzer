# Earnings db - schema

## `balance_sheet_assets`

| Column                     | Type          |
| -------------------------- | ------------- |
| date                       | date          |
| act_symbol                 | varchar(64)   |
| period                     | varchar(64)   |
| cash_and_equivalents       | decimal(24,8) |
| receivables                | decimal(24,8) |
| notes_receivable           | decimal(24,8) |
| inventories                | decimal(24,8) |
| other_current_assets       | decimal(24,8) |
| total_current_assets       | decimal(24,8) |
| net_property_and_equipment | decimal(24,8) |
| investments_and_advances   | decimal(24,8) |
| other_non_current_assets   | decimal(24,8) |
| deferred_charges           | decimal(24,8) |
| intangibles                | decimal(24,8) |
| deposits_and_other_assets  | decimal(24,8) |
| total_assets               | decimal(24,8) |

---

## `balance_sheet_equity`

| Column                       | Type          |
| ---------------------------- | ------------- |
| date                         | date          |
| act_symbol                   | varchar(64)   |
| period                       | varchar(64)   |
| preferred_stock              | decimal(24,8) |
| common_stock                 | decimal(24,8) |
| capital_surplus              | decimal(24,8) |
| retained_earnings            | decimal(24,8) |
| other_equity                 | decimal(24,8) |
| treasury_stock               | decimal(24,8) |
| total_equity                 | decimal(24,8) |
| total_liabilities_and_equity | decimal(24,8) |
| shares_outstanding           | decimal(24,8) |
| book_value_per_share         | decimal(16,2) |

---

## `balance_sheet_liabilities`

| Column                         | Type          |
| ------------------------------ | ------------- |
| date                           | date          |
| act_symbol                     | varchar(64)   |
| period                         | varchar(64)   |
| notes_payable                  | decimal(24,8) |
| accounts_payable               | decimal(24,8) |
| current_portion_long_term_debt | decimal(24,8) |
| current_portion_capital_leases | decimal(24,8) |
| accrued_expenses               | decimal(24,8) |
| income_taxes_payable           | decimal(24,8) |
| other_current_liabilities      | decimal(24,8) |
| total_current_liabilities      | decimal(24,8) |
| mortgages                      | decimal(24,8) |
| deferred_taxes_or_income       | decimal(24,8) |
| convertible_debt               | decimal(24,8) |
| long_term_debt                 | decimal(24,8) |
| non_current_liabilities        | decimal(24,8) |
| other_non_current_liabilities  | decimal(24,8) |
| minority_interest              | decimal(24,8) |
| total_liabilities              | decimal(24,8) |

---

## `cash_flow_statement`

| Column                             | Type          |
| ---------------------------------- | ------------- |
| date                               | date          |
| act_symbol                         | varchar(64)   |
| period                             | varchar(64)   |
| net_income                         | decimal(24,8) |
| depreciation_amortization          | decimal(24,8) |
| net_change_from_assets             | decimal(24,8) |
| net_cash_from_operations           | decimal(24,8) |
| other_operating_activities         | decimal(24,8) |
| net_cash_from_operating            | decimal(24,8) |
| property_and_equipment             | decimal(24,8) |
| acquisition_from_assets            | decimal(24,8) |
| investments                        | decimal(24,8) |
| other_investing_activities         | decimal(24,8) |
| net_cash_from_investing            | decimal(24,8) |
| issuance_of_capital_stock          | decimal(24,8) |
| issuance_of_debt                   | decimal(24,8) |
| increase_short_term_debt           | decimal(24,8) |
| payment_of_dividends               | decimal(24,8) |
| other_financing_activities         | decimal(24,8) |
| net_cash_from_financing            | decimal(24,8) |
| effect_of_exchange_rate            | decimal(24,8) |
| net_change_in_cash_and_equivalents | decimal(24,8) |
| cash_at_beginning_of_period        | decimal(24,8) |
| cash_at_end_of_period              | decimal(24,8) |
| diluted_net_eps                    | decimal(16,2) |

---

## `earnings_calendar`

| Column     | Type        |
| ---------- | ----------- |
| act_symbol | varchar(64) |
| date       | date        |
| when       | text        |

---

## `eps_estimate`

| Column          | Type         |
| --------------- | ------------ |
| date            | date         |
| act_symbol      | varchar(64)  |
| period          | varchar(64)  |
| period_end_date | date         |
| consensus       | decimal(7,2) |
| recent          | decimal(7,2) |
| count           | smallint     |
| high            | decimal(7,2) |
| low             | decimal(7,2) |
| year_ago        | decimal(7,2) |

---

## `eps_history`

| Column          | Type          |
| --------------- | ------------- |
| act_symbol      | varchar(64)   |
| period_end_date | date          |
| reported        | decimal(16,2) |
| estimate        | decimal(16,2) |

---

## `income_statement`

| Column                            | Type          |
| --------------------------------- | ------------- |
| date                              | date          |
| act_symbol                        | varchar(64)   |
| period                            | varchar(64)   |
| sales                             | decimal(24,8) |
| cost_of_goods                     | decimal(24,8) |
| gross_profit                      | decimal(24,8) |
| selling_administrative            | decimal(24,8) |
| income_after_depreciation         | decimal(24,8) |
| non_operating_income              | decimal(24,8) |
| interest_expense                  | decimal(24,8) |
| pretax_income                     | decimal(24,8) |
| income_taxes                      | decimal(24,8) |
| minority_interest                 | decimal(24,8) |
| investment_gains                  | decimal(24,8) |
| other_income                      | decimal(24,8) |
| income_from_continuing_operations | decimal(24,8) |
| extras_and_discontinued           | decimal(24,8) |
| net_income                        | decimal(24,8) |
| income_before_depreciation        | decimal(24,8) |
| depreciation_and_amortization     | decimal(24,8) |
| average_shares                    | decimal(24,8) |
| diluted_eps_before_non_recurring  | decimal(16,2) |
| diluted_net_eps                   | decimal(16,2) |

---

## `rank_score`

| Column     | Type        |
| ---------- | ----------- |
| date       | date        |
| act_symbol | varchar(64) |
| rank       | text        |
| value      | text        |
| growth     | text        |
| momentum   | text        |
| vgm        | text        |

---

## `sales_estimate`

| Column          | Type        |
| --------------- | ----------- |
| date            | date        |
| act_symbol      | varchar(64) |
| period          | varchar(64) |
| period_end_date | date        |
| consensus       | bigint      |
| count           | bigint      |
| high            | bigint      |
| low             | bigint      |
| year_ago        | bigint      |



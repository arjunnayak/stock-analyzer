# Stocks DB – Schema

## `dividend`

| Column     | Type          |
| ---------- | ------------- |
| act_symbol | varchar(64)   |
| ex_date    | date          |
| amount     | decimal(10,5) |

---

## `ohlcv`

| Column     | Type         |
| ---------- | ------------ |
| date       | date         |
| act_symbol | varchar(64)  |
| open       | decimal(7,2) |
| high       | decimal(7,2) |
| low        | decimal(7,2) |
| close      | decimal(7,2) |
| volume     | bigint       |

---

## `split`

| Column     | Type          |
| ---------- | ------------- |
| act_symbol | varchar(64)   |
| ex_date    | date          |
| to_factor  | decimal(10,5) |
| for_factor | decimal(10,5) |

---

## `symbol`

| Column           | Type        |
| ---------------- | ----------- |
| act_symbol       | varchar(64) |
| security_name    | text        |
| listing_exchange | text        |
| market_category  | text        |
| is_etf           | tinyint     |
| round_lot_size   | int         |
| is_test_issue    | tinyint     |
| financial_status | text        |
| cqs_symbol       | text        |
| nasdaq_symbol    | text        |
| is_next_shares   | tinyint     |
| last_seen        | date        |

---

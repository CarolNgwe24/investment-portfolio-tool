# Investment Portfolio Tool

A Python + MySQL tool that calculates real portfolio performance — cost basis, current value, profit/loss, and ROI — per asset and by asset class, in ZAR.

## What it does

- Pulls transaction history (buys/sells) and live asset prices from a MySQL database
- Calculates each position's **cost basis using average-cost accounting** — not a naive sum of signed transaction costs, which breaks (produces misleading or inverted ROI%) once a position is partially or fully sold
- Flags any **oversold positions** (a SELL that exceeds shares actually held), which usually points to missing transaction records or bad data ordering, rather than silently producing a wrong number
- Converts all monetary figures to **ZAR**, since underlying asset prices are USD-denominated
- Outputs a per-asset summary table plus a portfolio-wide cost basis and asset allocation breakdown

## Why average-cost basis matters

An earlier version of this tool summed signed transaction costs directly (+cost on BUY, -cost on SELL). That approach silently breaks the moment a position is closed or oversold:

- A fully-sold position could show **-100% ROI** on a position worth $0, because total cost basis went to zero
- An oversold position (more sold than ever bought) could **flip the sign of ROI entirely**, showing a large gain on what was actually a loss

This version tracks shares held and cost basis per asset in chronological order, releasing cost basis at the running average cost per share on each SELL — which keeps the math correct and any oversold data issue clearly flagged rather than hidden.

## Tech stack

- Python (pandas, NumPy)
- MySQL (via SQLAlchemy + mysql-connector-python)
- python-dotenv for credential management

## Database schema

Three tables: `assets`, `market_prices`, `transactions` — see the SQL in this repo (or your own MySQL Workbench setup) for exact structure. Each transaction records a BUY or SELL with quantity, price per unit, and a transaction date, which the average-cost calculation depends on.

## Notes

- The USD-to-ZAR conversion rate is currently a hardcoded snapshot in the script — update it periodically, or swap in a live FX API call for ongoing accuracy.
- This is a portfolio project built to demonstrate data analysis, SQL, and accurate financial calculation logic — not a production trading or accounting tool.

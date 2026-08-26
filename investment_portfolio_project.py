import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME", "portfolio_tracker")

if not DB_USER or not DB_PASS:
    raise RuntimeError(
        "DB_USER and DB_PASS must be set in your .env file — see .env.example"
    )

DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

USD_TO_ZAR = 15.95


def compute_average_cost_position(group: pd.DataFrame) -> pd.Series:
    """
    Walk a single asset's transactions in chronological order, tracking
    shares held and their average cost basis.

    This replaces naive signed-cost summation. Summing net_cost directly
    breaks once a position is fully or over-sold: total_cost can hit zero
    or go negative, which sends ROI to -100% on closed positions or flips
    its sign entirely on oversold ones. Here, each SELL releases cost
    basis at the *running average cost per share* at the time of the
    sale, which keeps total_cost >= 0 for any valid (non-oversold) history.
    """
    group = group.sort_values("transaction_date")
    shares_held = 0.0
    cost_basis = 0.0
    oversold = False

    for _, txn in group.iterrows():
        qty = txn["quantity"]
        price = txn["price_per_unit"]

        if txn["transaction_type"] == "BUY":
            shares_held += qty
            cost_basis += qty * price

        elif txn["transaction_type"] == "SELL":
            if qty > shares_held:
                oversold = True
            avg_cost = (cost_basis / shares_held) if shares_held > 0 else 0.0
            cost_basis -= qty * avg_cost
            shares_held -= qty

        else:
            raise ValueError(f"Unknown transaction_type: {txn['transaction_type']!r}")

    return pd.Series({
        "shares_held": shares_held,
        "total_cost": cost_basis,
        "oversold": oversold,
    })


try:
    df_transactions = pd.read_sql(
        "SELECT * FROM transactions ORDER BY asset_id, transaction_date",
        con=engine
    )

    df_assets_prices = pd.read_sql("""
        SELECT mp.asset_id, a.ticker, a.asset_name, a.asset_type, mp.current_price
        FROM market_prices mp
        JOIN assets a ON mp.asset_id = a.asset_id
    """, con=engine)

    if "transaction_date" not in df_transactions.columns:
        raise RuntimeError(
            "transactions table has no transaction_date column — "
            "average-cost tracking needs chronological order."
        )

    df_portfolio = (
        df_transactions.groupby("asset_id", group_keys=False)
        .apply(compute_average_cost_position, include_groups=False)
        .reset_index()
    )

except Exception as e:
    print(f"An error occurred: {e}")
    raise SystemExit(1)

df_final = pd.merge(df_portfolio, df_assets_prices, on="asset_id")

df_final["current_value_usd"] = df_final["shares_held"] * df_final["current_price"]
df_final["profit_loss_usd"] = df_final["current_value_usd"] - df_final["total_cost"]
df_final["roi_pct"] = np.where(
    df_final["total_cost"] > 0,
    (df_final["profit_loss_usd"] / df_final["total_cost"]) * 100,
    np.nan,
)

# Convert to ZAR for display
df_final["total_cost"] = df_final["total_cost"] * USD_TO_ZAR
df_final["current_value"] = df_final["current_value_usd"] * USD_TO_ZAR
df_final["profit_loss"] = df_final["profit_loss_usd"] * USD_TO_ZAR

print("\n" + "=" * 95)
print("  INVESTMENT PORTFOLIO PROJECT SUMMARY (ZAR)  ")
print(f"  Converted at R{USD_TO_ZAR:.2f} / USD")
print("=" * 95)

pd.set_option("display.float_format", lambda x: f"R{x:,.2f}")
print(df_final[["ticker", "asset_name", "asset_type", "shares_held",
                 "total_cost", "current_value", "profit_loss", "roi_pct"]].to_string(index=False))

if df_final["oversold"].any():
    flagged = df_final.loc[df_final["oversold"], "ticker"].tolist()
    print("\n⚠ WARNING: oversold positions detected (SELL quantity exceeded "
          f"shares held at the time): {', '.join(flagged)}")
    print("  Check the transactions table for missing BUY records or out-of-order data.")

total_portfolio_cost = df_final["total_cost"].sum()
print("\n" + "=" * 45)
print(f"Total portfolio cost basis: R{total_portfolio_cost:,.2f}")
print("=" * 45)

asset_summary = df_final.groupby("asset_type")["total_cost"].sum()
print("\nAsset Allocation Breakdown:")
print(asset_summary)
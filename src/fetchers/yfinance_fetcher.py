from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf


def fetch_ohlcv(
    ticker: str,
    start_date: date,
    end_date: date,
) -> Optional[pd.DataFrame]:
    """
    Fetch daily OHLCV data for a single ticker from Yahoo Finance.
    Returns None if the ticker is invalid or data is unavailable.

    Columns returned: ticker, date, open, high, low, close, adj_close, volume
    """
    try:
        raw = yf.download(
            ticker,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            auto_adjust=False,
            progress=False,
            multi_level_index=False,
        )
    except Exception as e:
        print(f"[yfinance_fetcher] Network error for {ticker}: {e}")
        return None

    if raw is None or raw.empty:
        print(f"[yfinance_fetcher] No data returned for {ticker}")
        return None

    df = raw.reset_index()
    df.columns = [str(c) for c in df.columns]

    rename_map = {
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    required = {"date", "open", "high", "low", "close", "adj_close", "volume"}
    missing = required - set(df.columns)
    if missing:
        print(f"[yfinance_fetcher] Missing columns for {ticker}: {missing}")
        return None

    df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]]
    df = df.dropna(subset=["date"])

    return df


def fetch_multiple(
    tickers: list[str],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Fetch OHLCV for multiple tickers, returning a single combined DataFrame.
    Tickers that fail are skipped with a warning; pipeline continues.
    """
    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        df = fetch_ohlcv(ticker, start_date, end_date)
        if df is not None and not df.empty:
            frames.append(df)
        else:
            print(f"[yfinance_fetcher] Skipping {ticker} — no data available")

    if not frames:
        return pd.DataFrame(
            columns=["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]
        )

    return pd.concat(frames, ignore_index=True)

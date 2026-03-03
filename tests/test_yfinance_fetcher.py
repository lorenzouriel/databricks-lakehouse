"""Unit tests for src/fetchers/yfinance_fetcher.py"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.fetchers.yfinance_fetcher import fetch_multiple, fetch_ohlcv


REQUIRED_COLS = {"ticker", "date", "open", "high", "low", "close", "adj_close", "volume"}


def _make_yf_response(ticker: str, n_rows: int = 5) -> pd.DataFrame:
    """Build a synthetic yfinance-style response DataFrame."""
    dates = pd.date_range("2024-01-02", periods=n_rows, freq="B")
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": [185.0 + i for i in range(n_rows)],
            "High": [186.0 + i for i in range(n_rows)],
            "Low": [183.0 + i for i in range(n_rows)],
            "Close": [184.5 + i for i in range(n_rows)],
            "Adj Close": [184.5 + i for i in range(n_rows)],
            "Volume": [60_000_000 + i * 100_000 for i in range(n_rows)],
        }
    )


@patch("src.fetchers.yfinance_fetcher.yf.download")
def test_fetch_ohlcv_returns_correct_columns(mock_download, start_date, end_date):
    mock_download.return_value = _make_yf_response("AAPL").set_index("Date")
    result = fetch_ohlcv("AAPL", start_date, end_date)

    assert result is not None
    assert REQUIRED_COLS == set(result.columns)


@patch("src.fetchers.yfinance_fetcher.yf.download")
def test_fetch_ohlcv_adds_ticker_column(mock_download, start_date, end_date):
    mock_download.return_value = _make_yf_response("AAPL").set_index("Date")
    result = fetch_ohlcv("AAPL", start_date, end_date)

    assert result is not None
    assert (result["ticker"] == "AAPL").all()


@patch("src.fetchers.yfinance_fetcher.yf.download")
def test_fetch_ohlcv_returns_none_for_empty_response(mock_download, start_date, end_date):
    mock_download.return_value = pd.DataFrame()
    result = fetch_ohlcv("INVALID_TICKER", start_date, end_date)

    assert result is None


@patch("src.fetchers.yfinance_fetcher.yf.download")
def test_fetch_ohlcv_returns_none_on_exception(mock_download, start_date, end_date):
    mock_download.side_effect = Exception("Connection error")
    result = fetch_ohlcv("AAPL", start_date, end_date)

    assert result is None


@patch("src.fetchers.yfinance_fetcher.yf.download")
def test_fetch_multiple_combines_tickers(mock_download, start_date, end_date):
    def side_effect(ticker, **kwargs):
        return _make_yf_response(ticker).set_index("Date")

    mock_download.side_effect = side_effect
    result = fetch_multiple(["AAPL", "BTC-USD"], start_date, end_date)

    assert not result.empty
    assert set(result["ticker"].unique()) == {"AAPL", "BTC-USD"}


@patch("src.fetchers.yfinance_fetcher.yf.download")
def test_fetch_multiple_skips_failed_ticker(mock_download, start_date, end_date):
    def side_effect(ticker, **kwargs):
        if ticker == "AAPL":
            return _make_yf_response("AAPL").set_index("Date")
        return pd.DataFrame()

    mock_download.side_effect = side_effect
    result = fetch_multiple(["AAPL", "INVALID"], start_date, end_date)

    assert not result.empty
    assert list(result["ticker"].unique()) == ["AAPL"]


@patch("src.fetchers.yfinance_fetcher.yf.download")
def test_fetch_multiple_returns_empty_df_for_all_failed(mock_download, start_date, end_date):
    mock_download.return_value = pd.DataFrame()
    result = fetch_multiple(["INVALID1", "INVALID2"], start_date, end_date)

    assert result.empty
    assert set(result.columns) == REQUIRED_COLS

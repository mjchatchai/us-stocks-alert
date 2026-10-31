"""
Pytest configuration and shared fixtures for Bot 3 & Bot 4 test suite.
"""

import os
import sys
import tempfile
import json
import pytest
import pandas as pd
import numpy as np

# Ensure project root and source directories are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT3_SRC = os.path.join(PROJECT_ROOT, "bot3_pullback", "src")
BOT4_SRC = os.path.join(PROJECT_ROOT, "bot4_thai_pullback", "src")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

for path in [PROJECT_ROOT, BOT3_SRC, BOT4_SRC, SRC_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture
def bot3_default_config():
    """Default configuration for Bot 3 (US Pullback)."""
    return {
        "portfolio_equity": 10000.0,
        "risk_per_trade_pct": 0.5,
        "max_allocation_per_trade_pct": 20.0,
        "board_lot_size": 1,
        "tp1_sell_ratio": 0.5,
        "trailing_ema": 9,
        "active_positions": {},
        "trade_history": []
    }


@pytest.fixture
def bot4_default_config():
    """Default configuration for Bot 4 (Thai SET Pullback)."""
    return {
        "portfolio_equity": 1000000.0,
        "risk_per_trade_pct": 0.5,
        "max_allocation_per_trade_pct": 20.0,
        "board_lot_size": 100,
        "tp1_sell_ratio": 0.5,
        "trailing_ema": 9,
        "min_turnover": 20000000.0,
        "active_positions": {},
        "trade_history": []
    }


@pytest.fixture
def sample_candlestick_df():
    """Generates synthetic OHLCV dataframe with various candle patterns."""
    dates = pd.date_range(start="2026-01-01", periods=100, freq="B")
    
    # Baseline steady uptrend series
    close = np.linspace(50.0, 100.0, 100)
    high = close + 1.5
    low = close - 1.5
    open_p = close - 0.5
    vol = np.full(100, 500000)

    df = pd.DataFrame({
        "Open": open_p,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": vol
    }, index=dates)
    return df


@pytest.fixture
def temp_config_file():
    """Provides a temporary config file that is cleaned up after test."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    initial_data = {
        "portfolio_equity": 10000.0,
        "active_positions": {},
        "trade_history": []
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(initial_data, f, indent=2)
    
    yield path

    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass

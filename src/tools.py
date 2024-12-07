import os

import pandas as pd
import requests
import yfinance as yf

def get_prices(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, interval='1d')

    # Ensure the DataFrame has the necessary columns
    if df.empty or 'Close' not in df.columns:
        raise ValueError("No price data returned")

    # Rename columns to match the expected format
    df.rename(columns={'Close': 'close', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'volume'}, inplace=True)

    # Sort by date
    df.sort_index(inplace=True)

    return df

def prices_to_df(prices):
    

    """Convert prices to a DataFrame."""
    ticker = prices.columns.get_level_values(1)[0]
    close = prices.columns.get_level_values(0)[1]
    vol = prices.columns.get_level_values(0)[-1]
    df = pd.DataFrame()
    df['close'] = pd.DataFrame(prices[close][ticker])
    df['volume'] = pd.DataFrame(prices[vol][ticker])

    df.columns = ["close","volume"]
    return df

# Update the get_price_data function to use the new functions
def get_price_data(ticker, start_date, end_date):
    prices = get_prices(ticker, start_date, end_date)
    return prices_to_df(prices)

def get_financial_metrics(ticker, report_period, period='ttm', limit=1):
    """Fetch financial metrics using yfinance."""
    stock = yf.Ticker(ticker)
    financials = stock.financials

    # Filter financials based on the report_period and period if necessary
    # Note: yfinance does not directly support period filtering like 'ttm'
    # You may need to manually handle this based on the data structure

    if financials.empty:
        raise ValueError("No financial metrics returned")

    # Return the financial metrics as needed
    return financials

def calculate_confidence_level(signals):
    """Calculate confidence level based on the difference between SMAs."""
    sma_diff_prev = abs(signals['sma_5_prev'] - signals['sma_20_prev'])
    sma_diff_curr = abs(signals['sma_5_curr'] - signals['sma_20_curr'])
    diff_change = sma_diff_curr - sma_diff_prev
    # Normalize confidence between 0 and 1
    confidence = min(max(diff_change / signals['current_price'], 0), 1)
    return confidence

def calculate_macd(prices_df):
    ema_12 = prices_df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = prices_df['close'].ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line, signal_line

def calculate_rsi(prices_df, period=14):
    delta = prices_df['close'].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(prices_df, window=20):
    sma = prices_df['close'].rolling(window).mean()
    std_dev = prices_df['close'].rolling(window).std()
    upper_band = sma + (std_dev * 2)
    lower_band = sma - (std_dev * 2)
    return upper_band, lower_band


def calculate_obv(prices_df):
    obv = [0]
    for i in range(1, len(prices_df)):
        if prices_df['close'].iloc[i] > prices_df['close'].iloc[i - 1]:
            obv.append(obv[-1] + prices_df['volume'].iloc[i])
        elif prices_df['close'].iloc[i] < prices_df['close'].iloc[i - 1]:
            obv.append(obv[-1] - prices_df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    prices_df['OBV'] = obv
    return prices_df['OBV']
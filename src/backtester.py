from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd

from tools import get_price_data
from agents import run_hedge_fund

class Backtester:
    def __init__(self, agent, ticker, start_date, end_date, initial_capital):
        self.agent = agent
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.portfolio = {"cash": initial_capital, "stock": 0}
        self.portfolio_values = []

    def parse_action(self, agent_output):
        try:
            # Expect JSON output from agent
            import json
            decision = json.loads(agent_output)
            return decision["action"], decision["quantity"]
        except:
            print(f"Error parsing action: {agent_output}")
            return "hold", 0

    def execute_trade(self, action, quantity, current_price):
        """Validate and execute trades based on portfolio constraints"""
        if action == "buy" and quantity > 0:
            cost = quantity * current_price
            if cost <= self.portfolio["cash"]:
                self.portfolio["stock"] += quantity
                self.portfolio["cash"] -= cost
                return quantity
            else:
                # Calculate maximum affordable quantity
                max_quantity = self.portfolio["cash"] // current_price
                if max_quantity > 0:
                    self.portfolio["stock"] += max_quantity
                    self.portfolio["cash"] -= max_quantity * current_price
                    return max_quantity
                return 0
        elif action == "sell" and quantity > 0:
            quantity = min(quantity, self.portfolio["stock"])
            if quantity > 0:
                self.portfolio["cash"] += quantity * current_price
                self.portfolio["stock"] -= quantity
                return quantity
            return 0
        return 0

    def run_backtest(self):
        dates = pd.date_range(self.start_date, self.end_date, freq="B")

        print("\nStarting backtest...")
        print(f"{'Date':<12} {'Ticker':<6} {'Action':<6} {'Quantity':>8} {'Price':>8} {'Cash':>12} {'Stock':>8} {'Total Value':>12}")
        print("-" * 70)

        for current_date in dates:
            lookback_start = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
            current_date_str = current_date.strftime("%Y-%m-%d")

            agent_output = self.agent(
                ticker=self.ticker,
                start_date=lookback_start,
                end_date=current_date_str,
                portfolio=self.portfolio
            )

            action, quantity = self.parse_action(agent_output)
            df = get_price_data(self.ticker, lookback_start, current_date_str)
            current_price = df.iloc[-1]['close']

            # Execute the trade with validation
            executed_quantity = self.execute_trade(action, quantity, current_price)

            # Update total portfolio value
            total_value = self.portfolio["cash"] + self.portfolio["stock"] * current_price
            self.portfolio["portfolio_value"] = total_value

            # Log the current state with executed quantity
            print(
                f"{current_date.strftime('%Y-%m-%d'):<12} {self.ticker:<6} {action:<6} {executed_quantity:>8} {current_price:>8.2f} "
                f"{self.portfolio['cash']:>12.2f} {self.portfolio['stock']:>8} {total_value:>12.2f}"
            )

            # Record the portfolio value
            self.portfolio_values.append(
                {"Date": current_date, "Portfolio Value": total_value}
            )

    def analyze_performance(self):
        # Convert portfolio values to DataFrame
        performance_df = pd.DataFrame(self.portfolio_values).set_index("Date")

        # Calculate total return
        total_return = (
                           self.portfolio["portfolio_value"] - self.initial_capital
                       ) / self.initial_capital
        print(f"Total Return: {total_return * 100:.2f}%")

        # Plot the portfolio value over time
        performance_df["Portfolio Value"].plot(
            title="Portfolio Value Over Time", figsize=(12, 6)
        )
        plt.ylabel("Portfolio Value ($)")
        plt.xlabel("Date")
        start_date = performance_df.index.min().strftime('%Y-%m-%d')
        end_date = performance_df.index.max().strftime('%Y-%m-%d')
        plt.savefig(f"{self.ticker}_{start_date}_to_{end_date}.png")


        # Compute daily returns
        performance_df["Daily Return"] = performance_df["Portfolio Value"].pct_change()

        # Calculate Sharpe Ratio (assuming 252 trading days in a year)
        mean_daily_return = performance_df["Daily Return"].mean()
        std_daily_return = performance_df["Daily Return"].std()
        sharpe_ratio = (mean_daily_return / std_daily_return) * (252 ** 0.5)
        print(f"Sharpe Ratio: {sharpe_ratio:.2f}")

        # Calculate Maximum Drawdown
        rolling_max = performance_df["Portfolio Value"].cummax()
        drawdown = performance_df["Portfolio Value"] / rolling_max - 1
        max_drawdown = drawdown.min()
        print(f"Maximum Drawdown: {max_drawdown * 100:.2f}%")

        return performance_df
    
### 4. Run the Backtest #####
if __name__ == "__main__":
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Run backtesting simulation')
    parser.add_argument('--ticker', type=str, default="AAPL", help='Stock ticker symbol (e.g., AAPL)')
    parser.add_argument('--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'), help='End date in YYYY-MM-DD format')
    parser.add_argument('--start_date', type=str, default=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), help='Start date in YYYY-MM-DD format')
    parser.add_argument('--initial_capital', type=float, default=100000, help='Initial capital amount (default: 100000)')

    args = parser.parse_args()

    import sqlite3

    # Connect to SQLite database
    conn = sqlite3.connect('backtest_performance.db')
    cursor = conn.cursor()

    # Create the main performance table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS performance (
            ticker TEXT,
            date TEXT,
            portfolio_value REAL,
            daily_return REAL,
            PRIMARY KEY (ticker, date)
        )
    ''')

    def add_column_if_not_exists(table_name, column_name, column_type):
        cursor.execute(f'''
            PRAGMA table_info({table_name});
        ''')
        columns = [row[1] for row in cursor.fetchall()]
        
        if column_name not in columns:
            cursor.execute(f'''
                ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};
            ''')

    # Add daily_return column if it doesn't exist
    add_column_if_not_exists('performance', 'daily_return', 'REAL')

    def backup_and_delete_historical_values(ticker):
        # Create backup table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_performance (
                ticker TEXT,
                date TEXT,
                portfolio_value REAL,
                daily_return REAL,
                PRIMARY KEY (ticker, date)
            )
        ''')
        
        # Insert records into backup table using parameter binding
        cursor.execute('''
            INSERT OR REPLACE INTO backup_performance 
            SELECT * FROM performance WHERE ticker = ?
        ''', (ticker,))
        
        # Delete old values from the performance table
        cursor.execute("DELETE FROM performance WHERE ticker = ?", (ticker,))
        conn.commit()

    # List of tickers to backtest
    tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "FB", "TSLA", "BRK.B", "NVDA", "JPM", "V", 
        "JNJ", "UNH", "PG", "HD", "MA", "DIS", "PYPL", "VZ", "NFLX", "INTC", 
        "CMCSA", "PEP", "T", "CSCO", "ADBE", "XOM", "NKE", "MRK", "CVX", "ABT", 
        "CRM", "TMO", "LLY", "IBM", "MDT", "COST", "AMGN", "QCOM", "TXN", "AVGO", 
        "HON", "LMT", "SBUX", "NOW", "ISRG", "PM", "BA", "CAT", "GS", "BLK", 
        "SCHW", "SPGI", "SYK", "DHR", "AMAT", "GILD", "LRCX", "ADP", "TROW", 
        "ATVI", "FISV", "FIS", "KMB", "CL", "NEM", "MS", "ZTS", "MDLZ", "SRE", 
        "CARR", "LNT", "DTE", "DOV", "ETR", "NDAQ", "WBA", "CNP", "WDC", "KMX", 
        "NTRS", "VTRS", "VFC"]

    for ticker in tickers:
        # Backup and delete historical values for the ticker
        backup_and_delete_historical_values(ticker)

        # Create an instance of Backtester
        backtester = Backtester(
            agent=run_hedge_fund,
            ticker=ticker,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
        )

        # Run the backtesting process
        backtester.run_backtest()
        performance_df = backtester.analyze_performance()

        # Save performance_df to the database
        performance_df.reset_index(inplace=True)
        performance_df['Ticker'] = ticker
        performance_df.rename(columns={
            'Date': 'date',
            'Portfolio Value': 'portfolio_value',
            'Daily Return': 'daily_return',
            'Ticker': 'ticker'
        }, inplace=True)
        performance_df.to_sql('performance', conn, if_exists='append', index=False)

    # Close the database connection
    conn.close()

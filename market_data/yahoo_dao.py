"""
YahooDAO

Data access object for fetching adjusted-close price series from Yahoo
Finance using RapidAPI (APIDojo). Provides a single function `fetch_adjusted_close` 
that returns a pandas DataFrame indexed by business-day dates.

Usage:
    from market_data.yahoo_dao import YahooDAO
    df = YahooDAO.fetch_adjusted_close(['XIU.TO','XWD.TO'], period='10y')

Notes:
- Requires RAPIDAPI_KEY and RAPIDAPI_HOST in environment.
- Uses local caching via `cache_path` to minimize API costs.
- Uses stock/v2/get-chart for reliable high-resolution daily data.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Iterable, Optional

import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
load_dotenv(".env.local")

logger = logging.getLogger(__name__)


class YahooDAO:
    @staticmethod
    def fetch_adjusted_close(
        tickers: Iterable[str],
        period: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1d",
        threads: bool = True,
        retry: int = 3,
        backoff_sec: float = 2.0,
        cache_path: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> pd.DataFrame:
        """Fetch adjusted close prices for `tickers` using RapidAPI (stock/v2/get-chart)."""
        
        tickers_list = list(tickers)
        api_key = os.getenv("RAPIDAPI_KEY")
        api_host = os.getenv("RAPIDAPI_HOST", "apidojo-yahoo-finance-v1.p.rapidapi.com")

        if not api_key:
            raise RuntimeError("RAPIDAPI_KEY not found in environment")

        # Configuration for time windows
        p1, p2 = None, None
        range_val = None

        if period:
            # Map standard periods or handle custom logic
            if period in ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd"]:
                range_val = period
            elif period == 'max':
                # For 'max', we want daily data. Yahoo's 'max' range often downsamples.
                # We'll use a 30-year window to force daily granularity if possible.
                end_dt = datetime.now()
                start_dt = end_dt.replace(year=end_dt.year - 30)
                p1 = int(start_dt.timestamp())
                p2 = int(end_dt.timestamp())
            else:
                # Custom period (e.g. '25y')
                end_dt = datetime.now()
                if period.endswith('y'):
                    years = int(period[:-1])
                    start_dt = end_dt.replace(year=end_dt.year - years)
                else:
                    start_dt = end_dt.replace(year=end_dt.year - 1)
                p1 = int(start_dt.timestamp())
                p2 = int(end_dt.timestamp())
        elif start:
            p1 = int(datetime.strptime(start, '%Y-%m-%d').timestamp())
            p2 = int(datetime.strptime(end, '%Y-%m-%d').timestamp()) if end else int(datetime.now().timestamp())
        else:
            range_val = "1y"

        # Cache check
        if cache_path and os.path.exists(cache_path):
            try:
                df_cached = pd.read_pickle(cache_path)
                if all(t in df_cached.columns for t in tickers_list):
                    last_date = df_cached.index.max()
                    # Return cache if it's less than 3 days old
                    if (datetime.now() - last_date).days < 3:
                        logger.info(f"Returning cached data from {cache_path}")
                        return df_cached[tickers_list].copy()
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")

        final_df = pd.DataFrame()
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": api_host
        }

        for ticker in tickers_list:
            attempt = 0
            success = False
            
            while attempt < retry:
                try:
                    # stock/v2/get-chart is the most reliable for non-downsampled data
                    url = f"https://{api_host}/stock/v2/get-chart"
                    params = {"symbol": ticker, "interval": interval}
                    if range_val:
                        params["range"] = range_val
                    else:
                        params["period1"] = str(p1)
                        params["period2"] = str(p2)
                    
                    response = requests.get(url, headers=headers, params=params, timeout=20)
                    response.raise_for_status()
                    data = response.json()
                    
                    # Parse Chart structure
                    chart_data = data.get("chart", {}).get("result", [])
                    if not chart_data:
                        raise ValueError(f"No chart result for {ticker}")
                    
                    result = chart_data[0]
                    timestamps = result.get("timestamp", [])
                    adjclose_list = result.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
                    
                    if not timestamps:
                        raise ValueError(f"No timestamps returned for {ticker}")
                    
                    # Some responses might have slightly different lengths for adjclose due to nulls
                    # but typically they match.
                    df_ticker = pd.DataFrame({
                        "date": pd.to_datetime(timestamps, unit='s'),
                        ticker: adjclose_list
                    })
                    df_ticker.set_index("date", inplace=True)
                    
                    if final_df.empty:
                        final_df = df_ticker
                    else:
                        # Join on index to align dates
                        final_df = final_df.join(df_ticker, how='outer')
                    
                    success = True
                    break
                except Exception as e:
                    attempt += 1
                    logger.error(f"Attempt {attempt} failed for {ticker}: {e}")
                    if attempt < retry:
                        time.sleep(backoff_sec * (2 ** (attempt - 1)))
            
            if not success:
                raise RuntimeError(f"Failed to fetch {ticker} after {retry} attempts")

        # Post-processing: sort, fill missing (holidays/different markets), drop all-NaN rows
        final_df = final_df.sort_index().ffill().dropna(how='all')

        # Cache the result
        if cache_path:
            try:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                final_df.to_pickle(cache_path)
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")

        return final_df[tickers_list]

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        # Quick test for a long period to verify daily resolution
        df = YahooDAO.fetch_adjusted_close(['XIU.TO'], period='10y')
        print(f"Fetched {len(df)} rows. Frequency check: {df.index[1] - df.index[0]}")
        print(df.tail())
    except Exception as e:
        print(f"Error: {e}")

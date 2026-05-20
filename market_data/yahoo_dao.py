"""
YahooDAO

Simple data access object for fetching adjusted-close price series from Yahoo
Finance using yfinance. Provides a single function `fetch_adjusted_close` that
returns a pandas DataFrame indexed by business-day dates and columns for each
requested ticker.

Usage:
    from market_data.yahoo_dao import YahooDAO
    df = YahooDAO.fetch_adjusted_close(['XIU.TO','XWD.TO'], period='10y')

Notes:
- No API key required (yfinance uses Yahoo public endpoints). The function will
  raise a RuntimeError on network or rate-limit failures.
- Optional local caching via `cache_path` parameter.
"""

from __future__ import annotations

from typing import Iterable, Optional
import logging
import os
import time

import pandas as pd
import yfinance as yf
import requests


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
        backoff_sec: float = 1.0,
        cache_path: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> pd.DataFrame:
        """Fetch adjusted close prices for `tickers`.

        Parameters
        - tickers: Iterable of ticker symbols (e.g. ['XIU.TO','XWD.TO']).
        - period: yfinance `period` string (e.g. '1y','5y','max'). If provided,
          `start`/`end` are ignored.
        - start/end: ISO date strings (YYYY-MM-DD).
        - interval: data interval (default '1d').
        - threads: whether to use multithreaded download.
        - retry: number of retry attempts on failure.
        - backoff_sec: initial backoff between retries (exponential).
        - cache_path: optional filepath to save/read cached DataFrame (pickle).
        - session: optional requests.Session to be used by yfinance download.

        Returns
        - pandas.DataFrame of adjusted close prices, forward-filled and with
          missing rows dropped.
        """
        tickers_list = list(tickers)

        # If a cache_path is provided and exists, try an incremental update.
        df_cached = None
        is_incremental = False
        if cache_path and os.path.exists(cache_path):
            try:
                df_cached = pd.read_pickle(cache_path)
            except Exception as exc:
                logger.warning("Failed to read cache at %s: %s", cache_path, exc)
                df_cached = None

        if df_cached is not None:
            # Only do incremental when the caller did not explicitly request a range.
            if all(t in df_cached.columns for t in tickers_list) and period is None and start is None and end is None:
                try:
                    last_saved = pd.to_datetime(df_cached.index.max()).tz_localize(None).normalize()
                except Exception:
                    last_saved = pd.Timestamp.min

                # Anchor to New York date to avoid timezone rollover issues on non-US hosts.
                today = pd.Timestamp.now(tz='America/New_York').tz_localize(None).normalize()

                if last_saved >= today:
                    return df_cached[tickers_list].copy()

                # Start from the next calendar day; let yfinance stream up to the present.
                start = (last_saved + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                end = None
                is_incremental = True
            else:
                df_cached = None

        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt < retry:
            try:
                # yfinance.download supports a `session` kw in newer versions; if
                # not supported it will be ignored by passing via kwargs.
                download_kwargs = dict(
                    tickers=tickers_list,
                    interval=interval,
                    threads=threads,
                    group_by='column',
                    auto_adjust=False,
                    progress=False,
                )
                if period:
                    download_kwargs['period'] = period
                else:
                    if start:
                        download_kwargs['start'] = start
                    if end:
                        download_kwargs['end'] = end

                # Provide a requests.Session to yfinance if available
                if session is not None:
                    download_kwargs['session'] = session

                raw = yf.download(**download_kwargs)

                if raw is None or raw.empty:
                    # Weekend / holiday fetch on an incremental path should not crash.
                    if is_incremental and df_cached is not None:
                        return df_cached[tickers_list].copy()
                    raise RuntimeError('yfinance returned empty DataFrame')

                # Extract Adjusted Close
                if isinstance(raw.columns, pd.MultiIndex):
                    if 'Adj Close' in raw.columns.get_level_values(0):
                        adj = raw['Adj Close']
                    else:
                        adj = raw.iloc[:, -len(tickers_list) :]
                else:
                    # single-level: may already be Adj Close
                    if 'Adj Close' in raw.columns:
                        adj = raw['Adj Close']
                    else:
                        # If download was called with single ticker, raw may be Series
                        adj = raw

                # Ensure DataFrame
                adj_df = pd.DataFrame(adj)

                # Align columns to requested tickers order
                missing_cols = [t for t in tickers_list if t not in adj_df.columns]
                if missing_cols:
                    # It's possible Yahoo returned different symbols; raise for clarity
                    raise RuntimeError(f'Missing tickers in response: {missing_cols}')

                # Fill forward, drop null rows
                adj_df = adj_df.sort_index()
                adj_df = adj_df.ffill().dropna(how='all')

                # Merge incremental results back into the cache when applicable.
                if is_incremental and df_cached is not None:
                    # If no new rows were returned, return cached
                    if adj_df.empty:
                        return df_cached[tickers_list].copy()

                    # Merge cached + new incremental data, preferring newly fetched rows
                    combined = pd.concat([df_cached, adj_df]).sort_index()
                    combined = combined[~combined.index.duplicated(keep='last')]
                    combined = combined.ffill().dropna(how='all')

                    # Cache merged DataFrame.
                    if cache_path:
                        try:
                            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                            combined.to_pickle(cache_path)
                        except Exception as exc:
                            logger.warning("Failed to write cache to %s: %s", cache_path, exc)

                    return combined[tickers_list].copy()

                # Otherwise cache the freshly fetched full series.
                if cache_path:
                    try:
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        adj_df.to_pickle(cache_path)
                    except Exception as exc:
                        logger.warning("Failed to write cache to %s: %s", cache_path, exc)

                return adj_df[tickers_list].copy()

            except Exception as exc:
                last_exc = exc
                attempt += 1
                if attempt >= retry:
                    break
                time.sleep(backoff_sec * (2 ** (attempt - 1)))

        raise RuntimeError(f'Failed to fetch prices from Yahoo after {retry} attempts') from last_exc


if __name__ == '__main__':
    # Quick CLI for manual testing
    import argparse

    parser = argparse.ArgumentParser(description='Fetch adjusted close prices via yfinance')
    parser.add_argument('tickers', nargs='+', help='Tickers to fetch')
    parser.add_argument('--period', default='10y')
    parser.add_argument('--cache', default=None, help='Optional pickle cache path')
    args = parser.parse_args()

    df = YahooDAO.fetch_adjusted_close(args.tickers, period=args.period, cache_path=args.cache)
    print(df.info())
    print(df.tail())

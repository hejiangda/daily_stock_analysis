# -*- coding: utf-8 -*-
"""
===================================
MyQuantFetcher - Professional Quantitative Data Provider (Priority 1)
===================================

Data Source: MyQuant (掘金量化) - https://www.myquant.cn
Features: Professional-grade quantitative data for Chinese A-shares
Requirements: MyQuant Token (MYQUANT_TOKEN environment variable)

Rate Limiting:
- Free tier: ~120 requests/minute (configurable)
- Implements per-minute call counter
- Uses tenacity for exponential backoff retry

Stock Code Format:
- Input: '600519', '000001' (standard 6-digit codes)
- Output: 'SHSE.600519', 'SZSE.000001' (MyQuant format)
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS
from .realtime_types import UnifiedRealtimeQuote, RealtimeSource, safe_float, safe_int
from src.config import get_config

logger = logging.getLogger(__name__)


class MyQuantFetcher(BaseFetcher):
    """
    MyQuant (掘金量化) Data Provider Implementation

    Data Source: https://www.myquant.cn
    SDK Documentation: https://www.myquant.cn/docs2/sdk/python/

    Features:
    - Professional-grade quantitative data
    - Requires token authentication
    - Supports A-shares, ETFs, indices

    Priority: Dynamic (1 if token configured, 99 otherwise)
    """

    name = "MyQuantFetcher"
    priority = int(os.getenv("MYQUANT_PRIORITY", "99"))  # Default to unavailable

    def __init__(self, rate_limit_per_minute: int = 120):
        """
        Initialize MyQuantFetcher

        Args:
            rate_limit_per_minute: Rate limit (default 120 for standard accounts)
        """
        self.rate_limit_per_minute = rate_limit_per_minute
        self._call_count = 0  # Call counter for current minute
        self._minute_start: Optional[float] = None  # Start time of current minute
        self._api = None  # MyQuant API instance
        self._token = None

        # Initialize API
        self._init_api()

        # Adjust priority based on configuration
        self.priority = self._determine_priority()

    def _init_api(self) -> None:
        """
        Initialize MyQuant SDK and set token

        If Token is not configured, this data source will be unavailable
        """
        config = get_config()
        self._token = getattr(config, 'myquant_token', None) or os.getenv('MYQUANT_TOKEN')

        if not self._token:
            logger.warning("MyQuant Token not configured, this data source will be unavailable")
            return

        try:
            from gm import api as gm_api

            # Set authentication token
            gm_api.set_token(self._token)
            self._api = gm_api
            logger.info("MyQuant API initialized successfully")

        except ImportError:
            logger.error("MyQuant SDK not installed. Run: pip install gm")
        except Exception as e:
            logger.error(f"MyQuant API initialization failed: {e}")

    def _determine_priority(self) -> int:
        """
        Determine priority based on token availability

        Priority logic:
        - If token configured and API valid: priority 1 (high)
        - If token not configured: priority 99 (disabled)

        Returns:
            Priority number (0=highest, larger number = lower priority)
        """
        if self._token and self._api is not None:
            return int(os.getenv("MYQUANT_PRIORITY", "1"))
        return 99

    def is_available(self) -> bool:
        """
        Check if MyQuant data source is available

        Returns:
            True if available, False otherwise
        """
        return self._api is not None

    def _check_rate_limit(self) -> None:
        """
        Check and enforce rate limits

        Rate limiting strategy:
        1. Check if we entered a new minute
        2. If so, reset the counter
        3. If current minute call count exceeds limit, force sleep
        """
        current_time = time.time()

        # Check if we need to reset the counter (new minute)
        if self._minute_start is None:
            self._minute_start = current_time
            self._call_count = 0
        elif current_time - self._minute_start >= 60:
            # A minute has passed, reset counter
            self._minute_start = current_time
            self._call_count = 0
            logger.debug("Rate limit counter reset")

        # Check if we exceeded the quota
        if self._call_count >= self.rate_limit_per_minute:
            # Calculate wait time (until next minute)
            elapsed = current_time - self._minute_start
            sleep_time = max(0, 60 - elapsed) + 1  # +1 second buffer

            logger.warning(
                f"MyQuant rate limit reached ({self._call_count}/{self.rate_limit_per_minute} calls/min), "
                f"sleeping {sleep_time:.1f}s..."
            )

            time.sleep(sleep_time)

            # Reset counter
            self._minute_start = time.time()
            self._call_count = 0

        # Increment call count
        self._call_count += 1
        logger.debug(f"MyQuant current minute call count: {self._call_count}/{self.rate_limit_per_minute}")

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        Convert standard stock code to MyQuant format

        MyQuant format: SHSE.600519, SZSE.000001

        Args:
            stock_code: Original code, e.g., '600519', '000001'

        Returns:
            MyQuant format code, e.g., 'SHSE.600519', 'SZSE.000001'
        """
        code = stock_code.strip().upper()

        # Already in MyQuant format
        if '.' in code:
            return code

        # Shanghai stocks: 600xxx, 601xxx, 603xxx, 688xxx (STAR Market)
        if code.startswith(('600', '601', '603', '688')):
            return f"SHSE.{code}"

        # Shenzhen stocks: 000xxx, 001xxx, 002xxx, 300xxx (ChiNext)
        if code.startswith(('000', '001', '002', '300')):
            return f"SZSE.{code}"

        # ETF codes
        # Shanghai ETF: 51xxxx, 52xxxx, 56xxxx, 58xxxx
        if code.startswith(('51', '52', '56', '58')) and len(code) == 6:
            return f"SHSE.{code}"

        # Shenzhen ETF: 15xxxx, 16xxxx, 18xxxx
        if code.startswith(('15', '16', '18')) and len(code) == 6:
            return f"SZSE.{code}"

        # Default to Shenzhen
        logger.warning(f"Cannot determine exchange for {code}, defaulting to SZSE")
        return f"SZSE.{code}"

    def _reverse_code(self, myquant_code: str) -> str:
        """
        Convert MyQuant code back to standard format

        Args:
            myquant_code: MyQuant format code, e.g., 'SHSE.600519'

        Returns:
            Standard code, e.g., '600519'
        """
        if '.' in myquant_code:
            return myquant_code.split('.')[1]
        return myquant_code

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, RateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch historical data from MyQuant

        Args:
            stock_code: Stock code, e.g., '600519'
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'

        Returns:
            Raw DataFrame from MyQuant API

        Raises:
            DataFetchError: If API call fails
            RateLimitError: If rate limit is exceeded
        """
        if self._api is None:
            raise DataFetchError("MyQuant API not initialized, check token configuration")

        # Check rate limit before API call
        self._check_rate_limit()

        # Convert to MyQuant format
        symbol = self._convert_stock_code(stock_code)

        # Convert date format to datetime
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        try:
            # Call MyQuant API
            # history() returns historical bar data
            df = self._api.history(
                symbol=symbol,
                start_time=start_dt,
                end_time=end_dt,
                frequency='1d',
                fields='eob,open,high,low,close,volume,amount',
                adjust=1,
                df=True,
            )

            if df is None or df.empty:
                raise DataFetchError(f"No data returned for {stock_code}")

            return df

        except Exception as e:
            error_msg = str(e).lower()
            if 'rate' in error_msg or 'limit' in error_msg or 'frequency' in error_msg:
                raise RateLimitError(f"MyQuant rate limit: {e}")
            raise DataFetchError(f"MyQuant fetch failed: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        Normalize MyQuant data to standard format

        MyQuant columns -> Standard columns:
        eob -> date
        open, high, low, close -> same
        volume -> volume
        amount -> amount

        Args:
            df: Raw DataFrame from MyQuant
            stock_code: Stock code for reference

        Returns:
            Normalized DataFrame with standard columns
        """
        df = df.copy()

        # Column mapping (MyQuant uses 'eob' as end-of-bar timestamp)
        column_mapping = {
            'eob': 'date',
            'bob': 'date',  # Fallback: begin-of-bar
        }
        df = df.rename(columns=column_mapping)

        # Ensure date format
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

        # Calculate pct_chg if not present
        if 'pct_chg' not in df.columns and 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100

        # Add stock code
        df['code'] = stock_code

        # Select standard columns (only those that exist)
        keep_cols = ['code'] + [col for col in STANDARD_COLUMNS if col in df.columns]
        df = df[keep_cols]

        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        Get real-time quote from MyQuant

        Args:
            stock_code: Stock code, e.g., '600519'

        Returns:
            UnifiedRealtimeQuote if successful, None otherwise
        """
        if self._api is None:
            return None

        try:
            self._check_rate_limit()

            # Convert to MyQuant format
            symbol = self._convert_stock_code(stock_code)

            # Get real-time quotes
            quotes = self._api.get_realtime_quotes(symbols=symbol)

            if not quotes or len(quotes) == 0:
                return None

            quote = quotes[0] if isinstance(quotes, list) else quotes

            # Parse quote data
            return UnifiedRealtimeQuote(
                code=stock_code,
                name=getattr(quote, 'symbol', None) or stock_code,
                price=safe_float(getattr(quote, 'price', None)),
                change_amount=safe_float(getattr(quote, 'change', None)),
                change_pct=safe_float(getattr(quote, 'change_pct', None)),
                open_price=safe_float(getattr(quote, 'open', None)),
                high=safe_float(getattr(quote, 'high', None)),
                low=safe_float(getattr(quote, 'low', None)),
                pre_close=safe_float(getattr(quote, 'pre_close', None)),
                volume=safe_int(getattr(quote, 'volume', None)),
                amount=safe_float(getattr(quote, 'amount', None)),
                source=RealtimeSource.MYQUANT,
            )

        except Exception as e:
            logger.warning(f"MyQuant get_realtime_quote failed for {stock_code}: {e}")
            return None

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        Get stock name from MyQuant

        Args:
            stock_code: Stock code, e.g., '600519'

        Returns:
            Stock name if successful, None otherwise
        """
        if self._api is None:
            return None

        try:
            self._check_rate_limit()

            # Convert to MyQuant format
            symbol = self._convert_stock_code(stock_code)

            # Get instrument info
            instruments = self._api.get_instruments(
                symbols=symbol,
                fields='symbol,sec_name',
                df=True,
            )

            if instruments is not None and not instruments.empty:
                return instruments.iloc[0].get('sec_name', None)

            return None

        except Exception as e:
            logger.warning(f"MyQuant get_stock_name failed for {stock_code}: {e}")
            return None

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        Get all stocks list from MyQuant

        Returns:
            DataFrame with columns: code, name, exchange
        """
        if self._api is None:
            return None

        try:
            self._check_rate_limit()

            # Get all instruments from SHSE and SZSE
            instruments = self._api.get_instruments(
                exchanges='SHSE,SZSE',
                sec_types='stock',
                fields='symbol,sec_name,exchange',
                df=True,
            )

            if instruments is None or instruments.empty:
                return None

            # Normalize to standard format
            df = instruments.copy()
            df = df.rename(columns={
                'symbol': 'code',
                'sec_name': 'name',
            })

            # Convert code format: SHSE.600519 -> 600519
            df['code'] = df['code'].apply(self._reverse_code)

            return df[['code', 'name', 'exchange']]

        except Exception as e:
            logger.warning(f"MyQuant get_stock_list failed: {e}")
            return None

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        Get main index data from MyQuant

        Args:
            region: Market region ('cn' for China A-shares)

        Returns:
            List of index data dictionaries
        """
        if self._api is None:
            return None

        if region != "cn":
            return None

        try:
            self._check_rate_limit()

            # Main A-share indices in MyQuant format
            indices = [
                ("SHSE.000001", "上证指数"),
                ("SZSE.399001", "深证成指"),
                ("SZSE.399006", "创业板指"),
                ("SHSE.000016", "上证50"),
                ("SHSE.000300", "沪深300"),
                ("SHSE.000905", "中证500"),
                ("SHSE.000852", "中证1000"),
            ]

            result = []
            for symbol, name in indices:
                try:
                    quotes = self._api.get_realtime_quotes(symbols=symbol)
                    if quotes and len(quotes) > 0:
                        quote = quotes[0] if isinstance(quotes, list) else quotes
                        result.append({
                            'code': self._reverse_code(symbol),
                            'name': name,
                            'current': safe_float(getattr(quote, 'price', None)),
                            'change': safe_float(getattr(quote, 'change', None)),
                            'change_pct': safe_float(getattr(quote, 'change_pct', None)),
                            'volume': safe_int(getattr(quote, 'volume', None)),
                            'amount': safe_float(getattr(quote, 'amount', None)),
                        })
                except Exception as e:
                    logger.debug(f"Failed to get index {symbol}: {e}")
                    continue

            return result if result else None

        except Exception as e:
            logger.warning(f"MyQuant get_main_indices failed: {e}")
            return None
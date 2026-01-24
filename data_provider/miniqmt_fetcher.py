# -*- coding: utf-8 -*-
"""
===================================
MiniQMT 数据源 (Priority -2)
===================================

数据来源：迅投 MiniQMT（通过 xtquant 库）
特点：量化交易专用、本地行情数据、支持实时和历史行情
文档：https://dict.thinktrader.net/nativeApi/

权限说明：
- 需要安装 MiniQMT 客户端
- 需要启动 MiniQMT 客户端并连接行情服务器
- 提供本地缓存的历史数据和实时行情
- 支持A股等市场

优先级：-2（高优先级，需要 MiniQMT 客户端）

使用说明：
1. 下载并安装 MiniQMT：https://www.thinktrader.net/
2. 启动 MiniQMT 客户端并连接行情服务器
3. 安装 xtquant 库：pip install xtquant
4. 可选：在 .env 中配置 MINIQMT_PATH 指定客户端路径
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS

logger = logging.getLogger(__name__)


class MiniQMTFetcher(BaseFetcher):
    """
    MiniQMT 数据获取器
    
    特点：
    - 量化交易专用平台
    - 本地缓存历史数据，速度快
    - 支持实时行情订阅
    - 支持分笔交易数据
    - 需要启动 MiniQMT 客户端
    """
    
    name = "MiniQMTFetcher"
    priority = -2  # 高优先级（需要 MiniQMT 客户端）
    
    def __init__(self):
        """初始化 MiniQMT 数据源"""
        super().__init__()
        
        # 尝试导入 xtquant 模块
        try:
            from xtquant import xtdata
            self.xtdata = xtdata
            logger.info("MiniQMT (xtquant) 模块导入成功")
        except ImportError as e:
            logger.error(f"xtquant 库未安装，请执行: pip install xtquant")
            raise DataFetchError("MiniQMT (xtquant) 库未安装") from e
        
        # 检查 MiniQMT 客户端路径（可选配置）
        self.client_path = os.getenv('MINIQMT_PATH')
        if self.client_path:
            logger.info(f"MiniQMT 客户端路径: {self.client_path}")
        
        # 连接状态
        self._connected = False
        self._connect()
        
        # 缓存股票代码映射
        self.code_map = {}
    
    def _connect(self) -> bool:
        """
        连接 MiniQMT 行情服务器
        
        注意：xtdata 会自动连接，但我们需要确保客户端已启动
        """
        try:
            # 测试连接：尝试获取股票列表
            # 如果 MiniQMT 未启动，这里会抛出异常
            stock_list = self.xtdata.get_stock_list_in_sector('A股')
            
            if stock_list is not None and len(stock_list) > 0:
                self._connected = True
                logger.info(f"MiniQMT 连接成功，A股市场股票数量: {len(stock_list)}")
                return True
            else:
                logger.warning("MiniQMT 连接异常：获取股票列表为空")
                return False
                
        except Exception as e:
            logger.warning(f"MiniQMT 连接失败: {e}")
            logger.warning("请确保：1) MiniQMT 客户端已启动 2) 已连接行情服务器")
            self._connected = False
            return False
    
    def _ensure_connection(self) -> None:
        """确保已连接到 MiniQMT"""
        if not self._connected:
            if not self._connect():
                raise DataFetchError(
                    "MiniQMT 未连接，请检查：\n"
                    "1. MiniQMT 客户端是否已启动\n"
                    "2. 是否已连接行情服务器\n"
                    "3. 网络连接是否正常"
                )
    
    def _convert_to_minipmt_code(self, stock_code: str) -> str:
        """
        转换股票代码为 MiniQMT 格式
        
        MiniQMT 格式：市场.代码
        - 上海：SH.600519
        - 深圳：SZ.000001
        - 北京：BJ.430047
        
        Args:
            stock_code: 6位股票代码，如 '600519'
            
        Returns:
            MiniQMT 格式代码，如 'SH.600519'
        """
        # 如果已经是 MiniQMT 格式，直接返回
        if '.' in stock_code and stock_code.split('.')[0] in ['SH', 'SZ', 'BJ']:
            return stock_code.upper()
        
        # 根据代码首位判断市场
        if stock_code.startswith('6'):
            return f'SH.{stock_code}'  # 上海证券交易所
        elif stock_code.startswith(('0', '3')):
            return f'SZ.{stock_code}'  # 深圳证券交易所
        elif stock_code.startswith('8') or stock_code.startswith('4'):
            return f'BJ.{stock_code}'  # 北京证券交易所
        else:
            logger.warning(f"无法识别股票代码市场: {stock_code}，默认使用深圳格式")
            return f'SZ.{stock_code}'
    
    def _convert_to_standard_code(self, minipmt_code: str) -> str:
        """
        将 MiniQMT 格式代码转换为标准6位代码
        
        Args:
            minipmt_code: MiniQMT 格式代码，如 'SH.600519'
            
        Returns:
            标准6位代码，如 '600519'
        """
        # 如果已经是标准格式，直接返回
        if '.' not in minipmt_code:
            return minipmt_code
        
        # 提取代码部分
        return minipmt_code.split('.')[-1]
    
    def _download_history_data(
        self,
        stock_code: str,
        period: str = '1d',
        start_time: str = None
    ) -> bool:
        """
        下载历史数据到本地
        
        MiniQMT 的数据是本地缓存的，首次使用需要下载
        
        Args:
            stock_code: 6位股票代码
            period: 周期（1d/1m等）
            start_time: 开始时间 'YYYYMMDD'，None 表示下载所有
            
        Returns:
            是否成功
        """
        try:
            minipmt_code = self._convert_to_minipmt_code(stock_code)
            
            logger.info(f"MiniQMT: 下载 {minipmt_code} 历史数据...")
            
            # 调用下载接口
            self.xtdata.download_history_data(
                stock_code=minipmt_code,
                period=period,
                start_time=start_time,
                incrementally=True  # 增量下载，只下载新数据
            )
            
            # 等待下载完成
            time.sleep(0.5)
            
            logger.info(f"MiniQMT: {minipmt_code} 历史数据下载完成")
            return True
            
        except Exception as e:
            logger.warning(f"MiniQMT 下载历史数据失败: {e}")
            return False
    
    def _fetch_raw_data(
        self,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        从 MiniQMT 获取原始数据
        
        Args:
            stock_code: 股票代码（6位）
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            
        Returns:
            原始数据 DataFrame
        """
        # 确保已连接
        self._ensure_connection()
        
        # 转换为 MiniQMT 格式
        minipmt_code = self._convert_to_minipmt_code(stock_code)
        logger.info(f"MiniQMT: 请求 {minipmt_code} 数据 [{start_date} ~ {end_date}]")
        
        # 下载历史数据（首次使用）
        start_time = start_date.replace('-', '')
        self._download_history_data(stock_code, '1d', start_time)
        
        try:
            # 获取本地数据
            # get_market_data_ex 可以获取所有字段（field_list=[]）
            # count=-1 表示获取所有可用数据
            df = self.xtdata.get_market_data_ex(
                field_list=[],
                stock_list=[minipmt_code],
                period='1d',
                count=-1,
                start_time=start_date.replace('-', ''),
                end_time=end_date.replace('-', ''),
                dividend_type='front'  # 前复权
            )
            
            # MiniQMT 返回的是多层索引 DataFrame
            # 第一层是股票代码，第二层是字段名
            if df is None or df.empty:
                raise DataFetchError(f"MiniQMT 返回空数据: {minipmt_code}")
            
            # 提取单只股票的数据（去掉第一层索引）
            if minipmt_code in df.columns.levels[0]:
                stock_df = df[minipmt_code]
            else:
                raise DataFetchError(f"MiniQMT 数据中未找到: {minipmt_code}")
            
            logger.info(f"MiniQMT: 成功获取 {len(stock_df)} 条数据")
            return stock_df
            
        except Exception as e:
            logger.error(f"MiniQMT 获取数据失败: {e}")
            raise DataFetchError(f"MiniQMT API 调用失败: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 MiniQMT 数据格式
        
        MiniQMT 返回的字段：
        - time: 时间（可能是日期或日期时间）
        - open: 开盘价
        - high: 最高价
        - low: 最低价
        - close: 收盘价
        - volume: 成交量
        - amount: 成交额
        - pcpChg: 涨跌幅（%）
        
        标准列名：
        - date: 日期
        - open, high, low, close: OHLC价格
        - volume: 成交量（股）
        - amount: 成交额（元）
        - pct_chg: 涨跌幅（%）
        """
        if df.empty:
            return df
        
        # 创建标准化副本
        normalized = pd.DataFrame()
        
        # MiniQMT 列名映射
        column_mapping = {
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount',
            'pcpChg': 'pct_chg',  # MiniQMT 使用 pcpChg 表示涨跌幅
        }
        
        # 复制列
        for src_col, dst_col in column_mapping.items():
            if src_col in df.columns:
                normalized[dst_col] = df[src_col]
        
        # 处理日期列
        if 'time' in df.columns:
            # time 可能是 datetime 或 date 类型
            normalized['date'] = pd.to_datetime(df['time']).dt.date
        elif df.index.name == 'time' or 'time' in str(df.index.name):
            normalized['date'] = pd.to_datetime(df.index).dt.date
        else:
            logger.warning(f"未找到日期列，使用索引: {df.index.name}")
            normalized['date'] = pd.to_datetime(df.index).date
        
        # 如果没有涨跌幅数据，尝试计算
        if 'pct_chg' not in normalized.columns and 'close' in normalized.columns:
            # 计算涨跌幅: (今日收盘 - 昨日收盘) / 昨日收盘 * 100
            normalized['pct_chg'] = normalized['close'].pct_change() * 100
        
        # 确保涨跌幅为数值类型
        if 'pct_chg' in normalized.columns:
            normalized['pct_chg'] = pd.to_numeric(normalized['pct_chg'], errors='coerce')
        
        # 确保标准列存在
        for col in STANDARD_COLUMNS:
            if col not in normalized.columns:
                if col == 'volume':
                    normalized[col] = 0
                elif col == 'amount':
                    normalized[col] = 0.0
                elif col == 'pct_chg':
                    normalized[col] = 0.0
                else:
                    normalized[col] = None
        
        # 按标准列顺序排列
        result = normalized[STANDARD_COLUMNS].copy()
        
        # 按日期升序排序
        result = result.sort_values('date').reset_index(drop=True)
        
        # 移除重复日期
        result = result.drop_duplicates(subset=['date'], keep='last')
        
        logger.info(f"MiniQMT: 标准化后数据 {len(result)} 条")
        return result
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((DataFetchError, RateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_daily_data(self, stock_code: str, days: int = 30) -> tuple[pd.DataFrame, str]:
        """
        获取日线数据
        
        Args:
            stock_code: 股票代码（6位）
            days: 获取天数
            
        Returns:
            (DataFrame, source_name)
        """
        try:
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 30)
            
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            # 获取原始数据
            df = self._fetch_raw_data(stock_code, start_str, end_str)
            
            # 标准化数据
            normalized_df = self._normalize_data(df, stock_code)
            
            # 计算技术指标
            result_df = self._calculate_indicators(normalized_df)
            
            # 截取最近 days 天
            result_df = result_df.tail(days).reset_index(drop=True)
            
            return result_df, self.name
            
        except Exception as e:
            logger.error(f"MiniQMT 获取 {stock_code} 数据失败: {e}")
            raise DataFetchError(f"MiniQMT 数据获取失败: {e}") from e
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情（tick 数据）
        
        Args:
            stock_code: 股票代码（6位）
            
        Returns:
            实时行情字典
        """
        try:
            self._ensure_connection()
            
            minipmt_code = self._convert_to_minipmt_code(stock_code)
            
            # 获取全推 tick 数据
            tick_data = self.xtdata.get_full_tick([minipmt_code])
            
            if tick_data and minipmt_code in tick_data:
                return tick_data[minipmt_code]
            
            return None
            
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return None
    
    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        获取股票名称
        
        Args:
            stock_code: 股票代码（6位）
            
        Returns:
            股票名称
        """
        try:
            self._ensure_connection()
            
            minipmt_code = self._convert_to_minipmt_code(stock_code)
            
            # 获取合约详细信息
            info = self.xtdata.get_instrument_detail(minipmt_code)
            
            if info and 'InstrumentName' in info:
                return info['InstrumentName']
            
            return None
            
        except Exception as e:
            logger.warning(f"获取股票名称失败: {e}")
            return None


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    # 测试 MiniQMT 数据源
    try:
        fetcher = MiniQMTFetcher()
        
        # 测试获取数据
        df = fetcher.get_daily_data('600519', days=30)
        print(f"\n获取数据成功，共 {len(df)} 条")
        print(df.tail())
        
        # 测试股票名称
        name = fetcher.get_stock_name('600519')
        if name:
            print(f"\n股票名称: {name}")
        
        # 测试实时行情
        quote = fetcher.get_realtime_quote('600519')
        if quote:
            print(f"\n实时行情: {quote}")
        
    except Exception as e:
        print(f"测试失败: {e}")

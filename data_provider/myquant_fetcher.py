# -*- coding: utf-8 -*-
"""
===================================
掘金量化数据源 (Priority -1)
===================================

数据来源：掘金量化平台（通过 gm.api 库）
特点：专业量化平台、数据质量高、支持实时和历史行情
文档：https://www.myquant.cn/docs2/sdk/python/

权限说明：
- 需要掘金账号和 Token
- 提供实时行情和历史K线数据
- 支持A股、港股、美股等市场
- 支持Level2高级行情

优先级：-1（最高优先级，需要配置 MYQUANT_TOKEN）

使用说明：
1. 注册掘金账号获取 Token：https://www.myquant.cn/
2. 安装 gm 库：pip install gm
3. 在 .env 中配置：MYQUANT_TOKEN=your_token_id
"""

import logging
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


class MyQuantFetcher(BaseFetcher):
    """
    掘金量化数据获取器
    
    特点：
    - 专业量化数据平台
    - 数据质量高、更新及时
    - 支持复权数据
    - 支持 Level2 高级行情（需要权限）
    """
    
    name = "MyQuantFetcher"
    priority = -1  # 最高优先级（需要 Token）
    
    def __init__(self):
        """初始化掘金量化数据源"""
        super().__init__()
        
        # 尝试导入 gm 模块
        try:
            from gm.api import (
                set_token,
                history,
                get_instrumentinfo,
                ADJUST_NONE,
                ADJUST_PREV,
                ADJUST_POST,
            )
            self.gm = {
                'set_token': set_token,
                'history': history,
                'get_instrumentinfo': get_instrumentinfo,
                'ADJUST_NONE': ADJUST_NONE,
                'ADJUST_PREV': ADJUST_PREV,
                'ADJUST_POST': ADJUST_POST,
            }
            logger.info("掘金量化模块导入成功")
        except ImportError as e:
            logger.error(f"gm 库未安装，请执行: pip install gm")
            raise DataFetchError("掘金量化库未安装") from e
        
        # 从环境变量获取 Token
        import os
        self.token = os.getenv('MYQUANT_TOKEN')
        
        if not self.token:
            raise DataFetchError("未配置 MYQUANT_TOKEN，请在 .env 中设置")
        
        # 初始化 Token
        try:
            self.gm['set_token'](self.token)
            logger.info(f"掘金量化 Token 已设置: {self.token[:8]}...")
        except Exception as e:
            logger.error(f"掘金量化 Token 设置失败: {e}")
            raise DataFetchError(f"掘金量化 Token 无效: {e}") from e
        
        # 股票代码映射表（6位代码 → 掘金格式）
        self.code_map = {}
    
    def _convert_to_myquant_code(self, stock_code: str) -> str:
        """
        转换股票代码为掘金格式
        
        Args:
            stock_code: 6位股票代码，如 '600519'
            
        Returns:
            掘金格式代码，如 'SHSE.600519'
        """
        # 如果已经是掘金格式，直接返回
        if '.' in stock_code:
            return stock_code.upper()
        
        # 根据代码首位判断市场
        if stock_code.startswith('6'):
            return f'SHSE.{stock_code}'  # 上海证券交易所
        elif stock_code.startswith(('0', '3')):
            return f'SZSE.{stock_code}'  # 深圳证券交易所
        elif stock_code.startswith('8') or stock_code.startswith('4'):
            return f'BJSE.{stock_code}'  # 北京证券交易所
        else:
            logger.warning(f"无法识别股票代码市场: {stock_code}，默认使用深圳格式")
            return f'SZSE.{stock_code}'
    
    def _convert_to_standard_code(self, myquant_code: str) -> str:
        """
        将掘金格式代码转换为标准6位代码
        
        Args:
            myquant_code: 掘金格式代码，如 'SHSE.600519'
            
        Returns:
            标准6位代码，如 '600519'
        """
        # 如果已经是标准格式，直接返回
        if '.' not in myquant_code:
            return myquant_code
        
        # 提取代码部分
        return myquant_code.split('.')[-1]
    
    def _fetch_raw_data(
        self,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        从掘金量化获取原始数据
        
        Args:
            stock_code: 股票代码（6位）
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            
        Returns:
            原始数据 DataFrame
        """
        # 转换为掘金格式
        myquant_code = self._convert_to_myquant_code(stock_code)
        logger.info(f"掘金量化: 请求 {myquant_code} 数据 [{start_date} ~ {end_date}]")
        
        try:
            # 调用掘金 history 接口
            df = self.gm['history'](
                symbol=myquant_code,
                frequency='1d',
                start_time=f'{start_date} 09:00:00',
                end_time=f'{end_date} 16:00:00',
                fields='open,high,low,close,volume,amount,pct_chg',
                adjust=self.gm['ADJUST_PREV'],  # 前复权
                df=True
            )
            
            if df is None or df.empty:
                raise DataFetchError(f"掘金量化返回空数据: {myquant_code}")
            
            logger.info(f"掘金量化: 成功获取 {len(df)} 条数据")
            return df
            
        except Exception as e:
            logger.error(f"掘金量化获取数据失败: {e}")
            raise DataFetchError(f"掘金量化 API 调用失败: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化掘金量化数据格式
        
        掘金量化返回的列名：
        - symbol: 标的代码
        - eob: End of Bar (K线结束时间)
        - open, high, low, close: OHLC价格
        - volume: 成交量（手）
        - amount: 成交额
        - pct_chg: 涨跌幅（%）
        
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
        
        # 掘金量化列名映射
        column_mapping = {
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount',
            'pct_chg': 'pct_chg',
        }
        
        # 复制列
        for src_col, dst_col in column_mapping.items():
            if src_col in df.columns:
                normalized[dst_col] = df[src_col]
        
        # 处理日期列（掘金使用 eob 字段）
        if 'eob' in df.columns:
            # eob 是 datetime 类型，转换为 date
            normalized['date'] = pd.to_datetime(df['eob']).dt.date
        elif 'datetime' in df.columns:
            normalized['date'] = pd.to_datetime(df['datetime']).dt.date
        else:
            # 如果没有日期列，使用索引
            logger.warning(f"未找到日期列，使用索引: {df.index.name}")
            normalized['date'] = pd.to_datetime(df.index).date
        
        # 掘金量单位是手，转换为股（1手=100股）
        if 'volume' in normalized.columns:
            normalized['volume'] = normalized['volume'] * 100
        
        # 确保涨跌幅为数值类型
        if 'pct_chg' in normalized.columns:
            normalized['pct_chg'] = pd.to_numeric(normalized['pct_chg'], errors='coerce')
        
        # 选择标准列，按顺序排列
        result = normalized[STANDARD_COLUMNS].copy()
        
        # 按日期升序排序
        result = result.sort_values('date').reset_index(drop=True)
        
        # 移除重复日期
        result = result.drop_duplicates(subset=['date'], keep='last')
        
        logger.info(f"掘金量化: 标准化后数据 {len(result)} 条")
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
            start_date = end_date - timedelta(days=days + 30)  # 多获取一些天，过滤非交易日
            
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
            logger.error(f"掘金量化获取 {stock_code} 数据失败: {e}")
            raise DataFetchError(f"掘金量化数据获取失败: {e}") from e
    
    def get_instrument_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取合约详细信息
        
        Args:
            stock_code: 股票代码（6位）
            
        Returns:
            合约信息字典
        """
        try:
            myquant_code = self._convert_to_myquant_code(stock_code)
            
            # 调用掘金接口
            info = self.gm['get_instrumentinfo'](symbol=myquant_code)
            
            if info and len(info) > 0:
                return info[0]
            
            return None
            
        except Exception as e:
            logger.error(f"获取合约信息失败: {e}")
            return None


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    # 测试掘金量化数据源
    try:
        fetcher = MyQuantFetcher()
        
        # 测试获取数据
        df = fetcher.get_daily_data('600519', days=30)
        print(f"\n获取数据成功，共 {len(df)} 条")
        print(df.tail())
        
        # 测试合约信息
        info = fetcher.get_instrument_info('600519')
        if info:
            print(f"\n合约信息: {info}")
        
    except Exception as e:
        print(f"测试失败: {e}")

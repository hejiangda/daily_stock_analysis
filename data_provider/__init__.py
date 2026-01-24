# -*- coding: utf-8 -*-
"""
===================================
数据源策略层 - 包初始化
===================================

本包实现策略模式管理多个数据源，实现：
1. 统一的数据获取接口
2. 自动故障切换
3. 防封禁流控策略

数据源优先级（按优先级数字排序，数字越小越优先）：

【专业量化平台（需要配置）】
- MyQuantFetcher (Priority -1) - 掘金量化，需 MYQUANT_TOKEN
- MiniQMTFetcher (Priority -2) - MiniQMT 客户端，需启动客户端

【免费数据源】
- EfinanceFetcher (Priority 0) - 东方财富（efinance 库）
- TushareFetcher (Priority 0) - Tushare Pro，需 TUSHARE_TOKEN
- AkshareFetcher (Priority 1) - 东方财富（akshare 库）
- BaostockFetcher (Priority 3) - 证券宝（baostock 库）
- YfinanceFetcher (Priority 4) - Yahoo Finance（yfinance 库）

优先级说明：
1. 优先级数字越小越优先
2. 同优先级按初始化顺序排列
3. 负数优先级表示需要特殊配置/客户端的数据源
"""

from .base import BaseFetcher, DataFetcherManager
from .myquant_fetcher import MyQuantFetcher
from .miniqmt_fetcher import MiniQMTFetcher
from .efinance_fetcher import EfinanceFetcher
from .akshare_fetcher import AkshareFetcher
from .tushare_fetcher import TushareFetcher
from .baostock_fetcher import BaostockFetcher
from .yfinance_fetcher import YfinanceFetcher

__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'MyQuantFetcher',
    'MiniQMTFetcher',
    'EfinanceFetcher',
    'AkshareFetcher',
    'TushareFetcher',
    'BaostockFetcher',
    'YfinanceFetcher',
]

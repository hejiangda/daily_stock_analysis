# CODEBUDDY.md This file provides guidance to CodeBuddy when working with code in this repository.

## 项目概述

这是一个基于 AI 大模型的 A/H 股自选股智能分析系统，每日自动分析股票并推送决策仪表盘到企业微信、飞书、Telegram、邮箱等渠道。

核心特性：
- AI 决策仪表盘：一句话核心结论 + 精确买卖点位 + 检查清单
- 多维度分析：技术面 + 筹码分布 + 舆情情报 + 实时行情
- 零成本部署：支持 GitHub Actions 免费运行
- 多数据源：AkShare、Tushare、Baostock、YFinance
- 多 AI 模型：Google Gemini（主力）、OpenAI 兼容 API（DeepSeek、通义千问等）

## 常用命令

### 运行和测试
```bash
# 正常运行（执行完整分析）
python main.py

# 调试模式（输出详细日志）
python main.py --debug

# 仅获取数据，不进行 AI 分析（用于数据验证）
python main.py --dry-run

# 分析指定股票（覆盖配置）
python main.py --stocks 600519,000001

# 不发送推送通知
python main.py --no-notify

# 单股推送模式（每分析完一只立即推送）
python main.py --single-notify

# 仅运行大盘复盘分析
python main.py --market-review

# 启用定时任务模式
python main.py --schedule

# 启动 WebUI（配置管理界面）
python main.py --webui

# 仅启动 WebUI 服务（通过 API 手动触发分析）
python main.py --webui-only
```

### 环境验证测试
```bash
# 运行所有基础测试
python test_env.py

# 仅测试配置加载
python test_env.py --config

# 查看数据库内容
python test_env.py --db

# 测试数据获取
python test_env.py --fetch

# 测试 LLM 调用
python test_env.py --llm

# 测试通知推送
python test_env.py --notify

# 查询指定股票数据
python test_env.py --stock 600519

# 运行所有测试（包括 LLM）
python test_env.py --all
```

### 代码质量检查
```bash
# 语法检查
python -m py_compile main.py config.py analyzer.py notification.py storage.py scheduler.py search_service.py market_analyzer.py stock_analyzer.py
python -m py_compile data_provider/*.py

# 使用 flake8 进行静态分析（仅检查严重错误）
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# 模块导入测试
python -c "from config import get_config; print('config OK')"
python -c "from storage import DatabaseManager; print('storage OK')"
python -c "from notification import NotificationService; print('notification OK')"
python -c "from data_provider import DataFetcherManager; print('data_provider OK')"
python -c "from analyzer import GeminiAnalyzer; print('analyzer OK')"
```

### Docker 部署
```bash
# 构建镜像
docker build -t stock-analysis .

# 运行容器
docker run -d \
  -e STOCK_LIST=600519,000001 \
  -e GEMINI_API_KEY=your_key \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -p 8000:8000 \
  stock-analysis

# 使用 docker-compose
docker-compose up -d
```

### WebUI 相关
```bash
# 启动 WebUI 服务（端口 8000）
python main.py --webui-only

# 使用环境变量配置 WebUI
WEBUI_HOST=0.0.0.0 WEBUI_PORT=8000 python main.py --webui-only

# WebUI API 接口：
# GET  /              - 配置管理页面
# GET  /health        - 健康检查
# GET  /analysis?code=xxx - 触发单只股票异步分析
# GET  /tasks         - 查询所有任务状态
# GET  /task?id=xxx   - 查询单个任务状态
```

## 高层架构

### 核心设计理念

1. **低并发防封禁**：默认使用 3 个并发线程（`max_workers=3`），并在数据源请求间添加随机延时（2-5 秒），避免触发反爬机制。

2. **多数据源降级策略**：DataFetcherManager 管理多个数据源适配器（Efinance、Akshare、Tushare、Baostock、YFinance），按优先级顺序尝试，确保数据获取成功率。

3. **断点续传机制**：数据库会记录每只股票的每日数据，重复运行时跳过已获取的数据，提高效率。

4. **模块化分层架构**：
   - **配置层**（`config.py`）：单例模式管理全局配置，从环境变量和 `.env` 文件加载
   - **数据层**（`data_provider/`）：多个数据源适配器，统一接口获取行情数据
   - **存储层**（`storage.py`）：SQLAlchemy ORM 管理 SQLite 数据库，支持智能更新
   - **分析层**（`analyzer.py`, `stock_analyzer.py`）：AI 分析器和技术指标计算
   - **搜索层**（`search_service.py`）：支持 Tavily、Bocha、SerpAPI 多搜索引擎
   - **通知层**（`notification.py`）：多渠道推送（企业微信、飞书、Telegram、邮件等）
   - **Web 层**（`web/`）：FastAPI 服务器提供配置管理界面
   - **调度层**（`main.py`, `scheduler.py`）：主流程协调和定时任务

### 主流程（StockAnalysisPipeline）

`main.py` 中的 `StockAnalysisPipeline` 类是整个系统的核心调度器，协调各模块完成分析流程：

1. **数据获取阶段**：调用 `DataFetcherManager.get_daily_data()` 从多数据源获取历史行情数据，并保存到数据库（`storage.py`）。

2. **增强数据阶段**：
   - 获取实时行情（量比、换手率、PE/PB 等）
   - 获取筹码分布数据
   - 进行趋势分析（基于 MA5/MA10/MA20 多头判断、乖离率、量能等）
   - 多维度情报搜索（最新消息、风险排查、业绩预期）

3. **AI 分析阶段**：调用 `GeminiAnalyzer.analyze()` 将技术面、实时行情、筹码、趋势分析、新闻情报等上下文发送给 AI 模型，生成决策仪表盘格式的分析报告。

4. **通知推送阶段**：
   - 单股推送模式（`SINGLE_STOCK_NOTIFY=true`）：每分析完一只股票立即推送
   - 汇总推送模式（默认）：所有股票分析完成后，生成决策仪表盘日报统一推送
   - 支持多渠道同时推送（企业微信、飞书、Telegram、邮件等）

5. **大盘复盘**：`MarketAnalyzer` 负责大盘复盘分析，包括主要指数、板块表现、北向资金等，可单独运行或与个股分析一起执行。

6. **飞书文档生成**：如果配置了飞书应用凭证，系统会自动生成飞书云文档，包含大盘复盘和个股决策仪表盘。

### 关键模块说明

**配置管理（config.py）**
- 使用单例模式确保全局只有一个配置实例
- 从系统环境变量和项目根目录的 `.env` 文件加载配置
- 支持热读取 `STOCK_LIST`（`refresh_stock_list()` 方法）
- 提供配置验证方法（`validate()`）

**数据源管理（data_provider/）**
- `DataFetcherManager`：统一管理多个数据源，按优先级顺序尝试
- `EfinanceFetcher`：最高优先级，使用东方财富数据
- `AkshareFetcher`：主要数据源，获取实时行情和筹码分布
- `TushareFetcher`、`BaostockFetcher`、`YfinanceFetcher`：备用数据源
- 所有 fetcher 继承自 `BaseFetcher`，实现统一接口

**AI 分析（analyzer.py）**
- `GeminiAnalyzer`：封装 Gemini API 调用，支持主模型和备选模型降级
- `AnalysisResult`：数据类，包含决策仪表盘、技术分析、基本面、消息面等完整分析结果
- 使用 tenacity 库实现重试机制（指数退避）
- 支持自定义 Prompt 生成决策仪表盘格式

**趋势分析（stock_analyzer.py）**
- `StockTrendAnalyzer`：基于交易理念的技术分析器
- 判断多头排列（MA5 > MA10 > MA20）
- 计算乖离率、量能变化
- 生成买入信号、评分和风险因素

**搜索服务（search_service.py）**
- `SearchService`：统一的新闻搜索接口
- 支持 Tavily、Bocha、SerpAPI 多个搜索引擎
- 多 Key 负载均衡和故障转移
- 提供 `search_comprehensive_intel()` 方法进行多维度情报搜索

**通知服务（notification.py）**
- `NotificationService`：多渠道推送
- 自动识别通知渠道（企业微信、飞书、Telegram、邮件、Pushover、自定义 Webhook）
- 支持长消息分批发送（飞书 20KB、企业微信 4KB 限制）
- 生成决策仪表盘格式的报告

**Web 界面（web/）**
- FastAPI 服务器提供配置管理界面
- `/`：查看和修改配置
- `/analysis?code=xxx`：触发单只股票异步分析
- `/tasks`：查询所有任务状态

### 交易理念内置

系统内置了特定的交易理念，在 `stock_analyzer.py` 和 `analyzer.py` 的 Prompt 中体现：

- **严进策略**：乖离率 > 5% 自动标记「危险」，严禁追高
- **趋势交易**：只做 MA5 > MA10 > MA20 多头排列
- **精确点位**：买入价、止损价、目标价
- **检查清单**：每项条件用 ✅⚠️❌ 标记

### 日志系统

日志输出到三个地方：
1. 控制台：根据 `--debug` 参数控制级别
2. 常规日志：`logs/stock_analysis_YYYYMMDD.log`（INFO 级别，10MB 轮转）
3. 调试日志：`logs/stock_analysis_debug_YYYYMMDD.log`（DEBUG 级别，50MB 轮转）

### 数据库

使用 SQLite 数据库（`data/stock_analysis.db`），通过 SQLAlchemy ORM 管理：

- `StockDaily` 表：存储每日行情数据和技术指标（OHLC、MA、量比等）
- 唯一约束：`(code, date)` 确保同一股票同一日期只有一条数据
- 支持断点续传：`has_today_data()` 方法检查今日数据是否已存在

### GitHub Actions

支持免费自动化运行：
- 定时触发：每个工作日北京时间 18:00（UTC 10:00）
- 手动触发：通过 Actions 页面手动运行，支持选择模式（完整分析/仅大盘/仅股票）
- 环境变量：通过 Secrets 和 Variables 管理敏感配置
- CI 流程：自动进行语法检查、静态分析、Docker 构建测试

### 开发注意事项

1. **添加新数据源**：在 `data_provider/` 下创建新的 fetcher 类，继承 `BaseFetcher`，实现 `get_daily_data()` 方法，并在 `DataFetcherManager` 中注册。

2. **添加新通知渠道**：在 `notification.py` 中的 `NotificationChannel` 枚举添加新类型，在 `NotificationService` 中实现对应的 `send_to_xxx()` 方法。

3. **修改 AI Prompt**：编辑 `analyzer.py` 中的 Prompt 模板，确保遵循决策仪表盘格式（操作建议、点位、检查清单）。

4. **流量控制**：修改 `config.py` 中的 `max_workers`、`akshare_sleep_min/max`、`gemini_request_delay` 等参数调整请求频率。

5. **WebUI 开发**：在 `web/` 包中修改 `handlers.py`、`services.py`、`templates.py` 添加新功能。

6. **测试新功能**：使用 `test_env.py` 验证配置、数据库、数据获取、LLM 调用、通知推送是否正常。

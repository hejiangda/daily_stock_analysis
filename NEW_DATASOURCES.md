# 掘金量化和 MiniQMT 数据源集成说明

## 📋 修改概述

本次修改为 A股智能分析系统添加了两个专业量化平台数据源：

1. **掘金量化** - 专业量化数据平台
2. **MiniQMT** - 迅投量化交易客户端

## 📁 新增文件

### 1. 数据源实现

- **`data_provider/myquant_fetcher.py`** - 掘金量化数据获取器
  - 优先级：-1（最高优先级之一）
  - 需要：`MYQUANT_TOKEN` 环境变量
  - 特点：API 调用、数据质量高、支持复权

- **`data_provider/miniqmt_fetcher.py`** - MiniQMT 数据获取器
  - 优先级：-2（最高优先级）
  - 需要：MiniQMT 客户端启动
  - 特点：本地缓存、速度快、支持实时行情

### 2. 文档

- **`docs/myquant_minipmt_guide.md`** - 完整使用指南
  - 注册和配置步骤
  - 验证和测试方法
  - 故障排查
  - 性能对比

- **`test_data_sources.py`** - 数据源测试脚本
  - 独立测试掘金量化
  - 独立测试 MiniQMT
  - 测试所有数据源

## 🔧 修改文件

### 1. `data_provider/__init__.py`

**修改内容**：
- 导入新的数据源类
- 更新数据源优先级说明
- 添加到 `__all__` 导出列表

### 2. `data_provider/base.py`

**修改内容**：
- `_init_default_fetchers()` 方法中：
  - 添加掘金量化初始化逻辑（检测 `MYQUANT_TOKEN`）
  - 添加 MiniQMT 初始化逻辑（尝试连接客户端）
  - 更新优先级说明文档

### 3. `requirements.txt`

**修改内容**：
- 添加 `gm>=0.17.0`（掘金量化 SDK）
- 添加 `xtquant>=1.1.0`（MiniQMT SDK）
- 更新数据源优先级注释

### 4. `README.md`

**修改内容**：
- 更新"数据来源"章节
- 添加专业数据源说明
- 添加使用指南链接

## 📊 数据源优先级

修改后的数据源优先级顺序：

| 优先级 | 数据源 | 类型 | 依赖说明 |
|--------|--------|------|----------|
| -2 | **MiniQMT** | 客户端 | 需要启动客户端 |
| -1 | **掘金量化** | 平台 | 需要 Token |
| 0 | Efinance | 免费 | 无需配置 |
| 0 | Tushare | 免费 | 需要 Token |
| 1 | Akshare | 免费 | 无需配置 |
| 3 | Baostock | 免费 | 无需配置 |
| 4 | Yfinance | 免费 | 无需配置 |

## 🚀 使用方法

### 方式一：配置后自动使用

1. **配置掘金量化**（推荐）
```env
# .env 文件
MYQUANT_TOKEN=your_token_id_here
```

2. **配置 MiniQMT**（可选）
```env
# .env 文件（可选，通常不需要）
MINIQMT_PATH=C:\path\to\minipmt
```

3. **启动 MiniQMT 客户端**（如果使用 MiniQMT）

4. **正常运行**
```bash
python main.py
```

程序会自动按优先级选择可用的数据源。

### 方式二：测试数据源

```bash
# 测试掘金量化
python test_data_sources.py --test myquant

# 测试 MiniQMT
python test_data_sources.py --test minipmt

# 测试所有
python test_data_sources.py --test all
```

### 方式三：单独测试

```bash
# 测试掘金量化
python data_provider/myquant_fetcher.py

# 测试 MiniQMT
python data_provider/miniqmt_fetcher.py
```

## 📖 详细文档

- [掘金量化和 MiniQMT 使用指南](docs/myquant_minipmt_guide.md)
- [掘金量化官方文档](https://www.myquant.cn/docs2/sdk/python/)
- [MiniQMT 官方文档](https://dict.thinktrader.net/nativeApi/)

## 🔑 配置示例

### 示例 1：使用掘金量化

```env
# 掘金量化配置
MYQUANT_TOKEN=abcdef123456...

# 自选股
STOCK_LIST=600519,000001,300750

# AI 配置
GEMINI_API_KEY=your_gemini_key

# 通知配置
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
```

### 示例 2：同时使用两个数据源

```env
# 掘金量化配置
MYQUANT_TOKEN=abcdef123456...

# MiniQMT 配置（可选）
MINIQMT_PATH=C:\Users\YourName\AppData\Local\MiniQMT

# 自选股
STOCK_LIST=600519,000001,300750

# AI 配置
GEMINI_API_KEY=your_gemini_key

# 通知配置
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
```

## ⚙️ 系统行为

### 数据源选择逻辑

1. 程序启动时，`DataFetcherManager` 会初始化所有可用的数据源
2. 按优先级排序（数字越小越优先）
3. 每次获取数据时，从最高优先级开始尝试
4. 如果失败，自动切换到下一个数据源
5. 记录每个数据源的使用情况

### 日志输出示例

```
[INFO] 已初始化 7 个数据源（按优先级）: MiniQMTFetcher(P-2), MyQuantFetcher(P-1), EfinanceFetcher(P0), TushareFetcher(P0), AkshareFetcher(P1), BaostockFetcher(P3), YfinanceFetcher(P4)
[INFO] 尝试使用 [MiniQMTFetcher] 获取 600519...
[INFO] MiniQMT: 请求 SH.600519 数据 [2025-01-23 ~ 2025-02-22]
[INFO] MiniQMT: 成功获取 30 条数据
[INFO] [MiniQMTFetcher] 600519 获取成功，共 30 条数据
```

## ✅ 验证清单

- [x] 创建掘金量化数据源 (`myquant_fetcher.py`)
- [x] 创建 MiniQMT 数据源 (`miniqmt_fetcher.py`)
- [x] 更新数据源管理器 (`base.py`)
- [x] 更新包初始化 (`__init__.py`)
- [x] 更新依赖列表 (`requirements.txt`)
- [x] 创建使用指南 (`docs/myquant_minipmt_guide.md`)
- [x] 创建测试脚本 (`test_data_sources.py`)
- [x] 更新 README.md
- [x] 检查 lint 错误

## 🐛 已知问题

### 掘金量化
- 需要 Token，免费账号有频率限制
- 网络环境可能影响 API 调用

### MiniQMT
- 必须启动客户端才能使用
- 首次使用需要下载历史数据（自动）
- 仅支持本地运行，不适合云端部署

## 💡 最佳实践

1. **推荐配置**：掘金量化作为主数据源，Efinance/Akshare 作为备用
2. **本地开发**：使用 MiniQMT 获得最快速度
3. **云端部署**：使用掘金量化或 Tushare（需要 Token）
4. **多数据源**：配置多个数据源提高可靠性

## 📞 支持

如有问题，请：

1. 查看 [使用指南](docs/myquant_minipmt_guide.md)
2. 运行测试脚本诊断：`python test_data_sources.py --test all`
3. 查看日志文件了解详细错误信息
4. 在 GitHub 提交 Issue

## 🎯 下一步

可选的扩展功能：

1. **掘金量化**：添加 Level2 高级行情支持
2. **MiniQMT**：添加实时行情订阅功能
3. **数据源监控**：添加数据源健康检查
4. **性能优化**：实现数据缓存策略

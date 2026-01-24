# 掘金量化和 MiniQMT 数据源使用指南

## 概述

本系统已集成掘金量化（MyQuant）和 MiniQMT 两个专业量化平台的数据源，提供更高质量、更稳定的股票数据。

### 数据源优先级

| 数据源 | 优先级 | 类型 | 依赖说明 |
|--------|--------|------|----------|
| **掘金量化** | -1 | 专业平台 | 需要注册账号获取 Token |
| **MiniQMT** | -2 | 客户端 | 需要安装并启动客户端 |
| Efinance | 0 | 免费 | 无需配置 |
| Akshare | 1 | 免费 | 无需配置 |
| Tushare | 2 | 免费 | 需要配置 Token |
| Baostock | 3 | 免费 | 无需配置 |
| Yfinance | 4 | 免费 | 无需配置 |

> 优先级数字越小越优先。负数优先级表示需要特殊配置/客户端的专业数据源。

---

## 一、掘金量化（MyQuant）

### 1.1 注册和获取 Token

1. 访问掘金量化官网：https://www.myquant.cn/
2. 注册账号并登录
3. 进入【我的账号】→【Token管理】
4. 创建新的 Token，复制 Token ID

### 1.2 安装依赖

```bash
pip install gm
```

### 1.3 配置 Token

在项目根目录的 `.env` 文件中添加：

```env
MYQUANT_TOKEN=your_token_id_here
```

### 1.4 验证配置

```bash
# 测试掘金量化数据源
python data_provider/myquant_fetcher.py
```

如果看到类似输出，说明配置成功：
```
掘金量化 Token 已设置: abc12345...
掘金量化: 请求 SHSE.600519 数据 [2025-01-23 ~ 2025-02-22]
掘金量化: 成功获取 30 条数据
掘金量化: 标准化后数据 30 条
获取数据成功，共 30 条
```

### 1.5 特点

✅ **优点**
- 数据质量高、更新及时
- 支持复权数据（前复权/后复权）
- 支持 A股、港股、美股等市场
- API 稳定，响应速度快

⚠️ **注意事项**
- 需要注册账号和 Token
- 免费账号有请求频率限制
- 适合高频调用场景

---

## 二、MiniQMT

### 2.1 下载和安装客户端

1. 访问迅投官网：https://www.thinktrader.net/
2. 下载 MiniQMT 客户端（投研端或券商定制端）
3. 安装并启动客户端
4. 确保客户端已连接行情服务器

### 2.2 安装依赖

```bash
pip install xtquant
```

### 2.3 配置路径（可选）

如果你的 MiniQMT 客户端安装在非默认路径，在 `.env` 中指定：

```env
MINIQMT_PATH=C:\Users\YourName\AppData\Local\MiniQMT
```

> 默认情况下，xtquant 会自动检测客户端路径，通常无需配置。

### 2.4 验证配置

```bash
# 测试 MiniQMT 数据源
python data_provider/miniqmt_fetcher.py
```

如果看到类似输出，说明配置成功：
```
MiniQMT (xtquant) 模块导入成功
MiniQMT 连接成功，A股市场股票数量: 5000+
MiniQMT: 下载 SH.600519 历史数据...
MiniQMT: SH.600519 历史数据下载完成
MiniQMT: 请求 SH.600519 数据 [2025-01-23 ~ 2025-02-22]
MiniQMT: 成功获取 30 条数据
```

### 2.5 特点

✅ **优点**
- 本地缓存历史数据，速度快
- 支持实时行情订阅
- 支持分笔交易数据
- 无需 Token，使用客户端权限

⚠️ **注意事项**
- 需要启动客户端才能使用
- 首次使用需要下载历史数据
- 适合本地运行环境

---

## 三、同时使用两个数据源

### 3.1 配置示例

在 `.env` 文件中同时配置两个数据源：

```env
# 掘金量化配置
MYQUANT_TOKEN=your_token_id_here

# MiniQMT 配置（可选）
MINIQMT_PATH=C:\path\to\minipmt

# 自选股列表
STOCK_LIST=600519,000001,300750

# 其他配置...
GEMINI_API_KEY=your_gemini_key
```

### 3.2 数据源优先级

程序会按以下优先级尝试数据源：

1. **掘金量化**（-1）- 需要配置 `MYQUANT_TOKEN`
2. **MiniQMT**（-2）- 需要启动客户端
3. **Efinance**（0）- 免费，无需配置
4. **Akshare**（1）- 免费，无需配置
5. **Tushare**（2）- 需要配置 `TUSHARE_TOKEN`
6. **Baostock**（3）- 免费，无需配置
7. **Yfinance**（4）- 免费，无需配置

如果高优先级数据源失败，会自动切换到下一个数据源。

---

## 四、使用示例

### 4.1 基本使用

```bash
# 正常运行（会自动使用最高优先级的可用数据源）
python main.py

# 查看使用了哪个数据源
# 日志中会显示："[MyQuantFetcher] 获取 600519 数据"
```

### 4.2 仅使用特定数据源

如果你想测试某个数据源，可以修改 `main.py` 中的 `DataFetcherManager` 初始化：

```python
from data_provider import MyQuantFetcher, MiniQMTFetcher

# 仅使用掘金量化
manager = DataFetcherManager(fetchers=[MyQuantFetcher()])

# 仅使用 MiniQMT
manager = DataFetcherManager(fetchers=[MiniQMTFetcher()])

# 组合使用（掘金优先，MiniQMT 备用）
manager = DataFetcherManager(fetchers=[
    MyQuantFetcher(),
    MiniQMTFetcher()
])
```

### 4.3 WebUI 使用

```bash
# 启动 WebUI（会自动使用配置的数据源）
python main.py --webui-only

# 访问 http://127.0.0.1:8000
# 在分析页面输入股票代码，系统会自动选择最佳数据源
```

---

## 五、故障排查

### 5.1 掘金量化常见问题

**问题：`gm 库未安装`**
```bash
# 解决方案
pip install gm
```

**问题：`掘金量化 Token 无效`**
- 检查 Token 是否正确复制
- 确保 Token 未过期
- 在掘金官网重新生成 Token

**问题：`掘金量化 API 调用失败`**
- 检查网络连接
- 确认 Token 有请求额度
- 查看具体错误信息

### 5.2 MiniQMT 常见问题

**问题：`xtquant 库未安装`**
```bash
# 解决方案
pip install xtquant
```

**问题：`MiniQMT 连接失败`**
- 确保 MiniQMT 客户端已启动
- 确保客户端已连接行情服务器
- 检查客户端版本是否支持 xtquant

**问题：`MiniQMT 数据为空`**
- 首次使用需要下载历史数据（系统会自动下载）
- 检查股票代码是否正确
- 确认客户端行情数据已更新

---

## 六、性能对比

### 6.1 响应速度

| 数据源 | 历史数据 | 实时数据 | 说明 |
|--------|----------|----------|------|
| **掘金量化** | 快 | 快 | 云端数据，API 响应快 |
| **MiniQMT** | 极快 | 快 | 本地缓存，首次下载后极快 |
| Efinance/Akshare | 中 | 中 | 爬虫接口，速度一般 |
| Tushare | 快 | 快 | 付费 API，速度快 |
| Baostock | 慢 | 慢 | 接口较慢 |

### 6.2 数据质量

| 数据源 | 数据完整性 | 复权支持 | 实时性 |
|--------|------------|----------|--------|
| **掘金量化** | ⭐⭐⭐⭐⭐ | ✅ 支持 | ⭐⭐⭐⭐⭐ |
| **MiniQMT** | ⭐⭐⭐⭐⭐ | ✅ 支持 | ⭐⭐⭐⭐⭐ |
| Efinance/Akshare | ⭐⭐⭐⭐ | ❌ 不支持 | ⭐⭐⭐⭐ |
| Tushare | ⭐⭐⭐⭐⭐ | ✅ 支持 | ⭐⭐⭐⭐⭐ |
| Baostock | ⭐⭐⭐ | ✅ 支持 | ⭐⭐⭐ |

---

## 七、进阶使用

### 7.1 掘金量化高级功能

掘金量化还提供以下功能（可自行扩展）：

```python
from gm.api import *

# Level2 高级行情（需要权限）
l2_data = history(
    symbol='SHSE.600519',
    frequency='l2transaction',
    start_time='2025-01-01 09:00:00',
    end_time='2025-01-23 16:00:00',
    df=True
)

# 实时订阅
subscribe(symbols='SHSE.600519', frequency='1d')
```

### 7.2 MiniQMT 高级功能

MiniQMT 支持更丰富的数据类型：

```python
from xtquant import xtdata

# 分笔交易数据
tick_data = xtdata.get_market_data(
    field_list=['lastPrice', 'volume'],
    stock_list=['600519.SH'],
    period='tick',
    count=100
)

# 订阅实时行情
def on_quote(data):
    print(data)

xtdata.subscribe_quote(
    '600519.SH',
    period='1d',
    callback=on_quote
)
```

---

## 八、总结和建议

### 推荐方案

**场景 1：个人使用，追求稳定性**
- 使用 **掘金量化** + **MiniQMT** 双数据源
- 掘金作为主数据源，MiniQMT 作为备用

**场景 2：本地运行，追求速度**
- 使用 **MiniQMT** 作为主数据源
- 历史数据本地缓存，响应极快

**场景 3：云端部署**
- 使用 **掘金量化** 或 **Tushare**（有 Token）
- 不需要安装客户端

**场景 4：测试和开发**
- 使用 **Efinance** 或 **Akshare**
- 无需配置，开箱即用

### 最佳实践

1. **多数据源配置**：同时配置多个数据源，提高可靠性
2. **定期更新**：保持客户端和 SDK 版本最新
3. **监控日志**：关注数据源切换和错误日志
4. **Token 管理**：妥善保管 Token，不要提交到 Git

---

## 九、相关文档

- [掘金量化官方文档](https://www.myquant.cn/docs2/sdk/python/)
- [MiniQMT 官方文档](https://dict.thinktrader.net/nativeApi/)
- [项目 README](../README.md)
- [CODEBUDDY.md](../CODEBUDDY.md)
- [执行流程分析](../FLOW_ANALYSIS.md)

---

## 十、技术支持

如有问题，请：

1. 查看本文档的【故障排查】章节
2. 查看官方文档链接
3. 在 GitHub 提交 Issue：https://github.com/ZhuLinsen/daily_stock_analysis/issues

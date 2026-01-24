# 掘金量化和 MiniQMT 快速参考

## 🚀 快速开始

### 掘金量化

```bash
# 1. 安装依赖
pip install gm

# 2. 配置 Token（在 .env 文件中）
MYQUANT_TOKEN=your_token_id

# 3. 测试
python data_provider/myquant_fetcher.py
```

### MiniQMT

```bash
# 1. 安装依赖
pip install xtquant

# 2. 启动客户端
# 运行 MiniQMT 客户端并连接行情服务器

# 3. 测试
python data_provider/miniqmt_fetcher.py
```

## 📋 配置文件示例

```env
# .env

# 掘金量化
MYQUANT_TOKEN=your_token_id_here

# MiniQMT（可选）
MINIQMT_PATH=C:\path\to\minipmt

# 自选股
STOCK_LIST=600519,000001,300750

# AI 配置
GEMINI_API_KEY=your_gemini_key

# 通知配置
WECHAT_WEBHOOK_URL=https://...
```

## 🧪 测试命令

```bash
# 测试掘金量化
python test_data_sources.py --test myquant

# 测试 MiniQMT
python test_data_sources.py --test minipmt

# 测试所有
python test_data_sources.py --test all
```

## 📊 数据源优先级

```
MiniQMT (P-2) → 掘金量化 (P-1) → Efinance (P0) → Akshare (P1) → ...
```

程序会自动选择最高优先级的可用数据源。

## 🔑 常用命令

```bash
# 正常运行（自动选择最佳数据源）
python main.py

# 指定分析股票
python main.py --stocks 600519,000001

# 调试模式
python main.py --debug

# WebUI
python main.py --webui-only
```

## 📖 文档链接

- [完整使用指南](myquant_minipmt_guide.md)
- [掘金量化官方文档](https://www.myquant.cn/docs2/sdk/python/)
- [MiniQMT 官方文档](https://dict.thinktrader.net/nativeApi/)

## 🐛 故障排查

### 掘金量化

| 问题 | 解决方案 |
|------|----------|
| `gm 库未安装` | `pip install gm` |
| `Token 无效` | 检查 Token 是否正确 |
| `API 调用失败` | 检查网络和 Token 额度 |

### MiniQMT

| 问题 | 解决方案 |
|------|----------|
| `xtquant 库未安装` | `pip install xtquant` |
| `连接失败` | 启动 MiniQMT 客户端 |
| `数据为空` | 等待历史数据下载 |

## 💡 最佳实践

1. **同时配置两个数据源**（掘金量化 + MiniQMT）提高可靠性
2. **定期运行测试**确保数据源正常工作
3. **监控日志**了解数据源使用情况
4. **妥善保管 Token**不要提交到 Git

## 📞 获取帮助

- 查看完整指南：[myquant_minipmt_guide.md](myquant_minipmt_guide.md)
- 运行测试：`python test_data_sources.py --test all`
- 查看 README.md 了解系统整体使用

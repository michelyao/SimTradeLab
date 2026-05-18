# 涨停封单衰减卖出策略 设计文档

## 1. 需求概述

监控当前账户所有持股，当股票涨停后，如果卖一的封单量小于5000手，主动以涨停价笼子低限价格卖出，在开板前提前逃顶。

## 2. API 数据字典

| 接口 | 用途 | 返回值说明 |
|------|------|-----------|
| `context.portfolio.positions` | 获取所有持仓 | dict[stock_code → Position]，`.amount` 为持仓数量(股) |
| `get_position(stock)` | 获取单只持仓 | Position 对象，支持 `.amount`/`.enable_amount`(可用股数) |
| `check_limit(stock)` | 涨跌停判断 | `{stock: status}`，status: `2`=触板涨停, `1`=涨停, `0`=正常, `-1`=跌停, `-2`=触板跌停 |
| `get_snapshot(stock)` | 行情快照 | `{stock: {up_px, last_px, offer_grp, bid_grp, ...}}` |
| `offer_grp[1]` | 卖一档 | `[价格, 委托量(股), 委托笔数]` |
| `order(stock, -qty, limit_price=price)` | 限价卖出 | 返回 Order ID，负数=卖出 |
| `run_interval(context, func, seconds=1)` | 每秒轮询 | 仅交易模式可用 |
| `is_trade()` | 模式判断 | True=交易模式, False=回测模式 |

## 3. 核心逻辑

### 3.1 价格笼子规则

沪深主板、创业板价格笼子（连续竞价阶段）：
- 卖出申报价格 ≥ 基准价 × 98%

本策略的卖出价格 = `up_px × 0.98`（涨停价 × 98%，其中基准价取涨停价），再 `round(..., 2)` 对齐最小变动价位。

### 3.2 封单量换算

需求中"5000首" = 5000手。PTrade 的 `offer_grp[1][1]` 委托量单位为**股**。
所以阈值 = `5000 × 100 = 500,000股`，作为可配置参数 `g.sell_threshold`。

### 3.3 涨停状态判断

`check_limit(stock)` 返回 `1`(涨停) 或 `2`(触板涨停，还有卖盘) 均视为涨停状态，进入封单检查流程。

## 4. 策略架构

```
george_limit_up_sell.py
├── initialize()
│   ├── 读取所有持仓 → g.holdings[]
│   ├── set_universe(g.holdings)  设置股票池
│   ├── run_interval(interval_handle, 1s)  交易模式秒级监控
│   └── if not is_trade: set_backtest()  回测兼容
│
├── before_trading_start()
│   ├── g.sold_stocks = []  重置已卖列表
│   └── refresh_holdings()  刷新持仓
│
├── interval_handle()  ← 核心轮询
│   └── for stock in g.holdings:
│       ├── stock in g.sold_stocks? → skip
│       ├── check_limit(stock) in [1,2]? → no: skip
│       │   └── yes → get_snapshot(stock)
│       │       ├── offer_grp[1][1] < g.sell_threshold? → no: skip
│       │       │   └── yes → order(stock, -sell_qty, limit_price=sell_price)
│       │       │       ├── success → log + g.sold_stocks.append(stock)
│       │       │       └── fail → log.error
│       │       └── exception → log.error  (per-stock try/except)
│
├── handle_data()  ← 回测兼容
│   └── → interval_handle()
│
└── set_backtest()
    ├── set_limit_mode("UNLIMITED")
    └── set_commission(0.00015, 5.0)
```

## 5. 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 运行模式 | run_interval(1秒) + handle_data | 封单变化快需要秒级监控；handle_data 兼容回测 |
| 获取持仓 | `context.portfolio.positions` | 回测/交易都可用 |
| 涨停判断 | `check_limit in [1,2]` | 1=涨停, 2=触板涨停，两者均表示股票已涨停 |
| 卖一封单 | `offer_grp[1][1]` 与 `5000*100` 比较 | 单位是股 |
| 卖出价格 | `round(up_px × 0.98, 2)` | 价格笼子底限公式 |
| 防重复卖出 | `g.sold_stocks` 列表 | 当日已卖出的股票不再处理 |
| 每日刷新 | `before_trading_start` 重置 | 新交易日重新开始监控 |
| 错误处理 | 每只股票独立 try/except | 单只异常不影响其他持仓 |
| 卖出量计算 | `(enable_amount // 100) * 100` | 取整到100股，不足100跳过 |

## 6. 风控保护

1. **数量合规**：卖出数量 = `(可用持仓 // 100) * 100`，确保100股整数倍
2. **最低持仓**：`enable_amount < 100` 时不卖出
3. **重复卖出防护**：卖出成功后加入 `g.sold_stocks` 列表
4. **异常隔离**：单只股票的异常不影响其他股票的判断
5. **空持仓保护**：无持仓时跳过轮询

## 7. 文件位置

- 策略文件：`strategies/george_limit_up_sell.py`
- 设计文档：`docs/superpowers/specs/2026-05-18-limit-up-sell-strategy-design.md`

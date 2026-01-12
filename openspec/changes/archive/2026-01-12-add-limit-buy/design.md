# 设计文档：George 限价买入功能

## 架构设计

### 状态转移条件
```
触发买入条件：
  last_status in [0, -1, -2] AND current_status.get(stock) == 2

日志记录：
  - 买入触发：log.info("line:{} george下单买入: last_px: {}, stock: {}".format(146, last_px, stock))
  - 条件未达到：log.debug("line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))
```

### 数据结构
- `check_limit(stock)` 返回字典，需要用 `.get(stock)` 获取状态值
- `get_snapshot(stock)` 返回字典，包含 stock 作为键，值为包含 last_px、offer_amount 等的字典
- 买入时从 `g.fund_list` 中删除整个键（`del g.fund_list[key]`）

### 实现流程

1. **轮询阶段**（`interval_handle` 函数）
   - 遍历股票池
   - 获取当前状态：`current_status = check_limit(stock)` 返回字典
   - 从 `g.stock_states` 获取上一次状态
   - 检查状态转移条件：`last_status in [0, -1, -2] and current_status.get(stock) == 2`
   - 更新 `g.limit1` 和 `g.limit2` 列表

2. **买入处理阶段**（`_proc_hit_board` 函数）
   - 获取快照数据：`snapshot = get_snapshot(stock)` 返回字典
   - 从快照中提取股票数据：`stock_data = snapshot.get(stock, {})`
   - 提取 last_px：`last_px = stock_data.get('last_px', 0)`
   - 记录买入日志
   - 从 `g.fund_list` 中删除该键：`del g.fund_list[key]`

3. **调试处理阶段**（`_proc_hit_board_debug` 函数）
   - 获取快照数据
   - 直接从snapshot获取：`last_px = snapshot.get('last_px', 0)`
   - 提取 offer_amount
   - 记录调试日志

## 数据流
```
interval_handle
  ├─ 遍历股票
  ├─ check_limit(stock) → 获取当前状态字典
  ├─ g.stock_states[stock] → 获取上一次状态
  ├─ 比较 last_status 和 current_status.get(stock)
  └─ 调用 _proc_hit_board 或 _proc_hit_board_debug 处理
      ├─ get_snapshot(stock) → 获取快照字典
      ├─ snapshot.get(stock, {}) → 获取股票数据
      ├─ 提取 last_px、offer_amount
      └─ 记录日志或删除 g.fund_list[key]
```

## 依赖关系
- 依赖 `add-george-state-tracking` 变更提供的 `g.stock_states` 状态存储
- 依赖现有的 `check_limit` 函数（返回字典）
- 依赖现有的 `get_snapshot` 函数（返回字典）
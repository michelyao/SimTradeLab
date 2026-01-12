# 设计文档：George 策略状态追踪

## 架构设计

### 状态存储结构
```
g.stock_states = {
    'stock_code': {
        'last_status': <int>,      # 上一次的状态值
        'current_status': <int>,   # 当前状态值
        'last_px': <float>,        # 上一次的价格
        'offer_price': <float>     # 报价
    }
}
```

### 状态值定义
- `0`：正常状态
- `1`：涨停状态（limit1）
- `2`：打板状态（limit2）
- `-1`：异常状态
- `-2`：其他异常状态

### 状态转移规则
触发买入条件：`last_status in [0, -1, -2] and current_status == 2`

## 实现流程

1. **初始化阶段**（`set_params` 函数）
   - 初始化 `g.stock_states` 为空字典
   - 初始化 `g.limit1` 和 `g.limit2` 为空列表

2. **轮询阶段**（`interval_handle` 函数）
   - 遍历股票池
   - 获取当前状态
   - 检查状态转移条件
   - 更新状态记录

3. **处理阶段**（`_proc_hit_board` 函数）
   - 获取快照数据
   - 检查状态转移
   - 记录相应日志

## 数据流
```
interval_handle
  ├─ 遍历股票
  ├─ check_limit(stock) → 获取状态
  ├─ 检查 g.stock_states[stock]
  ├─ 比较 last_status 和 current_status
  └─ 调用 _proc_hit_board 处理
```

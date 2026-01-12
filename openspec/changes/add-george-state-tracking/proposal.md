# 提案：George 策略状态追踪功能

## 概述
在 `hit_limit_single.py` 的 `interval_handle` 函数中实现股票状态追踪和状态转移检测，用于识别打板买入机会。

## 需求
1. **状态记录**：记录每个股票上一次数据的状态
   - `g.limit1`：保存 `check_limit` 返回状态为 1 的股票代码
   - `g.limit2`：保存 `check_limit` 返回状态为 2 的股票代码

2. **状态转移检测**：
   - 当上一次状态是 0、-1、-2，这次状态是 2 时
   - 记录：`log.info("line:{} george下单买入: last_px: {}, offer_price: {}, stock: {}".format(146, last_px, offer_price, stock))`
   - 否则记录：`log.debug("line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))`

## 实现范围
- 修改 `interval_handle` 函数
- 初始化全局状态变量 `g.limit1` 和 `g.limit2`
- 在 `_proc_hit_board` 函数中实现状态转移检测逻辑

## 关键决策
- 使用字典存储股票状态映射，便于快速查询和更新
- 在每次循环中更新状态，保持最新的状态信息

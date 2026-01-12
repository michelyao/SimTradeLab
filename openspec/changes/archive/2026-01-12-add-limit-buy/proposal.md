# 提案：George 限价买入功能

## 概述
在 `hit_limit_single.py` 的 `interval_handle` 函数中实现限价买入逻辑，根据股票状态转移条件触发买入操作。

## 需求
基于 `add-george-state-tracking` 变更提供的状态追踪机制，实现以下功能：

1. **状态转移检测**：
   - 当上一次状态是 0、-1、-2，这次状态是 2 时，触发买入
   - 记录：`log.info("line:{} george下单买入: last_px: {}, offer_price: {}, stock: {}".format(146, last_px, offer_price, stock))`
   - 并将这个stock所在的键值从 g.fund_list中删除

2. **条件未达到处理**：
   - 当状态转移不符合买入条件时，记录调试日志
   - 记录：`log.debug("line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))`

## 实现范围
- 修改 `interval_handle` 函数中的状态转移检测逻辑
- 在 `_proc_hit_board` 函数中实现买入条件判断和日志记录

## 关键决策
- 依赖 `add-george-state-tracking` 提供的状态追踪机制
- 使用现有的 `check_limit` 函数获取股票状态
- 保持日志格式与需求文档一致
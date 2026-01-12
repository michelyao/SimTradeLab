# 变更提案：refactor-hitboard-single

## 概述
优化 `hit_top_single.py` 中的 `interval_handle` 函数，按照 `get_snapshot` 接口规范进行改进，确保每次都从接口获取实时行情数据，不进行数据缓存。

## 需求来源
- 文件：`strategies/george_sell_strage/george.md`
- 需求：
  1. 按照 `get_snapshot` 函数说明对 `interval_handle` 函数进行优化
  2. 在优化过程中不要进行数据缓存，每次都从接口获取数据

## 当前问题
1. `_proc_hit_board` 函数中调用 `get_snapshot(stock)` 获取快照
2. 需要确保每次调用都获取最新的实时数据
3. 需要按照接口规范正确处理返回的快照数据结构

## 变更范围
- **文件**：`strategies/hit_top_single.py`
- **函数**：`interval_handle`、`_proc_hit_board`
- **影响**：打板策略的行情数据获取逻辑

## 实现策略
1. 确保 `get_snapshot` 每次都调用接口获取最新数据
2. 按照接口规范正确处理返回的数据结构
3. 验证数据完整性和有效性
4. 保持现有的业务逻辑不变

## 验收标准
- [ ] 每次 `interval_handle` 执行都从接口获取最新快照
- [ ] 正确处理 `get_snapshot` 返回的数据结构
- [ ] 代码符合项目编程规范（Python 3.5 兼容、无 f-string、手动行号）
- [ ] 保持现有的打板检测逻辑

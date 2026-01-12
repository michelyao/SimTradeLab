# 任务列表：George 限价买入功能实现

## 任务分解

### 1. 实现状态转移检测逻辑
- [x] 在 `interval_handle` 函数中获取当前状态
- [x] 从 `g.stock_states` 中获取上一次状态
- [x] 比较状态值，判断是否符合买入条件
- [x] 调用 `_proc_hit_board` 处理符合条件的股票

### 2. 实现买入日志记录
- [x] 在 `_proc_hit_board` 函数中获取快照数据（last_px, offer_price）
- [x] 当状态转移符合买入条件时，记录 info 级别日志
- [x] 格式：`log.info("line:{} george下单买入: last_px: {}, offer_price: {}, stock: {}".format(146, last_px, offer_price, stock))`

### 3. 实现条件未达到日志记录
- [x] 当状态转移不符合买入条件时，记录 debug 级别日志
- [x] 格式：`log.debug("line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))`

### 4. 测试验证
- [x] 验证状态转移检测逻辑正确性
- [x] 验证日志输出格式正确
- [x] 验证买入条件判断准确

## 依赖关系
- 任务 1 是基础，必须先完成
- 任务 2 和 3 依赖任务 1
- 任务 4 依赖任务 2 和 3
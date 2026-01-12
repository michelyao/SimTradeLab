# 规范：George 限价买入功能

## 新增需求

### 需求：限价买入触发
系统**必须**在股票状态从非打板状态转移到打板状态时，触发买入操作。

#### 场景：检测打板买入机会
系统**必须**检测股票状态从 0、-1、-2 转移到 2 的情况，并记录买入日志。

**前置条件**：
- 股票已有历史状态记录
- `last_status in [0, -1, -2]`
- `current_status == 2`

**后置条件**：
- 系统必须记录日志：`log.info("line:{} george下单买入: last_px: {}, offer_price: {}, stock: {}".format(146, last_px, offer_price, stock))`
- 其中 `last_px` 为上一次价格，`offer_price` 为当前报价

#### 场景：打板条件未达到
当状态转移不符合买入条件时，系统**必须**记录调试日志。

**前置条件**：状态转移不符合买入条件

**后置条件**：
- 系统必须记录日志：`log.debug("line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))`
- 其中 `last_px` 为上一次价格，`offer_amount` 为报价数量

## 修改需求

### 需求：状态转移检测集成
系统**必须**在 `interval_handle` 函数中集成状态转移检测逻辑，根据股票状态转移条件触发买入操作。

#### 场景：轮询中的状态转移检测
在每次轮询时，系统**必须**检查股票状态是否符合买入条件。

**前置条件**：
- `g.stock_states` 已初始化
- `check_limit(stock)` 返回当前状态

**后置条件**：
- 当状态转移符合买入条件时，调用 `_proc_hit_board` 处理
- 记录相应的日志信息
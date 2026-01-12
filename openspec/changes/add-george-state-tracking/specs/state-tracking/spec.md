# 规范：George 策略状态追踪功能

## 新增需求

### 需求：股票状态记录
系统**必须**记录每个股票上一次数据的状态。

#### 场景：初始化状态存储
当策略启动时，初始化全局状态存储结构，用于记录每个股票的状态变化。

**前置条件**：策略已启动，`set_params()` 函数被调用

**后置条件**：
- `g.stock_states` 必须初始化为空字典
- `g.limit1` 必须初始化为空列表
- `g.limit2` 必须初始化为空列表

#### 场景：更新股票状态
在每次轮询时，系统**必须**更新股票的当前状态，并保存上一次的状态。

**前置条件**：`check_limit(stock)` 返回状态值

**后置条件**：
- `g.stock_states[stock]['last_status']` 必须保存上一次状态
- `g.stock_states[stock]['current_status']` 必须保存当前状态
- 根据状态值必须更新 `g.limit1` 或 `g.limit2`

### 需求：状态转移检测
系统**必须**在上一次的状态是 0、-1、-2，这次的状态是 2 时，触发买入逻辑。

#### 场景：检测打板买入机会
系统**必须**检测股票状态从非打板状态转移到打板状态的情况。

**前置条件**：
- 股票已有历史状态记录
- `last_status in [0, -1, -2]`
- `current_status == 2`

**后置条件**：
- 系统必须记录日志：`log.info("line:{} george下单买入: last_px: {}, offer_price: {}, stock: {}".format(146, last_px, offer_price, stock))`

#### 场景：打板条件未达到
当状态转移不符合买入条件时，系统**必须**记录调试日志。

**前置条件**：状态转移不符合买入条件

**后置条件**：
- 系统必须记录日志：`log.debug("line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))`

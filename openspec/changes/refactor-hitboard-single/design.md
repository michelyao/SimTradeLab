# 设计文档：hitboard-single 优化

## 问题分析

### 当前实现
`_proc_hit_board` 函数通过 `get_snapshot(stock)` 获取单只股票的行情快照，然后提取关键字段进行打板检测。

### 接口规范
根据 `george.md` 中的 `get_snapshot` 说明：
- **参数**：单只股票代码或多只股票代码列表
- **返回**：dict 类型，key 为股票代码，value 为快照信息
- **异常**：返回空 dict `{}`
- **快照字段**：包含 `up_px`、`last_px`、`offer_grp` 等多个字段

### 关键字段说明
- `up_px`：涨停价格（float）
- `last_px`：最新成交价（float）
- `offer_grp`：委卖档位（dict），结构为 `{1: [价格, 委托量, 委托笔数], ...}`

## 优化方案

### 1. 数据获取
- 每次调用 `get_snapshot` 都从接口获取最新数据
- 不在内存中缓存快照数据
- 处理接口异常返回（空 dict）

### 2. 数据验证
- 验证返回的快照数据不为空
- 验证必要字段存在（`up_px`、`last_px`、`offer_grp`）
- 验证 `offer_grp` 包含第 5 档数据

### 3. 业务逻辑
- 保持现有的打板检测条件：`level_5_price == up_px and level_5_order <= 5000`
- 保持现有的日志输出格式
- 更新打印中行号。

## 实现细节

### 函数改进
1. `_proc_hit_board` 函数：
   - 调用 `get_snapshot(stock)` 获取快照
   - 验证返回数据的有效性
   - 提取必要字段进行打板检测

2. 数据结构处理：
   - `offer_grp` 是 dict，key 为档位号（1-5），value 为 [价格, 委托量, 委托笔数, ...]
   - 需要正确访问 `offer_grp[5][0]`（第 5 档价格）和 `offer_grp[5][1]`（第 5 档委托量）

### 错误处理
- 快照为空时返回
- 必要字段缺失时返回
- `offer_grp` 不完整时返回

## 代码风格约束
- Python 3.5 兼容性
- 不使用 f-string，使用 `.format()` 或 `%` 格式化
- 更新日志中的行号，保证其准确性。（因为不支持 `inspect.currentframe().f_lineno`）
- 防御式编程风格

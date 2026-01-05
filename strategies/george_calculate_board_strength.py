def calculate_board_strength(stock_data):
    """
    计算单条 Snapshot 数据的封板强度指标

    Args:
        stock_data (dict): 单只股票的详细数据字典 (即 snapshot 中的 value 部分)

    Returns:
        dict: 包含强度指标的字典，如果数据无效返回 None
    """
    try:
        # 1. 获取买一队列数据
        bid_grp = stock_data.get('bid_grp', {})
        # 检查是否有买一数据 (key 为 1)
        if not bid_grp or 1 not in bid_grp:
            return {'score': -1, 'reason': '无买盘数据'}

        # bid_grp[1] 结构通常为: [price, volume, order_count, ...]
        bid_1_info = bid_grp[1]
        bid_1_price = bid_1_info[0]
        bid_1_vol = bid_1_info[1]

        # 2. 获取流通股本 (注意单位，通常 snapshot 里是股数)
        circulation_amount = stock_data.get('circulation_amount', 0)

        # 3. 获取换手率
        turnover_ratio = stock_data.get('turnover_ratio', 0.0)

        # --- 计算核心指标 ---

        # A. 封单金额 (元)
        lock_money = bid_1_price * bid_1_vol

        # B. 封单占流通盘比例 (核心强度指标)
        # 如果流通股本为0，防止除零错误
        lock_ratio = (bid_1_vol / circulation_amount) if circulation_amount > 0 else 0.0

        # C. 综合打分 (示例逻辑)
        # 逻辑：封单占比越高越好，封单金额越大越好，换手率越低越好(对于缩量板)
        # 这里简单地以“封单占比”作为主要排序依据，这也是最能反映主力意愿的指标
        score = lock_ratio

        return {
            'lock_money': lock_money,           # 封单金额
            'lock_ratio': lock_ratio,           # 封单占比 (0.06 代表 6%)
            'turnover_ratio': turnover_ratio,   # 换手率
            'bid_1_vol': bid_1_vol,             # 封单量
            'score': score                      # 综合得分
        }

    except Exception as e:
        print(f"计算出错: {e}")
        return None

# ==========================================
# 测试数据 (来自您的日志)
# ==========================================
data_002413 = {
    'hsTimeStamp': 20260105092957000, 'preclose_px': 12.55, 'circulation_amount': 1293079400, 'turnover_ratio': 0.0039,
    'bid_grp': {1: [13.81, 78301053, 20622]} # 省略了后面详细数据
}

data_600363 = {
    'hsTimeStamp': 20260105092939000, 'preclose_px': 63.06, 'circulation_amount': 450888450, 'turnover_ratio': 0.0119,
    'bid_grp': {1: [69.37, 1911247, 1347]}
}

data_603608 = {
    'hsTimeStamp': 20260105092946000, 'preclose_px': 10.3, 'circulation_amount': 419716014, 'turnover_ratio': 0.0124,
    'bid_grp': {1: [11.33, 9429260, 2437]}
}

# 模拟数据列表
stocks = {
    '002413.SZ': data_002413,
    '600363.SS': data_600363,
    '603608.SS': data_603608
}

# ==========================================
# 执行筛选与排序
# ==========================================
results = []
for code, data in stocks.items():
    metrics = calculate_board_strength(data)
    if metrics:
        metrics['code'] = code
        results.append(metrics)

# 排序逻辑：优先按 封单占比 (lock_ratio) 降序排列
# 如果占比相近，可以再比较封单金额
sorted_results = sorted(results, key=lambda x: x['lock_ratio'], reverse=True)

print(f"{'代码':<10} | {'封单占比':<10} | {'封单金额(亿)':<12} | {'换手率':<10}")
print("-" * 50)
for res in sorted_results:
    print(f"{res['code']:<10} | {res['lock_ratio']:.2%}      | {res['lock_money']/1e8:<16.2f} | {res['turnover_ratio']:.2%}")

# 输出结果将显示 002413.SZ 排在第一位

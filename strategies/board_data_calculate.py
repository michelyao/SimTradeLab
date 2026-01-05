def analyze_stock_data(data):
    """
    分析股票数据，筛选出封板率最高的股票
    """
    results = []
    for stock_code, stock_info in data.items():
        # 获取涨停价
        up_px = stock_info['up_px']
        # 获取流通股本
        circulation_amount = stock_info['circulation_amount']
        # 获取涨停价上的买单数量
        bid_grp = stock_info['bid_grp']
        if up_px in [bid[0] for bid in bid_grp.values()]:
            for bid in bid_grp.values():
                if bid[0] == up_px:
                    bid_qty = bid[1]
                    break
        else:
            bid_qty = 0
        # 计算封板率
        if circulation_amount > 0:
            board_rate = bid_qty / circulation_amount
        else:
            board_rate = 0
        results.append({
            'stock_code': stock_code,
            'up_px': up_px,
            'bid_qty': bid_qty,
            'circulation_amount': circulation_amount,
            'board_rate': board_rate
        })
    # 按封板率降序排序
    results.sort(key=lambda x: x['board_rate'], reverse=True)
    return results

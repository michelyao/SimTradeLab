# -*- coding: utf-8 -*-
"""
止损卖出策略 - 10:00时根据中小指跌幅和单票跌幅执行止损
"""

from datetime import datetime


def get_index_drop_ratio(index_code='000905.XSHG'):
    """获取中小指日跌幅"""
    try:
        index_data = get_price(index_code, end_date=None, frequency='1d', fields=['close', 'open'], count=1)
        if index_data is not None and len(index_data) > 0:
            open_price = index_data['open'].iloc[0]
            close_price = index_data['close'].iloc[0]
            drop_ratio = (close_price - open_price) / open_price * 100
            return drop_ratio
    except Exception as e:
        log.warning("line:{} [get index drop ratio fail] {}".format(20, e))

    return 0


def get_stock_drop_ratio(stock, buy_price):
    """获取单票相对买入价的跌幅百分比"""
    current_data = get_current_data()
    current_price = current_data[stock].last_price
    drop_ratio = (current_price - buy_price) / buy_price * 100
    return drop_ratio


def is_10_oclock(context):
    """检查是否为10:00"""
    current_time = context.current_dt
    return current_time.hour == 10 and current_time.minute == 0


def generate_stoploss_signal(stock, context, buy_price):
    """生成止损卖出信号"""
    index_drop = get_index_drop_ratio()
    stock_drop = get_stock_drop_ratio(stock, buy_price)

    reason = None
    if index_drop <= -6:
        reason = 'index_drop'
    elif stock_drop <= -12:
        reason = 'stock_drop'

    if reason:
        current_data = get_current_data()
        signal = {
            'timestamp': context.current_dt,
            'stock': stock,
            'signal_type': 'stoploss',
            'price': current_data[stock].last_price,
            'buy_price': buy_price,
            'reason': reason,
            'index_drop': index_drop,
            'stock_drop': stock_drop
        }

        log.info("line:{} [stoploss signal] stock: {} reason: {} index_drop: {} stock_drop: {}".format(
            56, stock, reason, index_drop, stock_drop))

        return signal

    return None


def check_stoploss_sell_signal(context, positions):
    """检查止损卖出信号"""
    signals = []

    if not is_10_oclock(context):
        return signals

    for stock, position in positions.items():
        signal = generate_stoploss_signal(stock, context, position.avg_cost)
        if signal:
            signals.append(signal)

    return signals

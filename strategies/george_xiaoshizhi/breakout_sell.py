# -*- coding: utf-8 -*-
"""
破板卖出策略 - 14:00时检测破板信号并执行卖出
"""

from datetime import datetime


def is_limit_up(stock, context):
    """检查股票是否处于涨停状态"""
    current_data = get_current_data()
    stock_data = current_data[stock]
    return stock_data.last_price >= stock_data.high_limit * 0.9999


def detect_breakout(stock, context):
    """检测破板信号 - 股票从涨停状态回落到涨停价以下"""
    current_data = get_current_data()
    stock_data = current_data[stock]

    if stock_data.last_price < stock_data.high_limit * 0.9999:
        return True
    return False


def is_14_oclock(context):
    """检查是否为14:00"""
    current_time = context.current_dt
    return current_time.hour == 14 and current_time.minute == 0


def generate_breakout_signal(stock, context):
    """生成破板卖出信号"""
    if not detect_breakout(stock, context):
        return None

    current_data = get_current_data()
    signal = {
        'timestamp': context.current_dt,
        'stock': stock,
        'signal_type': 'breakout',
        'price': current_data[stock].last_price,
        'high_limit': current_data[stock].high_limit
    }

    log.info("line:{} [breakout signal] stock: {} price: {} high_limit: {}".format(
        35, stock, signal['price'], signal['high_limit']))

    return signal


def check_breakout_sell_signal(context, held_stocks):
    """检查破板卖出信号"""
    signals = []

    if not is_14_oclock(context):
        return signals

    for stock in held_stocks:
        signal = generate_breakout_signal(stock, context)
        if signal:
            signals.append(signal)

    return signals

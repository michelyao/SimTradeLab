# -*- coding: utf-8 -*-
"""
周二盘前选股模块 - 按市值升序选择5只股票
"""

from datetime import datetime


def is_tuesday_premarket(context):
    """检查是否为周二10:30盘前"""
    current_time = context.current_dt
    return current_time.weekday() == 1 and current_time.hour < 10 or (current_time.hour == 10 and current_time.minute < 30)


def filter_paused_stocks(stock_list, context):
    """排除停牌股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_limit_stocks(stock_list, context):
    """排除涨跌停股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if current_data[stock].last_price < current_data[stock].high_limit and current_data[stock].last_price > current_data[stock].low_limit]


def filter_low_liquidity_stocks(stock_list, context):
    """排除低流动性股票 - 基于成交量"""
    if not stock_list:
        return []

    volumes = history(1, unit='1m', field='volume', security_list=stock_list)
    min_volume = 1000000
    return [stock for stock in stock_list if volumes[stock][0] > min_volume]


def select_by_market_cap(stock_list, context, count=5):
    """按市值升序选择前N只股票"""
    if not stock_list:
        return []

    try:
        market_caps = get_fundamentals(query(valuation.code, valuation.market_cap).filter(valuation.code.in_(stock_list)).order_by(valuation.market_cap.asc()).limit(count))
        if market_caps is not None and len(market_caps) > 0:
            return list(market_caps['code'].values)
    except Exception as e:
        log.warning("line:{} [get market cap fail] {}".format(42, e))

    return stock_list[:count]


def select_stocks_tuesday_premarket(context):
    """周二10:30盘前选股 - 按市值升序选择5只股票"""
    if not is_tuesday_premarket(context):
        return []

    try:
        initial_list = get_index_stocks('000300.XSHG')

        initial_list = filter_paused_stocks(initial_list, context)
        initial_list = filter_limit_stocks(initial_list, context)
        initial_list = filter_low_liquidity_stocks(initial_list, context)

        final_list = select_by_market_cap(initial_list, context, count=5)

        log.info("line:{} [tuesday premarket stock selection] selected: {}".format(60, final_list))
        return final_list
    except Exception as e:
        log.error("line:{} [stock selection error] {}".format(63, e))
        return []

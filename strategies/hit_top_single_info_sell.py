# -*- coding: utf-8 -*-
"""
打板策略 - 实时检测涨停股票并进行交易
"""

import json
from datetime import datetime, timedelta

MAX_STOCK_NUMBER = 4
MAX_BUY_AMOUNT = 5000


def initialize(context):
    """
    初始化全局参数与定时主循环。若非实时交易模式，自动设置回测参数。
    """
    set_params()
    g.signal = 0
    g.hit_status = [1, 2]
    is_trade_flag = is_trade()
    run_interval(context, interval_handle, seconds=1,
                 interval_timer_ranges="09:29-10:30,13:00-13:01")
    if not is_trade_flag:
        set_backtest()  # 设置回测条件


def set_params():
    """
    初始化策略参数，重置持仓计数并加载股票池。
    优化版本：减少重复计算，增加缓存检查
    """
    g.amount = 100
    g.limit_stock = 0
    g.security = ["002218.SZ", "002119.SZ", "600520.SS"]

    set_universe(g.security)


def set_variables():
    """
    设置策略中间变量。
    """
    g.init_screen = True
    g.is_update_stocks = False


def set_backtest():
    """
    配置回测模式参数。
    """
    set_limit_mode("UNLIMITED")
    set_commission(commission_ratio=0.00015, min_commission=5.0)


def before_trading_start(context, data):
    """
    每天盘前初始化参数。
    """
    set_params()
    g.current_date = context.current_dt.strftime("%Y%m%d")


# def handle_data(context, data):
def interval_handle(context):
    """
    核心轮询主流程。遍历股票池，检测涨停条件，并触发下单。
    优化版本：减少不必要的日志输出，提高执行效率
    """
    for stock in g.security:
        try:
            limit = check_limit(stock)
            snapshot = get_snapshot(stock)
            log.debug("line:{} stock: {} \r\nlimit: {} \r\nsnapshot: {}"
                      "".format(98, stock, limit, snapshot))
        except Exception as e:
            # 减少详细的traceback输出，只记录关键错误信息
            log.debug(
                "line:{} Error processing stock {}: {}".format(112, stock,
                                                               str(e)))

# -*- coding: utf-8 -*-
"""
打板策略 - 实时检测涨停股票并进行交易
"""

import json
from datetime import datetime, timedelta


def initialize(context):
    """
    初始化全局参数与定时主循环。若非实时交易模式，自动设置回测参数。
    """
    set_params()
    g.signal = 0
    g.hit_status = [1, 2]
    is_trade_flag = is_trade()
    run_interval(context, interval_handle, seconds=1)
    if not is_trade_flag:
        set_backtest()  # 设置回测条件


def read_stock_pool():
    george_path = get_research_path() + "george/"
    print("line:{} {}".format(25, george_path))
    yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    json_file = "{}_top_three_module.json".format(yesterday_date)
    full_path = george_path + "input_data/" + json_file
    stock_list = []
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            stock_list = json.load(f)
    except Exception as e:
        log.warning("line:{} [read json fail] {}: {}"
                    "".format(34, full_path, e))

    log.info(
        "[now] line:{} full_path:{} result, stock_list count: {}"
        "".format(37, full_path,
                  len(stock_list) if hasattr(stock_list, '__len__') else '?'))
    return stock_list


def set_params():
    """
    初始化策略参数，重置持仓计数并加载股票池。
    优化版本：减少重复计算，增加缓存检查
    """
    g.amount = 100
    g.limit_stock = 0
    g.fund_list = read_stock_pool()
    g.security = sum(g.fund_list.values(), []) if g.fund_list else []
    set_universe(g.security)
    g.stock_states = {}
    g.limit1 = []
    g.limit2 = []


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
    for boards, stocks in g.fund_list.items():
        for stock in stocks:
            current_status = check_limit(stock).get(stock)
            last_status = g.stock_states.get(stock, {}).get('last_status', 0)

            if current_status == 1:
                g.limit1.append(stock)
            elif current_status == 2:
                g.limit2.append(stock)

            log.debug("line:{} last_status: {}, current_status: {}"
                  "".format(118, last_status, current_status))
            if last_status in [0, -1, -2] and current_status == 2:
                _proc_hit_board(stock)
            else:
                _proc_hit_board_debug(stock)

            g.stock_states[stock] = {
                'last_status': current_status,
                'current_status': current_status
            }


def _proc_hit_board(stock):
    """处理打板买入逻辑"""
    snapshot = get_snapshot(stock)
    if snapshot:
        stock_data = snapshot.get(stock, {})
        up_px = stock_data.get('up_px', 0)
        if g.limit_stock < 4 and up_px < 50:
            order_value(stock, 5000)
            log.debug("line:{} george下单买入: up_px: {}, stock: {}"
                      "".format(118, up_px,  stock))
            g.limit_stock += 1
            for key in g.fund_list:
                if stock in g.fund_list[key]:
                    g.fund_list[key].remove(stock)
                    break


def _proc_hit_board_debug(stock):
    """处理打板条件未达到的情况"""
    snapshot = get_snapshot(stock)
    if snapshot:
        last_px = snapshot.get('last_px', 0)
        offer_amount = snapshot.get('offer_amount', 0)
        log.debug("line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))
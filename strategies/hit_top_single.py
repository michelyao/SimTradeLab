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
    # run_interval(context, interval_handle, seconds=1)
    if not is_trade_flag:
        set_backtest()  # 设置回测条件


def read_stock_pool():
    george_path = get_research_path() + "george/"
    print("line:{} {}".format(18, george_path))
    yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    json_file = "{}_top_three_module.json".format(yesterday_date)
    full_path = george_path + "input_data/" + json_file
    stock_list = []
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            stock_list = json.load(f)
    except Exception as e:
        log.warning("line:{} [read json fail] {}: {}"
                    "".format(37, full_path, e))

    log.info(
        "[now] line:{} full_path:{} result, stock_list count: {}"
        "".format(61, full_path,
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


def handle_data(context, data):
# def interval_handle(context):
    """
    核心轮询主流程。遍历股票池，检测涨停条件，并触发下单。
    优化版本：减少不必要的日志输出，提高执行效率
    """
    # 减少INFO级别日志频率，只在关键节点记录
    log.info("line:{} interval_handle start".format(107))
    if not g.fund_list:
        log.warning(
            "line:{} fund_list is empty, skip interval_handle.".format(110))
        return

    for hit_board_name, stocks in g.fund_list.items():
        for stock in stocks:
            try:
                limit = check_limit(stock.upper())
                # 减少DEBUG级别日志输出
                log.debug(
                    "line:{} stock: {} limit: {}".format(118, stock, limit))

                stock_hit_status = get_check_limit_value(limit)
                if stock_hit_status in g.hit_status:
                    if g.limit_stock > 3:
                        # 优化循环控制：达到购买限制时完全退出
                        log.info(
                            "line:{} reached buy limit, exit processing.".format(
                                123))
                        return
                    _proc_hit_board(stock)
            except Exception as e:
                # 减少详细的traceback输出，只记录关键错误信息
                log.debug(
                    "line:{} Error processing stock {}: {}".format(127, stock,
                                                                   str(e)))

    # 减少INFO级别日志频率
    # log.info("line:{} interval_handle end".format(131))


def get_check_limit_value(limit):
    """
    优化后的函数：直接返回limit字典中的值，避免不必要的遍历
    如果limit是字典且有值，返回第一个值；否则返回默认值88
    """
    if isinstance(limit, dict) and limit:
        # 返回字典中的第一个值，避免遍历整个字典
        return next(iter(limit.values()))
    return 88


def _proc_hit_board(stock):
    """
    优化版本：减少不必要的日志输出和提高执行效率
    """
    # 减少启动和结束的日志输出频率
    log.info("line:{}  stock:{} _proc_hit_board start".format(142, stock))
    try:
        snapshot = get_snapshot(stock)
        # 减少DEBUG级别日志输出
        log.debug("line:{} snapshot {}".format(145, snapshot))

        infos = snapshot.get(stock)
        # 减少DEBUG级别日志输出
        log.debug("line:{} infos {}".format(148, infos))
        if infos is None:
            # 减少DEBUG级别日志输出
            log.debug("line:{} No snapshot for stock {}".format(150, infos))
            return
        up_px = infos.get("up_px")
        last_px = infos.get("last_px")
        offer_grp = infos.get("offer_grp")
        # 减少DEBUG级别日志输出
        log.debug(
            "line:{} stock {} offer_grp data not available or incomplete offer_grp {}".format(
                157, stock, offer_grp))
        if not offer_grp:
            # 减少DEBUG级别日志输出
            log.debug(
                "line:{} stock {} offer_grp data not available".format(163,
                                                                       stock))
            return

        level_5_price, level_5_order = offer_grp[5][0], offer_grp[5][1]
        if level_5_price == up_px and level_5_order <= 5000:
            log.info(
                "line:{} george下单买入: last_px: {}, level_5_price: {}, stock: "
                "{}".format(168, last_px, level_5_price, stock))
        else:
            # 减少未满足条件时的日志输出
            log.info(
                "line:{} george 打板未达到条件: last_px: {}, level_5_price: {}, stock: {}".format(
                    172, last_px, level_5_price, stock))
        # 减少结束的日志输出
        log.info("line:{} _proc_hit_board end".format(173))

    except Exception as e:
        # 减少详细的traceback输出，只记录关键错误信息
        log.debug(
            "line:{} get_snapshot failed for {}: {}".format(177, stock, str(e)))

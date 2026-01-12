# -*- coding: utf-8 -*-
"""
打板策略 - 实时检测涨停股票并进行交易
状态跟踪版本 - 记录每个股票上一次的状态变化
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
    """
    读取股票池文件
    """
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
    初始化状态跟踪变量
    """
    g.amount = 100
    g.limit_stock = 0
    g.fund_list = read_stock_pool()
    g.security = sum(g.fund_list.values(), []) if g.fund_list else []
    set_universe(g.security)

    # 状态跟踪变量
    g.stock_states = {}  # 记录每个股票的上一次状态: {stock_code: last_status}
    g.limit1 = []  # 保存状态为1的股票代码
    g.limit2 = []  # 保存状态为2的股票代码


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

    功能说明：
    1. 记录每个股票上一次数据来时的状态
       - g.limit1 保存 check_limit 返回状态是1的股票代码
       - g.limit2 保存 check_limit 返回状态是2的股票代码

    2. 当上一次的状态是 0, -1, -2 这次的状态是 2
       - 则 log.info("line:{} george下单买入: last_px: {}, offer_price: {}, stock: {}".format(146, last_px, offer_price, stock))
       - 否则 log.debug("line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))
    """
    # 减少INFO级别日志频率，只在关键节点记录
    log.debug("line:{} interval_handle start".format(87))
    if not g.fund_list:
        log.warning(
            "line:{} fund_list is empty, skip interval_handle.".format(89))
        return

    for hit_board_name, stocks in g.fund_list.items():
        for stock in stocks:
            try:
                # 1. 获取当前状态
                limit = check_limit(stock)
                current_status = limit.get(stock, 0) if isinstance(limit, dict) else 0

                # 2. 获取上一次的状态（默认为0）
                last_status = g.stock_states.get(stock, 0)

                # 3. 记录状态到对应的列表
                if current_status == 1:
                    if stock not in g.limit1:
                        g.limit1.append(stock)
                        log.debug("line:{} stock {} 状态为1，加入limit1".format(113, stock))
                elif current_status == 2:
                    if stock not in g.limit2:
                        g.limit2.append(stock)
                        log.debug("line:{} stock {} 状态为2，加入limit2".format(117, stock))

                # 4. 判断是否满足买入条件
                if last_status in [0, -1, -2] and current_status == 2:
                    # 满足条件：上一次是0/-1/-2，这次是2
                    _proc_hit_board(stock)
                else:
                    # 未满足条件
                    _proc_hit_board_debug(stock, last_status, current_status)

                # 5. 更新上一次的状态
                g.stock_states[stock] = current_status

            except Exception as e:
                log.debug(
                    "line:{} Error processing stock {}: {}".format(130, stock, str(e)))


def _proc_hit_board(stock):
    """
    处理满足条件的股票：记录买入日志

    Args:
        stock: 股票代码
    """
    try:
        snapshot = get_snapshot(stock)

        # 验证快照数据不为空
        if not snapshot:
            log.debug("line:{} snapshot is empty for stock {}".format(147, stock))
            return

        # 验证股票代码在快照中存在
        infos = snapshot.get(stock)
        if infos is None:
            log.debug("line:{} No snapshot for stock {}".format(150, stock))
            return

        # 获取必要字段
        up_px = infos.get("up_px")
        last_px = infos.get("last_px")
        offer_grp = infos.get("offer_grp")

        if up_px is None or last_px is None:
            log.debug("line:{} Missing required fields for stock {}".format(157, stock))
            return

        # 验证 offer_grp 数据结构
        if not offer_grp or not isinstance(offer_grp, dict):
            log.debug("line:{} offer_grp data not available for stock {}".format(161, stock))
            return

        # 验证第1档数据存在
        if 1 not in offer_grp or len(offer_grp[1]) < 2:
            log.debug("line:{} offer_grp level 1 data incomplete for stock {}".format(165, stock))
            return

        # 提取第1档数据（卖一档）
        offer_price = offer_grp[1][0]
        offer_amount = offer_grp[1][1]

        # 记录买入信息
        log.info(
            "line:{} george下单买入: last_px: {}, offer_price: {}, stock: {}".format(
                146, last_px, offer_price, stock))

        # 从fund_list中移除已买入的股票
        for key in g.fund_list:
            if stock in g.fund_list[key]:
                g.fund_list[key].remove(stock)
                log.debug("line:{} stock {} 已从fund_list中移除".format(182, stock))
                break

    except Exception as e:
        log.debug("line:{} get_snapshot failed for {}: {}".format(186, stock, str(e)))


def _proc_hit_board_debug(stock, last_status, current_status):
    """
    处理未满足条件的股票：记录debug日志

    Args:
        stock: 股票代码
        last_status: 上一次状态
        current_status: 当前状态
    """
    try:
        snapshot = get_snapshot(stock)

        # 验证快照数据不为空
        if not snapshot:
            log.debug("line:{} snapshot is empty for stock {}".format(197, stock))
            return

        # 验证股票代码在快照中存在
        infos = snapshot.get(stock)
        if infos is None:
            log.debug("line:{} No snapshot for stock {}".format(200, stock))
            return

        # 获取必要字段
        last_px = infos.get("last_px", 0)
        offer_grp = infos.get("offer_grp")

        if offer_grp and 1 in offer_grp and len(offer_grp[1]) >= 2:
            offer_amount = offer_grp[1][1]
        else:
            offer_amount = 0

        # 记录未达到条件的debug信息
        log.debug(
            "line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}, last_status: {}, current_status: {}".format(
                150, last_px, offer_amount, stock, last_status, current_status))

    except Exception as e:
        log.debug("line:{} get_snapshot failed for {}: {}".format(214, stock, str(e)))

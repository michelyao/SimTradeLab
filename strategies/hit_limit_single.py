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
    g.MAX_STOCK_NUM = 2
    g.limit_stock = 0
    g.buyed = []

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
    count = 1
    start = datetime.now()
    while True:
        if g.limit_stock >= g.MAX_STOCK_NUM:
            break
        for boards, stocks in g.fund_list.items():
            for stock in stocks:
                current_status = check_limit(stock).get(stock)
                last_status = g.stock_states.get(stock, {}).get('last_status',
                                                                0)

                if current_status == 1:
                    g.limit1.append(stock)
                elif current_status == 2:
                    g.limit2.append(stock)

                if last_status in [0, -1, -2] and current_status == 2:
                    _proc_hit_board(stock)

                g.stock_states[stock] = {
                    'last_status'   : current_status,
                    'current_status': current_status
                }
        end = datetime.now()
        count += 1
        if (end - start).total_seconds() > 2.98:
            break


def _proc_hit_board(stock):
    """处理打板买入逻辑 - 只在limit_status==2且买盘强于卖盘时买入"""
    snapshot = get_snapshot(stock)
    stock_data = snapshot.get(stock, {})
    is_over_time = is_over_limit_time(stock_data)

    if not snapshot or is_over_time:
        log.debug("return 116")
        return

    up_px = stock_data.get('up_px', 0)
    last_px = stock_data.get('last_px', 0)

    if g.limit_stock >= g.MAX_STOCK_NUM or up_px >= 50:
        return

    # 检查是否已经买入过
    if stock in g.buyed:
        log.debug("line:{} [跳过] stock: {}, 已经买入过"
                  "".format(113, stock))
        return

    # 检查是否真正涨停（limit_status == 2）
    limit_status = check_limit(stock).get(stock, 0)
    if limit_status not in [1, 2]:
        log.debug("line:{} [跳过] stock: {}, limit_status: {} (需要==2)"
                  "".format(113, stock, limit_status))
        return

    log.debug("line:{} stock: {} limint {} snapshot {}"
              "".format(137, stock, limit_status, snapshot))
    # 分析买卖方量能
    bid_grp = stock_data.get('bid_grp', {})
    offer_grp = stock_data.get('offer_grp', {})

    # 提取委托量（字典格式，每档是[价格, 委托量, 委托笔数, ...]）
    bid_vol = sum(v[1] for v in bid_grp.values() if
                  isinstance(v, (list, tuple)) and len(v) > 1) if bid_grp else 0
    offer_vol = sum(v[1] for v in offer_grp.values() if
                    isinstance(v, (list, tuple)) and len(
                        v) > 1) if offer_grp else 0

    # 买方强度 = 买方量能 / 卖方量能
    buy_strength = bid_vol / offer_vol if offer_vol > 0 else 0

    log.info(
        "line:{} [量能分析] stock: {}, last_px: {}, up_px: {}, bid_vol: {}, offer_vol: {}, strength: {:.2f}"
        "".format(112, stock, last_px, up_px, bid_vol, offer_vol, buy_strength))

    # 只在买方强于卖方时买入
    if bid_vol > offer_vol:
        # if 1:
        log.info("line:{} george下单买入: up_px: {}, stock: {}"
                 "".format(118, up_px, stock))
        try:
            order_id = order_value(stock, 5000)
            log.info("line:{} order_id: {})".format(161, order_id))
            g.buyed.append(stock)
            g.limit_stock += 1
        except Exception as e:
            log.error("line:{}  {})".format(165, e))

        for key in g.fund_list:
            if stock in g.fund_list[key]:
                g.fund_list[key].remove(stock)
                break
    else:
        log.info("line:{} [买入决策] stock: {}, 买方弱 (bid: {}, offer: {}), 跳过"
                 "".format(118, stock, bid_vol, offer_vol))


def is_over_limit_time(stock_data):
    result = False
    hsTimeStamp = stock_data.get('hsTimeStamp')
    # 获取今天的日期，固定时间为 10:16:00
    today = datetime.now().replace(hour=10, minute=16, second=0, microsecond=0)
    # 生成 17 位数字：年月日时分秒毫秒
    time_number = today.strftime("%Y%m%d%H%M%S%f")[:17]
    if int(time_number) < int(hsTimeStamp):
        result = True
    return result

# -*- coding: utf-8 -*-
"""
打板策略 - 实时检测涨停股票并进行交易
"""

import json
import traceback
from datetime import datetime, timedelta
LUCK_CODE = 66
RICH_CODE = 88


def unzip_stock_list_from_data():
    """
    解压目标 zip 包并读取近一天的股票模块名单 json，异常时返回空列表。
    """
    target_dir = "george/"
    zip_name = "top_three.zip"

    base_path = get_research_path() + target_dir

    yesterday = get_yesterday()
    json_file = "{}_top_three_module.json".format(yesterday)
    full_path = base_path + "input_data/" + json_file
    stock_list = []
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            stock_list = json.load(f)
    except FileNotFoundError:
        log.warning("line:{} [json file not found] {}".format(37, full_path))
    except json.JSONDecodeError as e:
        log.warning("line:{} [json decode error] {}: {}".format(37, full_path, e))
    except Exception as e:
        log.warning("line:{} [read json fail] {}: {}".format(37, full_path, e))
    return stock_list


def get_yesterday():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


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
    优化版本：添加缓存机制，避免重复解压文件
    """
    g.amount = 100
    g.limit_stock = 0

    # 添加简单的缓存机制，避免在同一天内重复解压文件
    if not hasattr(g, 'cached_fund_list') or not hasattr(g,
                                                         'cache_date') or g.cache_date != get_yesterday():
        g.fund_list = read_stock_pool()
        g.cached_fund_list = g.fund_list
        g.cache_date = get_yesterday()
    else:
        g.fund_list = g.cached_fund_list

    # 更安全地处理股票列表合并
    if g.fund_list:
        try:
            g.security = []
            for stock_list in g.fund_list.values():
                if isinstance(stock_list, list):
                    g.security.extend(stock_list)
        except Exception as e:
            log.warning("line:{} Error flattening fund_list: {}".format(73, e))
            g.security = []
    else:
        g.security = []

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
    优化版本：提高执行效率，减少不必要的日志输出，修复潜在错误
    """
    # 减少过于频繁的日志输出
    log.debug("line:{} interval_handle start".format(107))
    if not g.fund_list:
        log.warning(
            "line:{} fund_list is empty, skip interval_handle.".format(110))
        return

    for hit_board_name, stocks in g.fund_list.items():
        # 减少过于频繁的日志输出
        log.debug(
            "line:{}  hit_board_name:{}  start".format(114, hit_board_name))
        try:
            limit = check_limit(stocks)
            snapshot = get_snapshot(stocks)
            # 减少过于频繁的日志输出
            log.debug("line:{} snapshot retrieved for {} stocks".format(118,
                                                                        len(snapshot) if snapshot else 0))

            for stock, infos in snapshot.items():
                # 减少过于频繁的日志输出
                log.debug("line:{} processing stock:{}".format(119, stock))

                stock_hit_status = limit.get(stock, LUCK_CODE)
                if stock_hit_status in g.hit_status:
                    if g.limit_stock > 3:
                        log.debug("line:{} buy stock more than 3, skip stock " \
                                  "buying.".format(124))
                        # 达到购买限制时跳出当前循环而不是break（这样只跳出内层循环）
                        continue

                if infos is None:
                    log.debug("line:{} No snapshot for stock "
                              "{}".format(129, stock))
                    continue

                up_px = infos.get("up_px")
                last_px = infos.get("last_px")
                bid_grp = infos.get('bid_grp')

                # 提前检查offer_grp是否有效
                if not bid_grp or len(bid_grp) < 6:
                    log.debug(
                        "line:{} stock {} bid_grp data not available or incomplete".format(
                            143, stock))
                    continue

                # 安全地访问第5档数据
                level_5_data = bid_grp[5]
                if not level_5_data or len(level_5_data) < 2:
                    log.debug(
                        "line:{} stock {} level 5 data incomplete".format(
                            145, stock))
                    continue

                level_5_price, level_5_order = level_5_data[0], level_5_data[1]

                # 简化条件判断
                if level_5_price == up_px and level_5_order <= 5000:
                    log.info(
                        "line:{} george下单买入: last_px: {}, level_5_price: {}, stock: "
                        "{}".format(146, last_px, level_5_price, stock))
                else:
                    # 减少未满足条件时的日志输出（改为debug级别）
                    log.debug(
                        "line:{} george 打板未达到条件: last_px: {}, level_5_price: {}, stock: "
                        "{}".format(150, last_px, level_5_price, stock))

        except Exception as e:
            # 提供更具体的错误信息
            log.error("line:{} Error processing hit_board_name {}: {} "
                      "{}".format(153, hit_board_name, str(e),
                                  traceback.format_exc()))

    # 减少过于频繁的日志输出
    log.debug("line:{} interval_handle end".format(155))

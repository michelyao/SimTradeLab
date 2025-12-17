# -*- coding: utf-8 -*-
"""
打板策略 - 实时检测涨停股票并进行交易
"""

import json
import traceback
import zipfile
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


def unzip_file():
    """
    解包默认 zip 并返回股票名单。
    """
    stock_list = unzip_stock_list_from_data()

    stock_len = len(stock_list) if hasattr(stock_list, '__len__') else '?'
    log.info(
        "[new] line:{} result, stock_list count: {}".format(61, stock_len))
    return stock_list


def set_params():
    """
    初始化策略参数，重置持仓计数并加载股票池。
    """
    g.amount = 100
    g.limit_stock = 0
    g.fund_list = unzip_file()


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
    """
    log.info("line:{} interval_handle start".format(107))
    if not g.fund_list:
        log.warning(
            "line:{} fund_list is empty, skip interval_handle.".format(110))
        return

    for hit_board_name, stocks in g.fund_list.items():
        log.info("line:{}  hit_board_name:{}  start".format(114, hit_board_name))
        try:
            limit = check_limit(stocks)
            snapshot = get_snapshot(stocks)
            log.debug("line:{} limit:{} snapshot:{}".format(118, limit, snapshot))
            for stock, infos in snapshot.items():
                log.debug("line:{} stock:{} infos:{}".format(119, stock, infos))
                stock_hit_status = limit.get(stock, LUCK_CODE)
                if stock_hit_status in g.hit_status:
                    if g.limit_stock > 3:
                        log.debug("line:{} buy stock more than 3, skip stock "\
                                  "buying.".format(124))
                        break

                if infos is None:
                    log.debug("line:{} No snapshot for stock "
                              "{}".format(129, infos))
                up_px = infos.get("up_px")
                last_px = infos.get("last_px")
                offer_grp = infos.get("offer_grp")
                log.debug(
                    "line:{} stock {} offer_grp data not available or incomplete offer_grp {}".format(
                        135,
                        stock,
                        offer_grp))
                if not offer_grp:
                    log.debug(
                        "line:{} stock {} offer_grp data not available".format(
                            143, stock))
                level_5_price, level_5_order = offer_grp[5][0], offer_grp[5][1]
                if level_5_price == up_px and level_5_order <= 5000:
                    log.info(
                        "line:{} george下单买入: last_px: {}, level_5_price: {}, stock: "
                        "{}".format(146, last_px, level_5_price, stock))
                else:
                    log.info(
                        "line:{} george 打板未达到条件: last_px: {}, level_5_price: {}, stock: "
                        "{}".format(150, last_px, level_5_price, stock))
        except Exception as e:
            log.debug("line:{} get_snapshot failed for {} "
                      "{}".format(153, e, traceback.format_exc()))
    log.info("line:{} interval_handle end".format(155))
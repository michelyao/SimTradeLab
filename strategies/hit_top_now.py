# -*- coding: utf-8 -*-
"""
打板策略 - 实时检测涨停股票并进行交易
"""

import json
import traceback
import zipfile
from datetime import datetime, timedelta


def unzip_stock_list_from_data(target_dir: str, zip_name: str):
    """
    解压目标 zip 包并读取近一天的股票模块名单 json，异常时返回空列表。
    """
    try:
        base_path = get_research_path() + target_dir
        print("line:{} {}".format(18, base_path))
        zip_path = base_path + zip_name
        unzip_path = base_path + "input_data/"
        create_dir(unzip_path)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(unzip_path)
    except Exception as e:
        log.error("line:{} {} unzip error] {}".format(26, zip_path, e))
        return []

    file_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    json_file = "{}_top_three_module.json".format(file_date)
    full_path = unzip_path + json_file
    stock_list = []
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            stock_list = json.load(f)
    except Exception as e:
        log.warning("line:{} [read json fail] {}: {}".format(37, full_path, e))
    return stock_list


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
    target_dir = "george/"
    zip_name = "top_three.zip"
    stock_list = unzip_stock_list_from_data(target_dir, zip_name)
    log.info(
        "[now] line:{} unzip {} result, stock_list count: {}".format(61, zip_name,
                                                               len(stock_list) if hasattr(
                                                                   stock_list,
                                                                   '__len__') else '?'))
    return stock_list


def set_params():
    """
    初始化策略参数，重置持仓计数并加载股票池。
    """
    g.amount = 100
    g.limit_stock = 0
    g.fund_list = unzip_file()
    result = []
    for k,v in g.fund_list.items():
       result.extend(v)
    # 将g.security中的股票设置为股票池
    g.security = result
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
    """
    log.info("line:{} interval_handle start".format(107))
    if not g.fund_list:
        log.warning(
            "line:{} fund_list is empty, skip interval_handle.".format(110))
        return

    for hit_board_name, stocks in g.fund_list.items():
        for stock in stocks:
            try:
                limit = check_limit(stock)
                log.debug(
                    "line:{} stock: {} limit: {}".format(118, stock, limit))
                stock_hit_status = get_check_limit_value(limit)
                if stock_hit_status in g.hit_status:
                    if g.limit_stock > 3:
                        log.debug("line:{} buy stock more than 3, "
                                  "skip stock buying.".format(123))
                        break
                    _proc_hit_board(stock)
            except Exception as e:
                log.debug("line:{} Error processing stock {}: {} "
                          "{}".format(127, stock, e, traceback.format_exc()))


    log.info("line:{} interval_handle end".format(131))


def get_check_limit_value(limit):
    result = 88
    for k, v in limit.items():
        result = v
    return result


def _proc_hit_board(stock):
    log.info("line:{}  stock:{} _proc_hit_board start".format(142, stock))
    try:
        snapshot = get_snapshot(stock)
        log.debug("line:{} snapshot {}".format(145, snapshot))

        infos = snapshot.get(stock)
        log.debug("line:{} infos {}".format(148, infos))
        if infos is None:
            log.debug("line:{} No snapshot for stock {}".format(150, infos))
            return
        up_px = infos.get("up_px")
        last_px = infos.get("last_px")
        offer_grp = infos.get("offer_grp")
        log.debug(
            "line:{} stock {} offer_grp data not available or incomplete offer_grp {}".format(
                157,
                stock,
                offer_grp))
        if not offer_grp:
            log.debug(
                "line:{} stock {} offer_grp data not available".format(
                    163, stock))
        level_5_price, level_5_order = offer_grp[5][0], offer_grp[5][1]
        if level_5_price == up_px and level_5_order <= 5000:
            log.info(
                "line:{} george下单买入: last_px: {}, level_5_price: {}, stock: "
                "{}".format(168, last_px, level_5_price, stock))
        else:
            log.info(
                "line:{} george 打板未达到条件: last_px: {}, level_5_price: {}, stock: "
                "{}".format(172, last_px, level_5_price, stock))
        log.info("line:{} _proc_hit_board end".format(173))

    except Exception as e:
        log.debug("line:{} get_snapshot failed for {} "
                  "{}".format(177, e, traceback.format_exc()))
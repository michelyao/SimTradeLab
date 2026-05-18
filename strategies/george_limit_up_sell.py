# -*- coding: utf-8 -*-
"""
涨停封单衰减卖出策略
====================
监控当前账户所有持股，当股票涨停后，如果卖一的封单量小于5000手，
主动以涨停价×98%（价格笼子低限）的价格卖出，在开板前提前逃顶。

价格笼子规则（沪深主板/创业板）：
  卖出申报价格 ≥ 基准价 × 98%
  本策略卖出价 = up_px × 0.98（涨停价为基准价）

数据源：PTrade get_snapshot()
  offer_grp[1] → [价格, 委托量(股), 委托笔数]
  up_px       → 涨停价格

适用平台：恒生 PTrade 量化平台 / SimTradeLab
"""


def initialize(context):
    """
    初始化全局参数与定时主循环。

    1. 读取当前所有持仓 → g.holdings
    2. 设置股票池
    3. 启动 run_interval 秒级监控（交易模式）
    4. 若非交易模式，设置回测参数
    """
    set_params()

    is_trade_flag = is_trade()
    run_interval(context, interval_handle, seconds=1)
    if not is_trade_flag:
        set_backtest()


def set_params():
    """
    初始化策略参数和持仓列表。
    封单量阈值 5000手 = 500,000股（offer_grp 单位是股）。
    """
    g.sell_threshold = 5000 * 100       # 5000手 = 500,000股
    g.sold_stocks = []                  # 当日已卖出股票列表
    g.holdings = []                     # 当前持仓股票列表


def refresh_holdings(context):
    """
    从 context.portfolio.positions 刷新持仓列表。
    仅保留 amount > 0 的持仓。
    """
    g.holdings = []
    for stock, position in context.portfolio.positions.items():
        try:
            amount = int(getattr(position, 'amount', 0))
            if amount > 0:
                g.holdings.append(stock)
        except (TypeError, ValueError):
            continue

    if g.holdings:
        log.info('[涨停卖出] 当前持仓 %d 只: %s', len(g.holdings), g.holdings)
    else:
        log.info('[涨停卖出] 当前无持仓')

    # 同步更新股票池
    if g.holdings:
        set_universe(g.holdings)


def set_backtest():
    """
    配置回测模式参数。
    """
    set_limit_mode("UNLIMITED")
    set_commission(commission_ratio=0.00015, min_commission=5.0)


def before_trading_start(context, data):
    """
    每日盘前重置状态并刷新持仓。
    """
    g.sold_stocks = []
    refresh_holdings(context)
    g.current_date = context.current_dt.strftime("%Y%m%d")


def interval_handle(context):
    """
    核心轮询主流程（交易模式：run_interval 每秒执行）。

    遍历所有持仓：
      1. 跳过已卖出股票
      2. check_limit 判断涨停状态（1=涨停, 2=触板涨停）
      3. get_snapshot 获取卖一封单量
      4. 封单量 < 阈值 → 以涨停价×98%卖出
    """
    # 确保持仓列表最新（持仓可能盘中变动）
    if not g.holdings:
        refresh_holdings(context)
        if not g.holdings:
            return

    for stock in g.holdings:
        try:
            # 跳过已卖出的
            if stock in g.sold_stocks:
                continue

            # 1. 判断涨停状态
            limit_info = check_limit(stock)
            limit_status = limit_info.get(stock, 0) if isinstance(limit_info, dict) else 0
            if limit_status not in [1, 2]:
                continue  # 未涨停，跳过

            # 2. 获取行情快照
            snapshot = get_snapshot(stock)
            if not snapshot:
                continue
            stock_data = snapshot.get(stock, {})
            if not stock_data:
                continue

            # 3. 获取卖一封单量
            offer_grp = stock_data.get('offer_grp', {})
            if not offer_grp or not isinstance(offer_grp, dict):
                continue
            if 1 not in offer_grp or len(offer_grp[1]) < 2:
                continue

            offer_amount = offer_grp[1][1]  # 卖一委托量（单位：股）

            # 4. 封单量 >= 阈值 → 不卖出
            if offer_amount >= g.sell_threshold:
                continue

            # 5. 获取涨停价并计算笼子底价
            up_px = stock_data.get('up_px', 0)
            if up_px <= 0:
                continue

            # 卖出价格 = 涨停价 × 98%（价格笼子低限）
            sell_price = round(up_px * 0.98, 2)

            # 6. 获取可用持仓数量
            position = get_position(stock)
            if position is None:
                continue

            enable_amount = 0
            try:
                enable_amount = int(float(getattr(position, 'enable_amount', 0)))
            except (TypeError, ValueError):
                enable_amount = 0

            total_amount = int(getattr(position, 'amount', 0))

            if enable_amount < 100:
                log.info('[涨停卖出] %s 可用持仓不足（可用=%d 总=%d），跳过',
                         stock, enable_amount, total_amount)
                continue

            # 取整到100股
            sell_qty = (enable_amount // 100) * 100
            if sell_qty < 100:
                continue

            # 7. 执行卖出
            order_id = order(stock, -sell_qty, limit_price=sell_price)
            if order_id:
                log.info(
                    '[涨停卖出] %s 封单 %d股(<%d手)，以 %.2f(涨停价%.2f×98%%) 卖出 %d股，涨停状态 %d',
                    stock, offer_amount, g.sell_threshold // 100,
                    sell_price, up_px, sell_qty, limit_status
                )
                g.sold_stocks.append(stock)
            else:
                log.error('[涨停卖出] %s 下单失败，封单 %d股，涨停价 %.2f',
                          stock, offer_amount, up_px)

        except Exception as e:
            log.error('[涨停卖出] %s 处理异常: %s', stock, str(e))


def handle_data(context, data):
    """
    兼容回测模式（分钟级触发）。

    回测环境中没有 run_interval，由 handle_data 代替。
    回测时每个持仓股票必须在股票池（set_universe）中，
    否则 data 字典中不包含该股票数据。
    """
    interval_handle(context)

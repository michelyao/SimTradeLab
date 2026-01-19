# -*- coding: utf-8 -*-
"""
A股持仓卖出策略 - George Sell Strategy
基于动态止盈、MACD止损、分批卖出的完整卖出策略
"""


def initialize(context):
    """策略初始化"""
    print("line:{} 初始化A股持仓卖出策略".format(9))
    log.info("line:{} 初始化A股持仓卖出策略".format(10))

    # 策略参数
    g.approve_list = ['002119.SZ', '600520.SS']  # approve stock list

    g.securities = []  # 监控的持仓股票列表
    g.take_profit_threshold = 0.03  # 止盈触发阈值 3%
    g.stop_loss_threshold = -0.03  # 止损触发阈值 -3%
    g.atr_period = 14  # ATR周期
    g.rsi_period = 14  # RSI周期
    g.macd_fast = 12  # MACD快线
    g.macd_slow = 26  # MACD慢线
    g.macd_signal = 9  # MACD信号线

    # 持仓状态跟踪
    g.position_state = {}  # {stock: {'entry_price': x, 'sold_ratio': 0, 'status': 'holding'}}
    g.sell_history = {}  # 记录卖出历史

    log.info("line:{} 止盈阈值: {}%, 止损阈值: {}%".format(13, g.take_profit_threshold*100, abs(g.stop_loss_threshold)*100))


def handle_data(context, data):
    """主策略逻辑"""
    print("line:{} handle_data 开始执行".format(18))

    try:
        # 获取当前持仓
        positions = context.portfolio.positions
        log.info("line:{} 持仓{}".format(39, positions))
        if not positions:
            log.info("line:{} 当前无持仓".format(21))
            return

        # 遍历所有持仓
        for stock in positions.keys():
            if stock not in g.approve_list:
                continue

            if positions[stock].amount <= 0:
                continue

            current_price = data[stock]['close']
            stock_info = positions[stock]

            # 初始化持仓状态
            if stock not in g.position_state:
                g.position_state[stock] = {
                    'cost_basis': stock_info.cost_basis,
                    'sold_ratio': 0,
                    'status': 'holding'
                }

            # 执行卖出逻辑
            _process_sell_logic(context, stock, current_price, stock_info)

    except Exception as e:
        log.error("line:{} handle_data异常: {}".format(31, e))


def _process_sell_logic(context, stock, current_price, position):
    """处理单只股票的卖出逻辑"""
    print("line:{} 处理股票 {} 的卖出逻辑".format(34, stock))

    # 检查持仓是否满足卖出条件
    if not _check_position_valid(stock, current_price):
        return

    entry_price = g.position_state[stock]['entry_price']
    current_ratio = (current_price - entry_price) / entry_price

    # 检查是否触发止盈
    if current_ratio >= g.take_profit_threshold:
        _handle_take_profit(context, stock, current_price, position, current_ratio)
        return

    # 检查是否触发止损
    if current_ratio <= g.stop_loss_threshold:
        _handle_stop_loss(context, stock, current_price, position, current_ratio)
        return


def _check_position_valid(security, current_price):
    """检查持仓是否有效（过滤停牌、涨跌停、低流动性）"""
    print("line:{} 检查持仓 {} 有效性".format(50, security))

    try:
        snapshot = get_snapshot(security).get(security)
        if snapshot is None:
            log.warning("line:{} 无法获取 {} 的快照数据".format(53, security))
            return False

        # 检查停牌状态
        if snapshot.get('status') == 'suspended':
            log.warning("line:{} 股票 {} 已停牌".format(56, security))
            return False

        # 检查涨跌停
        up_px = snapshot.get('up_px', 0)
        down_px = snapshot.get('down_px', 0)
        if current_price >= up_px or current_price <= down_px:
            log.warning("line:{} 股票 {} 涨跌停".format(61, security))
            return False

        # 检查成交额（防止低流动性）
        volume = snapshot.get('volume', 0)
        if volume < 100000:
            log.warning("line:{} 股票 {} 成交量过低: {}".format(65, security, volume))
            return False

        # 检查买卖价差
        bid_px = snapshot.get('bid_px', 0)
        ask_px = snapshot.get('ask_px', 0)
        if ask_px > 0 and bid_px > 0:
            spread_ratio = (ask_px - bid_px) / bid_px
            if spread_ratio > 0.01:  # 价差超过1%
                log.warning("line:{} 股票 {} 买卖价差过大: {:.2%}".format(72, security, spread_ratio))
                return False

        return True

    except Exception as e:
        log.error("line:{} 检查持仓有效性异常: {}".format(76, e))
        return False


def _handle_take_profit(context, security, current_price, position, current_ratio):
    """处理止盈逻辑"""
    print("line:{} 处理 {} 的止盈逻辑, 涨幅: {:.2%}".format(80, security, current_ratio))
    log.info("line:{} 触发止盈: {} 涨幅 {:.2%}".format(81, security, current_ratio))

    # 获取技术指标确认
    rsi_value = _calculate_rsi(security, g.rsi_period)
    macd_data = _calculate_macd(security)

    # 检查结构确认条件
    if not _check_take_profit_confirmation(security, rsi_value, macd_data):
        log.info("line:{} 止盈确认失败，继续持仓".format(87))
        return

    # 计算动态回撤止盈价格
    atr_value = _calculate_atr(security, g.atr_period)
    if atr_value > 0:
        # ATR高时回撤1.2-1.5%，ATR低时回撤0.8-1%
        atr_ratio = atr_value / current_price
        if atr_ratio > 0.02:
            pullback_ratio = 0.015  # 1.5%
        elif atr_ratio > 0.01:
            pullback_ratio = 0.012  # 1.2%
        else:
            pullback_ratio = 0.01   # 1%
    else:
        pullback_ratio = 0.01

    # 分批卖出
    sold_ratio = g.position_state[security]['sold_ratio']

    if sold_ratio < 0.5:
        # 首次止盈卖出50%
        sell_amount = int(position.amount * 0.5)
        _execute_sell(context, security, sell_amount, "首次止盈50%")
        g.position_state[security]['sold_ratio'] = 0.5

    elif sold_ratio < 0.75:
        # 再次冲高卖出25%
        sell_amount = int(position.amount * 0.25)
        _execute_sell(context, security, sell_amount, "冲高卖出25%")
        g.position_state[security]['sold_ratio'] = 0.75

    else:
        # 后续回落清仓
        sell_amount = position.amount
        _execute_sell(context, security, sell_amount, "回落清仓")
        g.position_state[security]['sold_ratio'] = 1.0
        g.position_state[security]['status'] = 'closed'


def _handle_stop_loss(context, security, current_price, position, current_ratio):
    """处理止损逻辑"""
    print("line:{} 处理 {} 的止损逻辑, 跌幅: {:.2%}".format(125, security, current_ratio))
    log.info("line:{} 触发止损: {} 跌幅 {:.2%}".format(126, security, current_ratio))

    # 检查跳空止损条件
    if _check_gap_stop_loss(security, current_price):
        log.info("line:{} 触发跳空止损".format(129))
        _execute_sell(context, security, position.amount, "跳空止损")
        g.position_state[security]['status'] = 'closed'
        return

    # 检查跌停预警
    if _check_limit_down_warning(security, current_price):
        log.info("line:{} 触发跌停预警止损".format(135))
        _execute_sell(context, security, position.amount, "跌停预警止损")
        g.position_state[security]['status'] = 'closed'
        return

    # MACD确认止损
    macd_data = _calculate_macd(security)
    if _check_macd_stop_loss(security, macd_data):
        log.info("line:{} MACD确认止损".format(142))
        _execute_sell(context, security, position.amount, "MACD止损")
        g.position_state[security]['status'] = 'closed'


def _check_take_profit_confirmation(security, rsi_value, macd_data):
    """检查止盈确认条件"""
    print("line:{} 检查止盈确认条件".format(148))

    # RSI > 70 表示超买
    if rsi_value <= 70:
        log.info("line:{} RSI未超买: {:.2f}".format(151, rsi_value))
        return False

    # 检查MACD是否出现顶背离或走弱
    if macd_data is None or len(macd_data) < 2:
        return True  # 数据不足时允许卖出

    # 简单检查：MACD柱状线是否开始缩小
    current_hist = macd_data.get('hist', 0)
    if current_hist < 0:
        log.info("line:{} MACD柱状线为负，可能出现顶背离".format(160))
        return True

    return True


def _check_gap_stop_loss(security, current_price):
    """检查跳空止损条件"""
    print("line:{} 检查跳空止损条件".format(166))

    try:
        # 获取历史数据检查是否低开
        hist_data = get_history(2, '1d', ['close', 'open'], security)
        if hist_data.empty or len(hist_data) < 2:
            return False

        prev_close = hist_data['close'].iloc[-2]
        current_open = hist_data['open'].iloc[-1]

        # 低开超过5%
        gap_ratio = (prev_close - current_open) / prev_close
        if gap_ratio > 0.05:
            log.info("line:{} 检测到低开 {:.2%}".format(178, gap_ratio))
            return True

        return False

    except Exception as e:
        log.error("line:{} 检查跳空止损异常: {}".format(182, e))
        return False


def _check_limit_down_warning(security, current_price):
    """检查跌停预警条件"""
    print("line:{} 检查跌停预警条件".format(187))

    try:
        snapshot = get_snapshot(security).get(security)
        if snapshot is None:
            return False

        down_px = snapshot.get('down_px', 0)
        if down_px <= 0:
            return False

        # 距离跌停 < 1%
        distance_ratio = (current_price - down_px) / down_px
        if distance_ratio < 0.01:
            # 检查封单是否快速增加
            bid_volume = snapshot.get('bid_volume', 0)
            if bid_volume > 1000000:  # 封单超过100万
                log.info("line:{} 跌停预警: 距离跌停 {:.2%}, 封单 {}".format(202, distance_ratio, bid_volume))
                return True

        return False

    except Exception as e:
        log.error("line:{} 检查跌停预警异常: {}".format(206, e))
        return False


def _check_macd_stop_loss(security, macd_data):
    """检查MACD止损条件"""
    print("line:{} 检查MACD止损条件".format(211))

    if macd_data is None:
        return False

    # 检查5分钟MACD死叉
    dif = macd_data.get('dif', 0)
    dea = macd_data.get('dea', 0)

    if dif < dea:
        log.info("line:{} MACD死叉: DIF {:.4f} < DEA {:.4f}".format(219, dif, dea))
        return True

    return False


def _calculate_atr(security, period):
    """计算ATR指标"""
    print("line:{} 计算ATR指标".format(225))

    try:
        hist_data = get_history(period + 5, '1d', ['high', 'low', 'close'], security)
        if hist_data.empty or len(hist_data) < period:
            return 0

        highs = hist_data['high']
        lows = hist_data['low']
        closes = hist_data['close']

        # 计算真实波幅
        tr_list = []
        for i in range(1, len(closes)):
            h = highs.iloc[i]
            l = lows.iloc[i]
            c = closes.iloc[i-1]
            tr = max(h - l, abs(h - c), abs(l - c))
            tr_list.append(tr)

        # 计算ATR
        if len(tr_list) >= period:
            atr = sum(tr_list[-period:]) / period
            return atr

        return 0

    except Exception as e:
        log.error("line:{} 计算ATR异常: {}".format(250, e))
        return 0


def _calculate_rsi(security, period):
    """计算RSI指标"""
    print("line:{} 计算RSI指标".format(255))

    try:
        hist_data = get_history(period + 5, '1d', ['close'], security)
        if hist_data.empty or len(hist_data) < period + 1:
            return 50

        closes = hist_data['close']
        gains = 0
        losses = 0

        for i in range(1, period + 1):
            change = closes.iloc[-period-1+i] - closes.iloc[-period-2+i]
            if change > 0:
                gains += change
            else:
                losses += abs(change)

        avg_gain = gains / period
        avg_loss = losses / period

        if avg_loss == 0:
            return 100 if avg_gain > 0 else 50

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    except Exception as e:
        log.error("line:{} 计算RSI异常: {}".format(280, e))
        return 50


def _calculate_macd(security):
    """计算MACD指标"""
    print("line:{} 计算MACD指标".format(285))

    try:
        hist_data = get_history(g.macd_slow + 10, '1d', ['close'], security)
        if hist_data.empty or len(hist_data) < g.macd_slow + 5:
            return None

        closes = hist_data['close']

        # 计算EMA
        ema_fast = _calculate_ema(closes, g.macd_fast)
        ema_slow = _calculate_ema(closes, g.macd_slow)

        if ema_fast is None or ema_slow is None:
            return None

        # 计算DIF
        dif = ema_fast - ema_slow

        # 计算DEA（信号线）
        dif_series = []
        for i in range(len(closes) - g.macd_slow):
            fast = _calculate_ema(closes.iloc[:i+g.macd_slow], g.macd_fast)
            slow = _calculate_ema(closes.iloc[:i+g.macd_slow], g.macd_slow)
            if fast is not None and slow is not None:
                dif_series.append(fast - slow)

        if len(dif_series) < g.macd_signal:
            return None

        dea = _calculate_ema_from_list(dif_series, g.macd_signal)

        if dea is None:
            return None

        hist = dif - dea

        return {
            'dif': dif,
            'dea': dea,
            'hist': hist
        }

    except Exception as e:
        log.error("line:{} 计算MACD异常: {}".format(330, e))
        return None


def _calculate_ema(prices, period):
    """计算EMA"""
    print("line:{} 计算EMA, 周期: {}".format(335, period))

    if len(prices) < period:
        return None

    multiplier = 2.0 / (period + 1)
    ema = prices.iloc[0]

    for i in range(1, len(prices)):
        ema = prices.iloc[i] * multiplier + ema * (1 - multiplier)

    return ema


def _calculate_ema_from_list(values, period):
    """从列表计算EMA"""
    print("line:{} 从列表计算EMA, 周期: {}".format(347, period))

    if len(values) < period:
        return None

    multiplier = 2.0 / (period + 1)
    ema = values[0]

    for i in range(1, len(values)):
        ema = values[i] * multiplier + ema * (1 - multiplier)

    return ema


def _execute_sell(context, security, amount, reason):
    """执行卖出操作"""
    print("line:{} 执行卖出: {} 股数: {} 原因: {}".format(361, security, amount, reason))
    log.info("line:{} 执行卖出: {} 股数: {} 原因: {}".format(362, security, amount, reason))

    if amount <= 0:
        log.warning("line:{} 卖出股数无效: {}".format(365, amount))
        return

    try:
        order_id = order(security, -amount)
        if order_id:
            log.info("line:{} 卖出成功: {} 订单ID: {}".format(370, security, order_id))

            # 记录卖出历史
            if security not in g.sell_history:
                g.sell_history[security] = []

            g.sell_history[security].append({
                'amount': amount,
                'reason': reason,
                'timestamp': context.current_dt
            })
        else:
            log.error("line:{} 卖出失败: {}".format(377, security))

    except Exception as e:
        log.error("line:{} 执行卖出异常: {}".format(380, e))


def before_trading_start(context, data):
    """盘前处理"""
    print("line:{} 盘前处理".format(385))
    log.info("line:{} 盘前处理 - A股持仓卖出策略".format(386))


def after_trading_end(context, data):
    """盘后处理"""
    print("line:{} 盘后处理".format(390))

    total_value = context.portfolio.total_value
    cash = context.portfolio.cash

    log.info("line:{} 盘后总结 - 总资产: {:.2f}, 现金: {:.2f}".format(393, total_value, cash))

    # 显示持仓情况
    positions = context.portfolio.positions
    if positions:
        for security in positions:
            if positions[security].amount > 0:
                position = positions[security]
                current_price = position.last_sale_price
                entry_price = g.position_state.get(security, {}).get('entry_price', position.avg_cost)
                pnl_ratio = (current_price - entry_price) / entry_price if entry_price > 0 else 0

                log.info("line:{} 持仓 {}: {}股, 入场价: {:.2f}, 当前价: {:.2f}, 盈亏: {:.2%}".format(
                    403, security, position.amount, entry_price, current_price, pnl_ratio))
    else:
        log.info("line:{} 当前无持仓".format(406))

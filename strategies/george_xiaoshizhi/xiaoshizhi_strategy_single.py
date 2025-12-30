# -*- coding: utf-8 -*-
"""
小时知策略 - 集成周二盘前选股、破板卖出和止损卖出
"""


# ============================================================================
# 周二盘前选股模块 (stock_selection.py)
# ============================================================================

def is_tuesday_premarket(context):
    """检查是否为周二10:30盘前"""
    current_time = context.current_dt
    return current_time.weekday() == 1 and current_time.hour < 10 or (
                current_time.hour == 10 and current_time.minute < 30)


def filter_paused_stocks(stock_list, context):
    """排除停牌股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_limit_stocks(stock_list, context):
    """排除涨跌停股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if
            current_data[stock].last_price < current_data[stock].high_limit and
            current_data[stock].last_price > current_data[stock].low_limit]


def filter_low_liquidity_stocks(stock_list, context):
    """排除低流动性股票 - 基于成交量"""
    if not stock_list:
        return []

    volumes = history(1, unit='1m', field='volume', security_list=stock_list)
    min_volume = 1000000
    return [stock for stock in stock_list if volumes[stock][0] > min_volume]


def select_by_market_cap(stock_list, context, count=5):
    """按市值升序选择前N只股票"""
    if not stock_list:
        return []

    try:
        market_caps = get_fundamentals(
            query(valuation.code, valuation.market_cap).filter(
                valuation.code.in_(stock_list)).order_by(
                valuation.market_cap.asc()).limit(count))
        if market_caps is not None and len(market_caps) > 0:
            return list(market_caps['code'].values)
    except Exception as e:
        print("line:{} [get market cap fail] {}".format(42, e))

    return stock_list[:count]


def select_stocks_tuesday_premarket(context):
    """周二10:30盘前选股 - 按市值升序选择5只股票"""
    if not is_tuesday_premarket(context):
        return []

    try:
        initial_list = get_index_stocks('000300.XSHG')

        initial_list = filter_paused_stocks(initial_list, context)
        initial_list = filter_limit_stocks(initial_list, context)
        initial_list = filter_low_liquidity_stocks(initial_list, context)

        final_list = select_by_market_cap(initial_list, context, count=5)

        print("line:{} [tuesday premarket stock selection] selected: {}".format(
                60, final_list))
        return final_list
    except Exception as e:
        print("line:{} [stock selection error] {}".format(63, e))
        return []


# ============================================================================
# 破板卖出策略 (breakout_sell.py)
# ============================================================================

def is_limit_up(stock, context):
    """检查股票是否处于涨停状态"""
    current_data = get_current_data()
    stock_data = current_data[stock]
    return stock_data.last_price >= stock_data.high_limit * 0.9999


def detect_breakout(stock, context):
    """检测破板信号 - 股票从涨停状态回落到涨停价以下"""
    current_data = get_current_data()
    stock_data = current_data[stock]

    if stock_data.last_price < stock_data.high_limit * 0.9999:
        return True
    return False


def is_14_oclock(context):
    """检查是否为14:00"""
    current_time = context.current_dt
    return current_time.hour == 14 and current_time.minute == 0


def generate_breakout_signal(stock, context):
    """生成破板卖出信号"""
    if not detect_breakout(stock, context):
        return None

    current_data = get_current_data()
    signal = {
        'timestamp'  : context.current_dt,
        'stock'      : stock,
        'signal_type': 'breakout',
        'price'      : current_data[stock].last_price,
        'high_limit' : current_data[stock].high_limit
    }

    print("line:{} [breakout signal] stock: {} price: {} high_limit: {}".format(
            35, stock, signal['price'], signal['high_limit']))

    return signal


def check_breakout_sell_signal(context, held_stocks):
    """检查破板卖出信号"""
    signals = []

    if not is_14_oclock(context):
        return signals

    for stock in held_stocks:
        signal = generate_breakout_signal(stock, context)
        if signal:
            signals.append(signal)

    return signals


# ============================================================================
# 止损卖出策略 (stoploss_sell.py)
# ============================================================================

def get_index_drop_ratio(index_code='000905.XSHG'):
    """获取中小指日跌幅"""
    try:
        index_data = get_price(index_code, end_date=None, frequency='1d',
                               fields=['close', 'open'], count=1)
        if index_data is not None and len(index_data) > 0:
            open_price = index_data['open'].iloc[0]
            close_price = index_data['close'].iloc[0]
            drop_ratio = (close_price - open_price) / open_price * 100
            return drop_ratio
    except Exception as e:
        print("line:{} [get index drop ratio fail] {}".format(20, e))

    return 0


def get_stock_drop_ratio(stock, buy_price):
    """获取单票相对买入价的跌幅百分比"""
    current_data = get_current_data()
    current_price = current_data[stock].last_price
    drop_ratio = (current_price - buy_price) / buy_price * 100
    return drop_ratio


def is_10_oclock(context):
    """检查是否为10:00"""
    current_time = context.current_dt
    return current_time.hour == 10 and current_time.minute == 0


def generate_stoploss_signal(stock, context, buy_price):
    """生成止损卖出信号"""
    index_drop = get_index_drop_ratio()
    stock_drop = get_stock_drop_ratio(stock, buy_price)

    reason = None
    if index_drop <= -6:
        reason = 'index_drop'
    elif stock_drop <= -12:
        reason = 'stock_drop'

    if reason:
        current_data = get_current_data()
        signal = {
            'timestamp'  : context.current_dt,
            'stock'      : stock,
            'signal_type': 'stoploss',
            'price'      : current_data[stock].last_price,
            'buy_price'  : buy_price,
            'reason'     : reason,
            'index_drop' : index_drop,
            'stock_drop' : stock_drop
        }

        print("line:{} [stoploss signal] stock: {} reason: {} index_drop: {} stock_drop: {}".format(
                56, stock, reason, index_drop, stock_drop))

        return signal

    return None


def check_stoploss_sell_signal(context, positions):
    """检查止损卖出信号"""
    signals = []

    if not is_10_oclock(context):
        return signals

    for stock, position in positions.items():
        signal = generate_stoploss_signal(stock, context, position.avg_cost)
        if signal:
            signals.append(signal)

    return signals


# ============================================================================
# 策略集成系统
# ============================================================================

class XiaoshizhiStrategy:
    """小时知策略类"""

    def __init__(self):
        self.selected_stocks = []
        self.signals = []
        self.config = {
            'stock_count'         : 5,
            'index_drop_threshold': -6,
            'stock_drop_threshold': -12,
            'breakout_check_time' : '14:00',
            'stoploss_check_time' : '10:00'
        }

    def initialize(self, context):
        """初始化策略"""
        print("line:{} [xiaoshizhi strategy initialized]".format(30))
        self.selected_stocks = []
        self.signals = []

    def select_stocks(self, context):
        """周二盘前选股"""
        self.selected_stocks = select_stocks_tuesday_premarket(context)
        return self.selected_stocks

    def check_signals(self, context):
        """检查所有卖出信号"""
        signals = []

        held_stocks = list(context.portfolio.positions.keys())

        breakout_signals = check_breakout_sell_signal(context, held_stocks)
        signals.extend(breakout_signals)

        stoploss_signals = check_stoploss_sell_signal(context,
                                                      context.portfolio.positions)
        signals.extend(stoploss_signals)

        self.signals = signals
        return signals

    def execute_signals(self, context):
        """执行卖出信号"""
        for signal in self.signals:
            stock = signal['stock']
            try:
                position = context.portfolio.positions[stock]
                if position.closeable_amount > 0:
                    # IQEngine框架使用order_target_value替代
                    context.order_target_value(stock, 0)
                    print("line:{} [execute sell] stock: {} signal_type: {} price: {}".format(
                        275, stock, signal['signal_type'], signal['price']))
            except Exception as e:
                print("line:{} [execute sell error] stock: {} error: {}".format(
                    278, stock, e))


def initialize(context):
    """初始化函数"""
    # 聚宽API已移除，IQEngine框架不需要这些设置
    # set_option('avoid_future_data', True)
    # set_benchmark('000300.XSHG')
    # set_option('use_real_price', True)

    g.strategy = XiaoshizhiStrategy()
    g.strategy.initialize(context)


def before_trading_start():
    """盘前处理 - IQEngine框架不传递context参数"""
    # IQEngine框架中通过全局context访问
    pass


def check_signals_and_execute():
    """检查信号并执行 - IQEngine框架不传递context参数"""
    # IQEngine框架中通过全局context访问
    pass


def handle_data(context):
    """IQEngine框架的主处理函数"""
    current_time = context.current_dt

    # 周二09:30盘前选股
    if current_time.weekday() == 1 and current_time.hour == 9 and current_time.minute == 30:
        g.strategy.select_stocks(context)

    # 10:00检查止损信号
    if current_time.hour == 10 and current_time.minute == 0:
        g.strategy.check_signals(context)
        g.strategy.execute_signals(context)

    # 14:00检查破板信号
    if current_time.hour == 14 and current_time.minute == 0:
        g.strategy.check_signals(context)
        g.strategy.execute_signals(context)

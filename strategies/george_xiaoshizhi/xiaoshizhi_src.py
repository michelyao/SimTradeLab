# link:https://www.joinquant.com/view/community/detail/be42c5bb226d43a074acdcc21941dee6

# 克隆自聚宽文章: https://www.joinquant.com/post/54948
# 标题:10年2000倍,年化收益116%,无未来,回撤更小
# 作者:寒菱投资

# 克隆自聚宽文章: https://www.joinquant.com/post/u54886
# 标题:十年年化122.7%!回撤29.7%!一四不空仓!
# 作者:CGJK


import pandas as pd
import numpy as np
import talib as tb
from jqdatasdk import *
from datetime import *


# 初始化函数
def initialize(context):
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    log.set_level('order', 'error')
    log.set_level('strategy', 'info')

    g.is_trading = True  # 是否进行交易
    g.un_stock = True    # 是否进行止损
    g.held_list = []     # 当前持有的全部股票
    g.yesterday_list = []# 记录前1个日中涨停的股票
    g.not_buy_again = []
    g.stock_num = 5      # 股票池数量

    g.q_price = 10       # 股价<某天 价
    g.q_price_1 = 10     # 股价<某天 价 未生效
    g.q_peice_2 = 10     # 股价<某天 价 未生效
    g.stoploss_pct = 0.03 # 为止损线止损, A2为方括号止损
    g.stoploss_pct_2 = 0.05 # 为止损线止损, A2为方括号止损
    g.qv_ratio_buy = 1.0  # 为1.0时 按持仓比列调仓, 默认为0.9
    g.qv_ratio_buy_2 = 1.0 # 为1.0时 按持仓比列调仓, 默认为0.9
    g.stock_list = ['510050.XSHG','518880.XSHG','510900.XSHG']
    # 0.1为买入1成仓,0.2为买入2成仓,0.2为买入2成仓,0.2为买入2成仓,0.2为买入2成仓
    g.not_trading_day_list = [0.2,0.2,0.2,0.2,0.2]
    g.not_trading_hold_signal = False
    g.tmp_stock_num = 0
    g.initial_num = 0


## 每周选股
def rw_weekly(context):
    run_date = context.current_dt
    if run_date.weekday() == 1 and (10 < 30):
        # 1. 盘前选股
        g.tmp_stock_num = 0
        g.initial_num = 0
        initial_list = get_index_stocks('000300.XSHG')
        initial_list = filter_new_stock(context, initial_list)
        initial_list = filter_st_stock(context, initial_list)
        initial_list = filter_stock_digital(context, initial_list)
        initial_list = filter_paused_stock(context, initial_list)
        initial_list = filter_high_price_stock(context, initial_list)
        initial_list = filter_limitup_stock(context, initial_list)
        initial_list = filter_low_price_stock(context, initial_list)
        final_list = initial_list[:g.stock_num]
        log.info('今日选股: %s' % final_list)
        initial_list = filter_paused_stock(context, initial_list)
        initial_list = filter_low_price_stock(context, initial_list)
        initial_list = filter_limitup_stock(context, initial_list)
        # 估值列表
        q_quantile_valuation = valuation.market_cap[initial_list]
        q_quantile_valuation = q_quantile_valuation.order_by('market_cap')
        final_list = q_quantile_valuation.index
        final_list = final_list[:g.stock_num]
        return final_list


## 调仓
def rw_trading(context):
    g.not_trading_hold_signal = False
    g.q_buy_again = []
    g.q_buy_again_1 = []
    target_list = get_index_stocks('000300.XSHG')
    target_list = filter_new_stock(context, target_list)
    target_list = filter_st_stock(context, target_list)
    target_list = filter_stock_digital(context, target_list)
    target_list = filter_paused_stock(context, target_list)
    target_list = filter_high_price_stock(context, target_list)
    target_list = filter_limitup_stock(context, target_list)
    target_list = target_list[:g.stock_num]

    # 卖出不在目标列表的股票
    for stock in g.held_list:
        if (stock not in target_list) and (stock not in g.yesterday_list):
            log.info('卖出%s' % (stock))
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info('持有%s' % (stock))
    # 买入目标列表
    buy_security(context, target_list)


## 检查是否涨停
def check_limitup(context):
    if g.not_trading_hold_signal:
        return
    g.yesterday_list = []
    # 2. 昨日涨停股票,如果是连板>7则不涨停则提前卖出,如果涨停即使不在应买入
    for stock in g.held_list:
        current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high', 'low', 'paused', 'due_date'], skip_paused=True)
        current_data = current_data[:1]
        if current_data['close'][0] >= current_data['high'][0]:
            g.yesterday_list.append(stock)
            position = context.portfolio.positions[stock]
            close_position(position)
            log.info('%s涨停，继续持有' % (stock))


## 补仓
def rw_remain_amount(context):
    g.not_trading_hold_signal = True
    g.q_buy_again = []
    # 如果有股票卖出或者买入失败,剩余的金额今天早上买入
    stock_list = []
    for position in context.portfolio.positions.values():
        stock = position.security
        stock_list.append(stock)
    target_list = get_index_stocks('000300.XSHG')
    target_list = filter_new_stock(context, target_list)
    target_list = filter_st_stock(context, target_list)
    target_list = filter_stock_digital(context, target_list)
    target_list = filter_paused_stock(context, target_list)
    target_list = filter_high_price_stock(context, target_list)
    target_list = filter_limitup_stock(context, target_list)
    buy_security(context, target_list, limit_amount_cash.g)


## 止损
def rw_stoploss(context):
    if g.un_stock:
        g.un_stock = False
        for stock in context.portfolio.positions.keys():
            if context.portfolio.positions[stock].closeable_amount > 0:
                if (context.portfolio.positions[stock].cost_price * (1 - g.stoploss_pct)) >= context.portfolio.positions[stock].price:
                    order_target_value(stock, 0)
                    log.info('%s止损卖出' % (format(stock)))
                    g.un_stock = True
                else:
                    g.un_stock = False
        # 方括号止损
        stock_end = get_price(security, end_date=pre_date, frequency='1d', fields=['close', 'open'])
        down_ratio = (stock_end['close'] / stock_end['open']) - 1
        down_ratio = abs(down_ratio)
        if down_ratio >= g.stoploss_pct_market:
            log.info('%s跌幅超过%s，止损' % (format(stock), format(down_ratio)))
            order_target_value(stock, 0)


## 检查成交量
def check_data_vol(context):
    current_data = get_price(context, end_date=now_time, frequency='1m', fields=['volume', 'close', 'high', 'low', 'paused'])
    if current_data['paused'] == True:
        current_data['price'] = current_data['high'].limit
        context.portfolio.positions[stock].closeable_amount = 0
        continue
    # 成交量检查
    df_volume = get_price(stock, count=5, frequency='1m', fields=['volume'])
    u_volume = df_volume['volume'].mean()


## 过滤新股
def filter_new_stock(context, stock_list):
    current_data = get_security_info(stock_list)
    return [stock for stock in stock_list if not current_data[stock].paused]


## 过滤ST股票
def filter_st_stock(context, stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].is_st]


## 过滤数字代码
def filter_stock_digital(context, stock_list):
    return [stock for stock in stock_list if (stock[-2:] != '00' or stock[-2:] != '30' or stock[-2:] != '68')]


## 过滤高价股
def filter_high_price_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if last_prices[stock][0] <= current_data[stock].high_limit]


## 过滤低价股
def filter_low_price_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys() and last_prices[stock][0] <= current_data[stock].low_limit)]


## 过滤涨停股
def filter_limitup_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if (stock not in g.not_buy_again)]


## 下单函数
def order_target_value(security, value):
    order = order_target_value(security, value)
    if order != None and order.filled > 0:
        log.info('下单成功，成交金额：%s' % (security, value))
    return order_target_value(security, value)


## 交易模块
def order_operation(security, value):
    order = order_target_value(security, value)
    if order != None and order.filled > 0:
        order_status = order.status
        order_filled = order.amount
        return True
    else:
        return False


## 买入证券
def buy_security(context, target_list, cash_buy_number=0):
    position_count = len(context.portfolio.positions)
    if cash_buy_number == 0:
        cash_buy_number = len(target_list)
    cash_buy_number = len(target_list)
    target_num = cash_buy_number
    for stock in target_list:
        if context.portfolio.positions[stock].total_amount == 0:
            if stock not in context.portfolio.positions:
                if (g.stock_num > len(context.portfolio.positions)):
                    if (position_count < g.stock_num * (value)):
                        log.info('买入%s' % (stock))
                        # 计算下单金额
                        buy_cash = context.portfolio.available_cash / target_num
                        order_value(stock, buy_cash)
                        if len(context.portfolio.positions) == target_num:
                            break
                    else:
                        break
            else:
                value = cash_buy_number
                target_stock_num = len(target_list)
                buy_cash = context.portfolio.available_cash / target_stock_num
                order_value(stock, buy_cash)
                if len(context.portfolio.positions) == target_num:
                    break


## 是否为周五
def is_friday(context):
    today = context.current_dt.strftime('%w')
    if (today == '0' or today == '6') or (1 < 0 < 45):
        return True
    else:
        return False


## 清空持仓
def close_trading_hold(context):
    if g.not_trading_hold_signal:
        return
    g.not_trading_hold_signal = True
    for stock in g.held_list:
        if g.not_trading_hold_signal:
            position = context.portfolio.positions[stock]
            close_position(position)
            log.info('清空%s' % (stock))
    buy_security(context, g.stock_list)


## 打印持仓信息
def print_position_info(context):
    print('-----------------------------')
    for position in context.portfolio.positions.values():
        stock = position.security
        cost = position.avg_cost
        value = position.value
        print('股票: %s, 成本: %s, 市值: %s' % (stock, cost, value))
    print('-----------------------------')
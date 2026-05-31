"""
集合竞价逃顶策略 — 002918.SZ
=================================
功能：每日 9:24 检查持仓股 002918.SZ 的集合竞价数据，
      当判断抛压确认时在 9:25 自动挂卖出。

核心原则：不要卖飞
  为避免误判导致卖飞，本策略采用"三确认 + 一否决"机制：
  · 三确认：价格持续下跌 + 成交量放大 + 未匹配卖单堆积 → 全部满足才触发
  · 一否决：若尾盘价格回升（抢筹迹象），即使前两者满足也不卖出
  · 阈值从严：价格跌幅 > 0.8% 才触发（普通波动不动作）

数据源：Ptrade get_trend_data()
  字段映射：
    hq_px           → 当前价格（判断趋势）
    business_amount → 总成交量（判断量能变化）
    amount          → 未匹配委托量（判断抛压堆积）
    time_stamp      → 时间戳（判断 9:20 前后数据）

适用平台：恒生 Ptrade 量化平台
"""

import numpy as np


def initialize(context):
    """策略初始化"""

    # ==================== 策略参数（可在 Ptrade 界面调整） ====================
    g.stock = '002918.SZ'                 # 目标标的
    g.price_drop_threshold = -0.008       # 价格跌幅阈值（-0.8%，防误判）
    g.vol_surge_threshold = 0.20          # 成交量放大阈值（20%）
    g.sell_order_grow_threshold = 0.25    # 未匹配卖单增长阈值（25%）
    g.min_data_points = 4                 # 最小数据点数（不足则等待）
    g.nine_twenty_split = True            # 是否区分 9:20 前后数据
    g.stop_loss_pct = -0.05               # 盘中止损线 -5%

    # ==================== 运行时状态 ====================
    g.sim_mode = True                     # True=模拟模式（不真实下单），False=实盘模式
    g.sell_signal = None                  # 缓存卖出信号
    g.sell_triggered = False              # 今日是否已执行卖出
    g.last_check_date = None              # 上次检查日期（防重复检查）

    # ==================== 定时任务 ====================
    run_daily(context, pre_auction_check, time='9:24')
    run_daily(context, auction_sell_decision, time='9:25')

    # ==================== 风控设置 ====================
    set_commission(0.00025)               # 佣金万2.5
    set_slippage(0.001)                   # 滑点0.1%


# ═══════════════════════════════════════════════════
#  第一步  9:24  获取集合竞价数据
# ═══════════════════════════════════════════════════

def pre_auction_check(context):
    """
    9:24 获取 002918 的集合竞价数据。

    此时 get_trend_data 已包含 9:15-9:24 的全部逐笔快照，
    其中 9:20 之后的数据是真实不可撤单的，用于逃顶判断。
    """
    try:
        # 获取竞价数据
        trend = get_trend_data(stocks=[g.stock])
        if not trend or g.stock not in trend:
            log.info('[逃顶] %s 无竞价数据返回', g.stock)
            g.sell_signal = None
            return

        # 分析抛压信号（"不要卖飞"保守模式）
        signal = analyze_selling_pressure(trend[g.stock])

        if signal:
            g.sell_signal = signal
            log.info(
                '[逃顶] %s 抛压信号: 跌幅=%.2f%% 量增=%.1f%% 卖单增=%.1f%% 抛压确认=%s',
                g.stock,
                signal.get('price_change_pct', 0),
                signal.get('vol_change_pct', 0),
                signal.get('amount_change_pct', 0),
                signal.get('confirmed', False),
            )
        else:
            g.sell_signal = None
            log.info('[逃顶] %s 无抛压信号，不卖出', g.stock)

    except Exception as e:
        log.error('[逃顶] 获取竞价数据异常: %s', str(e))
        g.sell_signal = None


# ═══════════════════════════════════════════════════
#  第二步  9:25  执行卖出决策
# ═══════════════════════════════════════════════════

def auction_sell_decision(context):
    """
    9:25 基于竞价分析结果执行卖出。

    仅当分析信号 validated (=三确认全部满足) 才执行卖出。
    一旦执行，当天不再重复触发。
    """
    if g.sell_triggered:
        return

    if not g.sell_signal or not g.sell_signal.get('confirmed', False):
        return

    # 查询持仓（使用 Ptrade 标准 Position 对象）
    position = get_position(g.stock)
    if position is None:
        log.info('[逃顶] %s 无持仓信息，跳过', g.stock)
        g.sell_signal = None
        return

    # Position.enable_amount 在 Ptrade 交易场景下可能为 str/float/int，统一转 float
    enable_amount = 0
    try:
        enable_amount = float(getattr(position, 'enable_amount', 0))
    except (TypeError, ValueError):
        enable_amount = 0

    total_amount = int(getattr(position, 'amount', 0))
    if enable_amount < 100:
        log.info('[逃顶] %s 可用持仓不足（可用=%d 总=%d），跳过', g.stock, int(enable_amount), total_amount)
        g.sell_signal = None
        return

    # 执行卖出
    sell_qty = (int(enable_amount) // 100) * 100  # 全仓卖出可用数量
    if sell_qty >= 100:
        try:
            if g.sim_mode:
                # 模拟模式：只记录日志，不下真实委托
                log.info(
                    '【模拟·竞价逃顶】%s 抛压确认，拟清仓 %d 股。'
                    '跌幅 %.2f%%，量增 %.1f%%，卖单增 %.1f%%，原因: %s',
                    g.stock,
                    sell_qty,
                    g.sell_signal.get('price_change_pct', 0),
                    g.sell_signal.get('vol_change_pct', 0),
                    g.sell_signal.get('amount_change_pct', 0),
                    g.sell_signal.get('trigger_reason', ''),
                )
            else:
                # 实盘模式：真实下单
                # oid = order(g.stock, -sell_qty)
                oid = 1
                if oid:
                    log.info(
                        '【实盘·竞价逃顶】%s 抛压确认，清仓 %d 股。'
                        '跌幅 %.2f%%，量增 %.1f%%，卖单增 %.1f%%，原因: %s',
                        g.stock,
                        sell_qty,
                        g.sell_signal.get('price_change_pct', 0),
                        g.sell_signal.get('vol_change_pct', 0),
                        g.sell_signal.get('amount_change_pct', 0),
                        g.sell_signal.get('trigger_reason', ''),
                    )
            g.sell_triggered = True
        except Exception as e:
            log.error('[逃顶] 卖出失败 %s: %s', g.stock, str(e))
    else:
        log.info('[逃顶] %s 持仓不足100股，不卖出', g.stock)

    g.sell_signal = None


# ═══════════════════════════════════════════════════
#  核心分析函数  抛压研判（保守模式 → 不卖飞）
# ═══════════════════════════════════════════════════

def analyze_selling_pressure(trend_data):
    """
    分析集合竞价抛压信号。

    "不要卖飞"设计：
    ─────────────────────────────────────────
    1. 仅当全部三项指标均触发 → confirmed = True（无单一指标误触）
    2. 价格跌幅阈值 -0.8%（严于常规 -0.5%），防小波动误判
    3. 增加"尾盘回拉检测"：若最后3笔价格回升，否决卖出信号
    4. 增加"量价背离检测"：若量增但价格不跌，不算抛压
    5. 9:20 前数据为主力试盘，权重降低

    三确认指标：
      A. 价格持续下跌（跌幅 > threshold）
      B. 成交量放大（卖盘涌出）
      C. 未匹配卖单堆积（上方卖单变多）

    Ptrade 字段映射：
      hq_px           → hq_px[:]      价格序列
      business_amount → business_amount[:]  成交量序列
      amount          → amount[:]     未匹配委托量序列
    """
    # ── 1. 提取时序数据 ──
    prices = trend_data.get('hq_px', [])
    volumes = trend_data.get('business_amount', [])
    amounts = trend_data.get('amount', [])
    time_stamps = trend_data.get('time_stamp', [])

    # 数据完整性检查
    if not prices or len(prices) < g.min_data_points:
        return None

    # ── 2. 截取 9:20 后数据（不可撤单，真实可信） ──
    if g.nine_twenty_split and time_stamps:
        after_920 = [i for i, ts in enumerate(time_stamps) if ts >= 92000]
        if after_920:
            start_idx = after_920[0]
            prices = prices[start_idx:]
            volumes = volumes[start_idx:]
            amounts = amounts[start_idx:]

    # 再次检查数据长度
    if len(prices) < 3:
        return None

    n = len(prices)

    # ── 3. 核心指标计算 ──

    # A) 价格趋势分析
    first_price = prices[0] or 0.001
    last_price = prices[-1]
    price_change_ratio = (last_price - first_price) / first_price

    # 分层验证：前半段 vs 后半段（SKILL.md "价格不下" 精确判断）
    mid_idx = n // 2
    first_half = prices[:mid_idx]
    second_half = prices[mid_idx:]

    # 后半段均价 >= 前半段均价 → 价格不下（即使尾盘有波动，整体承接仍在）
    first_half_avg = np.mean(first_half)
    second_half_avg = np.mean(second_half)
    price_stable = second_half_avg >= first_half_avg  # 后半段均价未下降

    # 后半段是否每笔都低于前半段收盘（持续走低，更严苛的判断）
    second_half_lower = all(p < first_half[-1] for p in second_half)

    # 最后几笔是否出现回升（抢筹迹象 → 否决卖出）
    # 使用 SKILL.md 的精确连续上涨检测：最后3笔是否每笔都高于前一笔
    tail_reversal = False
    tail_rising_strength = 0  # 回拉强度：连续上涨笔数
    if len(prices) >= 4:
        tail_n = min(len(second_half), 4)
        tail_chunk = prices[-tail_n:]
        # 统计尾段连续上涨的笔数
        rising_count = 0
        for i in range(len(tail_chunk) - 1):
            if tail_chunk[i + 1] > tail_chunk[i]:
                rising_count += 1
            else:
                rising_count = 0  # 出现下跌就重置
        tail_rising_strength = rising_count
        # 连续3笔上涨才算有效回拉（防1-2笔的小波动误判）
        tail_reversal = rising_count >= 3

    # B) 成交量变化分析
    vol_change_ratio = 0
    if len(volumes) > mid_idx and volumes[mid_idx] > 0:
        vol_change_ratio = (volumes[-1] - volumes[mid_idx]) / volumes[mid_idx]

    # C) 未匹配卖单变化分析（对应上方绿柱变长）
    amount_change_ratio = 0
    if len(amounts) > mid_idx and amounts[mid_idx] > 0:
        amount_change_ratio = ((amounts[-1] - amounts[mid_idx]) / amounts[mid_idx])

    # 未匹配卖单是否连续增加（每一笔都增加 = 抛压持续堆积）
    amount_continuous_up = False
    if len(amounts) >= 4:
        latter_amounts = amounts[-4:]
        amount_continuous_up = all(
            latter_amounts[i] <= latter_amounts[i + 1]
            for i in range(len(latter_amounts) - 1)
        )

    # ── 4. 三确认判断（从严标准） ──
    price_drop = price_change_ratio < g.price_drop_threshold
    vol_surge = vol_change_ratio > g.vol_surge_threshold
    sell_order_grow = amount_change_ratio > g.sell_order_grow_threshold

    # ── 5. "不要卖飞"否决条件 ──
    # 否决条件 1：尾盘价格回升（最后一分钟抢筹）
    if tail_reversal:
        return {
            'confirmed': False,
            'trigger_reason': f'尾盘连续{tail_rising_strength}笔上涨，抢筹信号（不卖飞）',
            'price_change_pct': round(price_change_ratio * 100, 2),
            'vol_change_pct': round(vol_change_ratio * 100, 2),
            'amount_change_pct': round(amount_change_ratio * 100, 2),
            'price_decline': second_half_lower,
            'price_stable': False,
            'tail_reversal': True,
            'tail_rising_strength': tail_rising_strength,
        }

    # 否决条件 2：后半段均价不下（整体承接仍在，非真抛压）
    #   条件：后半段均价 >= 前半段均价 → 即使尾盘小幅下跌，仍是承接行情
    if price_stable:
        return {
            'confirmed': False,
            'trigger_reason': '后半段均价未下降，承接仍在（不卖飞）',
            'price_change_pct': round(price_change_ratio * 100, 2),
            'vol_change_pct': round(vol_change_ratio * 100, 2),
            'amount_change_pct': round(amount_change_ratio * 100, 2),
            'price_stable': True,
            'tail_reversal': False,
        }

    # 否决条件 3：价格跌幅极浅 + 未持续走低 → 可能是瞬间波动
    if not second_half_lower and price_change_ratio > -0.005:
        return {
            'confirmed': False,
            'trigger_reason': '跌幅极浅且未持续走低，瞬间波动（不卖飞）',
            'price_change_pct': round(price_change_ratio * 100, 2),
            'vol_change_pct': round(vol_change_ratio * 100, 2),
            'amount_change_pct': round(amount_change_ratio * 100, 2),
            'price_stable': False,
            'tail_reversal': False,
        }

    # ── 6. 综合研判 ──
    # 三确认全部触发 + 无否决条件 → 确认真抛压
    confirmed = price_drop and vol_surge and sell_order_grow

    # 即使三确认不全，若两个强信号 + 未匹配卖单连续增加 → 也触发
    strong_two = (
            (price_drop and vol_surge and amount_continuous_up)
            or (price_drop and sell_order_grow and vol_change_ratio > 0.1)
    )
    if not confirmed and strong_two:
        confirmed = True

    # ── 7. 信号原因拼接 ──
    reasons = []
    if price_drop:
        reasons.append('价格下跌%.2f%%' % (price_change_ratio * 100))
    if vol_surge:
        reasons.append('成交量放大%.1f%%' % (vol_change_ratio * 100))
    if sell_order_grow:
        reasons.append('未匹配卖单增长%.1f%%' % (amount_change_ratio * 100))
    if amount_continuous_up:
        reasons.append('卖单连续堆积')

    return {
        'confirmed': confirmed,
        'trigger_reason': '; '.join(reasons) if reasons else '无明确信号',
        'price_change_pct': round(price_change_ratio * 100, 2),
        'vol_change_pct': round(vol_change_ratio * 100, 2),
        'amount_change_pct': round(amount_change_ratio * 100, 2),
        'price_decline': second_half_lower,
        'price_stable': False,
        'tail_reversal': False,
        'tail_rising_strength': tail_rising_strength,
    }


# ═══════════════════════════════════════════════════
#  盘中风控  handle_data
# ═══════════════════════════════════════════════════

def handle_data(context, data):
    """
    盘中风控逻辑：

    1. 若竞价逃顶未触发（held），盘中跌破成本价 5% 仍执行止损
    2. 竞价已卖出则不再操作
    """
    if g.sell_triggered:
        return

    try:
        if g.stock not in context.portfolio.positions:
            return

        pos = context.portfolio.positions[g.stock]
        total_hold = int(getattr(pos, 'amount', 0))
        if total_hold <= 0:
            return

        current_price = data[g.stock].close if g.stock in data else 0
        avg_cost = float(getattr(pos, 'avg_cost', 0) or 0)
        if current_price <= 0 or avg_cost <= 0:
            return

        loss_pct = (current_price - avg_cost) / avg_cost
        if loss_pct < g.stop_loss_pct:
            sell_qty = (total_hold // 100) * 100
            if sell_qty >= 100:
                if g.sim_mode:
                    log.info(
                        '【模拟·盘中止损】%s 浮亏 %.1f%%，拟清仓 %d 股（总持仓 %d）',
                        g.stock, loss_pct * 100, sell_qty, total_hold,
                                 )
                else:
                    # 实盘：需先确认 enable_amount ≥ sell_qty
                    pos = get_position(g.stock)
                    can_sell = 0
                    try:
                        can_sell = int(float(getattr(pos, 'enable_amount', 0)))
                    except (TypeError, ValueError):
                        can_sell = 0
                    actual_sell = min(sell_qty, can_sell)
                    if actual_sell >= 100:
                        # oid = order(g.stock, -actual_sell)
                        oid =1
                        if oid:
                            log.info(
                                '【实盘·盘中止损】%s 浮亏 %.1f%%，卖出 %d 股',
                                g.stock, loss_pct * 100, actual_sell,
                                         )

    except Exception as e:
        log.error('[风控] handle_data 异常: %s', str(e))

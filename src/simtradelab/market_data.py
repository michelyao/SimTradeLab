# -*- coding: utf-8 -*-
"""
市场数据接口模块

=======================
PTrade 完全兼容数据接口
=======================

提供与 PTrade 完全一致的市场数据获取接口，支持：

📊 **基础行情数据**
- get_history(): 历史数据获取，与PTrade参数完全一致
- get_price(): 实时/历史价格查询
- get_current_data(): 当前市场数据快照

📈 **技术指标计算**
- get_MACD(), get_KDJ(), get_RSI(), get_CCI(): 技术指标
- get_technical_indicators(): 批量技术指标计算

🔍 **高级市场数据**
- get_snapshot(): 股票快照数据，包含买卖五档
- get_individual_entrust(): 逐笔委托数据
- get_individual_transaction(): 逐笔成交数据
- get_gear_price(): 档位行情价格

📋 **市场统计数据**
- get_volume_ratio(): 量比计算
- get_turnover_rate(): 换手率
- get_pe_ratio(): 市盈率
- get_pb_ratio(): 市净率
- get_sort_msg(): 板块行业排名

🕐 **交易日历**
- get_previous_trading_date(): 上一交易日
- get_next_trading_date(): 下一交易日

PTrade 兼容性说明:
- 所有函数参数与PTrade完全一致
- 返回数据格式与PTrade保持统一
- 支持PTrade的所有数据频率和字段
- 错误处理方式与PTrade相同

数据源支持:
- CSV文件数据（本地回测）
- Tushare数据源（在线数据）
- AkShare数据源（免费数据）
- 可扩展其他数据源
"""
from typing import Union, List, Optional, Dict, Any
import hashlib
import pandas as pd
import numpy as np
from .logger import log


def get_history(
        engine: 'BacktestEngine',
        count: int,
        frequency: str = '1d',
        field: Union[str, List[str]] = ['open', 'high', 'low', 'close',
                                        'volume', 'money', 'price'],
        security_list: Optional[List[str]] = None,
        fq: Optional[str] = None,
        include: bool = False,
        fill: str = 'nan',
        is_dict: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
) -> Union[pd.DataFrame, Dict[str, Dict[str, np.ndarray]]]:
    """
    获取历史数据

    Args:
        engine: 回测引擎实例
        count: K线数量，大于0，返回指定数量的K线行情
        frequency: K线周期，支持1分钟线(1m)、5分钟线(5m)、15分钟线(15m)、30分钟线(30m)、
                  60分钟线(60m)、120分钟线(120m)、日线(1d)、周线(1w/weekly)、
                  月线(mo/monthly)、季度线(1q/quarter)和年线(1y/yearly)频率的数据，默认为'1d'
        field: 指明数据结果集中所支持输出的行情字段，默认为['open','high','low','close','volume','money','price']
               支持字段：open, high, low, close, volume, money, price, preclose, high_limit, low_limit, unlimited
        security_list: 要获取数据的股票列表，None表示在上下文中的universe中选中的所有股票
        fq: 数据复权选项，支持pre-前复权，post-后复权，dypre-动态前复权，None-不复权，默认为None
        include: 是否包含当前周期，True–包含，False-不包含，默认为False
        fill: 行情获取不到某一时刻的分钟数据时，是否用上一分钟的数据进行填充该时刻数据，
              'pre'–用上一分钟数据填充，'nan'–NaN进行填充，默认为'nan'
        is_dict: 返回是否是字典(dict)格式{str: array()}，True–是，False-不是，默认为False
        start_date: 开始日期 (扩展参数)
        end_date: 结束日期 (扩展参数)
        
    Returns:
        DataFrame 或字典格式的历史数据
    """
    if security_list is None:
        security_list = list(engine.data.keys())

    if isinstance(field, str):
        field = [field]

    frequency_mapping = {
        '1d'  : 'D', 'daily': 'D', '1m': 'T', 'minute': 'T', '5m': '5T',
        '5min': '5T',
        '15m' : '15T', '15min': '15T', '30m': '30T', '30min': '30T', '1h': 'H',
        'hour': 'H', '1w': 'W', 'week': 'W', '1M': 'M', 'month': 'M'
    }
    pandas_freq = frequency_mapping.get(frequency, 'D')

    extended_fields = {
        'pre_close', 'change', 'pct_change', 'amplitude',
        'turnover_rate', 'amount', 'vwap', 'high_limit', 'low_limit'
    }

    if is_dict:
        result = {}
        for sec in security_list:
            if sec not in engine.data:
                result[sec] = {col: np.array([]) for col in field}
                continue

            hist_df = engine.data[sec].copy()

            if hasattr(engine, 'context') and engine.context.current_dt:
                valid_hist = hist_df[
                    hist_df.index <= engine.context.current_dt] if include else \
                    hist_df[hist_df.index < engine.context.current_dt]
            else:
                valid_hist = hist_df

            if start_date:
                valid_hist = valid_hist[
                    valid_hist.index >= pd.to_datetime(start_date)]
            if end_date:
                valid_hist = valid_hist[
                    valid_hist.index <= pd.to_datetime(end_date)]

            if pandas_freq != 'D' and not valid_hist.empty:
                if pandas_freq in ['T', '5T', '15T', '30T', 'H']:
                    expanded_data = []
                    for _, row in valid_hist.iterrows():
                        periods_per_day = 240 if pandas_freq == 'T' else 48 if pandas_freq == '5T' else 16 if pandas_freq == '15T' else 8 if pandas_freq == '30T' else 4
                        day_start = _.replace(hour=9, minute=30)
                        time_range = pd.date_range(start=day_start,
                                                   periods=periods_per_day,
                                                   freq=pandas_freq)
                        daily_range = row['high'] - row['low']
                        for i, _ in enumerate(time_range):
                            progress = i / periods_per_day
                            noise = np.random.normal(0, daily_range * 0.01)
                            minute_close = max(row['low'], min(row['high'], row[
                                'low'] + daily_range * progress + noise))
                            expanded_data.append({
                                'open'  : minute_close * (
                                        1 + np.random.normal(0, 0.001)),
                                'high'  : minute_close * (1 + abs(
                                    np.random.normal(0, 0.002))),
                                'low'   : minute_close * (1 - abs(
                                    np.random.normal(0, 0.002))),
                                'close' : minute_close,
                                'volume': row['volume'] / periods_per_day
                            })
                    if expanded_data:
                        valid_hist = pd.DataFrame(expanded_data)
                        valid_hist.index = pd.date_range(
                            start=valid_hist.index[0].replace(hour=9,
                                                              minute=30),
                            periods=len(expanded_data), freq=pandas_freq)
                elif pandas_freq in ['W', 'M']:
                    valid_hist = valid_hist.resample(pandas_freq).agg(
                        {'open' : 'first', 'high': 'max', 'low': 'min',
                         'close': 'last', 'volume': 'sum'}).dropna()

            if count and len(valid_hist) > count:
                valid_hist = valid_hist.tail(count)

            if valid_hist.empty:
                result[sec] = {col: np.array([]) for col in field}
                continue

            for ext_field in field:
                if ext_field in extended_fields:
                    pre_close = valid_hist['close'].shift(1)
                    if ext_field == 'pre_close':
                        valid_hist['pre_close'] = pre_close
                    elif ext_field == 'change':
                        valid_hist['change'] = valid_hist['close'] - pre_close
                    elif ext_field == 'pct_change':
                        valid_hist['pct_change'] = (valid_hist[
                                                        'close'] / pre_close - 1) * 100
                    elif ext_field == 'amplitude':
                        valid_hist['amplitude'] = ((valid_hist['high'] -
                                                    valid_hist[
                                                        'low']) / pre_close) * 100
                    elif ext_field == 'turnover_rate':
                        hash_factor = int(
                            hashlib.md5(sec.encode()).hexdigest()[:8],
                            16) / 0xffffffff
                        valid_hist['turnover_rate'] = 2.5 + 5.0 * hash_factor
                    elif ext_field == 'amount':
                        valid_hist['amount'] = valid_hist['volume'] * \
                                               valid_hist['close'] / 10000
                    elif ext_field == 'vwap':
                        valid_hist['vwap'] = (valid_hist['high'] + valid_hist[
                            'low'] + valid_hist['close'] * 2) / 4
                    elif ext_field == 'high_limit':
                        valid_hist['high_limit'] = pre_close * 1.1
                    elif ext_field == 'low_limit':
                        valid_hist['low_limit'] = pre_close * 0.9

            result[sec] = {col: valid_hist[
                col].to_numpy() if col in valid_hist.columns else np.array([])
                           for col in field}
        return result

    result_df = pd.DataFrame()
    for sec in security_list:
        if sec not in engine.data:
            continue
        hist_df = engine.data[sec].copy()
        if hasattr(engine, 'context') and engine.context.current_dt:
            valid_hist = hist_df[
                hist_df.index <= engine.context.current_dt] if include else \
                hist_df[hist_df.index < engine.context.current_dt]
        else:
            valid_hist = hist_df
        if start_date:
            valid_hist = valid_hist[
                valid_hist.index >= pd.to_datetime(start_date)]
        if end_date:
            valid_hist = valid_hist[
                valid_hist.index <= pd.to_datetime(end_date)]
        if count and len(valid_hist) > count:
            valid_hist = valid_hist.tail(count)
        if valid_hist.empty:
            continue
        for f in field:
            if f in valid_hist.columns:
                result_df[(f, sec)] = valid_hist[f]
            else:
                log.warning(f"字段 '{f}' 不存在")

    # 确保即使结果为空也返回明确的DataFrame而不是容易被误用的空DataFrame
    if result_df.empty:
        # 返回带有明确列结构的空DataFrame，避免布尔值混淆
        columns = [(f, sec) for f in field for sec in security_list if
                   sec in engine.data]
        result_df = pd.DataFrame(columns=columns)

    return result_df


def get_price(
        engine: 'BacktestEngine',
        security: Union[str, List[str]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: str = '1d',
        fields: Optional[Union[str, List[str]]] = None,
        count: Optional[int] = None
) -> pd.DataFrame:
    """
    获取价格数据
    
    Args:
        engine: 回测引擎实例
        security: 股票代码或股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        frequency: 数据频率
        fields: 字段名或字段列表
        count: 数据条数
        
    Returns:
        价格数据DataFrame
    """
    count = count or 1
    securities = [security] if isinstance(security, str) else security
    fields = ['close'] if fields is None else (
        [fields] if isinstance(fields, str) else fields)

    all_supported_fields = {
        'open', 'high', 'low', 'close', 'volume', 'pre_close', 'change',
        'pct_change',
        'amplitude', 'turnover_rate', 'vwap', 'amount', 'high_limit',
        'low_limit'
    }

    result_data = {}
    for sec in securities:
        if sec not in engine.data:
            log.warning(f"股票 {sec} 的数据不存在")
            continue

        hist_df = engine.data[sec]
        current_dt = engine.context.current_dt if hasattr(engine,
                                                          'context') else None
        valid_hist = hist_df[
            hist_df.index < current_dt] if current_dt else hist_df

        if valid_hist.empty:
            log.warning(f"股票 {sec} 没有有效的历史数据")
            continue

        recent_data = valid_hist.tail(count)
        result_data[sec] = {}
        for field in fields:
            if field in recent_data.columns:
                result_data[sec][field] = recent_data[field].tolist()
            elif field in all_supported_fields:
                calculated_values = []
                for _, row in recent_data.iterrows():
                    pre_close = row['close'] * 0.98
                    if field == 'pre_close':
                        calculated_values.append(pre_close)
                    elif field == 'change':
                        calculated_values.append(row['close'] - pre_close)
                    elif field == 'pct_change':
                        calculated_values.append(
                            ((row['close'] - pre_close) / pre_close) * 100)
                    elif field == 'amplitude':
                        calculated_values.append(
                            ((row['high'] - row['low']) / pre_close) * 100)
                    elif field == 'turnover_rate':
                        hash_factor = int(
                            hashlib.md5(sec.encode()).hexdigest()[:8],
                            16) / 0xffffffff
                        calculated_values.append(2.5 + 5.0 * hash_factor)
                    elif field == 'vwap':
                        calculated_values.append(
                            (row['high'] + row['low'] + row['close'] * 2) / 4)
                    elif field == 'amount':
                        calculated_values.append(
                            row['volume'] * row['close'] / 10000)
                    elif field == 'high_limit':
                        calculated_values.append(pre_close * 1.1)
                    elif field == 'low_limit':
                        calculated_values.append(pre_close * 0.9)
                result_data[sec][field] = calculated_values
            else:
                log.warning(f"不支持的字段: {field}")
                result_data[sec][field] = [None] * count

    if not result_data:
        # 对于单个股票请求close价格的情况，返回None而不是空DataFrame，避免布尔值错误
        if isinstance(security, str) and len(fields) == 1 and fields[
            0] == 'close':
            return None
        return pd.DataFrame()

    sample_data = engine.data[securities[0]]
    current_dt = engine.context.current_dt if hasattr(engine,
                                                      'context') else None
    valid_hist = sample_data[
        sample_data.index < current_dt] if current_dt else sample_data
    time_index = valid_hist.tail(count).index

    result_df = pd.DataFrame()
    for field in fields:
        for sec in securities:
            if sec in result_data and field in result_data[sec] and len(
                    result_data[sec][field]) == len(time_index):
                result_df[(field, sec)] = pd.Series(result_data[sec][field],
                                                    index=time_index)

    if len(fields) == 1:
        result_df.columns = [col[1] for col in result_df.columns]

    # 特殊处理：单个股票的单个字段（通常是close价格），返回数值而不是DataFrame
    if isinstance(security, str) and len(fields) == 1 and not result_df.empty:
        if fields[0] == 'close':
            # 返回最新的close价格作为数值
            return float(result_df.iloc[-1, 0])

    return result_df


def get_current_data(
        engine: 'BacktestEngine',
        security: Optional[Union[str, List[str]]] = None
) -> Dict[str, Dict[str, float]]:
    """
    获取当前实时市场数据
    
    Args:
        engine: 回测引擎实例
        security: 股票代码或股票代码列表，None表示所有股票
        
    Returns:
        当前市场数据字典
    """
    securities = list(engine.data.keys()) if security is None else (
        [security] if isinstance(security, str) else security)
    current_data = {}
    for sec in securities:
        if sec not in engine.data:
            log.warning(f"股票 {sec} 的数据不存在")
            continue

        hist_df = engine.data[sec]
        current_dt = engine.context.current_dt if hasattr(engine,
                                                          'context') else None
        valid_hist = hist_df[
            hist_df.index <= current_dt] if current_dt else hist_df

        if valid_hist.empty:
            continue

        latest_data = valid_hist.iloc[-1]
        hash_factor = int(hashlib.md5(sec.encode()).hexdigest()[:8],
                          16) / 0xffffffff
        current_price = latest_data['close']
        spread = current_price * 0.001

        current_data[sec] = {
            'open'         : latest_data['open'], 'high': latest_data['high'],
            'low'          : latest_data['low'],
            'close'        : current_price, 'volume': latest_data['volume'],
            'bid1'         : current_price - spread,
            'bid2'         : current_price - spread * 2,
            'bid3'         : current_price - spread * 3,
            'bid4'         : current_price - spread * 4,
            'bid5'         : current_price - spread * 5,
            'ask1'         : current_price + spread,
            'ask2'         : current_price + spread * 2,
            'ask3'         : current_price + spread * 3,
            'ask4'         : current_price + spread * 4,
            'ask5'         : current_price + spread * 5,
            'bid1_volume'  : int(1000 + 5000 * hash_factor),
            'bid2_volume'  : int(800 + 4000 * hash_factor),
            'bid3_volume'  : int(600 + 3000 * hash_factor),
            'bid4_volume'  : int(400 + 2000 * hash_factor),
            'bid5_volume'  : int(200 + 1000 * hash_factor),
            'ask1_volume'  : int(1200 + 5500 * hash_factor),
            'ask2_volume'  : int(900 + 4500 * hash_factor),
            'ask3_volume'  : int(700 + 3500 * hash_factor),
            'ask4_volume'  : int(500 + 2500 * hash_factor),
            'ask5_volume'  : int(300 + 1500 * hash_factor),
            'pre_close'    : current_price * 0.98,
            'change'       : current_price * 0.02, 'pct_change': 2.04,
            'amount'       : np.float64(latest_data['volume']) * np.float64(
                current_price) / 10000,
            'turnover_rate': 2.5 + 5.0 * hash_factor,
            'high_limit'   : current_price * 0.98 * 1.1,
            'low_limit'    : current_price * 0.98 * 0.9,
            'amplitude'    : ((latest_data['high'] - latest_data['low']) / (
                    current_price * 0.98)) * 100,
            'vwap'         : (latest_data['high'] + latest_data[
                'low'] + current_price * 2) / 4,
        }
    return current_data


def get_market_snapshot(
        engine: 'BacktestEngine',
        security: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None
) -> pd.DataFrame:
    """
    获取市场快照数据
    
    Args:
        engine: 回测引擎实例
        security: 股票代码或股票代码列表
        fields: 字段名或字段列表
        
    Returns:
        市场快照数据DataFrame
    """
    current_data = get_current_data(engine, security)
    if not current_data:
        return pd.DataFrame()

    all_fields = [
        'open', 'high', 'low', 'close', 'volume', 'amount', 'pre_close',
        'change', 'pct_change',
        'amplitude', 'turnover_rate', 'bid1', 'bid2', 'bid3', 'bid4', 'bid5',
        'ask1', 'ask2', 'ask3',
        'ask4', 'ask5', 'bid1_volume', 'bid2_volume', 'bid3_volume',
        'bid4_volume', 'bid5_volume',
        'ask1_volume', 'ask2_volume', 'ask3_volume', 'ask4_volume',
        'ask5_volume', 'high_limit',
        'low_limit', 'vwap'
    ]
    fields = ['open', 'high', 'low', 'close', 'volume', 'change',
              'pct_change'] if fields is None else (
        [fields] if isinstance(fields, str) else fields)

    data_dict = {field: [current_data[sec].get(field) for sec in current_data]
                 for field in fields}
    return pd.DataFrame(data_dict, index=list(current_data.keys()))


def get_technical_indicators(
        engine: 'BacktestEngine',
        security: Union[str, List[str]],
        indicators: Union[str, List[str]],
        period: int = 20,
        **kwargs: Any
) -> pd.DataFrame:
    """
    计算技术指标
    
    Args:
        engine: 回测引擎实例
        security: 股票代码或股票代码列表
        indicators: 指标名或指标列表
        period: 计算周期
        **kwargs: 其他参数
        
    Returns:
        技术指标数据DataFrame
    """
    securities = [security] if isinstance(security, str) else security
    indicators = [indicators] if isinstance(indicators, str) else indicators
    result_data = {}

    for sec in securities:
        if sec not in engine.data:
            log.warning(f"股票 {sec} 的数据不存在")
            continue

        hist_df = engine.data[sec]
        current_dt = engine.context.current_dt if hasattr(engine,
                                                          'context') else None
        valid_hist = hist_df[
            hist_df.index <= current_dt] if current_dt else hist_df

        if len(valid_hist) < period:
            log.warning(f"股票 {sec} 的历史数据不足，需要至少 {period} 条数据")
            continue

        result_data[sec] = {}
        close_prices = valid_hist['close'].values
        high_prices = valid_hist['high'].values
        low_prices = valid_hist['low'].values

        for indicator in indicators:
            try:
                if indicator.upper() == 'MA':
                    result_data[sec][f'MA{period}'] = pd.Series(
                        close_prices).rolling(window=period).mean().tolist()
                elif indicator.upper() == 'EMA':
                    result_data[sec][f'EMA{period}'] = pd.Series(
                        close_prices).ewm(span=period,
                                          adjust=False).mean().tolist()
                elif indicator.upper() == 'MACD':
                    fast_period = kwargs.get('fast_period', 12)
                    slow_period = kwargs.get('slow_period', 26)
                    signal_period = kwargs.get('signal_period', 9)
                    ema_fast = pd.Series(close_prices).ewm(span=fast_period,
                                                           adjust=False).mean()
                    ema_slow = pd.Series(close_prices).ewm(span=slow_period,
                                                           adjust=False).mean()
                    dif = ema_fast - ema_slow
                    dea = dif.ewm(span=signal_period, adjust=False).mean()
                    result_data[sec]['MACD_DIF'] = dif.tolist()
                    result_data[sec]['MACD_DEA'] = dea.tolist()
                    result_data[sec]['MACD_HIST'] = ((dif - dea) * 2).tolist()
                elif indicator.upper() == 'RSI':
                    delta = pd.Series(close_prices).diff()
                    gain = (delta.where(delta > 0, 0)).rolling(
                        window=period).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(
                        window=period).mean()
                    rs = gain / loss
                    result_data[sec][f'RSI{period}'] = (
                            100 - (100 / (1 + rs))).tolist()
                elif indicator.upper() == 'BOLL':
                    std_multiplier = kwargs.get('std_multiplier', 2)
                    ma = pd.Series(close_prices).rolling(window=period).mean()
                    std = pd.Series(close_prices).rolling(window=period).std()
                    result_data[sec]['BOLL_UPPER'] = (
                            ma + std_multiplier * std).tolist()
                    result_data[sec]['BOLL_MIDDLE'] = ma.tolist()
                    result_data[sec]['BOLL_LOWER'] = (
                            ma - std_multiplier * std).tolist()
                elif indicator.upper() == 'KDJ':
                    k_period = kwargs.get('k_period', 9)
                    low_min = pd.Series(low_prices).rolling(
                        window=k_period).min()
                    high_max = pd.Series(high_prices).rolling(
                        window=k_period).max()
                    rsv = (pd.Series(close_prices) - low_min) / (
                            high_max - low_min) * 100
                    k_values = rsv.ewm(com=2, adjust=False).mean()
                    d_values = k_values.ewm(com=2, adjust=False).mean()
                    j_values = 3 * k_values - 2 * d_values
                    result_data[sec]['KDJ_K'] = k_values.tolist()
                    result_data[sec]['KDJ_D'] = d_values.tolist()
                    result_data[sec]['KDJ_J'] = j_values.tolist()
                elif indicator.upper() == 'CCI':
                    # CCI (Commodity Channel Index) 顺势指标
                    cci_period = kwargs.get('cci_period', period)
                    typical_price = (pd.Series(high_prices) + pd.Series(
                        low_prices) + pd.Series(close_prices)) / 3
                    sma_tp = typical_price.rolling(window=cci_period).mean()

                    # 计算平均绝对偏差 (MAD)
                    def calculate_mad(x):
                        return (x - x.mean()).abs().mean()

                    mad = typical_price.rolling(window=cci_period).apply(
                        calculate_mad, raw=False)
                    cci = (typical_price - sma_tp) / (0.015 * mad)
                    result_data[sec][f'CCI{cci_period}'] = cci.tolist()
            except Exception as e:
                log.warning(f"计算技术指标 {indicator} 时出错: {e}")

    if not result_data:
        return pd.DataFrame()

    sample_data = engine.data[securities[0]]
    current_dt = engine.context.current_dt if hasattr(engine,
                                                      'context') else None
    valid_hist = sample_data[
        sample_data.index <= current_dt] if current_dt else sample_data
    time_index = valid_hist.index

    result_df = pd.DataFrame()
    for sec in result_data:
        for indicator_name, values in result_data[sec].items():
            if len(values) == len(time_index):
                result_df[(indicator_name, sec)] = pd.Series(values,
                                                             index=time_index)

    return result_df


# ==================== 独立技术指标函数接口 ====================
# 符合ptradeAPI标准的独立技术指标函数

def get_MACD(
        engine: 'BacktestEngine',
        security: Union[str, List[str]],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
) -> pd.DataFrame:
    """
    计算MACD指标 (异同移动平均线)

    Args:
        engine: 回测引擎实例
        security: 股票代码，支持单个股票或股票列表
        fast_period: 快线周期，默认12
        slow_period: 慢线周期，默认26
        signal_period: 信号线周期，默认9

    Returns:
        包含MACD_DIF, MACD_DEA, MACD_HIST的数据框
    """
    return get_technical_indicators(
        engine, security, 'MACD',
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period
    )


def get_KDJ(
        engine: 'BacktestEngine',
        security: Union[str, List[str]],
        k_period: int = 9
) -> pd.DataFrame:
    """
    计算KDJ指标 (随机指标)

    Args:
        engine: 回测引擎实例
        security: 股票代码，支持单个股票或股票列表
        k_period: K值计算周期，默认9

    Returns:
        包含KDJ_K, KDJ_D, KDJ_J的数据框
    """
    return get_technical_indicators(
        engine, security, 'KDJ',
        k_period=k_period
    )


def get_RSI(
        engine: 'BacktestEngine',
        security: Union[str, List[str]],
        period: int = 14
) -> pd.DataFrame:
    """
    计算RSI指标 (相对强弱指标)

    Args:
        engine: 回测引擎实例
        security: 股票代码，支持单个股票或股票列表
        period: 计算周期，默认14

    Returns:
        包含RSI值的数据框
    """
    return get_technical_indicators(
        engine, security, 'RSI',
        period=period
    )


def get_CCI(
        engine: 'BacktestEngine',
        security: Union[str, List[str]],
        period: int = 20
) -> pd.DataFrame:
    """
    计算CCI指标 (顺势指标)

    Args:
        engine: 回测引擎实例
        security: 股票代码，支持单个股票或股票列表
        period: 计算周期，默认20

    Returns:
        包含CCI值的数据框
    """
    return get_technical_indicators(
        engine, security, 'CCI',
        cci_period=period
    )


# ==================== 市场信息API ====================

def get_market_list(engine: 'BacktestEngine') -> List[str]:
    """
    获取市场列表
    
    Args:
        engine: 回测引擎实例
        
    Returns:
        市场代码列表
    """
    # 根据股票代码后缀判断市场
    markets = set()

    if not engine.data:
        return []

    for security in engine.data.keys():
        if '.' in security:
            market = security.split('.')[-1]
            markets.add(market)
        else:
            # 默认市场
            markets.add('SZ')  # 深圳

    market_list = list(markets)
    log.info(f"获取市场列表: {market_list}")
    return market_list


def get_cash(engine: 'BacktestEngine') -> float:
    """
    获取当前现金
    
    Args:
        engine: 回测引擎实例
        
    Returns:
        当前现金金额
    """
    if hasattr(engine, 'context') and engine.context:
        return engine.context.portfolio.cash
    return 0.0


def get_total_value(engine: 'BacktestEngine') -> float:
    """
    获取总资产
    
    Args:
        engine: 回测引擎实例
        
    Returns:
        总资产金额
    """
    if hasattr(engine, 'context') and engine.context:
        return engine.context.portfolio.total_value
    return 0.0


def get_datetime(engine: 'BacktestEngine') -> str:
    """
    获取当前时间
    
    Args:
        engine: 回测引擎实例
        
    Returns:
        当前时间字符串
    """
    if hasattr(engine,
               'context') and engine.context and engine.context.current_dt:
        return engine.context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    return ""


def get_previous_trading_date(engine: 'BacktestEngine',
                              date: str = None) -> str:
    """
    获取上一交易日
    
    Args:
        engine: 回测引擎实例
        date: 基准日期，None表示当前日期
        
    Returns:
        上一交易日字符串
    """
    from .utils import get_trading_day
    import pandas as pd

    previous_date = get_trading_day(engine, date, offset=-1)
    if previous_date:
        return previous_date.strftime('%Y-%m-%d')
    return ""


def get_next_trading_date(engine: 'BacktestEngine', date: str = None) -> str:
    """
    获取下一交易日
    
    Args:
        engine: 回测引擎实例
        date: 基准日期，None表示当前日期
        
    Returns:
        下一交易日字符串
    """
    from .utils import get_trading_day
    import pandas as pd

    next_date = get_trading_day(engine, date, offset=1)
    if next_date:
        return next_date.strftime('%Y-%m-%d')
    return ""


# =================================================================
# 高级市场数据API - 从utils.py迁移而来，保持PTrade兼容性
# =================================================================

def get_snapshot(engine: 'BacktestEngine', stock: str) -> Dict[str, Any]:
    """
    获取股票快照数据 (PTrade兼容)
    
    Args:
        engine: 回测引擎实例
        stock: 股票代码
        
    Returns:
        dict: 快照数据
    """
    trade_data_mint_fact = {'hsTimeStamp'                        : 20260423103103000,
                            'trade_mins'                         : 2,
                            'trade_status'                       : 'TRADE',
                            'preclose_px'                        : 18.63,
                            'open_px'                            : 20.49,
                            'last_px'                            : 20.49,
                            'high_px'                            : 20.49,
                            'low_px'                             : 20.01,
                            'wavg_px'                            : 20.46,
                            'business_count'                     : 15160,
                            'business_amount'                    : 17761773,
                            'business_balance'                   : 363342313.0,
                            'up_px'                              : 20.49,
                            'down_px'                            : 16.77,
                            'current_amount'                     : 959700,
                            'business_amount_in'                 : 3065182,
                            'business_amount_out'                : 14696591,
                            'issue_date'                         : 0,
                            'amount'                             : 0,
                            'settlement'                         : 0.0,
                            'prev_settlement'                    : 0.0,
                            'turnover_ratio'                     : 0.0241,
                            'type_flag'                          : 0,
                            'business_balance_scale'             : 363342313130,
                            'exercise_date'                      : 0,
                            'exercise_price'                     : 0.0,
                            'contract_unit'                      : 0,
                            'contract_code'                      : '',
                            'exercise_type'                      : '',
                            'call_put'                           : '',
                            'start_trade_date'                   : 0,
                            'end_trade_date'                     : 0,
                            'expire_date'                        : 0,
                            'security_status_flag'               : 0,
                            'tick_size'                          : 0.0,
                            'entrust_rate'                       : 0.3394,
                            'vol_ratio'                          : 165.17,
                            'entrust_diff'                       : 18314.55,
                            'pe_rate'                            : 67.1,
                            'pb_rate'                            : 3.42,
                            'circulation_amount'                 : 736174691,
                            'px_change_rate'                     : 9.98,
                            'total_bidqty'                       : 3613607,
                            'total_offerqty'                     : 1782152,
                            'total_bid_turnover'                 : 0,
                            'total_offer_turnover'               : 0,
                            'iopv'                               : 0.0,
                            'bid_grp'                            : {
                                1: [20.46, 43400, 43, {1 : 6700, 2: 6500,
                                                       3 : 3800, 4: 100,
                                                       5 : 1000, 6: 500, 7: 200,
                                                       8 : 5000, 9: 1000,
                                                       10: 2100, 11: 200,
                                                       12: 1000, 13: 100,
                                                       14: 200, 15: 200,
                                                       16: 100, 17: 200,
                                                       18: 2000, 19: 500,
                                                       20: 700, 21: 500,
                                                       22: 100, 23: 200,
                                                       24: 200, 25: 700,
                                                       26: 100, 27: 900,
                                                       28: 200, 29: 700,
                                                       30: 600, 31: 1000,
                                                       32: 400, 33: 1000,
                                                       34: 1000, 35: 400,
                                                       36: 600, 37: 200,
                                                       38: 600, 39: 500,
                                                       40: 200, 41: 300,
                                                       42: 700, 43: 200}], 2: [
                                    20.45, 100907, 83], 3: [20.44, 100, 1], 4: [
                                    20.43, 13700, 11], 5: [20.42, 322500, 104],
                                6: [20.41, 6700, 4], 7: [20.4, 21600, 23], 8: [
                                    20.39, 400, 2], 9: [20.38, 1600, 3], 10: [
                                    20.37, 3700, 5]}, 'offer_grp': {
            1                                                               : [
                20.49, 1782152, 967,
                {1 : 740, 2: 400, 3: 100, 4: 200, 5: 1600, 6: 200, 7: 400,
                 8 : 200, 9: 2900, 10: 300, 11: 600, 12: 100, 13: 600, 14: 500,
                 15: 1000, 16: 900, 17: 500, 18: 300, 19: 200, 20: 1000,
                 21: 1000, 22: 600, 23: 13900, 24: 11000, 25: 1000, 26: 500,
                 27: 1200, 28: 2000, 29: 1000, 30: 3000, 31: 500, 32: 2000,
                 33: 5000, 34: 100, 35: 200, 36: 6800, 37: 100, 38: 400,
                 39: 2500, 40: 600, 41: 100, 42: 100, 43: 100, 44: 3700,
                 45: 500, 46: 200, 47: 800, 48: 4500, 49: 1400, 50: 500}], 2: [
                0.0, 0, 0], 3                                               : [
                0.0, 0, 0], 4                                               : [
                0.0, 0, 0], 5                                               : [
                0.0, 0, 0], 6                                               : [
                0.0, 0, 0], 7                                               : [
                0.0, 0, 0], 8                                               : [
                0.0, 0, 0], 9                                               : [
                0.0, 0, 0], 10                                              : [
                0.0, 0, 0]}}
    if isinstance(stock, list):
        return {item: trade_data_mint_fact for item in stock}
    else:
        return {stock: trade_data_mint_fact}

    if stock in engine.data:
        latest_data = engine.data[stock].iloc[-1]
        snapshot = {
            'code'       : stock,
            'open'       : latest_data['open'],
            'high'       : latest_data['high'],
            'low'        : latest_data['low'],
            'close'      : latest_data['close'],
            'volume'     : latest_data['volume'],
            'turnover'   : latest_data['close'] * latest_data['volume'],
            'bid1'       : latest_data['close'] * 0.999,
            'ask1'       : latest_data['close'] * 1.001,
            'bid1_volume': 10000,
            'ask1_volume': 10000
        }
    else:
        snapshot = {'code': stock, 'error': 'No data available'}

    log.info(f"获取股票快照: {stock}")
    return snapshot


def get_volume_ratio(engine: 'BacktestEngine', stock: str) -> float:
    """
    获取股票量比 (PTrade兼容)
    
    Args:
        engine: 回测引擎实例
        stock: 股票代码
        
    Returns:
        float: 量比
    """
    if stock in engine.data and len(engine.data[stock]) >= 5:
        recent_volume = engine.data[stock]['volume'].iloc[-1]
        avg_volume = engine.data[stock]['volume'].iloc[-5:].mean()
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
    else:
        volume_ratio = 1.0

    log.info(f"获取量比: {stock} -> {volume_ratio:.2f}")
    return volume_ratio


def get_turnover_rate(engine: 'BacktestEngine', stock: str) -> float:
    """
    获取股票换手率 (PTrade兼容)
    
    Args:
        engine: 回测引擎实例
        stock: 股票代码
        
    Returns:
        float: 换手率(%)
    """
    import random
    # 模拟换手率计算（在实际应用中应该从数据源获取）
    turnover_rate = random.uniform(0.5, 5.0)  # 0.5%-5%
    log.info(f"获取换手率: {stock} -> {turnover_rate:.2f}%")
    return turnover_rate


def get_pe_ratio(engine: 'BacktestEngine', stock: str) -> float:
    """
    获取股票市盈率 (PTrade兼容)
    
    Args:
        engine: 回测引擎实例
        stock: 股票代码
        
    Returns:
        float: 市盈率
    """
    import random
    # 模拟市盈率（在实际应用中应该从数据源获取）
    pe_ratio = random.uniform(10, 50)
    log.info(f"获取市盈率: {stock} -> {pe_ratio:.2f}")
    return pe_ratio


def get_pb_ratio(engine: 'BacktestEngine', stock: str) -> float:
    """
    获取股票市净率 (PTrade兼容)
    
    Args:
        engine: 回测引擎实例
        stock: 股票代码
        
    Returns:
        float: 市净率
    """
    import random
    # 模拟市净率（在实际应用中应该从数据源获取）
    pb_ratio = random.uniform(0.5, 8.0)
    log.info(f"获取市净率: {stock} -> {pb_ratio:.2f}")
    return pb_ratio


def get_individual_entrust(engine: 'BacktestEngine',
                           stocks: Union[str, List[str]],
                           start_time: str = None, end_time: str = None) -> \
        Dict[str, pd.DataFrame]:
    """
    获取逐笔委托行情 (PTrade兼容)

    Args:
        engine: 回测引擎实例
        stocks: 股票代码或股票列表
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        dict: 逐笔委托数据，key为股票代码，value为DataFrame
    """
    from datetime import datetime, timedelta

    if isinstance(stocks, str):
        stocks = [stocks]

    result = {}

    for stock in stocks:
        # 模拟逐笔委托数据
        current_time = datetime.now()
        time_range = pd.date_range(
            start=current_time - timedelta(minutes=30),
            end=current_time,
            freq='10s'  # 每10秒一条记录
        )

        n_records = len(time_range)

        # 生成模拟数据
        base_price = 10.0  # 基础价格
        entrust_data = pd.DataFrame({
            'business_time'     : [int(t.timestamp() * 1000) for t in
                                   time_range],  # 毫秒时间戳
            'hq_px'             : np.round(
                base_price + np.random.normal(0, 0.1, n_records), 2),  # 委托价格
            'business_amount'   : np.random.randint(100, 10000, n_records),
            # 委托量
            'order_no'          : [f"ORD{i:06d}" for i in range(n_records)],
            # 委托编号
            'business_direction': np.random.choice([0, 1], n_records),
            # 0-卖，1-买
            'trans_kind'        : np.random.choice([1, 2, 3], n_records)
            # 1-市价，2-限价，3-本方最优
        })

        result[stock] = entrust_data

    log.info(f"获取逐笔委托数据: {len(stocks)}只股票")
    return result


def get_individual_transaction(engine: 'BacktestEngine',
                               stocks: Union[str, List[str]],
                               start_time: str = None, end_time: str = None) -> \
        Dict[str, pd.DataFrame]:
    """
    获取逐笔成交行情 (PTrade兼容)

    Args:
        engine: 回测引擎实例
        stocks: 股票代码或股票列表
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        dict: 逐笔成交数据，key为股票代码，value为DataFrame
    """
    from datetime import datetime, timedelta

    if isinstance(stocks, str):
        stocks = [stocks]

    result = {}

    for stock in stocks:
        # 模拟逐笔成交数据
        current_time = datetime.now()
        time_range = pd.date_range(
            start=current_time - timedelta(minutes=30),
            end=current_time,
            freq='15s'  # 每15秒一条记录
        )

        n_records = len(time_range)

        # 生成模拟数据
        base_price = 10.0  # 基础价格
        transaction_data = pd.DataFrame({
            'business_time'     : [int(t.timestamp() * 1000) for t in
                                   time_range],  # 毫秒时间戳
            'hq_px'             : np.round(
                base_price + np.random.normal(0, 0.05, n_records), 2),  # 成交价格
            'business_amount'   : np.random.randint(100, 5000, n_records),
            # 成交量
            'trade_index'       : [f"TRD{i:06d}" for i in range(n_records)],
            # 成交编号
            'business_direction': np.random.choice([0, 1], n_records),
            # 0-卖，1-买
            'buy_no'            : [f"BUY{i:06d}" for i in range(n_records)],
            # 叫买方编号
            'sell_no'           : [f"SELL{i:06d}" for i in range(n_records)],
            # 叫卖方编号
            'trans_flag'        : np.random.choice([0, 1], n_records,
                                                   p=[0.95, 0.05]),  # 0-普通，1-撤单
            'trans_identify_am' : np.random.choice([0, 1], n_records,
                                                   p=[0.9, 0.1]),  # 0-盘中，1-盘后
            'channel_num'       : np.random.randint(1, 10, n_records)  # 成交通道信息
        })

        result[stock] = transaction_data

    log.info(f"获取逐笔成交数据: {len(stocks)}只股票")
    return result


def get_gear_price(engine: 'BacktestEngine', security: str) -> Dict[str, Any]:
    """
    获取指定代码的档位行情价格 (PTrade兼容)

    Args:
        engine: 回测引擎实例
        security: 股票代码

    Returns:
        dict: 档位行情数据
    """
    import random
    from datetime import datetime

    # 模拟档位行情数据
    base_price = 10.0

    # 生成买卖五档数据
    bid_prices = []
    ask_prices = []

    for i in range(5):
        bid_price = round(base_price - (i + 1) * 0.01, 2)
        ask_price = round(base_price + (i + 1) * 0.01, 2)
        bid_prices.append(bid_price)
        ask_prices.append(ask_price)

    gear_data = {
        'security'        : security,
        'timestamp'       : int(datetime.now().timestamp() * 1000),
        'bid_prices'      : bid_prices,  # 买一到买五价格
        'bid_volumes'     : [random.randint(100, 10000) for _ in range(5)],
        # 买一到买五量
        'ask_prices'      : ask_prices,  # 卖一到卖五价格
        'ask_volumes'     : [random.randint(100, 10000) for _ in range(5)],
        # 卖一到卖五量
        'last_price'      : base_price,  # 最新价
        'total_bid_volume': sum([random.randint(100, 10000) for _ in range(5)]),
        # 委买总量
        'total_ask_volume': sum([random.randint(100, 10000) for _ in range(5)]),
        # 委卖总量
    }

    log.info(f"获取档位行情: {security}")
    return gear_data


def get_sort_msg(engine: 'BacktestEngine', market_type: str = 'sector',
                 sort_field: str = 'pct_change', ascending: bool = False,
                 count: int = 20) -> List[Dict[str, Any]]:
    """
    获取板块、行业的涨幅排名 (PTrade兼容)

    Args:
        engine: 回测引擎实例
        market_type: 市场类型 ('sector'-板块, 'industry'-行业)
        sort_field: 排序字段 ('pct_change'-涨跌幅, 'volume'-成交量, 'amount'-成交额)
        ascending: 是否升序排列
        count: 返回数量

    Returns:
        list: 排名数据列表
    """
    import random

    # 模拟板块/行业数据
    if market_type == 'sector':
        sectors = [
            '银行板块', '证券板块', '保险板块', '地产板块', '钢铁板块',
            '煤炭板块', '有色板块', '石油板块', '电力板块', '汽车板块',
            '家电板块', '食品板块', '医药板块', '科技板块', '军工板块'
        ]
        data_source = sectors
    else:  # industry
        industries = [
            '银行业', '证券业', '保险业', '房地产业', '钢铁业',
            '煤炭业', '有色金属', '石油化工', '电力行业', '汽车制造',
            '家用电器', '食品饮料', '医药生物', '计算机', '国防军工'
        ]
        data_source = industries

    # 生成模拟排名数据
    sort_data = []
    for i, name in enumerate(data_source[:count]):
        item = {
            'name'      : name,
            'code'      : f"{market_type.upper()}{i:03d}",
            'pct_change': round(random.uniform(-5.0, 8.0), 2),  # 涨跌幅 -5% 到 8%
            'volume'    : random.randint(1000000, 100000000),  # 成交量
            'amount'    : random.randint(100000000, 10000000000),  # 成交额
            'up_count'  : random.randint(0, 50),  # 上涨家数
            'down_count': random.randint(0, 50),  # 下跌家数
            'flat_count': random.randint(0, 10),  # 平盘家数
        }
        sort_data.append(item)

    # 按指定字段排序
    sort_data.sort(key=lambda x: x[sort_field], reverse=not ascending)

    log.info(f"获取{market_type}排名数据: {len(sort_data)}个")
    return sort_data

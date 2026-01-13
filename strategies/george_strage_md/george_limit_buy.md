在文件E:\P_python\kay\SimTradeLab_old\strategies\george_omo_limit_single.py中的interval_handle函数中实现以下功能。
1. 记录每个股票上一次数据来的时候的状态。
    - g.limit1保存check_limit返回状态是1的股票代码。
    - g.limit2保存check_limit返回状态是2的股票代码。
2. **当** 上一次的状态是0,-1, -2这次的状态是2
   **则** log.info( "line:{} george下单买入: last_px: {}, offer_price: {}, stock: {}".format(146, last_px, offer_price, stock))
   **否则** log.debug( "line:{} george 打板未达到条件: last_px: {}, offer_amount: {}, stock: {}".format(150, last_px, offer_amount, stock))



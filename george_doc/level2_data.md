需要实现的需求如下：
1. 从ptrade实盘获取level2数据以最高效的方式，转存出来，供盘后使用。
2. 逐笔成交(get_individual_transaction)，逐笔委托(get_individual_entrust),股票所有订单(get_all_orders)
3. 文件保存方式和hit_limit_l2_point中的read_stock_pool函数保持一致。
4. 不修改simtradeLab中的框架。只实现转存的策略文件。
5. 这个策略文件只在ptrade环境中运行。
6. 数据转存的频率和粒度，组合触发方案（5000条或5分钟，任一触发保存）
7. 数据文件的格式和组织结构，使用jsonL.
8. stock_list =['600519.ss']
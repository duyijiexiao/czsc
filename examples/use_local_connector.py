# -*- coding: utf-8 -*-
"""
本地数据源使用示例

本示例展示如何使用本地SQLite数据库进行缠论分析
"""
from czsc import CZSC, Freq
from czsc.connectors import get_raw_bars, get_all_symbols, get_date_range, search_stocks


def example_basic_analysis():
    """基础缠论分析示例"""
    print("=" * 60)
    print("示例1: 基础缠论分析")
    print("=" * 60)

    bars = get_raw_bars("000001", "日线", "20220101", "20241231")
    print(f"获取到 {len(bars)} 条K线数据")

    c = CZSC(bars)
    print(f"股票代码: {c.symbol}")
    print(f"K线周期: {c.freq}")
    print(f"原始K线数量: {len(c.bars_raw)}")
    print(f"笔的数量: {len(c.bi_list)}")

    if c.bi_list:
        last_bi = c.bi_list[-1]
        print(f"最后一笔方向: {last_bi.direction}")
        print(f"最后一笔长度: {last_bi.length}")


def example_multi_symbol():
    """多股票分析示例"""
    print("\n" + "=" * 60)
    print("示例2: 多股票分析")
    print("=" * 60)

    symbols = get_all_symbols()
    print(f"数据库中共有 {len(symbols)} 只股票")

    test_symbols = symbols[:5]
    print(f"分析前5只股票: {test_symbols}")

    for symbol in test_symbols:
        start, end = get_date_range(symbol)
        print(f"  {symbol}: {start} ~ {end}")


def example_search_stock():
    """搜索股票示例"""
    print("\n" + "=" * 60)
    print("示例3: 搜索股票")
    print("=" * 60)

    results = search_stocks("平安")
    print(f"搜索'平安'结果:")
    for r in results[:10]:
        print(f"  {r['code']}: {r['name']}")


def example_custom_strategy():
    """自定义策略示例"""
    print("\n" + "=" * 60)
    print("示例4: 简单策略回测")
    print("=" * 60)

    bars = get_raw_bars("000001", "日线", "20200101", "20241231")
    c = CZSC(bars)

    bi_list = c.bi_list
    up_count = sum(1 for bi in bi_list if bi.direction.value == "向上")
    down_count = sum(1 for bi in bi_list if bi.direction.value == "向下")

    print(f"总笔数: {len(bi_list)}")
    print(f"向上笔: {up_count}")
    print(f"向下笔: {down_count}")


if __name__ == "__main__":
    example_basic_analysis()
    example_multi_symbol()
    example_search_stock()
    example_custom_strategy()
    print("\n" + "=" * 60)
    print("示例运行完成!")
    print("=" * 60)

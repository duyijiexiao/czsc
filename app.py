#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缠中说禅技术分析系统 - 统一入口

直接运行启动Web界面:
    python app.py

命令行模式:
    python app.py analyze --symbol 000001
    python app.py plot --symbol 000001
    python app.py search 平安
"""
import argparse
import os
import sys


def cmd_web(args):
    """启动 Streamlit Web 界面"""
    import subprocess

    web_app_path = os.path.join(os.path.dirname(__file__), "web_app.py")

    if not os.path.exists(web_app_path):
        print("错误: 未找到 web_app.py 文件")
        return 1

    print("正在启动缠论分析系统...")
    print("请在浏览器中访问: http://localhost:8501")
    print("按 Ctrl+C 停止服务\n")
    
    subprocess.run(["streamlit", "run", web_app_path])
    return 0


def cmd_analyze(args):
    """缠论分析"""
    from czsc import CZSC
    from czsc.connectors import get_raw_bars, get_stock_info
    from czsc.utils.sig import get_zs_seq

    symbol = args.symbol
    sdt = args.start
    edt = args.end

    print(f"\n{'='*50}")
    print(f"缠论分析: {symbol}")
    print(f"时间范围: {sdt} ~ {edt}")
    print(f"{'='*50}\n")

    stock_info = get_stock_info(symbol)
    if stock_info:
        print(f"股票名称: {stock_info.get('name', 'N/A')}")

    print(f"\n正在获取K线数据...")
    bars = get_raw_bars(symbol, "日线", sdt, edt)

    if not bars:
        print(f"错误: 未获取到 {symbol} 的数据")
        return 1

    print(f"获取到 {len(bars)} 条K线数据")
    print(f"数据范围: {bars[0].dt.strftime('%Y-%m-%d')} ~ {bars[-1].dt.strftime('%Y-%m-%d')}")

    print(f"\n正在进行缠论分析...")
    c = CZSC(bars)

    zs_list = get_zs_seq(c.bi_list)

    print(f"\n{'='*50}")
    print(f"分析结果")
    print(f"{'='*50}")
    print(f"笔的数量: {len(c.bi_list)}")
    print(f"中枢数量: {len(zs_list)}")

    if c.bi_list:
        last_bi = c.bi_list[-1]
        print(f"\n最后一笔:")
        print(f"  方向: {last_bi.direction.value}")
        print(f"  起点: {last_bi.fx_a.dt.strftime('%Y-%m-%d')} @ {last_bi.fx_a.raw_bars[-1].close:.2f}")
        print(f"  终点: {last_bi.fx_b.dt.strftime('%Y-%m-%d')} @ {last_bi.fx_b.raw_bars[-1].close:.2f}")

    if zs_list:
        last_zs = zs_list[-1]
        print(f"\n最后一个中枢:")
        print(f"  区间: [{last_zs.zd:.2f}, {last_zs.zg:.2f}]")

    print(f"\n当前状态:")
    print(f"  最近收盘价: {bars[-1].close:.2f}")
    print(f"  分析完成!")

    return 0


def cmd_plot(args):
    """生成可视化"""
    from czsc import CZSC
    from czsc.connectors import get_raw_bars, get_stock_info
    from czsc.connectors.local_connector import get_stock_data
    from czsc.utils.plotting.kline import KlineChart

    symbol = args.symbol
    sdt = args.start
    edt = args.end
    output = args.output

    print(f"\n{'='*50}")
    print(f"生成可视化图表: {symbol}")
    print(f"{'='*50}\n")

    stock_info = get_stock_info(symbol)
    stock_name = stock_info.get("name", symbol) if stock_info else symbol

    print(f"正在获取K线数据...")
    bars = get_raw_bars(symbol, "日线", sdt, edt)

    if not bars:
        print(f"错误: 未获取到 {symbol} 的数据")
        return 1

    print(f"获取到 {len(bars)} 条K线数据")

    sdt_fmt = f"{sdt[:4]}-{sdt[4:6]}-{sdt[6:8]}" if len(sdt) == 8 else sdt
    edt_fmt = f"{edt[:4]}-{edt[4:6]}-{edt[6:8]}" if len(edt) == 8 else edt
    df_ma = get_stock_data(symbol, sdt_fmt, edt_fmt, include_ma=True)

    print(f"正在进行缠论分析...")
    c = CZSC(bars)

    print(f"正在生成图表...")
    title = f"{stock_name} ({symbol}) - 缠论分析"
    kc = KlineChart(n_rows=3, title=title)

    df = kline_to_df(bars)
    kc.add_kline(df, name="K线")

    ma_colors = {
        "ma5": "#FF6B6B",
        "ma10": "#4ECDC4",
        "ma20": "#FFE66D",
        "ma30": "#95E1D3",
    }
    week_ma_colors = {
        "week_ma5": "#FF9FF3",
        "week_ma10": "#54A0FF",
        "week_ma20": "#5F27CD",
        "week_ma30": "#00D2D3",
    }

    if not df_ma.empty:
        for ma_name, color in ma_colors.items():
            if ma_name in df_ma.columns:
                ma_data = df_ma[ma_name].dropna()
                if len(ma_data) > 0:
                    kc.add_scatter_indicator(
                        df_ma["dt"],
                        df_ma[ma_name],
                        name=f"日{ma_name.upper()}",
                        row=1,
                        line_color=color,
                        line_width=1.0,
                        show_legend=True,
                        visible=True,
                    )

        for ma_name, color in week_ma_colors.items():
            if ma_name in df_ma.columns:
                ma_data = df_ma[ma_name].dropna()
                if len(ma_data) > 0:
                    display_name = ma_name.replace("week_", "周").upper()
                    kc.add_scatter_indicator(
                        df_ma["dt"],
                        df_ma[ma_name],
                        name=display_name,
                        row=1,
                        line_color=color,
                        line_width=1.2,
                        line_dash="dash",
                        show_legend=True,
                        visible=True,
                    )

    kc.add_vol(df, row=2)
    kc.add_macd(df, row=3)

    if c.bi_list:
        bi_x = []
        bi_y = []
        for bi in c.bi_list:
            bi_x.append(bi.fx_a.dt)
            bi_y.append(bi.fx_a.raw_bars[-1].close)
        bi_x.append(c.bi_list[-1].fx_b.dt)
        bi_y.append(c.bi_list[-1].fx_b.raw_bars[-1].close)

        kc.add_scatter_indicator(
            bi_x,
            bi_y,
            name="笔",
            row=1,
            line_color="yellow",
            line_width=1.5,
            show_legend=True,
        )

    output_path = output or f"{symbol}_czsc.html"
    kc.fig.write_html(output_path)
    print(f"\n图表已保存: {output_path}")
    print(f"请用浏览器打开查看")
    print(f"\n已添加均线指标:")
    print(f"  日线: MA5, MA10, MA20, MA30 (实线)")
    print(f"  周线: MA5, MA10, MA20, MA30 (虚线)")

    return 0


def cmd_search(args):
    """搜索股票"""
    from czsc.connectors import search_stocks

    keyword = args.keyword

    print(f"\n{'='*50}")
    print(f"搜索股票: {keyword}")
    print(f"{'='*50}\n")

    results = search_stocks(keyword)

    if not results:
        print(f"未找到包含 '{keyword}' 的股票")
        return 0

    print(f"找到 {len(results)} 只股票:\n")
    print(f"{'代码':<10} {'名称':<15}")
    print(f"{'-'*25}")
    for stock in results[:20]:
        print(f"{stock['code']:<10} {stock['name']:<15}")

    if len(results) > 20:
        print(f"\n... 还有 {len(results) - 20} 只股票未显示")

    return 0


def kline_to_df(bars):
    """将 RawBar 列表转换为 DataFrame"""
    import pandas as pd

    data = []
    for bar in bars:
        data.append(
            {
                "dt": bar.dt,
                "open": bar.open,
                "close": bar.close,
                "high": bar.high,
                "low": bar.low,
                "vol": bar.vol,
            }
        )
    return pd.DataFrame(data)


def main():
    parser = argparse.ArgumentParser(
        prog="czsc",
        description="缠中说禅技术分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python app.py              启动Web界面 (默认)
  python app.py web          启动Web界面
  python app.py analyze --symbol 000001    分析股票
  python app.py plot --symbol 000001       生成图表
  python app.py search 平安                搜索股票
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    p_web = subparsers.add_parser("web", help="启动Web界面")
    p_web.set_defaults(func=cmd_web)

    p_analyze = subparsers.add_parser("analyze", help="缠论分析")
    p_analyze.add_argument("--symbol", default="000001", help="股票代码 (默认: 000001)")
    p_analyze.add_argument("--start", default="20230101", help="开始日期 (默认: 20230101)")
    p_analyze.add_argument("--end", default="20231231", help="结束日期 (默认: 20231231)")
    p_analyze.set_defaults(func=cmd_analyze)

    p_plot = subparsers.add_parser("plot", help="生成可视化")
    p_plot.add_argument("--symbol", default="000001", help="股票代码 (默认: 000001)")
    p_plot.add_argument("--start", default="20230101", help="开始日期 (默认: 20230101)")
    p_plot.add_argument("--end", default="20231231", help="结束日期 (默认: 20231231)")
    p_plot.add_argument("--output", "-o", help="输出文件路径 (默认: {symbol}_czsc.html)")
    p_plot.set_defaults(func=cmd_plot)

    p_search = subparsers.add_parser("search", help="搜索股票")
    p_search.add_argument("keyword", help="搜索关键词 (股票代码或名称)")
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args()

    if args.command is None:
        return cmd_web(args)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

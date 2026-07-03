#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缠中说禅技术分析系统 - Web界面
"""
import os
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'

import streamlit as st
import pandas as pd
from plotly import graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title='缠论分析系统', layout='wide')

st.sidebar.title('缠论分析系统')
page = st.sidebar.radio('功能导航', ['K线图表', '缠论分析', '多股票对比', '股票搜索', '周线选股1'])

from czsc.connectors import get_raw_bars, get_all_symbols, get_date_range, search_stocks, get_stock_info
from czsc.connectors.local_connector import get_stock_data
from czsc import CZSC
import numpy as np


def get_available_symbols():
    """获取可用股票代码列表"""
    try:
        symbols = get_all_symbols()
        return symbols
    except Exception:
        return []


def plot_kline(bars, title="K线图", ma_df=None, freq='日线'):
    """绘制K线图"""
    if not bars:
        return None
    
    df = pd.DataFrame([
        {
            'dt': bar.dt.strftime('%Y-%m-%d') if hasattr(bar.dt, 'strftime') else str(bar.dt)[:10],
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'vol': bar.vol
        }
        for bar in bars
    ])
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=('价格', '成交量')
    )
    
    fig.add_trace(
        go.Candlestick(
            x=df['dt'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K线',
            increasing_line_color='red',
            decreasing_line_color='green'
        ),
        row=1, col=1
    )
    
    if ma_df is not None and not ma_df.empty:
        ma_df_copy = ma_df.copy()
        ma_df_copy['dt'] = ma_df_copy['dt'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)[:10])
        
        ma_colors = {
            'ma5': '#FF6B6B',
            'ma10': '#4ECDC4',
            'ma20': '#FFE66D',
            'ma30': '#95E1D3',
        }
        week_ma_colors = {
            'week_ma5': '#FF9FF3',
            'week_ma10': '#54A0FF',
            'week_ma20': '#5F27CD',
            'week_ma30': '#00D2D3',
        }
        
        if freq in ['日线', 'D']:
            for ma_name, color in ma_colors.items():
                if ma_name in ma_df_copy.columns:
                    ma_data = ma_df_copy[ma_name].dropna()
                    if len(ma_data) > 0:
                        fig.add_trace(
                            go.Scatter(
                                x=ma_df_copy['dt'],
                                y=ma_df_copy[ma_name],
                                mode='lines',
                                name=f"MA{ma_name.replace('ma', '')}",
                                line=dict(color=color, width=1),
                                showlegend=True
                            ),
                            row=1, col=1
                        )
        
        if freq in ['周线', 'W']:
            for ma_name, color in week_ma_colors.items():
                if ma_name in ma_df_copy.columns:
                    ma_data = ma_df_copy[ma_name].dropna()
                    if len(ma_data) > 0:
                        display_name = f"MA{ma_name.replace('week_ma', '')}"
                        fig.add_trace(
                            go.Scatter(
                                x=ma_df_copy['dt'],
                                y=ma_df_copy[ma_name],
                                mode='lines',
                                name=display_name,
                                line=dict(color=color, width=1.2),
                                showlegend=True
                            ),
                            row=1, col=1
                        )
    
    fig.add_trace(
        go.Bar(
            x=df['dt'],
            y=df['vol'],
            name='成交量',
            marker_color='rgba(100, 149, 237, 0.6)'
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        height=600,
        showlegend=True,
        hovermode='x unified',
        xaxis=dict(type='category'),
        xaxis2=dict(type='category')
    )
    
    fig.update_xaxes(title_text='日期', row=2, col=1, tickformat='%Y-%m-%d', tickangle=45)
    fig.update_yaxes(title_text='价格', row=1, col=1)
    fig.update_yaxes(title_text='成交量', row=2, col=1)
    
    return fig


def plot_czsc(czsc_obj, title="缠论分析", ma_df=None, freq='日线'):
    """绘制缠论分析图"""
    if not czsc_obj or not czsc_obj.bars_raw:
        return None
    
    bars_raw = czsc_obj.bars_raw
    df = pd.DataFrame([
        {
            'dt': bar.dt.strftime('%Y-%m-%d') if hasattr(bar.dt, 'strftime') else str(bar.dt)[:10],
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'vol': bar.vol
        }
        for bar in bars_raw
    ])
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=('缠论分析', '成交量')
    )
    
    fig.add_trace(
        go.Candlestick(
            x=df['dt'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K线',
            increasing_line_color='red',
            decreasing_line_color='green'
        ),
        row=1, col=1
    )
    
    if ma_df is not None and not ma_df.empty:
        ma_df_copy = ma_df.copy()
        ma_df_copy['dt'] = ma_df_copy['dt'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)[:10])
        
        ma_colors = {
            'ma5': '#FF6B6B',
            'ma10': '#4ECDC4',
            'ma20': '#FFE66D',
            'ma30': '#95E1D3',
        }
        week_ma_colors = {
            'week_ma5': '#FF9FF3',
            'week_ma10': '#54A0FF',
            'week_ma20': '#5F27CD',
            'week_ma30': '#00D2D3',
        }
        
        if freq in ['日线', 'D']:
            for ma_name, color in ma_colors.items():
                if ma_name in ma_df_copy.columns:
                    ma_data = ma_df_copy[ma_name].dropna()
                    if len(ma_data) > 0:
                        fig.add_trace(
                            go.Scatter(
                                x=ma_df_copy['dt'],
                                y=ma_df_copy[ma_name],
                                mode='lines',
                                name=f"MA{ma_name.replace('ma', '')}",
                                line=dict(color=color, width=1),
                                showlegend=True
                            ),
                            row=1, col=1
                        )
        
        if freq in ['周线', 'W']:
            for ma_name, color in week_ma_colors.items():
                if ma_name in ma_df_copy.columns:
                    ma_data = ma_df_copy[ma_name].dropna()
                    if len(ma_data) > 0:
                        display_name = f"MA{ma_name.replace('week_ma', '')}"
                        fig.add_trace(
                            go.Scatter(
                                x=ma_df_copy['dt'],
                                y=ma_df_copy[ma_name],
                                mode='lines',
                                name=display_name,
                                line=dict(color=color, width=1.2),
                                showlegend=True
                            ),
                            row=1, col=1
                        )
    
    if czsc_obj.bi_list:
        bi_traces_x = []
        bi_traces_y = []
        for bi in czsc_obj.bi_list:
            sdt_str = bi.sdt.strftime('%Y-%m-%d') if hasattr(bi.sdt, 'strftime') else str(bi.sdt)[:10]
            edt_str = bi.edt.strftime('%Y-%m-%d') if hasattr(bi.edt, 'strftime') else str(bi.edt)[:10]
            bi_traces_x.extend([sdt_str, edt_str, None])
            bi_traces_y.extend([bi.fx_a.fx, bi.fx_b.fx, None])
        
        fig.add_trace(
            go.Scatter(
                x=bi_traces_x,
                y=bi_traces_y,
                mode='lines',
                name='笔',
                line=dict(color='blue', width=2)
            ),
            row=1, col=1
        )
    
    if hasattr(czsc_obj, 'fx_list') and czsc_obj.fx_list:
        fx_high_x = []
        fx_high_y = []
        fx_low_x = []
        fx_low_y = []
        
        for fx in czsc_obj.fx_list:
            if hasattr(fx, 'mark'):
                dt_str = fx.dt.strftime('%Y-%m-%d') if hasattr(fx.dt, 'strftime') else str(fx.dt)[:10]
                if fx.mark.value == '顶':
                    fx_high_x.append(dt_str)
                    fx_high_y.append(fx.high)
                else:
                    fx_low_x.append(dt_str)
                    fx_low_y.append(fx.low)
        
        if fx_high_x:
            fig.add_trace(
                go.Scatter(
                    x=fx_high_x,
                    y=fx_high_y,
                    mode='markers',
                    name='顶分型',
                    marker=dict(symbol='triangle-down', size=12, color='green')
                ),
                row=1, col=1
            )
        
        if fx_low_x:
            fig.add_trace(
                go.Scatter(
                    x=fx_low_x,
                    y=fx_low_y,
                    mode='markers',
                    name='底分型',
                    marker=dict(symbol='triangle-up', size=12, color='red')
                ),
                row=1, col=1
            )
    
    fig.add_trace(
        go.Bar(
            x=df['dt'],
            y=df['vol'],
            name='成交量',
            marker_color='rgba(100, 149, 237, 0.6)'
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        height=700,
        showlegend=True,
        hovermode='x unified',
        xaxis=dict(type='category'),
        xaxis2=dict(type='category')
    )
    
    fig.update_xaxes(title_text='日期', row=2, col=1, tickformat='%Y-%m-%d', tickangle=45)
    fig.update_yaxes(title_text='价格', row=1, col=1)
    fig.update_yaxes(title_text='成交量', row=2, col=1)
    
    return fig


def show_czsc_stats(czsc_obj):
    """显示缠论分析统计信息"""
    if not czsc_obj:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("原始K线数", len(czsc_obj.bars_raw))
    
    with col2:
        st.metric("无包含K线数", len(czsc_obj.bars_ubi))
    
    with col3:
        st.metric("笔数量", len(czsc_obj.bi_list))
    
    with col4:
        if czsc_obj.bi_list:
            last_bi = czsc_obj.bi_list[-1]
            direction = "向上" if last_bi.direction.value == "向上" else "向下"
            st.metric("最后一笔方向", direction)
        else:
            st.metric("最后一笔方向", "无")


if page == 'K线图表':
    st.header('K线图表')
    
    symbols = get_available_symbols()
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if symbols:
            default_symbol = symbols[0] if symbols else "000001"
            symbol = st.selectbox('选择股票代码', symbols, index=0)
        else:
            symbol = st.text_input('输入股票代码', value='000001')
    
    with col2:
        freq = st.selectbox('选择周期', ['日线', '周线', '月线'], index=0)
    
    with col3:
        days = st.selectbox('数据范围', [30, 60, 90, 180, 365, 730], index=2)
    
    if st.button('查询', key='kline_query'):
        with st.spinner('正在加载数据...'):
            try:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
                
                bars = get_raw_bars(symbol, freq, start_date, end_date)
                
                if bars:
                    sdt_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
                    edt_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
                    ma_df = get_stock_data(symbol, sdt_fmt, edt_fmt, include_ma=True)
                    
                    stock_info = get_stock_info(symbol)
                    stock_name = stock_info.get('name', '') if stock_info else ''
                    title = f"{symbol} {stock_name} - {freq}"
                    
                    fig = plot_kline(bars, title, ma_df, freq)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    st.subheader('数据统计')
                    col1, col2, col3, col4 = st.columns(4)
                    df = pd.DataFrame([{
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close,
                        'vol': bar.vol
                    } for bar in bars])
                    
                    with col1:
                        st.metric("数据条数", len(bars))
                    with col2:
                        st.metric("最高价", f"{df['high'].max():.2f}")
                    with col3:
                        st.metric("最低价", f"{df['low'].min():.2f}")
                    with col4:
                        change = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
                        st.metric("涨跌幅", f"{change:.2f}%")
                else:
                    st.warning(f'未找到股票 {symbol} 的数据')
            except Exception as e:
                st.error(f'获取数据失败: {str(e)}')

elif page == '缠论分析':
    st.header('缠论分析')
    
    symbols = get_available_symbols()
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if symbols:
            symbol = st.selectbox('选择股票代码', symbols, index=0, key='czsc_symbol')
        else:
            symbol = st.text_input('输入股票代码', value='000001', key='czsc_symbol_input')
    
    with col2:
        freq = st.selectbox('选择周期', ['日线', '周线', '月线'], index=0, key='czsc_freq')
    
    with col3:
        days = st.selectbox('数据范围', [60, 90, 180, 365, 730], index=2, key='czsc_days')
    
    if st.button('分析', key='czsc_analyze'):
        with st.spinner('正在进行缠论分析...'):
            try:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
                
                bars = get_raw_bars(symbol, freq, start_date, end_date)
                
                if bars:
                    czsc_obj = CZSC(bars)
                    
                    sdt_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
                    edt_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
                    ma_df = get_stock_data(symbol, sdt_fmt, edt_fmt, include_ma=True)
                    
                    stock_info = get_stock_info(symbol)
                    stock_name = stock_info.get('name', '') if stock_info else ''
                    title = f"{symbol} {stock_name} - 缠论分析"
                    
                    fig = plot_czsc(czsc_obj, title, ma_df, freq)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    st.subheader('缠论统计')
                    show_czsc_stats(czsc_obj)
                    
                    if czsc_obj.bi_list:
                        st.subheader('笔列表')
                        bi_data = []
                        for i, bi in enumerate(czsc_obj.bi_list[-20:], 1):
                            bi_data.append({
                                '序号': i,
                                '方向': bi.direction.value,
                                '开始时间': bi.sdt.strftime('%Y-%m-%d'),
                                '结束时间': bi.edt.strftime('%Y-%m-%d'),
                                '开始价格': f"{bi.fx_a.fx:.2f}",
                                '结束价格': f"{bi.fx_b.fx:.2f}",
                                '长度': bi.length,
                                '涨跌幅': f"{bi.change * 100:.2f}%"
                            })
                        st.dataframe(pd.DataFrame(bi_data), use_container_width=True)
                else:
                    st.warning(f'未找到股票 {symbol} 的数据')
            except Exception as e:
                st.error(f'分析失败: {str(e)}')

elif page == '多股票对比':
    st.header('多股票对比')
    
    symbols = get_available_symbols()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if symbols:
            default_symbols = symbols[:3] if len(symbols) >= 3 else symbols
            selected_symbols = st.multiselect('选择股票代码 (最多5只)', symbols, default=default_symbols[:3])
        else:
            selected_symbols = st.text_input('输入股票代码 (逗号分隔)', value='000001,000002,600000').split(',')
            selected_symbols = [s.strip() for s in selected_symbols if s.strip()]
    
    with col2:
        days = st.selectbox('数据范围', [30, 60, 90, 180, 365], index=2, key='compare_days')
    
    if st.button('对比', key='compare_query'):
        if len(selected_symbols) > 5:
            st.warning('最多只能选择5只股票进行对比')
            selected_symbols = selected_symbols[:5]
        
        if selected_symbols:
            with st.spinner('正在加载数据...'):
                try:
                    end_date = datetime.now().strftime('%Y%m%d')
                    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
                    
                    all_data = {}
                    for sym in selected_symbols:
                        bars = get_raw_bars(sym, '日线', start_date, end_date)
                        if bars:
                            all_data[sym] = bars
                    
                    if all_data:
                        fig = go.Figure()
                        
                        colors = ['blue', 'red', 'green', 'purple', 'orange']
                        
                        for i, (sym, bars) in enumerate(all_data.items()):
                            df = pd.DataFrame([{
                                'dt': bar.dt.strftime('%Y-%m-%d') if hasattr(bar.dt, 'strftime') else str(bar.dt)[:10],
                                'close': bar.close
                            } for bar in bars])
                            
                            first_close = df['close'].iloc[0]
                            df['normalized'] = (df['close'] / first_close - 1) * 100
                            
                            stock_info = get_stock_info(sym)
                            stock_name = stock_info.get('name', '') if stock_info else ''
                            label = f"{sym} {stock_name}"
                            
                            fig.add_trace(go.Scatter(
                                x=df['dt'],
                                y=df['normalized'],
                                mode='lines',
                                name=label,
                                line=dict(color=colors[i % len(colors)], width=2)
                            ))
                        
                        fig.update_layout(
                            title='多股票走势对比 (归一化)',
                            xaxis_title='日期',
                            yaxis_title='涨跌幅 (%)',
                            height=600,
                            hovermode='x unified',
                            xaxis=dict(type='category'),
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1
                            )
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.subheader('对比统计')
                        stats_data = []
                        for sym, bars in all_data.items():
                            df = pd.DataFrame([{
                                'open': bar.open,
                                'high': bar.high,
                                'low': bar.low,
                                'close': bar.close,
                                'vol': bar.vol
                            } for bar in bars])
                            
                            stock_info = get_stock_info(sym)
                            stock_name = stock_info.get('name', '') if stock_info else ''
                            
                            stats_data.append({
                                '代码': sym,
                                '名称': stock_name,
                                '数据条数': len(bars),
                                '最新价': f"{df['close'].iloc[-1]:.2f}",
                                '最高价': f"{df['high'].max():.2f}",
                                '最低价': f"{df['low'].min():.2f}",
                                '涨跌幅': f"{(df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100:.2f}%",
                                '平均成交量': f"{df['vol'].mean():.0f}"
                            })
                        
                        st.dataframe(pd.DataFrame(stats_data), use_container_width=True)
                    else:
                        st.warning('未找到任何股票数据')
                except Exception as e:
                    st.error(f'获取数据失败: {str(e)}')
        else:
            st.warning('请选择至少一只股票')

elif page == '股票搜索':
    st.header('股票搜索')
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        keyword = st.text_input('输入股票代码或名称', placeholder='例如: 000001 或 平安')
    
    with col2:
        st.write('')
        st.write('')
        search_btn = st.button('搜索', key='search_btn')
    
    if search_btn and keyword:
        with st.spinner('正在搜索...'):
            try:
                results = search_stocks(keyword)
                
                if results:
                    st.subheader(f'搜索结果 (共 {len(results)} 条)')
                    
                    df_results = pd.DataFrame(results)
                    df_results.columns = ['代码', '名称']
                    
                    st.dataframe(df_results, use_container_width=True)
                    
                    if st.button('清空结果', key='clear_results'):
                        st.rerun()
                else:
                    st.info(f'未找到包含 "{keyword}" 的股票')
            except Exception as e:
                st.error(f'搜索失败: {str(e)}')
    
    st.subheader('所有股票列表')
    
    if st.button('加载全部股票', key='load_all'):
        with st.spinner('正在加载...'):
            try:
                all_symbols = get_all_symbols()
                
                if all_symbols:
                    st.write(f'共 {len(all_symbols)} 只股票')
                    
                    page_size = 50
                    total_pages = (len(all_symbols) + page_size - 1) // page_size
                    
                    page_num = st.number_input('页码', min_value=1, max_value=total_pages, value=1)
                    
                    start_idx = (page_num - 1) * page_size
                    end_idx = start_idx + page_size
                    page_symbols = all_symbols[start_idx:end_idx]
                    
                    symbols_with_info = []
                    for sym in page_symbols:
                        info = get_stock_info(sym)
                        if info:
                            symbols_with_info.append({
                                '代码': info.get('code', sym),
                                '名称': info.get('name', '')
                            })
                        else:
                            symbols_with_info.append({
                                '代码': sym,
                                '名称': ''
                            })
                    
                    df_symbols = pd.DataFrame(symbols_with_info)
                    st.dataframe(df_symbols, use_container_width=True)
                    
                    st.write(f'第 {page_num}/{total_pages} 页')
                else:
                    st.warning('未找到任何股票数据')
            except Exception as e:
                st.error(f'加载失败: {str(e)}')

elif page == '周线选股1':
    st.header('周线选股1 - 稳健向上趋势筛选')
    
    st.subheader('参数配置')
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        window_weeks = st.number_input('分析窗口(周)', min_value=13, max_value=104, value=52)
    
    with col2:
        segment_length = st.number_input('分段长度(周)', min_value=4, max_value=13, value=8)
    
    with col3:
        down_segment_threshold = st.slider('向下段占比阈值(%)', min_value=20, max_value=50, value=35)
    
    with col4:
        boll_threshold = st.slider('BOLL中轨上方占比阈值(%)', min_value=50, max_value=80, value=60)
    
    with st.expander('高级参数'):
        col1, col2, col3 = st.columns(3)
        with col1:
            macd_smooth_period = st.number_input('MACD平滑周期', min_value=3, max_value=10, value=5)
        with col2:
            local_low_window = st.number_input('局部低点检测窗口', min_value=2, max_value=5, value=3)
        with col3:
            boll_period = st.number_input('BOLL周期', min_value=10, max_value=30, value=20)
    
    st.subheader('选股范围')
    symbols = get_available_symbols()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if symbols:
            selected_symbols = st.multiselect('选择股票（留空则全选）', symbols, default=[])
        else:
            selected_symbols = []
            st.warning('未获取到股票列表')
    
    with col2:
        max_stocks = st.number_input('最大筛选数量', min_value=10, max_value=500, value=100)
    
    if st.button('开始选股', key='weekly_selection_start'):
        from czsc.sensors.weekly_selection import WeeklyStockSelector
        from czsc import connectors
        import time
        
        selector = WeeklyStockSelector(
            local_connector=connectors,
            window_weeks=window_weeks,
            macd_smooth_period=macd_smooth_period,
            local_low_window=local_low_window,
            boll_period=boll_period,
        )
        
        target_symbols = selected_symbols if selected_symbols else symbols[:max_stocks]
        
        edt = datetime.now().strftime('%Y%m%d')
        sdt = (datetime.now() - timedelta(weeks=window_weeks)).strftime('%Y%m%d')
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        total = len(target_symbols)
        
        for i, symbol in enumerate(target_symbols):
            progress_bar.progress((i + 1) / total)
            status_text.text(f'正在筛选: {symbol} ({i+1}/{total})')
            
            try:
                result = selector.screen_stock(
                    symbol, sdt, edt,
                    min_boll_ratio=boll_threshold/100,
                    max_down_segment_ratio=down_segment_threshold/100
                )
                if result['passed']:
                    results.append(result)
            except Exception as e:
                continue
        
        status_text.text(f'筛选完成! 共找到 {len(results)} 只符合条件的股票')
        
        if results:
            st.subheader('筛选结果')
            
            df_summary = selector.get_screening_summary(results)
            st.dataframe(df_summary, use_container_width=True)
            
            with st.expander('查看详细信息'):
                for result in results:
                    st.write(f"**{result['symbol']}**")
                    checks = result.get('checks', {})
                    indicators = result.get('indicators', {})
                    st.json({
                        '向下段占比': f"{checks.get('segment_slope', {}).get('down_ratio', 0):.1%}",
                        'BOLL中轨上方占比': f"{checks.get('boll_position', {}).get('ratio', 0):.1%}",
                        '总体斜率': f"{checks.get('total_slope', {}).get('slope', 0):.4f}",
                        '低点数量': len(indicators.get('local_lows', [])),
                        '低点抬升': checks.get('low_ascending', {}).get('passed', False),
                    })
                    st.divider()
        else:
            st.info('未找到符合条件的股票')

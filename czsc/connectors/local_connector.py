"""
author: local
create_dt: 2024
describe: 本地SQLite数据源连接器
"""

import os
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd
from loguru import logger

import czsc
from czsc import Freq, RawBar

DB_PATH = os.getenv(
    "LOCAL_DB_PATH",
    r"D:\wx_folder\code\dingding\爬虫\akshare\股票历史数据\stock_data.db",
)


def get_all_symbols():
    """获取数据库中所有股票代码

    Returns:
        list: 股票代码列表，如 ['000001', '000002', ...]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_%'")
    tables = cursor.fetchall()
    conn.close()
    symbols = [t[0].replace("stock_", "") for t in tables]
    return symbols


def get_stock_info(symbol: str):
    """获取股票基本信息

    Args:
        symbol: 股票代码，如 '000001'

    Returns:
        dict: 股票信息
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    table_name = f"stock_{symbol}"
    cursor.execute(f"SELECT stock_code, stock_name FROM {table_name} LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"code": row[0], "name": row[1]}
    return None


def get_stock_data(symbol: str, sdt: str = None, edt: str = None, include_ma: bool = True):
    """获取股票日线数据

    Args:
        symbol: 股票代码，如 '000001'
        sdt: 开始日期，格式 'YYYY-MM-DD'，默认为最早日期
        edt: 结束日期，格式 'YYYY-MM-DD'，默认为最新日期
        include_ma: 是否包含均线数据，默认为 True

    Returns:
        pd.DataFrame: K线数据
    """
    conn = sqlite3.connect(DB_PATH)
    table_name = f"stock_{symbol}"

    sql = f"""
        SELECT 
            trade_date as dt,
            stock_code as symbol,
            open_price as open,
            close_price as close,
            high_price as high,
            low_price as low,
            volume as vol,
            amount
        FROM {table_name}
        WHERE 1=1
    """

    if sdt:
        sql += f" AND trade_date >= '{sdt}'"
    if edt:
        sql += f" AND trade_date <= '{edt}'"

    sql += " ORDER BY trade_date ASC"

    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        logger.warning(f"未找到股票 {symbol} 的数据")
        return df

    df["dt"] = pd.to_datetime(df["dt"])
    df["symbol"] = symbol
    df["freq"] = Freq.D

    float_cols = ["open", "close", "high", "low", "vol", "amount"]
    df[float_cols] = df[float_cols].astype(float)

    if include_ma:
        close = df["close"].values

        df["ma5"] = _calculate_ma(close, 5)
        df["ma10"] = _calculate_ma(close, 10)
        df["ma20"] = _calculate_ma(close, 20)
        df["ma30"] = _calculate_ma(close, 30)

        week_close = _resample_to_week(df)
        df["week_ma5"] = _calculate_ma(week_close, 5)
        df["week_ma10"] = _calculate_ma(week_close, 10)
        df["week_ma20"] = _calculate_ma(week_close, 20)
        df["week_ma30"] = _calculate_ma(week_close, 30)

    return df


def _calculate_ma(close: np.ndarray, period: int) -> np.ndarray:
    """计算移动平均线

    Args:
        close: 收盘价数组
        period: 周期

    Returns:
        np.ndarray: 均线数组
    """
    result = np.full(len(close), np.nan)
    for i in range(period - 1, len(close)):
        result[i] = np.mean(close[i - period + 1 : i + 1])
    return result


def _resample_to_week(df: pd.DataFrame) -> np.ndarray:
    """将日线数据重采样为周线，返回周收盘价

    Args:
        df: 日线数据 DataFrame

    Returns:
        np.ndarray: 周收盘价数组 (与日线等长，每日填充对应的周收盘价)
    """
    df_copy = df.copy()
    df_copy.set_index("dt", inplace=True)
    weekly = df_copy.resample("W-FRI").agg({"close": "last"})
    weekly_close = weekly["close"].values

    result = np.full(len(df), np.nan)
    week_idx = 0
    for i, row in enumerate(df.itertuples()):
        if i > 0 and df.iloc[i]["dt"].week != df.iloc[i - 1]["dt"].week:
            week_idx = min(week_idx + 1, len(weekly_close) - 1)
        if week_idx < len(weekly_close) and not np.isnan(weekly_close[week_idx]):
            result[i] = weekly_close[week_idx]

    return result


def _resample_to_weekly_df(df: pd.DataFrame) -> pd.DataFrame:
    """将日线数据重采样为周线 DataFrame

    周线重采样规则：
    - 周线的开盘价 = 该周第一根日线的开盘价
    - 周线的收盘价 = 该周最后一根日线的收盘价
    - 周线的最高价 = 该周所有日线最高价的最大值
    - 周线的最低价 = 该周所有日线最低价的最小值
    - 周线的成交量 = 该周所有日线成交量之和

    Args:
        df: 日线数据 DataFrame，必须包含 dt, open, close, high, low, vol 列

    Returns:
        pd.DataFrame: 周线数据，包含 dt, open, close, high, low, vol, amount 等列
    """
    if df.empty:
        return pd.DataFrame()

    df_copy = df.copy()
    df_copy.set_index("dt", inplace=True)

    ohlc_dict = {
        "open": "first",
        "close": "last",
        "high": "max",
        "low": "min",
        "vol": "sum",
        "amount": "sum",
    }

    if "symbol" in df_copy.columns:
        ohlc_dict["symbol"] = "first"

    weekly = df_copy.resample("W-FRI").agg(ohlc_dict)
    weekly = weekly.dropna(subset=["open", "close"])

    weekly = weekly.reset_index()
    weekly["freq"] = Freq.W

    return weekly


def get_weekly_data(symbol: str, sdt: str = None, edt: str = None) -> pd.DataFrame:
    """获取股票周线数据

    通过获取日线数据后重采样为周线

    Args:
        symbol: 股票代码，如 '000001'
        sdt: 开始日期，格式 'YYYY-MM-DD'，默认为最早日期
        edt: 结束日期，格式 'YYYY-MM-DD'，默认为最新日期

    Returns:
        pd.DataFrame: 周线K线数据，包含 dt, open, close, high, low, vol, amount 等列
    """
    df_daily = get_stock_data(symbol, sdt, edt, include_ma=False)

    if df_daily.empty:
        logger.warning(f"未找到股票 {symbol} 的日线数据，无法生成周线")
        return pd.DataFrame()

    df_weekly = _resample_to_weekly_df(df_daily)

    logger.info(f"获取 {symbol} 周线数据: {sdt} ~ {edt}, 共 {len(df_weekly)} 条")
    return df_weekly


def get_raw_bars_weekly(symbol: str, sdt: str, edt: str) -> list[RawBar]:
    """获取周线 RawBar 对象列表

    Args:
        symbol: 股票代码，如 '000001' 或 '000001.SZ'
        sdt: 开始日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD'
        edt: 结束日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD'

    Returns:
        list[RawBar]: 周线 RawBar 对象列表
    """
    symbol = symbol.split(".")[0].split("#")[0]

    if len(sdt) == 8:
        sdt = f"{sdt[:4]}-{sdt[4:6]}-{sdt[6:8]}"
    if len(edt) == 8:
        edt = f"{edt[:4]}-{edt[4:6]}-{edt[6:8]}"

    df_weekly = get_weekly_data(symbol, sdt, edt)

    if df_weekly.empty:
        return []

    bars = []
    for i, row in df_weekly.iterrows():
        bar = RawBar(
            symbol=row["symbol"],
            dt=row["dt"],
            id=i,
            freq=Freq.W,
            open=row["open"],
            close=row["close"],
            high=row["high"],
            low=row["low"],
            vol=int(row["vol"]) if row["vol"] > 0 else 0,
            amount=row["amount"] if "amount" in row else 0,
        )
        bars.append(bar)

    logger.info(f"获取 {symbol} 周线 RawBar: {sdt} ~ {edt}, 共 {len(bars)} 条")
    return bars


def format_kline(df: pd.DataFrame, freq: Freq = Freq.D) -> list[RawBar]:
    """将DataFrame转换为RawBar列表

    Args:
        df: K线数据DataFrame
        freq: K线周期

    Returns:
        list[RawBar]: RawBar对象列表
    """
    if df.empty:
        return []

    bars = []
    for i, row in df.iterrows():
        bar = RawBar(
            symbol=row["symbol"],
            dt=row["dt"],
            id=i,
            freq=freq,
            open=row["open"],
            close=row["close"],
            high=row["high"],
            low=row["low"],
            vol=int(row["vol"]) if row["vol"] > 0 else 0,
            amount=row["amount"],
        )
        bars.append(bar)
    return bars


def get_raw_bars(symbol: str, freq: str, sdt: str, edt: str, fq: str = "后复权", **kwargs) -> list[RawBar]:
    """获取RawBar对象列表 - 兼容czsc标准接口

    Args:
        symbol: 股票代码，如 '000001' 或 '000001.SZ'
        freq: K线周期，支持 '日线', 'D', 'W', 'M'
        sdt: 开始日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD'
        edt: 结束日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD'
        fq: 复权方式（暂未实现，保留参数）
        **kwargs: 其他参数

    Returns:
        list[RawBar]: RawBar对象列表
    """
    symbol = symbol.split(".")[0].split("#")[0]

    freq_map = {
        "日线": Freq.D,
        "D": Freq.D,
        "周线": Freq.W,
        "W": Freq.W,
        "月线": Freq.M,
        "M": Freq.M,
    }
    freq_obj = freq_map.get(freq, Freq.D)

    if len(sdt) == 8:
        sdt = f"{sdt[:4]}-{sdt[4:6]}-{sdt[6:8]}"
    if len(edt) == 8:
        edt = f"{edt[:4]}-{edt[4:6]}-{edt[6:8]}"

    df = get_stock_data(symbol, sdt, edt)
    bars = format_kline(df, freq_obj)

    logger.info(f"获取 {symbol} {freq} 数据: {sdt} ~ {edt}, 共 {len(bars)} 条")
    return bars


def get_date_range(symbol: str):
    """获取股票数据的时间范围

    Args:
        symbol: 股票代码

    Returns:
        tuple: (开始日期, 结束日期)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    table_name = f"stock_{symbol}"
    try:
        cursor.execute(f"SELECT MIN(trade_date), MAX(trade_date) FROM {table_name}")
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        conn.close()
        logger.error(f"获取 {symbol} 时间范围失败: {e}")
        return None, None


def search_stocks(keyword: str):
    """搜索股票

    Args:
        keyword: 关键词（股票代码或名称）

    Returns:
        list: 匹配的股票列表
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_%'")
    tables = cursor.fetchall()

    results = []
    for table in tables:
        table_name = table[0]
        symbol = table_name.replace("stock_", "")
        try:
            cursor.execute(f"SELECT stock_code, stock_name FROM {table_name} LIMIT 1")
            row = cursor.fetchone()
            if row:
                code, name = row
                if keyword.upper() in code or keyword in name:
                    results.append({"code": code, "name": name})
        except Exception:
            continue

    conn.close()
    return results


if __name__ == "__main__":
    print("=== 测试本地数据连接器 ===")

    symbols = get_all_symbols()
    print(f"共 {len(symbols)} 只股票")
    print(f"前10只: {symbols[:10]}")

    print("\n=== 搜索股票 ===")
    results = search_stocks("平安")
    print(f"搜索'平安': {results}")

    print("\n=== 获取股票数据 ===")
    df = get_stock_data("000001", "2023-01-01", "2023-12-31")
    print(f"000001 2023年数据: {len(df)} 条")
    print(df.head())

    print("\n=== 获取RawBar ===")
    bars = get_raw_bars("000001", "日线", "20230101", "20231231")
    print(f"RawBar数量: {len(bars)}")
    if bars:
        print(f"第一条: {bars[0]}")
        print(f"最后一条: {bars[-1]}")

    print("\n=== 数据时间范围 ===")
    start, end = get_date_range("000001")
    print(f"000001 数据范围: {start} ~ {end}")

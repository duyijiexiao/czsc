"""
author: zengbin93
email: zeng_bin8888@163.com
create_dt: 2024
describe: 周线选股核心算法模块
"""

from typing import Callable, Optional

import numpy as np
import pandas as pd
from loguru import logger
from scipy import stats
from tqdm import tqdm

from czsc import Freq, RawBar
from czsc.utils.ta import EMA, MACD


class WeeklyStockSelector:
    """周线选股主类

    基于周线数据的选股策略，主要考察以下维度：
    1. MACD平滑均值线趋势
    2. 分段斜率分析
    3. 局部低点抬升
    4. BOLL位置分析
    5. 总体斜率验证
    """

    def __init__(
        self,
        local_connector: object,
        window_weeks: int = 52,
        macd_smooth_period: int = 5,
        local_low_window: int = 3,
        min_slope_threshold: float = 0.0,
        boll_period: int = 20,
        boll_std_dev: float = 2.0,
        **kwargs,
    ):
        """初始化周线选股器

        :param local_connector: 本地数据连接器对象，需提供 get_raw_bars 方法
        :param window_weeks: 分析窗口周数，默认52周（约一年）
        :param macd_smooth_period: MACD平滑周期，默认5
        :param local_low_window: 局部低点检测窗口，默认3
        :param min_slope_threshold: 最小斜率阈值，默认0.0
        :param boll_period: BOLL周期，默认20
        :param boll_std_dev: BOLL标准差倍数，默认2.0
        :param kwargs: 其他参数
        """
        self.local_connector = local_connector
        self.window_weeks = window_weeks
        self.macd_smooth_period = macd_smooth_period
        self.local_low_window = local_low_window
        self.min_slope_threshold = min_slope_threshold
        self.boll_period = boll_period
        self.boll_std_dev = boll_std_dev
        self.kwargs = kwargs

    def get_weekly_bars(
        self,
        symbol: str,
        sdt: str,
        edt: str,
    ) -> list[RawBar]:
        """获取周线数据

        调用 local_connector 获取日线数据后重采样为周线

        :param symbol: 股票代码
        :param sdt: 开始日期，格式 'YYYYMMDD'
        :param edt: 结束日期，格式 'YYYYMMDD'
        :return: 周线 RawBar 列表
        """
        daily_bars = self.local_connector.get_raw_bars(
            symbol=symbol,
            freq="D",
            sdt=sdt,
            edt=edt,
            fq="后复权",
        )

        if not daily_bars:
            logger.warning(f"股票 {symbol} 未获取到日线数据")
            return []

        df = pd.DataFrame([
            {
                "dt": bar.dt,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "vol": bar.vol,
                "amount": bar.amount,
            }
            for bar in daily_bars
        ])

        df.set_index("dt", inplace=True)
        weekly_df = df.resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "vol": "sum",
            "amount": "sum",
        }).dropna()

        weekly_bars = []
        for i, (dt, row) in enumerate(weekly_df.iterrows()):
            bar = RawBar(
                symbol=symbol,
                dt=dt,
                id=i,
                freq=Freq.W,
                open=row["open"],
                close=row["close"],
                high=row["high"],
                low=row["low"],
                vol=int(row["vol"]) if row["vol"] > 0 else 0,
                amount=row["amount"],
            )
            weekly_bars.append(bar)

        logger.info(f"股票 {symbol} 获取周线数据 {len(weekly_bars)} 条")
        return weekly_bars

    def calculate_macd_smoothed(
        self,
        close: np.ndarray,
        fastperiod: int = 12,
        slowperiod: int = 26,
        signalperiod: int = 9,
    ) -> np.ndarray:
        """计算MACD平滑均值线

        使用 czsc.utils.ta.MACD 计算MACD指标，然后对MACD值进行平滑处理

        :param close: 收盘价序列
        :param fastperiod: 快周期，默认12
        :param slowperiod: 慢周期，默认26
        :param signalperiod: 信号周期，默认9
        :return: 平滑后的MACD均值线数组
        """
        if len(close) < slowperiod + signalperiod:
            logger.warning("数据长度不足以计算MACD")
            return np.array([])

        diff, dea, macd = MACD(close, fastperiod, slowperiod, signalperiod)

        smoothed_macd = EMA(macd, timeperiod=self.macd_smooth_period)

        return smoothed_macd

    def calculate_segment_slopes(
        self,
        data: np.ndarray,
        segment_length: Optional[int] = None,
        num_segments: Optional[int] = None,
    ) -> tuple[list[float], float]:
        """分段斜率分析

        对每一段数据做线性回归计算斜率

        :param data: 数据序列
        :param segment_length: 每段长度，与 num_segments 二选一
        :param num_segments: 分段数量，与 segment_length 二选一
        :return: (各段斜率列表, 向下段占比)
        """
        if len(data) == 0:
            return [], 0.0

        if segment_length is None and num_segments is None:
            num_segments = 4

        if num_segments is not None:
            segment_length = max(1, len(data) // num_segments)

        if segment_length is None or segment_length < 1:
            segment_length = max(1, len(data) // 4)

        slopes = []
        down_count = 0
        total_segments = 0

        for i in range(0, len(data) - segment_length + 1, segment_length):
            segment = data[i : i + segment_length]
            if len(segment) < 2:
                continue

            x = np.arange(len(segment))
            slope, _ = np.polyfit(x, segment, 1)
            slopes.append(float(slope))

            if slope < 0:
                down_count += 1
            total_segments += 1

        down_ratio = down_count / total_segments if total_segments > 0 else 0.0

        return slopes, round(down_ratio, 4)

    def detect_local_lows(
        self,
        close: np.ndarray,
        window: Optional[int] = None,
    ) -> list[dict]:
        """检测局部低点

        局部低点定义：某点的收盘价低于前后各N个点的收盘价

        :param close: 收盘价序列
        :param window: 检测窗口，默认使用 self.local_low_window
        :return: 局部低点列表，每个元素包含 {'index': 索引, 'value': 值}
        """
        if window is None:
            window = self.local_low_window

        if len(close) < 2 * window + 1:
            return []

        local_lows = []
        for i in range(window, len(close) - window):
            left_values = close[i - window : i]
            right_values = close[i + 1 : i + window + 1]
            current_value = close[i]

            if all(current_value <= left_values) and all(current_value <= right_values):
                local_lows.append({
                    "index": i,
                    "value": float(current_value),
                })

        return local_lows

    def check_low_ascending(
        self,
        local_lows: list[dict],
        tolerance: float = 0.0,
    ) -> tuple[bool, float, list[dict]]:
        """检查低点抬升

        验证每个低点都不低于前一个低点（允许一定容差）

        :param local_lows: 局部低点列表
        :param tolerance: 容差比例，默认0.0
        :return: (是否通过验证, 低点连线斜率, 验证详情列表)
        """
        if len(local_lows) < 2:
            return True, 0.0, []

        details = []
        is_ascending = True

        for i in range(1, len(local_lows)):
            prev_low = local_lows[i - 1]["value"]
            curr_low = local_lows[i]["value"]
            threshold = prev_low * (1 - tolerance)
            passed = curr_low >= threshold

            if not passed:
                is_ascending = False

            details.append({
                "prev_index": local_lows[i - 1]["index"],
                "curr_index": local_lows[i]["index"],
                "prev_value": prev_low,
                "curr_value": curr_low,
                "passed": passed,
            })

        x = np.array([low["index"] for low in local_lows])
        y = np.array([low["value"] for low in local_lows])

        if len(x) >= 2:
            slope, _ = np.polyfit(x, y, 1)
        else:
            slope = 0.0

        return is_ascending, float(slope), details

    def calculate_boll_position(
        self,
        close: np.ndarray,
        period: Optional[int] = None,
        std_dev: Optional[float] = None,
    ) -> float:
        """BOLL位置分析

        计算收盘价在BOLL中轨上方的周数占比

        :param close: 收盘价序列
        :param period: BOLL周期，默认使用 self.boll_period
        :param std_dev: 标准差倍数，默认使用 self.boll_std_dev
        :return: 收盘价在中轨上方的周数占比
        """
        if period is None:
            period = self.boll_period
        if std_dev is None:
            std_dev = self.boll_std_dev

        if len(close) < period:
            logger.warning("数据长度不足以计算BOLL")
            return 0.0

        mid_band = np.full(len(close), np.nan)
        for i in range(period - 1, len(close)):
            mid_band[i] = np.mean(close[i - period + 1 : i + 1])

        valid_indices = ~np.isnan(mid_band)
        above_mid = close[valid_indices] >= mid_band[valid_indices]

        if len(above_mid) == 0:
            return 0.0

        ratio = np.sum(above_mid) / len(above_mid)
        return round(float(ratio), 4)

    def check_total_slope(
        self,
        data: np.ndarray,
        min_slope: Optional[float] = None,
    ) -> tuple[bool, float, float]:
        """总体斜率验证

        对整个时间窗口的数据做线性回归

        :param data: 数据序列
        :param min_slope: 最小斜率阈值，默认使用 self.min_slope_threshold
        :return: (斜率是否为正, 斜率值, R平方值)
        """
        if min_slope is None:
            min_slope = self.min_slope_threshold

        if len(data) < 2:
            return False, 0.0, 0.0

        x = np.arange(len(data))
        slope, intercept = np.polyfit(x, data, 1)

        y_pred = slope * x + intercept
        ss_res = np.sum((data - y_pred) ** 2)
        ss_tot = np.sum((data - np.mean(data)) ** 2)

        if ss_tot == 0:
            r_squared = 0.0
        else:
            r_squared = 1 - (ss_res / ss_tot)

        is_positive = slope >= min_slope

        return is_positive, round(float(slope), 6), round(float(r_squared), 4)

    def screen_stock(
        self,
        symbol: str,
        sdt: str,
        edt: str,
        check_low_ascending_flag: bool = True,
        check_total_slope_flag: bool = True,
        check_boll_position_flag: bool = True,
        check_segment_slope_flag: bool = True,
        min_boll_ratio: float = 0.5,
        max_down_segment_ratio: float = 0.5,
        low_ascending_tolerance: float = 0.02,
    ) -> dict:
        """单只股票筛选

        组合所有规则进行筛选

        :param symbol: 股票代码
        :param sdt: 开始日期
        :param edt: 结束日期
        :param check_low_ascending_flag: 是否检查低点抬升
        :param check_total_slope_flag: 是否检查总体斜率
        :param check_boll_position_flag: 是否检查BOLL位置
        :param check_segment_slope_flag: 是否检查分段斜率
        :param min_boll_ratio: BOLL位置最小占比阈值
        :param max_down_segment_ratio: 分段斜率向下段最大占比
        :param low_ascending_tolerance: 低点抬升容差
        :return: 筛选结果字典
        """
        result = {
            "symbol": symbol,
            "passed": False,
            "weekly_bars_count": 0,
            "indicators": {},
            "checks": {},
            "error": None,
        }

        try:
            weekly_bars = self.get_weekly_bars(symbol, sdt, edt)

            if len(weekly_bars) < self.window_weeks:
                result["error"] = f"周线数据不足，需要至少 {self.window_weeks} 周"
                return result

            result["weekly_bars_count"] = len(weekly_bars)

            weekly_bars = weekly_bars[-self.window_weeks :]

            close = np.array([bar.close for bar in weekly_bars])

            smoothed_macd = self.calculate_macd_smoothed(close)
            if len(smoothed_macd) == 0:
                result["error"] = "MACD计算失败"
                return result

            result["indicators"]["smoothed_macd"] = smoothed_macd.tolist()
            result["indicators"]["close"] = close.tolist()

            local_lows = self.detect_local_lows(close)
            result["indicators"]["local_lows"] = local_lows

            low_ascending_passed, low_slope, low_details = self.check_low_ascending(
                local_lows, tolerance=low_ascending_tolerance
            )
            result["checks"]["low_ascending"] = {
                "passed": low_ascending_passed,
                "slope": low_slope,
                "details": low_details,
            }

            total_slope_passed, total_slope, r_squared = self.check_total_slope(smoothed_macd)
            result["checks"]["total_slope"] = {
                "passed": total_slope_passed,
                "slope": total_slope,
                "r_squared": r_squared,
            }

            boll_ratio = self.calculate_boll_position(close)
            boll_passed = boll_ratio >= min_boll_ratio
            result["checks"]["boll_position"] = {
                "passed": boll_passed,
                "ratio": boll_ratio,
            }

            segment_slopes, down_ratio = self.calculate_segment_slopes(smoothed_macd, num_segments=4)
            segment_passed = down_ratio <= max_down_segment_ratio
            result["checks"]["segment_slope"] = {
                "passed": segment_passed,
                "slopes": segment_slopes,
                "down_ratio": down_ratio,
            }

            all_checks = []
            if check_low_ascending_flag:
                all_checks.append(low_ascending_passed)
            if check_total_slope_flag:
                all_checks.append(total_slope_passed)
            if check_boll_position_flag:
                all_checks.append(boll_passed)
            if check_segment_slope_flag:
                all_checks.append(segment_passed)

            result["passed"] = all(all_checks) if all_checks else True

        except Exception as e:
            logger.exception(f"股票 {symbol} 筛选异常: {e}")
            result["error"] = str(e)

        return result

    def screen_all_stocks(
        self,
        symbols: list[str],
        sdt: str,
        edt: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        **kwargs,
    ) -> list[dict]:
        """批量筛选

        遍历所有股票进行筛选

        :param symbols: 股票代码列表
        :param sdt: 开始日期
        :param edt: 结束日期
        :param progress_callback: 进度回调函数，参数为 (当前索引, 总数, 股票代码)
        :param kwargs: 传递给 screen_stock 的其他参数
        :return: 通过筛选的股票结果列表
        """
        passed_results = []
        total = len(symbols)

        for i, symbol in enumerate(tqdm(symbols, desc="周线选股进度")):
            if progress_callback:
                progress_callback(i, total, symbol)

            try:
                result = self.screen_stock(symbol, sdt, edt, **kwargs)

                if result["passed"]:
                    passed_results.append(result)
                    logger.info(f"股票 {symbol} 通过筛选")

            except Exception as e:
                logger.warning(f"股票 {symbol} 筛选失败: {e}")
                continue

        logger.info(f"筛选完成: 共 {total} 只股票，通过 {len(passed_results)} 只")
        return passed_results

    def get_screening_summary(
        self,
        results: list[dict],
    ) -> pd.DataFrame:
        """获取筛选结果汇总

        :param results: screen_all_stocks 返回的结果列表
        :return: 汇总 DataFrame
        """
        if not results:
            return pd.DataFrame()

        summary_data = []
        for r in results:
            row = {
                "symbol": r["symbol"],
                "weekly_bars_count": r["weekly_bars_count"],
                "low_ascending_passed": r["checks"].get("low_ascending", {}).get("passed", False),
                "low_slope": r["checks"].get("low_ascending", {}).get("slope", 0),
                "total_slope_passed": r["checks"].get("total_slope", {}).get("passed", False),
                "total_slope": r["checks"].get("total_slope", {}).get("slope", 0),
                "r_squared": r["checks"].get("total_slope", {}).get("r_squared", 0),
                "boll_passed": r["checks"].get("boll_position", {}).get("passed", False),
                "boll_ratio": r["checks"].get("boll_position", {}).get("ratio", 0),
                "segment_passed": r["checks"].get("segment_slope", {}).get("passed", False),
                "down_ratio": r["checks"].get("segment_slope", {}).get("down_ratio", 0),
            }
            summary_data.append(row)

        df = pd.DataFrame(summary_data)
        return df

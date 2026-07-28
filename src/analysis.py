"""시계열 분석 — 항공 승객 수(1949-01 ~ 1960-12, 144개월).

**표준 라이브러리만 씁니다**(차트는 matplotlib). pandas 를 쓰지 않은 이유는 이동평균·
변화율·계절 지수가 각각 몇 줄이라, 직접 구현하면 **무엇을 계산하는지가 코드에 드러나기**
때문입니다. 데이터가 수십만 행이 되면 pandas 가 맞습니다.

분석 흐름:
  ① 적재·검증  — 결측치·이상치 확인
  ② 기법 적용  — 이동평균(추세) · 전월 대비 변화율 · 전년 동월 대비 · 월별 계절 지수
  ③ 분해(보너스) — 추세 / 계절성 / 잔차
  ④ 예측(보너스) — 계절 나이브 베이스라인 + 오차 측정
"""

from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

DATA_FILE = "data/airline_passengers.csv"

# 이동평균 창 크기. 월별 데이터의 계절 주기가 12개월이므로 12를 쓴다 —
# 한 해를 통째로 평균 내면 계절 요인이 상쇄되고 **추세만** 남는다.
MA_WINDOW = 12
SEASON_PERIOD = 12
# 이상치 판정 기준(IQR 배수). 1.5 는 관례값이고, 이 데이터에는 걸리는 값이 없다.
IQR_MULTIPLIER = 1.5


@dataclass
class Series:
    """시계열 한 벌 — 월(YYYY-MM) 과 값이 같은 순서로 짝지어진 상태."""

    months: list[str] = field(default_factory=list)
    values: list[float] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.values)

    def year_of(self, index: int) -> int:
        return int(self.months[index][:4])

    def month_of(self, index: int) -> int:
        return int(self.months[index][5:7])


def load(path: str = DATA_FILE) -> Series:
    """CSV → Series. 순서를 **월 기준으로 정렬**해 둔다.

    정렬을 여기서 하는 이유: 이동평균·변화율은 "앞뒤 순서가 맞다"는 전제 위에서만 뜻이
    있다. 파일이 뒤섞여 들어와도 뒤 계산이 조용히 틀리지 않게 입구에서 보장한다.
    """
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            month = (row.get("Month") or "").strip()
            raw = (row.get("Passengers") or "").strip()
            if not month or not raw:
                continue  # 결측 행은 건너뛰고 아래 report_quality 가 몇 건인지 알린다
            rows.append((month, float(raw)))

    rows.sort(key=lambda item: item[0])
    series = Series()
    for month, value in rows:
        series.months.append(month)
        series.values.append(value)
    return series


def quality_check(series: Series, path: str = DATA_FILE) -> dict:
    """데이터 기본 정보와 결측·이상치 판정 → dict.

    **결측을 두 가지로 나눠 본다**:
      ① 값이 빈 행      — 파일에 있는데 값이 없음
      ② 빠진 달        — 행 자체가 없음(1949-01~1960-12 사이에 구멍)
    ②는 파일만 훑어서는 안 보인다. 기간을 만들어 놓고 대조해야 찾을 수 있다.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        total_rows = sum(1 for _ in csv.DictReader(f))

    expected = []
    start_year, start_month = int(series.months[0][:4]), int(series.months[0][5:7])
    for offset in range(len(series)):
        year = start_year + (start_month - 1 + offset) // 12
        month = (start_month - 1 + offset) % 12 + 1
        expected.append(f"{year:04d}-{month:02d}")
    missing_months = [m for m in expected if m not in set(series.months)]

    values = series.values
    quartile1, _, quartile3 = statistics.quantiles(values, n=4)
    iqr = quartile3 - quartile1
    low = quartile1 - IQR_MULTIPLIER * iqr
    high = quartile3 + IQR_MULTIPLIER * iqr
    outliers = [
        {"month": series.months[i], "value": values[i]}
        for i in range(len(values))
        if values[i] < low or values[i] > high
    ]

    return {
        "file_rows": total_rows,
        "loaded": len(series),
        "empty_rows": total_rows - len(series),
        "period": f"{series.months[0]} ~ {series.months[-1]}",
        "missing_months": missing_months,
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 1),
        "median": statistics.median(values),
        "stdev": round(statistics.stdev(values), 1),
        "iqr_bounds": (round(low, 1), round(high, 1)),
        "outliers": outliers,
    }


def moving_average(values: list[float], window: int = MA_WINDOW) -> list[float | None]:
    """중심 이동평균 → 앞뒤 (window//2) 개는 None.

    **왜 중심(centered)인가**: 앞에서부터 쌓는 후행 평균은 추세선이 실제보다 오른쪽으로
    밀린다(위상 지연). 추세의 위치를 보려는 것이므로 창의 가운데에 값을 놓는다.

    창이 짝수(12)면 가운데가 두 칸 사이에 걸린다. 그래서 12개월 평균을 두 번 겹쳐
    (2×12 이동평균) 가운데를 맞춘다 — 계절 조정에서 쓰는 표준 방식이다.
    """
    n = len(values)
    half = window // 2
    result: list[float | None] = [None] * n
    for i in range(half, n - half):
        chunk = values[i - half : i + half + 1]
        # 양 끝을 0.5 가중 — 12개월 두 벌의 평균과 같아진다
        weighted = sum(chunk[1:-1]) + (chunk[0] + chunk[-1]) / 2
        result[i] = weighted / window
    return result


def change_rate(values: list[float], lag: int = 1) -> list[float | None]:
    """변화율(%) — lag 개월 전 대비. 앞 lag 개는 None.

    lag=1  전월 대비 : 단기 움직임. 계절성 때문에 크게 출렁인다.
    lag=12 전년 동월 대비 : **계절 요인을 상쇄**한다 — 같은 달끼리 비교하므로
           "여름이라 늘었다"가 아니라 "작년 여름보다 늘었다"를 본다.
    """
    result: list[float | None] = [None] * len(values)
    for i in range(lag, len(values)):
        previous = values[i - lag]
        if previous:
            result[i] = (values[i] - previous) / previous * 100
    return result


def seasonal_index(series: Series) -> dict[int, float]:
    """월별 계절 지수 — 그 달이 연평균의 몇 배인지.

    각 값을 **그 해 평균**으로 나눈 뒤 달별로 평균 낸다. 연도별 평균으로 나누는 이유는
    이 데이터가 해마다 우상향하기 때문이다 — 전체 평균으로 나누면 뒤쪽 연도가 무조건
    크게 나와 계절이 아니라 추세를 재게 된다.
    """
    by_year: dict[int, list[float]] = {}
    for i in range(len(series)):
        by_year.setdefault(series.year_of(i), []).append(series.values[i])
    year_mean = {year: statistics.fmean(vals) for year, vals in by_year.items()}

    ratios: dict[int, list[float]] = {}
    for i in range(len(series)):
        mean = year_mean[series.year_of(i)]
        if mean:
            ratios.setdefault(series.month_of(i), []).append(series.values[i] / mean)
    return {month: round(statistics.fmean(vals), 3) for month, vals in sorted(ratios.items())}


def yearly_stats(series: Series) -> list[dict]:
    """연도별 합계·평균·최댓값·변동성 — 구간별 통계."""
    by_year: dict[int, list[float]] = {}
    for i in range(len(series)):
        by_year.setdefault(series.year_of(i), []).append(series.values[i])

    rows = []
    previous_total = None
    for year, values in sorted(by_year.items()):
        total = sum(values)
        rows.append({
            "year": year,
            "total": int(total),
            "mean": round(statistics.fmean(values), 1),
            "max": int(max(values)),
            "min": int(min(values)),
            "stdev": round(statistics.stdev(values), 1),
            # 변동계수(CV) — 표준편차를 평균으로 나눈 값. 규모가 커지면 표준편차도 같이
            # 커지므로, 진짜 "출렁임이 심해졌는지"는 이 비율로 봐야 한다.
            "cv": round(statistics.stdev(values) / statistics.fmean(values) * 100, 1),
            "yoy": round((total - previous_total) / previous_total * 100, 1)
            if previous_total else None,
        })
        previous_total = total
    return rows


def decompose(series: Series) -> dict:
    """보너스 (A) — 승법 분해: 값 = 추세 × 계절 × 잔차.

    **승법(곱셈)을 쓰는 이유**: 이 데이터는 규모가 커질수록 계절 진폭도 함께 커진다
    (1949년 여름 봉우리와 1960년 여름 봉우리의 높이가 다르다). 가법(덧셈) 분해는
    계절 진폭이 일정하다고 가정하므로 여기서는 잔차에 계절 무늬가 남는다.
    """
    trend = moving_average(series.values, SEASON_PERIOD)
    indices = seasonal_index(series)

    seasonal = [indices[series.month_of(i)] for i in range(len(series))]
    residual: list[float | None] = []
    for i in range(len(series)):
        if trend[i] is None or not seasonal[i]:
            residual.append(None)
        else:
            residual.append(series.values[i] / (trend[i] * seasonal[i]))
    return {"trend": trend, "seasonal": seasonal, "residual": residual}


def seasonal_naive_forecast(series: Series, horizon: int = 12) -> dict:
    """보너스 (B) — 계절 나이브 예측 + 오차 측정.

    방법: "작년 같은 달 값 × 최근 연간 성장률". 가장 단순한 축에 속하지만,
    **베이스라인이 있어야 더 복잡한 모델이 나은지 판단할 수 있다.**

    검증은 홀드아웃으로 한다 — 마지막 12개월을 떼어 두고 앞부분만으로 예측한 뒤,
    떼어 둔 실제값과 비교한다. 학습에 쓴 데이터로 정확도를 재면 항상 좋게 나온다.
    """
    if len(series) <= horizon * 2:
        raise ValueError("검증용 홀드아웃을 떼려면 최소 2주기 이상의 데이터가 필요합니다")

    split = len(series) - horizon
    train_values = series.values[:split]
    actual = series.values[split:]
    actual_months = series.months[split:]

    # 최근 2년 합계를 비교해 연간 성장률을 잡는다(작년 대비 올해가 몇 배였나).
    last_year = sum(train_values[-horizon:])
    prev_year = sum(train_values[-horizon * 2 : -horizon])
    growth = last_year / prev_year if prev_year else 1.0

    predicted = [train_values[-horizon + i] * growth for i in range(horizon)]

    errors = [predicted[i] - actual[i] for i in range(horizon)]
    abs_pct = [abs(errors[i]) / actual[i] * 100 for i in range(horizon) if actual[i]]
    return {
        "horizon": horizon,
        "growth_factor": round(growth, 4),
        "months": actual_months,
        "actual": actual,
        "predicted": [round(p, 1) for p in predicted],
        "mae": round(statistics.fmean([abs(e) for e in errors]), 1),
        "mape": round(statistics.fmean(abs_pct), 2),
        # 편향(bias) — 부호를 살린 평균 오차. 양수면 계속 과대예측했다는 뜻이다.
        "bias": round(statistics.fmean(errors), 1),
    }


def build_summary(series: Series) -> dict:
    """분석 결과 요약 → dict. **M1-2(AI Agent)가 이 JSON 을 시스템 프롬프트로 받는다.**

    무엇을 넣을지 고른 기준: 사람이 리포트를 읽지 않고도 "이 데이터가 어떤 것인지"를
    말할 수 있을 만큼. 원본 144개 값을 통째로 넘기면 프롬프트가 커지기만 하고
    모델이 요약을 다시 해야 한다.
    """
    quality = quality_check(series)
    years = yearly_stats(series)
    indices = seasonal_index(series)
    forecast = seasonal_naive_forecast(series)
    yoy = change_rate(series.values, 12)
    yoy_valid = [v for v in yoy if v is not None]

    peak_month = max(indices, key=lambda m: indices[m])
    low_month = min(indices, key=lambda m: indices[m])

    return {
        "dataset": "Airline Passengers (Box & Jenkins)",
        "period": quality["period"],
        "points": len(series),
        "unit": "천 명(월간 탑승객 수)",
        "stats": {
            "min": quality["min"], "max": quality["max"],
            "mean": quality["mean"], "median": quality["median"],
            "stdev": quality["stdev"],
        },
        "growth": {
            "first_year_total": years[0]["total"],
            "last_year_total": years[-1]["total"],
            "total_growth_pct": round(
                (years[-1]["total"] - years[0]["total"]) / years[0]["total"] * 100, 1
            ),
            "avg_yoy_pct": round(statistics.fmean(yoy_valid), 1) if yoy_valid else None,
        },
        "seasonality": {
            "peak_month": peak_month,
            "peak_index": indices[peak_month],
            "low_month": low_month,
            "low_index": indices[low_month],
            "monthly_index": indices,
        },
        "volatility": {
            "first_year_cv": years[0]["cv"],
            "last_year_cv": years[-1]["cv"],
        },
        "forecast_baseline": {
            "method": "seasonal naive × growth",
            "horizon": forecast["horizon"],
            "mape": forecast["mape"],
            "mae": forecast["mae"],
            "bias": forecast["bias"],
        },
        "quality": {
            "empty_rows": quality["empty_rows"],
            "missing_months": quality["missing_months"],
            "outliers": quality["outliers"],
        },
    }


def save_summary(summary: dict, path: str = "output/summary.json") -> str:
    """요약 JSON 저장 → 경로. M1-2 가 읽어 가는 파일이다."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return path

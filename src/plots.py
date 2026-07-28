"""시각화 4종 — 원계열+추세, 변화율, 계절 지수, 분해·예측.

**한글 폰트·Agg 백엔드 처리는 A2-1 에서 확립하고 A2-2·A2-3 이 이어받은 방식**을 그대로
씁니다. matplotlib 기본 폰트에 한글 글리프가 없어 라벨이 네모(□)로 나오는데, 그림은
정상적으로 만들어지므로 파일만 보면 놓칩니다.

차트마다 답하는 질문이 다릅니다:
  ① 원계열+이동평균 — "전체적으로 어떤 모양인가?"  (추세·계절성·진폭 확대)
  ② 변화율          — "얼마나 빨리 변하나?"        (단기 vs 계절 조정)
  ③ 계절 지수·연도별 — "언제가 성수기인가?"        (계절 요인 분리)
  ④ 분해·예측       — "구성 요소로 나누면?"        (보너스)
"""

from __future__ import annotations

import os

import matplotlib

# ⚠ pyplot import **전에** 백엔드를 지정한다. "Agg" = 화면 없이 파일로만 그린다.
matplotlib.use("Agg")

import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

KOREAN_FONTS = [
    "Malgun Gothic",  # Windows
    "AppleGothic",  # macOS
    "NanumGothic",  # Linux (fonts-nanum)
    "NanumSquareRound",
    "Noto Sans CJK KR",  # Linux (fonts-noto-cjk)
    "Noto Sans KR",
]

RAW_COLOR = "#4C72B0"
TREND_COLOR = "#C44E52"
ACCENT = "#55A868"
MUTED = "#8C8C8C"
DPI = 150


def setup_korean_font() -> str | None:
    """설치된 한글 폰트를 matplotlib 기본으로 지정 → 폰트 이름(없으면 None).

    `axes.unicode_minus = False` 를 함께 끄는 것이 **이 미션에서 특히 중요**하다 —
    변화율 차트에는 음수 눈금이 나오는데, 한글 폰트 상당수에 유니코드 음수 기호(−)가
    없어서 마이너스만 네모로 표시된다.
    """
    installed = {f.name for f in fm.fontManager.ttflist}
    for name in KOREAN_FONTS:
        if name in installed:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return name
    print("[경고] 한글 폰트를 찾지 못했습니다 — 차트의 한글이 네모(□)로 나옵니다.")
    print("       Linux: sudo apt install fonts-nanum")
    return None


def _year_ticks(months: list[str]) -> tuple[list[int], list[str]]:
    """1월 위치만 눈금으로. 144개월 라벨을 다 찍으면 읽을 수 없다."""
    positions = [i for i, m in enumerate(months) if m.endswith("-01")]
    return positions, [months[i][:4] for i in positions]


def plot_series_trend(series, trend, out_dir: str) -> str:
    """① 원계열 + 12개월 중심 이동평균."""
    setup_korean_font()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = range(len(series))

    ax.plot(x, series.values, color=RAW_COLOR, linewidth=1.4, label="월별 승객 수", alpha=0.85)
    # 이동평균은 앞뒤가 None 이라 그대로 넘기면 그 구간이 비어 그려진다(의도한 모습).
    ax.plot(x, trend, color=TREND_COLOR, linewidth=2.6, label="12개월 이동평균(추세)")

    positions, labels = _year_ticks(series.months)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_ylabel("승객 수(천 명)")
    ax.set_title("항공 승객 수와 추세 (1949–1960)")
    ax.legend(loc="upper left")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    path = os.path.join(out_dir, "01_series_trend.png")
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)  # figure 를 닫는다 — 반복 호출하면 메모리에 쌓인다
    return path


def plot_change_rate(series, mom, yoy, out_dir: str) -> str:
    """② 변화율 — 전월 대비(회색) vs 전년 동월 대비(초록)."""
    setup_korean_font()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = range(len(series))

    ax.plot(x, mom, color=MUTED, linewidth=1.1, label="전월 대비(%)", alpha=0.8)
    ax.plot(x, yoy, color=ACCENT, linewidth=2.2, label="전년 동월 대비(%)")
    # 0% 기준선 — 증가와 감소를 가르는 선이 없으면 부호를 눈으로 세야 한다.
    ax.axhline(0, color="#333333", linewidth=0.9)

    positions, labels = _year_ticks(series.months)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_ylabel("변화율(%)")
    ax.set_title("변화율 — 전월 대비는 계절 때문에 출렁이고, 전년 동월 대비는 추세를 보여 준다")
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    path = os.path.join(out_dir, "02_change_rate.png")
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    return path


def plot_seasonality(indices: dict[int, float], years: list[dict], out_dir: str) -> str:
    """③ 월별 계절 지수 + 연도별 변동계수 — 두 패널."""
    setup_korean_font()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2))

    months = list(indices)
    values = [indices[m] for m in months]
    # 1.0(연평균)을 넘으면 성수기, 밑돌면 비수기 — 색으로 갈라 한눈에 보이게 한다.
    colors = [ACCENT if v >= 1 else MUTED for v in values]
    ax1.bar([f"{m}월" for m in months], values, color=colors)
    ax1.axhline(1.0, color=TREND_COLOR, linewidth=1.2, linestyle="--", label="연평균(1.0)")
    ax1.set_ylim(0.7, 1.3)
    ax1.set_ylabel("계절 지수")
    ax1.set_title("월별 계절 지수")
    ax1.legend()
    ax1.tick_params(axis="x", rotation=45)
    ax1.spines[["top", "right"]].set_visible(False)

    ax2.plot([y["year"] for y in years], [y["cv"] for y in years],
             marker="o", color=TREND_COLOR, linewidth=2)
    ax2.set_ylabel("변동계수 CV(%)")
    ax2.set_title("연도별 변동성 — 규모 대비 출렁임")
    ax2.grid(axis="y", linestyle=":", alpha=0.4)
    ax2.tick_params(axis="x", rotation=45)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    path = os.path.join(out_dir, "03_seasonality.png")
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    return path


def plot_decompose_forecast(series, parts: dict, forecast: dict, out_dir: str) -> str:
    """④ 보너스 — 승법 분해 3단 + 예측 검증."""
    setup_korean_font()
    fig, axes = plt.subplots(4, 1, figsize=(11, 11), sharex=False)
    x = range(len(series))
    positions, labels = _year_ticks(series.months)

    axes[0].plot(x, parts["trend"], color=TREND_COLOR, linewidth=2.2)
    axes[0].set_title("분해 ① 추세 — 12개월 중심 이동평균")
    axes[0].set_ylabel("천 명")

    axes[1].plot(x, parts["seasonal"], color=ACCENT, linewidth=1.6)
    axes[1].axhline(1.0, color=MUTED, linewidth=0.9, linestyle="--")
    axes[1].set_title("분해 ② 계절 — 월별 지수(해마다 같은 무늬가 반복된다)")
    axes[1].set_ylabel("배수")

    axes[2].plot(x, parts["residual"], color=MUTED, linewidth=1.2)
    axes[2].axhline(1.0, color=TREND_COLOR, linewidth=0.9, linestyle="--")
    axes[2].set_title("분해 ③ 잔차 — 추세·계절로 설명되지 않는 나머지")
    axes[2].set_ylabel("배수")

    for ax in axes[:3]:
        ax.set_xticks(positions)
        ax.set_xticklabels(labels)
        ax.grid(axis="y", linestyle=":", alpha=0.35)
        ax.spines[["top", "right"]].set_visible(False)

    # 예측 패널 — 홀드아웃 12개월만 확대해 실제와 예측을 나란히 본다.
    fx = range(forecast["horizon"])
    axes[3].plot(fx, forecast["actual"], marker="o", color=RAW_COLOR, linewidth=2, label="실제")
    axes[3].plot(fx, forecast["predicted"], marker="s", color=TREND_COLOR, linewidth=2,
                 linestyle="--", label="예측(계절 나이브)")
    axes[3].fill_between(fx, forecast["actual"], forecast["predicted"],
                         color=TREND_COLOR, alpha=0.12)
    axes[3].set_xticks(list(fx))
    axes[3].set_xticklabels([m[5:] + "월" for m in forecast["months"]], rotation=45)
    axes[3].set_ylabel("천 명")
    axes[3].set_title(
        f"보너스 예측 — 홀드아웃 12개월 검증 (MAPE {forecast['mape']}% · "
        f"MAE {forecast['mae']} · 편향 {forecast['bias']:+.1f})"
    )
    axes[3].legend()
    axes[3].grid(axis="y", linestyle=":", alpha=0.35)
    axes[3].spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    path = os.path.join(out_dir, "04_decompose_forecast.png")
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    return path

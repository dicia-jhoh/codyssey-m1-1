"""분석 전체를 한 번에 돌린다 — 차트 4장 + 요약 JSON.

실행: python run_analysis.py

노트북 대신 스크립트를 고른 이유: 이 분석은 **매번 같은 순서로** 돌아야 하고, 결과가
파일로 남아야 한다. 노트북은 셀을 순서 없이 실행할 수 있어 "리포트의 숫자가 어느 시점
코드로 나온 것인지" 가 흐려진다. 재현성이 목적이면 스크립트가 낫다.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import analysis  # noqa: E402
import dashboard  # noqa: E402
import plots  # noqa: E402

OUT_DIR = "output"


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1/6] 데이터 적재·검증")
    series = analysis.load()
    quality = analysis.quality_check(series)
    print(f"      {quality['period']} · {quality['loaded']}개 포인트")
    print(f"      빈 행 {quality['empty_rows']}건 · 빠진 달 {len(quality['missing_months'])}개")
    print(f"      IQR 경계 {quality['iqr_bounds']} · 이상치 {len(quality['outliers'])}건")

    print("[2/6] 시계열 기법 적용")
    trend = analysis.moving_average(series.values)
    mom = analysis.change_rate(series.values, 1)
    yoy = analysis.change_rate(series.values, 12)
    indices = analysis.seasonal_index(series)
    years = analysis.yearly_stats(series)
    peak = max(indices, key=lambda m: indices[m])
    print(f"      성수기 {peak}월(지수 {indices[peak]}) · 연도 {years[0]['year']}~{years[-1]['year']}")

    print("[3/6] 분해·예측(보너스)")
    parts = analysis.decompose(series)
    forecast = analysis.seasonal_naive_forecast(series)
    halves = analysis.seasonal_index_by_half(series)
    print(f"      예측 MAPE {forecast['mape']}% · MAE {forecast['mae']} · 편향 {forecast['bias']:+.1f}")
    print(f"      계절 지수 이동 — 성수기 {halves['peak_shift']:+.3f} · 비수기 {halves['low_shift']:+.3f}")

    print("[4/6] 차트 생성")
    made = [
        plots.plot_series_trend(series, trend, OUT_DIR),
        plots.plot_change_rate(series, mom, yoy, OUT_DIR),
        plots.plot_seasonality(indices, years, OUT_DIR),
        plots.plot_decompose_forecast(series, parts, forecast, OUT_DIR),
        plots.plot_seasonal_shift(halves, OUT_DIR),
    ]
    for path in made:
        print(f"      {path}")

    print("[5/6] 요약 JSON 저장 (M1-2 입력용)")
    summary = analysis.build_summary(series)
    path = analysis.save_summary(summary, os.path.join(OUT_DIR, "summary.json"))
    print(f"      {path}")

    print("[6/6] 탐색 대시보드 생성(보너스)")
    html_path = dashboard.save(dashboard.build_html(series, summary), OUT_DIR)
    print(f"      {html_path}")

    print("\n=== 연도별 통계 ===")
    print(f"{'연도':<6}{'합계':>8}{'평균':>9}{'최대':>7}{'CV%':>7}{'전년비%':>9}")
    for row in years:
        yoy_text = f"{row['yoy']:+.1f}" if row["yoy"] is not None else "-"
        print(f"{row['year']:<6}{row['total']:>8}{row['mean']:>9}{row['max']:>7}"
              f"{row['cv']:>7}{yoy_text:>9}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

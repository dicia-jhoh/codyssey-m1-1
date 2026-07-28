# 항공 승객 수 시계열 분석 (M1-1)

1949~1960년 월별 국제선 항공 승객 수(144개월)를 분석해 **성장·계절 구조·변동성 변화**를
확인하고, 짧은 구간을 예측해 본 데이터 분석 프로젝트입니다.

**📊 분석 리포트 전문 → [REPORT.md](REPORT.md)**

| 항목 | 값 |
|---|---|
| 데이터 | Airline Passengers (Box & Jenkins) · 144개월 · 결측 0 |
| 출처 | [jbrownlee/Datasets](https://github.com/jbrownlee/Datasets/blob/master/airline-passengers.csv) |
| 적용 기법 | 중심 이동평균 · 변화율(전월/전년 동월) · 월별 계절 지수 · 연도별 구간 통계 |
| 시각화 | 4종 (원계열+추세 · 변화율 · 계절성 · 분해+예측) |
| 보너스 | 승법 시계열 분해 · 계절 나이브 예측(MAPE 2.95%) |
| 외부 의존 | `matplotlib` 하나 |

---

## 빠른 실행

```bash
git clone https://github.com/dicia-jhoh/codyssey-m1-1.git
cd codyssey-m1-1

python3 --version                  # 3.10 이상
pip install -r requirements.txt

python run_analysis.py
```

`output/` 에 차트 4장과 `summary.json` 이 생깁니다. 실행에 난수가 없어 **몇 번을 돌려도
같은 값**이 나옵니다.

## 코드 구성

```text
codyssey-m1-1/
├── REPORT.md           분석 리포트 (질문·전처리·인사이트·결론·AI 사용 로그)
├── run_analysis.py     실행 진입점 — 5단계를 순서대로
├── src/
│   ├── analysis.py     적재·검증·시계열 기법·분해·예측·요약
│   └── plots.py        차트 4종 (한글 폰트 자동 탐색 포함)
├── data/
│   └── airline_passengers.csv   원본 데이터(저장소에 동봉)
├── images/             리포트용 차트 사본
└── requirements.txt    matplotlib
```

## 주요 결과

| 인사이트 | 근거 |
|---|---|
| 12년간 약 3.8배 성장, 꾸준한 상승 | 연간 합계 1,520 → 5,714 (+275.9%), 평균 전년비 +12.9% |
| 여름 성수기 뚜렷 | 계절 지수 8월 1.237 / 11월 0.832 (약 1.49배 차이) |
| 성장과 함께 변동성도 확대 | 변동계수 10.8%(1949) → 16.3%(1960) |
| 성장 정체 구간 2회 | 1954년 +6.2%, 1958년 +3.4% |
| 계절 요인은 곱셈으로 작동 | 봉우리-골 차이 40 → 230, 승법 분해 잔차에 계절 무늬 없음 |

자세한 관찰·해석 구분과 한계는 [REPORT.md](REPORT.md) 를 보세요.

## 다음 미션과의 연결

`output/summary.json` 이 **M1-2(풀스택 AI Agent)의 입력**입니다. 분석 결론을 구조화해
두었으므로, M1-2 는 이 파일을 시스템 프롬프트에 넣어 데이터에 근거한 답변을 만듭니다.

```json
{
  "dataset": "Airline Passengers (Box & Jenkins)",
  "period": "1949-01 ~ 1960-12",
  "points": 144,
  "growth": { "total_growth_pct": 275.9, "avg_yoy_pct": 12.9 },
  "seasonality": { "peak_month": 8, "peak_index": 1.237, "low_month": 11, "low_index": 0.832 },
  "volatility": { "first_year_cv": 10.8, "last_year_cv": 16.3 },
  "forecast_baseline": { "method": "seasonal naive × growth", "mape": 2.95, "bias": 5.4 }
}
```

원본 144개 값을 통째로 넘기지 않고 요약만 넘기는 이유: 프롬프트가 커지기만 하고 모델이
요약을 다시 해야 합니다. **분석의 결론은 분석한 쪽에서 내는 것**이 맞습니다.

## 준비물 (전제 지식 0)

| 확인 항목 | 없으면 |
|---|---|
| Python 3.10 이상 | [python.org](https://www.python.org/downloads/) |
| Git | [git-scm.com](https://git-scm.com/) |
| matplotlib | `pip install -r requirements.txt` |
| 한글 폰트 | Windows·macOS 기본 제공. Linux 는 `sudo apt install fonts-nanum` |

## 용어 사전

리포트를 읽기 전에 알아 두면 좋은 말들입니다. 전체 목록은 [REPORT.md 10장](REPORT.md)에
있습니다.

| 용어 | 뜻 |
|---|---|
| **시계열** | 시간 순서대로 기록된 데이터. 순서가 곧 정보다 |
| **트렌드(추세)** | 장기적으로 오르거나 내리는 큰 흐름 |
| **계절성** | 일정한 주기로 반복되는 패턴(여기서는 12개월) |
| **이동평균** | 앞뒤 몇 개를 평균 내 울퉁불퉁함을 깎는 방법 |
| **계절 지수** | 그 달이 연평균의 몇 배인지. 1.0보다 크면 성수기 |
| **변동계수(CV)** | 표준편차 ÷ 평균. 규모가 다른 기간의 흔들림을 비교할 때 쓴다 |
| **승법 분해** | 값 = 추세 × 계절 × 잔차. 계절 진폭이 규모에 비례할 때 쓴다 |
| **홀드아웃** | 일부 구간을 떼어 두고 학습에 안 쓰는 것. 예측 성능을 정직하게 재려고 |
| **MAPE** | 평균 절대 백분율 오차. 실제값 대비 몇 % 벗어났는지 |

## 따라 하기

1. **내려받고 설치합니다.**
   ```bash
   git clone https://github.com/dicia-jhoh/codyssey-m1-1.git
   cd codyssey-m1-1 && pip install -r requirements.txt
   ```
2. **분석을 돌립니다.** 콘솔에 단계별 진행과 연도별 통계표가 나옵니다.
   ```bash
   python run_analysis.py
   ```
3. **차트를 엽니다.** `output/01_series_trend.png` 부터 순서대로 보면 리포트의 흐름과
   같습니다.
4. **리포트를 읽습니다.** [REPORT.md](REPORT.md) 의 4장에서 각 차트의 **관찰**과
   **해석**이 어떻게 구분되는지 확인하세요.
5. **수치를 바꿔 봅니다.** `src/analysis.py` 의 `MA_WINDOW` 를 3이나 6으로 바꾸고 다시
   돌리면 추세선이 어떻게 달라지는지 볼 수 있습니다(계절이 덜 상쇄됩니다).
6. **다른 데이터로 돌려 봅니다.** `data/` 에 `Month,Passengers` 형식의 CSV 를 넣고
   `DATA_FILE` 을 바꾸면 같은 분석이 그대로 돕니다.

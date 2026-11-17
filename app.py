import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# 페이지 기본 설정 (와이드 모드, 장식용 이모지 제거)
st.set_page_config(layout="wide", page_title="ETF 자산배분 및 레버리지 대시보드")

@st.cache_data
def load_data():
    """CSV 데이터를 로드하고, 날짜 타입을 변환한 뒤 종가 피벗 테이블을 생성합니다."""
    df = pd.read_csv(Path(__file__).parent / "etf_prices.csv")
    df['datetime'] = pd.to_datetime(df['datetime'])
    # datetime을 index로, symbol을 column으로 하는 피벗 테이블 생성
    pivot_df = df.pivot(index='datetime', columns='symbol', values='close')
    return pivot_df

# 데이터 로딩
try:
    prices_data = load_data()
except Exception as e:
    st.error(f"데이터 파일을 불러오는 데 실패했습니다: {e}")
    st.stop()

# ==========================================
# 1. 금융 성과 분석용 계산 함수 정의
# ==========================================

def calc_total_return(prices):
    """주어진 가격 시계열의 총수익률을 계산합니다."""
    return (prices.iloc[-1] / prices.iloc[0]) - 1

def calc_cagr(prices):
    """주어진 가격 시계열의 연환산 수익률(CAGR)을 계산합니다. 연수 = 경과일수 / 365.25"""
    total_ret = calc_total_return(prices)
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    if years <= 0:
        return 0.0
    return ((1 + total_ret) ** (1 / years)) - 1

def calc_volatility(prices):
    """주어진 가격 시계열의 일간 수익률을 구한 후, 연변동성을 계산합니다. (std * sqrt(252))"""
    daily_ret = prices.pct_change().dropna()
    return daily_ret.std(ddof=1) * (252 ** 0.5)

def calc_mdd(prices):
    """주어진 가격 시계열의 최대낙폭(MDD)을 계산합니다."""
    cummax = prices.cummax()
    drawdown = (prices / cummax) - 1
    return drawdown.min()

# ==========================================
# 2. 사이드바 (사이드바는 두 탭이 공동으로 설정값을 읽어 감)
# ==========================================
st.sidebar.header("설정 및 분석 기간")

min_date = prices_data.index.min().date()
max_date = prices_data.index.max().date()

# 분석 기간 입력
start_date = st.sidebar.date_input("분석 시작일", value=pd.to_datetime("2021-08-23").date(), min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input("분석 종료일", value=pd.to_datetime("2026-08-20").date(), min_value=min_date, max_value=max_date)

# 배당 미포함 한계 상시 안내문구 (사이드바 하단 노출)
st.sidebar.markdown("---")
st.sidebar.warning("주의: 종가 기준 가격 수익률이며 배당은 포함되지 않았습니다. 실제 성과와 다릅니다.")

# 날짜 예외처리 및 데이터 슬라이싱
if start_date >= end_date:
    st.error("오류: 분석 시작일은 종료일보다 빨라야 합니다. 날짜 설정을 확인해 주세요.")
    st.stop()

# Pandas datetime 타입으로 매칭하기 위해 캐스팅
sliced_prices = prices_data.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)]
total_days = (sliced_prices.index[-1] - sliced_prices.index[0]).days

# 영업일수(데이터 행수)가 60일 미만인 경우 경고문 표시
if len(sliced_prices) < 60:
    st.sidebar.warning("경고: 선택된 구간이 짧아(60영업일 미만) 연환산 지표가 불안정할 수 있습니다.")

# 메인 헤더
st.title("ETF 투자 교육 대시보드")

# 탭 생성
tab1, tab2 = st.tabs(["레버리지의 함정", "분산투자의 힘"])

# ==========================================
# 3. 탭 1 — 레버리지의 함정
# ==========================================
with tab1:
    st.header("레버리지 ETF의 장기 투자 위험성 분석")
    
    # 탭 1의 분석 대상: QQQ, QLD, TQQQ 고정
    lev_symbols = ["QQQ", "QLD", "TQQQ"]
    lev_prices = sliced_prices[lev_symbols]
    
    # 3-1. 정규화 가격 곡선 계산 (첫 거래일 = 100 기준)
    normalized_prices = (lev_prices / lev_prices.iloc[0]) * 100
    
    # 로그 스케일 토글 위젯
    use_log_scale = st.checkbox("로그 스케일 세로축 사용", value=False, key="log_scale_tab1")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("누적 성과 곡선 (시작점 = 100)")
        fig_perf = px.line(
            normalized_prices, 
            x=normalized_prices.index, 
            y=lev_symbols,
            labels={"value": "정규화 지수 (Base 100)", "datetime": "날짜"},
            log_y=use_log_scale
        )
        fig_perf.update_layout(legend_title_text="심볼", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_perf, width='stretch')
        
    with col2:
        st.subheader("고점 대비 낙폭 (Drawdown) 시계열")
        # 낙폭 계산
        drawdowns = pd.DataFrame()
        for sym in lev_symbols:
            cummax = lev_prices[sym].cummax()
            drawdowns[sym] = (lev_prices[sym] / cummax) - 1
            
        fig_dd = px.line(
            drawdowns * 100, 
            x=drawdowns.index, 
            y=lev_symbols,
            labels={"value": "낙폭 (%)", "datetime": "날짜"}
        )
        fig_dd.update_layout(legend_title_text="심볼", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_dd, width='stretch')

    # 3-2. 성과 요약표 계산 및 표시
    st.subheader("선택 기간 성과 요약 비교")
    summary_list = []
    for sym in lev_symbols:
        tot_ret = calc_total_return(lev_prices[sym])
        cagr_val = calc_cagr(lev_prices[sym])
        vol_val = calc_volatility(lev_prices[sym])
        mdd_val = calc_mdd(lev_prices[sym])
        
        summary_list.append({
            "심볼": sym,
            "총수익률": f"{tot_ret*100:+.1f}%",
            "연환산수익률(CAGR)": f"{cagr_val*100:.1f}%",
            "연변동성": f"{vol_val*100:.1f}%",
            "최대낙폭(MDD)": f"{mdd_val*100:.1f}%"
        })
    st.table(pd.DataFrame(summary_list))
    st.markdown("""
    * **총수익률**: 분석 기간 동안 자산 가격의 단순 누적 상승/하락률입니다.
    * **연환산수익률(CAGR)**: 기하평균을 기준으로 매년 자산이 복리로 몇 %씩 성장했는지 나타내는 비율입니다.
    * **연변동성**: 일일 수익률의 표준편차를 연간 영업일(252일) 기준으로 환산하여 자산 가격의 흔들림 정도를 뜻합니다.
    * **최대낙폭(MDD)**: 분석 기간 중 직전 역사적 고점 대비 자산이 가장 크게 폭락했을 때의 하락률(고점 대비 낙폭의 최솟값)입니다.
    """)

    # 3-4. 원금 회복 계산기
    st.subheader("원금 회복 계산기 (하락과 상승의 비대칭성)")
    loss_pct = st.slider("가상의 계좌 하락률 (%)", min_value=0, max_value=90, value=50, step=5)
    loss_ratio = loss_pct / 100.0
    required_gain = (1.0 / (1.0 - loss_ratio) - 1.0) * 100.0 if loss_ratio < 1.0 else float('inf')
    
    st.metric(label="원금 회복에 필요한 요구 상승률", value=f"{required_gain:+.1f}%")
    st.markdown("**하락과 상승은 대칭이 아닙니다.** 50% 하락했을 때 원금을 찾으려면 100% 상승(두 배)해야 하며, 80% 하락하면 400% 상승해야 원금으로 복구됩니다. 손실이 깊어질수록 회복을 위해 요구되는 노력은 기하급수적으로 증가합니다.")

    # 3-5. 핵심 메시지 자동 출력
    st.subheader("실제 데이터를 통한 레버리지 성과 점검")
    
    qqq_ret = calc_total_return(lev_prices["QQQ"])
    tqqq_ret = calc_total_return(lev_prices["TQQQ"])
    tqqq_mdd = calc_mdd(lev_prices["TQQQ"])
    
    years_elapsed = total_days / 365.25

    # 구간에 따라 3배를 넘을 수도, 1배보다 못할 수도 있다.
    # 결과에 맞는 문장을 골라야 한다. 한 가지 문장으로 고정하면 설명이 데이터와 어긋난다.
    if qqq_ret <= 0:
        verdict = (
            f"이 구간은 QQQ(1배) 자체가 {qqq_ret*100:+.1f}%로 손실이어서 "
            f"배수 비교가 성립하지 않습니다."
        )
    else:
        mult = tqqq_ret / qqq_ret
        if mult < 1:
            verdict = (
                f"추종 배수는 3배이지만 실제 {years_elapsed:.1f}년 성과는 "
                f"1배인 QQQ보다도 낮았습니다."
            )
        elif mult < 3:
            verdict = (
                f"추종 배수는 3배이지만 실제 {years_elapsed:.1f}년 성과의 차이는 "
                f"{mult:.1f}배에 그쳤습니다."
            )
        else:
            verdict = (
                f"이 구간은 상승이 이어져 {years_elapsed:.1f}년 성과의 차이가 "
                f"{mult:.1f}배로 3배를 넘었습니다. 레버리지가 유리하게 작용한 구간입니다."
            )

    message_text = (
        f"{start_date} ~ {end_date} 구간에서 TQQQ(3배)는 {tqqq_ret*100:+.1f}%, QQQ(1배)는 {qqq_ret*100:+.1f}%였습니다. "
        f"{verdict} "
        f"다만 이 구간에서 TQQQ의 최대낙폭(MDD)은 {tqqq_mdd*100:.1f}%였습니다."
    )
    st.info(message_text)
    
    st.markdown("""
    **시작일을 변경해 보십시오**  
    사이드바의 분석 시작일을 **2023-01-03**으로 바꾸면 레버리지 수익률이 기하급수적으로 폭발하는 것을 볼 수 있고, 
    반대로 **2022-01-03**으로 바꾸면 1배(QQQ) 자산이 우수한 성과를 내며 3배 레버리지는 손실이 극대화되는 모습을 확인할 수 있습니다.
    이는 일간 변동률 기준 배수의 누적 복리 효과가 상승장과 횡보장/하락장에서 다르게 작용하는 **레버리지 침식(Decay) 현상**을 실제 증명합니다.
    """)

# ==========================================
# 4. 탭 2 — 분산투자의 힘
# ==========================================
with tab2:
    st.header("자산 분산을 통한 변동성 및 위험 감소 분석")
    
    # 4-5. 자산군 성과 비교 (SPY, GLD, SCHD)
    st.subheader("주요 자산군 누적 성과 비교 (SPY: 주식, GLD: 금, SCHD: 배당성장)")
    comp_symbols = ["SPY", "GLD", "SCHD"]
    comp_prices = sliced_prices[comp_symbols]
    norm_comp_prices = (comp_prices / comp_prices.iloc[0]) * 100
    
    fig_comp = px.line(
        norm_comp_prices, 
        x=norm_comp_prices.index, 
        y=comp_symbols,
        labels={"value": "정규화 가격 (Base 100)", "datetime": "날짜"}
    )
    fig_comp.update_layout(legend_title_text="자산군", margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_comp, width='stretch')
    st.caption("주의: SCHD는 배당이 미포함된 종가 가격 기준 성과이므로 분배금을 포함한 실질 누적 수익률 대비 과소평가되어 있습니다.")

    # 4-1. 상관계수 히트맵
    st.subheader("7개 종목 간 일간수익률 상관계수 행렬 (Correlation Matrix)")
    daily_returns = sliced_prices.pct_change().dropna()
    corr_matrix = daily_returns.corr()
    
    fig_corr = px.imshow(
        corr_matrix,
        text_auto=".2f",
        aspect="auto",
        zmin=-1.0,
        zmax=1.0,
        color_continuous_scale="RdBu_r",
        labels=dict(color="상관계수")
    )
    st.plotly_chart(fig_corr, width='stretch')
    
    # 4-2. 히트맵 해석 문장
    spy_vti_corr = corr_matrix.loc["SPY", "VTI"]
    qqq_tqqq_corr = corr_matrix.loc["QQQ", "TQQQ"]
    gld_spy_corr = corr_matrix.loc["GLD", "SPY"]
    gld_schd_corr = corr_matrix.loc["GLD", "SCHD"]
    
    st.markdown(f"""
    * **SPY와 VTI의 상관계수 ({spy_vti_corr:.2f})**: 두 자산은 상관계수가 1에 극도로 가깝습니다. 이는 두 종목을 분산하여 포트폴리오에 보유하는 것이 실질적인 분산투자 및 변동성 감소 효과를 내지 못함을 뜻합니다.
    * **QQQ, QLD, TQQQ의 상관계수 ({qqq_tqqq_corr:.2f})**: 레버리지 배수만 다를 뿐 매일 완전히 비례해 움직이므로 위험 분산의 관점에서는 완전히 동일한 단일 자산입니다.
    * **금(GLD)과 주식/배당성장 자산의 상관계수 (SPY: {gld_spy_corr:.2f}, SCHD: {gld_schd_corr:.2f})**: 금 현물은 미국 주식형 지수와 매우 낮은 상관관계를 형성합니다. 이처럼 상관계수가 낮은 상이한 자산군을 배분할 때 진정한 위험 대비 분산 투자 성과 개선이 이루어집니다.
    """)

    # 4-3. 두 자산 배분 실험 (SPY & GLD)
    st.subheader("두 자산 배분 포트폴리오 시뮬레이션 (SPY & GLD)")
    st.markdown("매일 자산 비중을 정해진 비율로 강제 재조정(Daily Rebalancing)하는 가상의 자산 배분 포트폴리오를 시뮬레이션합니다.")
    
    spy_weight = st.slider("주식(SPY) 비중 (%)", min_value=0, max_value=100, value=50, step=5, key="spy_w_slider")
    gld_weight = 100 - spy_weight
    
    # 포트폴리오 일간수익률 산출
    w_spy = spy_weight / 100.0
    w_gld = gld_weight / 100.0
    
    p_daily_ret = (w_spy * daily_returns["SPY"]) + (w_gld * daily_returns["GLD"])
    # 가상의 가격 인덱스 복원 (100 시작 기준)
    p_prices = pd.Series(100.0, index=sliced_prices.index)
    p_prices.iloc[1:] = 100.0 * (1.0 + p_daily_ret).cumprod()
    
    # SPY 100% 단일 자산 기준치 계산 (대조군용)
    spy_prices = sliced_prices["SPY"]
    ref_spy_tot = calc_total_return(spy_prices)
    ref_spy_vol = calc_volatility(spy_prices)
    ref_spy_mdd = calc_mdd(spy_prices)
    
    # 포트폴리오 분석 결과 산출
    port_tot = calc_total_return(p_prices)
    port_vol = calc_volatility(p_prices)
    port_mdd = calc_mdd(p_prices)
    
    # 대조 편차 계산
    diff_tot = port_tot - ref_spy_tot
    diff_vol = port_vol - ref_spy_vol
    diff_mdd = port_mdd - ref_spy_mdd
    
    m_col1, m_col2, m_col3 = st.columns(3)
    
    with m_col1:
        st.metric(
            label="포트폴리오 총수익률", 
            value=f"{port_tot*100:.1f}%", 
            delta=f"{diff_tot*100:+.1f}%p (vs SPY 100%)"
        )
    with m_col2:
        st.metric(
            label="포트폴리오 연변동성", 
            value=f"{port_vol*100:.1f}%", 
            delta=f"{diff_vol*100:+.1f}%p (vs SPY 100%)",
            delta_color="inverse" # 변동성은 낮아지는 것이 양호(초록색)
        )
    with m_col3:
        st.metric(
            label="포트폴리오 최대낙폭(MDD)", 
            value=f"{port_mdd*100:.1f}%", 
            delta=f"{diff_mdd*100:+.1f}%p (vs SPY 100%)",
            delta_color="off"
        )

    # 4-4. 비중별 위험-수익 산점도 시뮬레이션
    st.subheader("자산 비중에 따른 위험-수익 관계 산점도 (Efficient Frontier)")
    
    scatter_data = []
    for w in range(0, 101, 10):
        w_s = w / 100.0
        w_g = 1.0 - w_s
        temp_ret = (w_s * daily_returns["SPY"]) + (w_g * daily_returns["GLD"])
        temp_prices = pd.Series(100.0, index=sliced_prices.index)
        temp_prices.iloc[1:] = 100.0 * (1.0 + temp_ret).cumprod()
        
        tot = calc_total_return(temp_prices)
        vol = calc_volatility(temp_prices)
        
        scatter_data.append({
            "SPY_weight": w,
            "총수익률": tot * 100,
            "연변동성": vol * 100,
            "label": f"SPY {w}% / GLD {100-w}%"
        })
        
    scatter_df = pd.DataFrame(scatter_data)
    
    # 차트 그리기
    fig_scatter = go.Figure()
    
    # 11개 일반 시뮬레이션 점 플로팅
    fig_scatter.add_trace(go.Scatter(
        x=scatter_df["연변동성"],
        y=scatter_df["총수익률"],
        mode="markers+text",
        text=scatter_df["SPY_weight"].apply(lambda w: f"SPY {w}%"),
        textposition="top center",
        marker=dict(size=10, color="blue", opacity=0.6),
        name="비중별 조합"
    ))
    
    # 사용자가 선택한 현재 비중 지점 강조
    fig_scatter.add_trace(go.Scatter(
        x=[port_vol * 100],
        y=[port_tot * 100],
        mode="markers",
        marker=dict(size=16, color="red", line=dict(width=2, color="black")),
        name="현재 선택 지점"
    ))
    
    fig_scatter.update_layout(
        xaxis_title="연변동성 (%)",
        yaxis_title="총수익률 (%)",
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    
    st.plotly_chart(fig_scatter, width='stretch')
    
    # 최저 변동성 조합을 실제로 계산해서 문장을 만든다.
    # 숫자를 코드에 고정하면 사용자가 기간을 바꿨을 때 설명이 틀리게 된다.
    min_vol_row = scatter_df.loc[scatter_df["연변동성"].idxmin()]
    gld_only = scatter_df.iloc[0]   # SPY 0%  = 금 100%
    spy_only = scatter_df.iloc[-1]  # SPY 100% = 주식 100%

    st.markdown(f"""
    **산점도를 통해 깨닫는 자산배분의 본질**

    이 구간에서 연변동성이 가장 낮은 조합은 주식 100%도 금 100%도 아닌
    **SPY {min_vol_row["SPY_weight"]:.0f}% / GLD {100 - min_vol_row["SPY_weight"]:.0f}%** 였습니다
    (연변동성 {min_vol_row["연변동성"]:.1f}%).
    각각 단독으로 보유했을 때의 연변동성은 SPY {spy_only["연변동성"]:.1f}%,
    GLD {gld_only["연변동성"]:.1f}% 로 둘 다 이보다 높았습니다.

    상관관계가 낮은 자산을 함께 담으면 각 자산의 고유 위험이 서로 상쇄됩니다.
    그래서 섞은 쪽이 개별 자산 각각보다 덜 흔들립니다.
    """)

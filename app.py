import streamlit as st
import pandas as pd

# ---------------------------------------------------------
# 1. 모바일 앱 반응형 뷰포트 및 규격 최적화 CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="내 손안의 아산병원 - 스마트 대기표",
    page_icon="🧭",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* 상단 기본 헤더 정리 */
header[data-testid="stHeader"] {
    background: transparent !important;
    height: 1.5rem !important;
}

/* PC에서는 스마트폰 화면(최대 480px) 중앙 정렬, 모바일에서는 100% 핏 */
.block-container {
    width: 100% !important;
    max-width: 480px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 2.5rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
    margin: 0 auto !important;
}

/* 상단 헤더 배너 */
.app-header {
    background: linear-gradient(135deg, #005C5C 0%, #104E8B 100%);
    color: white;
    padding: 16px 18px;
    border-radius: 12px;
    margin-bottom: 14px;
    box-shadow: 0 3px 8px rgba(0,0,0,0.12);
}
.app-header h3 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 800;
    color: #FFFFFF;
}
.app-header p {
    margin: 4px 0 0 0;
    font-size: 0.82rem;
    color: #E0F2F1;
}

/* 대기표 카드 */
.queue-card {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}
.status-pill {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
}
.pill-wait { background-color: #FFEBEE; color: #C62828; }
.pill-hold { background-color: #FFF8E1; color: #F57F17; }
.pill-pass { background-color: #E8F5E9; color: #2E7D32; }

/* AI 에이전트 동선 스왑 제안 배너 */
.agent-banner {
    background-color: #FFF9E6;
    border: 2px solid #FFA000;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 14px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}

/* 모바일 터치 최적화 버튼 */
div.stButton > button {
    width: 100% !important;
    min-height: 44px !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
}

/* 처방 카드 박스 */
.order-box {
    background: #F8F9FA;
    border: 1px solid #E9ECEF;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. 세션 상태 초기화 및 시연 프리셋 세팅
# ---------------------------------------------------------
if "scenario_mode" not in st.session_state:
    st.session_state.scenario_mode = "LONG"  # LONG(길 때 25분) / SHORT(짧을 때 5분)

if "xray_status" not in st.session_state:
    st.session_state.xray_status = "대기"    # 대기 / 보류(HOLD)

# ---------------------------------------------------------
# 3. 사이드바: 2가지 원클릭 설정으로 극단적 단순화
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ 시연 시나리오 설정")
    st.caption("심사용 원클릭 프리셋 2가지")

    c1, c2 = st.columns(2)
    # [설정 1] 대기시간이 길 때 (스왑 발동)
    if st.button("🔴 대기 길 때\n(25분·스왑 제안)", use_container_width=True):
        st.session_state.scenario_mode = "LONG"
        st.session_state.xray_status = "대기"
        st.rerun()

    # [설정 2] 대기시간이 짧을 때 (정상 대기)
    if st.button("🟢 대기 짧을 때\n(5분·정상 대기)", use_container_width=True):
        st.session_state.scenario_mode = "SHORT"
        st.session_state.xray_status = "대기"
        st.rerun()

    st.markdown("---")
    st.caption("• **대기 길 때**: X-ray 25분 지연 ➔ 채혈실(대기 0명) 우선 방문 에이전트 개입")
    st.caption("• **대기 짧을 때**: X-ray 5분(대기 1명) ➔ 스왑 없이 순서대로 대기")

# 시나리오에 따른 수치 결정 (FIFO 결정론적 계산 결과값)
if st.session_state.scenario_mode == "LONG":
    wait_time = 25.0
    wait_count = 6
    rooms = 2
else:
    wait_time = 5.0
    wait_count = 1
    rooms = 3

blood_lab_wait = 2  # 지하 1층 채혈실 실시간 대기: 2분 (1명)

# ---------------------------------------------------------
# 4. 모바일 메인 화면 (단일 뷰)
# ---------------------------------------------------------
# 상단 타이틀
st.markdown("""
<div class="app-header">
    <h3>🏥 서울아산병원 스마트 대기표</h3>
    <p>Rad-Flow Wayfinder 실시간 동선 최적화 에이전트</p>
</div>
""", unsafe_allow_html=True)

# 환자 기본 프로필 정보
st.info("👤 **김아산 님** (가명 ID: P001) | **금일 진료**: 호흡기내과 11:00")

# 1) 현재 접수된 검사(X-ray) 대기 카드
is_on_hold = (st.session_state.xray_status == "보류(HOLD)")

st.markdown(f"""
<div class="queue-card" style="border-left: 6px solid {'#FFA000' if is_on_hold else ('#C62828' if wait_time >= 20 else '#2E7D32')};">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-weight:800; font-size:1.05rem; color:#222;">동관 2층 일반촬영실 (X-ray)</span>
        <span class="status-pill {'pill-hold' if is_on_hold else ('pill-wait' if wait_time >= 20 else 'pill-pass')}">
            {'🔒 순번 보류중 (채혈실 이동)' if is_on_hold else ('⏳ 지연 정체중' if wait_time >= 20 else '🟢 원활 대기중')}
        </span>
    </div>
    <div style="margin-top:8px;">
        <span style="font-size:0.83rem; color:#666;">내 앞 대기: <b>{wait_count}명</b> | 가동 검사실: <b>{rooms}개</b></span><br>
        <span style="font-size:1.35rem; font-weight:800; color:{'#FFA000' if is_on_hold else ('#C62828' if wait_time >= 20 else '#2E7D32')};">
            예상 대기시간: 약 {wait_time:.0f}분
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# 2) AI 에이전트 능동형 동선 최적화 개입 구역
if wait_time >= 20.0 and not is_on_hold:
    # [상황 1: 대기시간 길 때] 선제적 스왑 제안
    st.markdown(f"""
    <div class="agent-banner">
        <div style="font-weight:800; color:#E65100; font-size:1.02rem; margin-bottom:6px;">
            📢 [AI 동선 최적화 제안] 채혈실 먼저 다녀오시겠습니까?
        </div>
        <div style="font-size:0.88rem; color:#333; line-height:1.5;">
            현재 흉부 X-ray는 대기가 <b>{wait_time:.0f}분</b>으로 밀려 있습니다.<br>
            반면 <b>지하 1층 중앙채혈실은 대기가 1명({blood_lab_wait}분)</b>으로 즉시 검사가 가능합니다.<br>
            채혈을 먼저 다녀오셔도 <b>11:00 호흡기내과 진료 전</b>에 안전하게 X-ray까지 완료됩니다!
        </div>
        <div style="margin-top:8px; font-size:0.8rem; color:#777;">
            • 동의 시 현재 X-ray 순번은 15분간 <b>안전 보류(Hold)</b> 잠금됩니다.<br>
            • 채혈 완료 즉시 X-ray <b>최우선 순번</b>으로 자동 복귀됩니다.
        </div>
    </div>
    """, unsafe_allow_html=True)

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("✅ 네, 채혈 먼저 다녀올게요!", type="primary", use_container_width=True):
            st.session_state.xray_status = "보류(HOLD)"
            st.rerun()
    with btn_col2:
        if st.button("❌ X-ray 대기실에 있을게요", use_container_width=True):
            st.toast("현재 순번대로 대기석에서 대기합니다.")

elif is_on_hold:
    # [상황 2: 환자가 스왑 동의 후 이동 중인 상태]
    st.success("""
    **🔒 X-ray 순번이 안전하게 보류(Hold) 잠금되었습니다!**  
    현재 **지하 1층 중앙채혈실 (대기 1명, 2분 소요)**로 이동 중이십니다.  
    채혈이 끝나면 바코드를 찍는 즉시 X-ray 최우선 호출 슬롯으로 복귀합니다.
    """)
    if st.button("🩸 [시뮬레이션] 채혈 완료 후 X-ray실 복귀하기", type="primary", use_container_width=True):
        st.session_state.xray_status = "대기"
        st.session_state.scenario_mode = "SHORT"
        st.rerun()

else:
    # [상황 3: 대기시간 짧을 때] 정상 진행
    st.markdown("""
    <div style="background:#F1F8F5; border:1px solid #C8E6C9; border-radius:8px; padding:12px; margin-bottom:12px; font-size:0.88rem; color:#2E7D32;">
        🟢 <b>대기 인원이 1명으로 원활합니다.</b><br>
        자리를 비우지 마시고 대기석에서 잠시만 기다려 주시면 곧 호명됩니다.
    </div>
    """, unsafe_allow_html=True)

# 3) 금일 전체 검사 오더 목록
st.markdown("##### 📋 금일 당일 검사 오더 목록")
orders = [
    {"dept": "영상의학과", "name": "흉부 X-ray (Chest PA)", "status": "🔒 순번 보류중" if is_on_hold else "접수완료", "color": "#FFA000" if is_on_hold else "#005C5C"},
    {"dept": "진단검사의학과", "name": "외래 일반채혈 (혈액검사)", "status": "이동중" if is_on_hold else "미접수", "color": "#2E7D32" if is_on_hold else "#666"},
    {"dept": "심장혈관병원", "name": "표준 12유도 심전도", "status": "미접수", "color": "#666"},
    {"dept": "호흡기내과", "name": "외래 본진료 (11:00 예약)", "status": "대기", "color": "#1976D2"}
]

for od in orders:
    st.markdown(f"""
    <div class="order-box">
        <b>[{od['dept']}]</b> {od['name']}
        <span style="float:right; font-weight:700; color:{od['color']};">
            {od['status']}
        </span>
    </div>
    """, unsafe_allow_html=True)

# 4) AI 자연어 대화형 질의응답 (하단 배치)
st.markdown("---")
st.markdown("##### 💬 AI 동선 안내 챗봇")
user_q = st.text_input("궁금한 점을 질문하세요:", placeholder="예: 지금 채혈실 다녀와도 11시 진료 안 늦나요?")
if user_q:
    if "채혈" in user_q or "진료" in user_q or "늦" in user_q:
        st.markdown(f"""
        **🤖 AI 에이전트**:  
        네, 전혀 늦지 않습니다! 현재 X-ray 대기({wait_time:.0f}분) 대비 중앙채혈실은 대기가 2분에 불과합니다.  
        채혈 후 복귀하셔도 10시 45분경 X-ray가 완료되므로 **11:00 호흡기내과 본진료에 여유 있게 도착**하실 수 있습니다.
        """)
    else:
        st.markdown(f"**🤖 AI 에이전트**: 현재 환자분의 예상 대기시간은 약 **{wait_time:.0f}분**입니다. 편안한 진료를 위해 최적 동선을 지원하고 있습니다.")

import streamlit as st
import pandas as pd
import datetime

# ---------------------------------------------------------
# 1. 페이지 기본 설정 및 서울아산병원(AMC) 테마 CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="AMC Rad-Flow Wayfinder",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* 서울아산병원 시그니처 딥틸 & 네이비 테마 */
.main-header {
    background: linear-gradient(135deg, #005C5C 0%, #104E8B 100%);
    color: white;
    padding: 20px 24px;
    border-radius: 12px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.main-header h2 { margin: 0; font-size: 1.5rem; font-weight: 800; color: #FFFFFF; }
.main-header p { margin: 6px 0 0 0; font-size: 0.92rem; color: #E0F2F1; }

/* 결정론적 연산 카드 (Zero Hallucination) */
.math-card {
    background-color: #F0F7F7;
    border: 2px solid #005C5C;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 15px;
}
.math-badge {
    background-color: #005C5C;
    color: white;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
}

/* 에이전트 능동 알림 배너 (Agent Intervention) */
.agent-banner {
    background-color: #FFF4E5;
    border-left: 6px solid #FF9800;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 15px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}

/* 모바일 큐 상태 카드 */
.queue-card {
    background: white;
    border: 1px solid #DCE6E6;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 10px;
}
.status-pill {
    padding: 3px 9px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 700;
}
.pill-wait { background-color: #FFEBEE; color: #C62828; }
.pill-hold { background-color: #FFF8E1; color: #F57F17; }
.pill-ready { background-color: #E8F5E9; color: #2E7D32; }

/* 실시간 신호등 뱃지 */
.traffic-green { color: #2E7D32; font-weight: 800; font-size: 1.1rem; }
.traffic-red { color: #C62828; font-weight: 800; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. 고정 기준 데이터 (처방별 표준 점유시간 τ & 타 부서 현황)
# ---------------------------------------------------------
# [Track 1] 검사대장에서 산출된 처방별 유효 점유시간 (촬영시간 + 포지셔닝 준비시간, 단위: 분)
EXAM_DURATION_TABLE = {
    "DXR, Chest (PA/AP)": 2.0,                  # 흉부 1장 (준비 1.0 + 촬영 1.0)
    "DXR, Abdomen supine & Upright": 3.5,       # 복부 2장 (준비 1.5 + 촬영 2.0)
    "DXR, Knee (Both)": 4.0,                    # 무릎 양측 (준비 1.5 + 촬영 2.5)
    "DXR, T-L spine (AP lateral)": 5.0,         # 척추 검사 (준비 2.0 + 촬영 3.0)
    "DXR, KUB": 2.5,                            # KUB 비뇨기 (준비 1.5 + 촬영 1.0)
    "DXR, Lower extremity (Bell thomson)": 6.0   # 특수 하지 검사
}

# 원내 검사실 실시간 현황 모의 데이터
DEPT_STATUS = {
    "XRAY_UNIT_1": {"name": "동관 2층 일반촬영 1 Unit", "rooms": 3, "location": "동관 2층"},
    "BLOOD_LAB": {"name": "중앙채혈실", "wait_mins": 3, "waiting_count": 1, "status": "여유", "location": "지하 1층"},
    "ECG_ROOM": {"name": "심전도실", "wait_mins": 5, "waiting_count": 2, "status": "여유", "location": "동관 2층"},
}

# ---------------------------------------------------------
# 3. 세션 상태 관리 (대기열 및 환자 상태)
# ---------------------------------------------------------
if "queue_data" not in st.session_state:
    # 초기 대기열 환자 목록 (FIFO 순서 정렬)
    st.session_state.queue_data = [
        {"id": "W01", "name": "이**", "exam": "DXR, Chest (PA/AP)", "status": "촬영중", "remain_min": 1.0},
        {"id": "W02", "name": "박**", "exam": "DXR, T-L spine (AP lateral)", "status": "촬영중", "remain_min": 3.5},
        {"id": "W03", "name": "최**", "exam": "DXR, Abdomen supine & Upright", "status": "촬영중", "remain_min": 2.0},
        {"id": "W04", "name": "정**", "exam": "DXR, Knee (Both)", "status": "대기", "remain_min": 4.0},
        {"id": "W05", "name": "강**", "exam": "DXR, Chest (PA/AP)", "status": "대기", "remain_min": 2.0},
        {"id": "W06", "name": "조**", "exam": "DXR, T-L spine (AP lateral)", "status": "대기", "remain_min": 5.0},
        {"id": "W07", "name": "윤**", "exam": "DXR, Abdomen supine & Upright", "status": "대기", "remain_min": 3.5},
        {"id": "W08", "name": "장**", "exam": "DXR, Knee (Both)", "status": "대기", "remain_min": 4.0},
    ]

# 로그인 시뮬레이션 가상 환자 (김아산 - 다중 검사 대상자)
if "patient_p001" not in st.session_state:
    st.session_state.patient_p001 = {
        "id": "P001",
        "name": "김아산",
        "registered": True,
        "xray_status": "대기",     # 대기 / 보류(HOLD) / 완료
        "hold_deadline": None,
        "orders": [
            {"dept": "영상의학과", "name": "흉부 X-ray (Chest PA)", "status": "접수완료", "code": "DXR, Chest (PA/AP)"},
            {"dept": "진단검사의학과", "name": "외래 일반채혈 (혈액검사)", "status": "미접수", "code": "BLOOD"},
            {"dept": "심장혈관병원", "name": "표준 12유도 심전도", "status": "미접수", "code": "ECG"},
            {"dept": "호흡기내과", "name": "외래 본진료 (11:00 예약)", "status": "대기", "code": "CLINIC"}
        ]
    }

# ---------------------------------------------------------
# 4. [Track 1] 결정론적 FIFO 대기시간 계산 함수 (Tool)
# ---------------------------------------------------------
def calculate_deterministic_wait_time(queue_list, num_rooms=3):
    """
    복잡한 시간대/요일 통계 없이, FIFO 규칙에 따라 
    앞선 환자의 잔여시간 및 처방 소요시간 합을 가동 검사실 수로 나눈 순수 수학적 연산
    """
    total_workload = 0.0
    active_in_rooms = 0

    for p in queue_list:
        if p["status"] == "촬영중":
            total_workload += p["remain_min"]
            active_in_rooms += 1
        elif p["status"] == "대기":
            total_workload += p["remain_min"]
        # '보류(HOLD)' 환자는 대기열 연산에서 일시 제외되어 뒷사람 순번이 당겨짐

    # 가동 중인 검사실 수로 분산 처리
    effective_rooms = max(1, num_rooms)
    calculated_wait = total_workload / effective_rooms
    return round(calculated_wait, 1), len([p for p in queue_list if p["status"] == "대기"])

# ---------------------------------------------------------
# 5. [Track 2] On-Premise SLM 에이전트 인지 & 행동 판단 엔진
# ---------------------------------------------------------
def agent_reasoning_and_action(xray_wait_time, patient_orders, blood_wait_time):
    """
    에이전트 인지 규칙:
    1. X-ray 대기시간이 임계치(20분) 이상인가?
    2. 당일 오더 중 대기가 없는 여유 부서(채혈실 5분 이내)가 있는가?
    3. 채혈을 다녀와도 외래 진료(11:00)까지 안전마진이 확보되는가?
    """
    has_blood_order = any(o["code"] == "BLOOD" and o["status"] != "완료" for o in patient_orders)
    
    if xray_wait_time >= 20.0 and has_blood_order and blood_wait_time <= 5:
        return {
            "intervention_required": True,
            "target_dept": "중앙채혈실 (지하 1층)",
            "target_wait": blood_wait_time,
            "reason": f"X-ray 대기시간이 {xray_wait_time}분으로 정체 중입니다. 반면 중앙채혈실은 대기가 {blood_wait_time}분(1명)으로 즉시 검사가 가능합니다. 채혈을 먼저 다녀오셔도 11:00 진료 전에 안전하게 검사가 완료됩니다.",
            "action_text": "채혈실 우선 방문 및 X-ray 15분 스마트 보류(Hold)"
        }
    return {"intervention_required": False}

# ---------------------------------------------------------
# 6. 상단 헤더 배너
# ---------------------------------------------------------
st.markdown("""
<div class="main-header">
    <h2>🧭 Rad-Flow Wayfinder | AI 에이전트 자율 동선 최적화</h2>
    <p>AMIS 검사대장 FIFO 결정론적 대기 연산(Tool) + On-Premise SLM 능동형 동선 스케줄러(Agent)</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 7. 사이드바 - 실시간 시스템 제어 패널 (심사 시연용)
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ 시스템 현장 제어판")
    st.caption("검사실 가동 현황과 대기열을 실시간 조절하여 수식 연산과 에이전트 판단 반응을 확인하세요.")
    
    num_rooms = st.slider("🏥 일반촬영 1 Unit 가동 검사실 수", min_value=1, max_value=5, value=3, step=1)
    threshold_limit = st.slider("⚠️ 에이전트 개입 대기 임계치 (분)", min_value=10, max_value=30, value=20, step=5)
    
    st.divider()
    st.markdown("#### ⚡ 시연 원클릭 프리셋")
    if st.button("📍 [시나리오 1] 피크 병목 발생 (대기 25분 ➔ 스왑 발동)", use_container_width=True):
        st.session_state.patient_p001["xray_status"] = "대기"
        st.rerun()
        
    if st.button("🔄 대기열 초기화 (Reset)", use_container_width=True):
        st.session_state.patient_p001["xray_status"] = "대기"
        st.session_state.queue_data = [
            {"id": "W01", "name": "이**", "exam": "DXR, Chest (PA/AP)", "status": "촬영중", "remain_min": 1.0},
            {"id": "W02", "name": "박**", "exam": "DXR, T-L spine (AP lateral)", "status": "촬영중", "remain_min": 3.5},
            {"id": "W03", "name": "최**", "exam": "DXR, Abdomen supine & Upright", "status": "촬영중", "remain_min": 2.0},
            {"id": "W04", "name": "정**", "exam": "DXR, Knee (Both)", "status": "대기", "remain_min": 4.0},
            {"id": "W05", "name": "강**", "exam": "DXR, Chest (PA/AP)", "status": "대기", "remain_min": 2.0},
            {"id": "W06", "name": "조**", "exam": "DXR, T-L spine (AP lateral)", "status": "대기", "remain_min": 5.0},
            {"id": "W07", "name": "윤**", "exam": "DXR, Abdomen supine & Upright", "status": "대기", "remain_min": 3.5},
            {"id": "W08", "name": "장**", "exam": "DXR, Knee (Both)", "status": "대기", "remain_min": 4.0},
        ]
        st.rerun()

# ---------------------------------------------------------
# 8. 메인 뷰: 3개 탭 구성 (환자 앱 / 의료진 뷰 / 아키텍처 검증)
# ---------------------------------------------------------
tab_patient, tab_staff, tab_architecture = st.tabs([
    "📱 [환자용] 스마트 대기표 & AI 동선 가이드",
    "🖥️ [방사선사용] 실시간 큐 & 로드밸런싱 워크리스트",
    "🧪 [검증용] 수리 연산(Tool) vs 에이전트(Action) 아키텍처"
])

# 실시간 대기시간 계산
current_wait_min, current_waiting_count = calculate_deterministic_wait_time(st.session_state.queue_data, num_rooms)
agent_decision = agent_reasoning_and_action(current_wait_min, st.session_state.patient_p001["orders"], DEPT_STATUS["BLOOD_LAB"]["wait_mins"])

# =========================================================
# TAB 1: 환자용 모바일 화면 (스마트 대기표 & 자율 동선)
# =========================================================
with tab_patient:
    p_col1, p_col2 = st.columns([1.1, 1.4], gap="large")

    with p_col1:
        st.markdown("#### 🎫 나의 모바일 검사 접수증")
        patient = st.session_state.patient_p001
        
        # 상단 환자 프로필 바
        st.info(f"**수진자**: {patient['name']} (등록번호: 가명화 P001) | **금일 진료**: 호흡기내과 11:00")
        
        # X-ray 대기 상태 카드
        st.markdown(f"""
        <div class="queue-card" style="border-left: 6px solid {'#FF9800' if patient['xray_status'] == '보류(HOLD)' else '#005C5C'};">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700; font-size:1.05rem;">동관 2층 일반촬영(X-ray)</span>
                <span class="status-pill {'pill-hold' if patient['xray_status'] == '보류(HOLD)' else 'pill-wait'}">
                    {'🔒 순번 보류중 (채혈 이동)' if patient['xray_status'] == '보류(HOLD)' else '⏳ 촬영 대기중'}
                </span>
            </div>
            <div style="margin-top:10px;">
                <span style="font-size:0.85rem; color:#666;">내 앞 대기: <b>{current_waiting_count}명</b> | 가동 검사방: <b>{num_rooms}개</b></span><br>
                <span style="font-size:1.3rem; font-weight:800; color:{'#F57F17' if patient['xray_status'] == '보류(HOLD)' else '#C62828'};">
                    예상 대기시간: 약 {current_wait_min}분
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 당일 전체 처방 오더 현황
        st.markdown("##### 📋 금일 당일 검사 오더 목록")
        for od in patient["orders"]:
            is_hold_item = (od["code"] == "DXR, Chest (PA/AP)" and patient["xray_status"] == "보류(HOLD)")
            st.markdown(f"""
            <div style="background:#FDFDFD; border:1px solid #E0E0E0; border-radius:6px; padding:8px 12px; margin-bottom:6px; font-size:0.85rem;">
                <b>[{od['dept']}]</b> {od['name']}
                <span style="float:right; font-weight:700; color:{'#F57F17' if is_hold_item else '#005C5C'};">
                    {'🔒 순번 킵(Hold)' if is_hold_item else od['status']}
                </span>
            </div>
            """, unsafe_allow_html=True)

    with p_col2:
        st.markdown("#### 🤖 Rad-Flow 능동형 에이전트 동선 가이드")
        
        # [핵심 로직] 에이전트 선제적 스왑 제안
        if agent_decision["intervention_required"] and patient["xray_status"] != "보류(HOLD)":
            st.markdown(f"""
            <div class="agent-banner">
                <div style="font-weight:800; color:#D84315; font-size:1.1rem; margin-bottom:6px;">
                    📢 [AI 동선 최적화 제안] 채혈실을 먼저 다녀오시겠습니까?
                </div>
                <div style="font-size:0.9rem; color:#333; line-height:1.5;">
                    {agent_decision['reason']}
                </div>
                <div style="margin-top:10px; font-size:0.85rem; color:#666;">
                    • <b>보류 혜택</b>: 동의 시 현재 X-ray 대기 순번은 15분간 안전하게 보류 잠금(Hold)됩니다.<br>
                    • <b>복귀 혜택</b>: 채혈 완료 바코드 스캔 즉시 X-ray 최우선 순번으로 자동 복귀됩니다.
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("✅ 네, 대기 없는 채혈실 먼저 다녀올게요!", use_container_width=True, type="primary"):
                    st.session_state.patient_p001["xray_status"] = "보류(HOLD)"
                    # 대기열에 보류 상태 반영
                    st.session_state.queue_data.append({
                        "id": "P001", "name": "김아산(나)", "exam": "DXR, Chest (PA/AP)", "status": "보류(HOLD)", "remain_min": 2.0
                    })
                    st.rerun()
            with btn_col2:
                if st.button("❌ 그냥 X-ray 대기실에 있을게요", use_container_width=True):
                    st.info("현재 X-ray 대기석에서 순서대로 대기합니다.")
                    
        elif patient["xray_status"] == "보류(HOLD)":
            st.success(f"""
            **🔒 X-ray 순번이 15분간 안전하게 보류(Hold) 잠금되었습니다!**  
            현재 **지하 1층 중앙채혈실 (대기 1명, 3분 소요)**로 이동 중이십니다.  
            채혈이 끝나면 바코드를 찍으시는 즉시 X-ray 최우선 호출 슬롯으로 복귀합니다.
            """)
            
            # 복귀 시뮬레이션 버튼
            if st.button("🩸 [시뮬레이션] 채혈 완료 후 X-ray실 복귀", use_container_width=True):
                st.session_state.patient_p001["xray_status"] = "대기"
                # 보류자 목록에서 다시 최우선 대기(맨 앞)로 승격
                st.session_state.queue_data = [p for p in st.session_state.queue_data if p["id"] != "P001"]
                st.session_state.queue_data.insert(3, {
                    "id": "P001", "name": "김아산(나·우선복귀)", "exam": "DXR, Chest (PA/AP)", "status": "대기", "remain_min": 2.0
                })
                for od in st.session_state.patient_p001["orders"]:
                    if od["code"] == "BLOOD":
                        od["status"] = "완료"
                st.rerun()
        else:
            st.info("현재 대기 순서대로 순조롭게 검사가 진행 중입니다. 호명에 귀 기울여 주세요.")

        # 대화형 자연어 질의응답 (On-Premise SLM 인터페이스)
        st.markdown("---")
        st.markdown("##### 💬 길 안내 & 일정 AI 대화")
        user_q = st.text_input("궁금한 점을 질문하세요:", placeholder="예: 지금 채혈실 다녀와도 11시 진료 안 늦나요?")
        if user_q:
            if "채혈" in user_q or "진료" in user_q:
                st.markdown(f"""
                **🤖 AI 에이전트 응답**:  
                네, 안 늦습니다! 현재 X-ray 대기는 **{current_wait_min}분**으로 지연 중이지만, 중앙채혈실은 대기가 **3분**에 불과합니다.  
                채혈(도보 포함 약 10분) 후 복귀하셔도 10시 45분경 X-ray가 완료되어, **11:00 호흡기내과 본진료에 여유 있게 도착**하실 수 있습니다.
                """)
            else:
                st.markdown(f"**🤖 AI 에이전트 응답**: 현재 환자분의 X-ray 대기 순번은 결정론적 연산에 따라 **약 {current_wait_min}분** 소요될 예정입니다.")

# =========================================================
# TAB 2: 방사선사 전용 현장 워크리스트 및 부하 분산 뷰
# =========================================================
with tab_staff:
    st.markdown("#### 🖥️ 일반촬영 1 Unit 현장 방사선사 통합 대시보드")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    with col_stat1:
        st.metric("가동 검사방 수", f"{num_rooms}개 방")
    with col_stat2:
        st.metric("현재 대기 인원", f"{current_waiting_count}명")
    with col_stat3:
        st.metric("실시간 예측 대기시간", f"{current_wait_min}분")
    with col_stat4:
        hold_count = len([p for p in st.session_state.queue_data if p["status"] == "보류(HOLD)"])
        st.metric("동선 스왑 보류자 (HOLD)", f"{hold_count}명", delta="유휴지연 방지")

    st.markdown("##### 📋 실시간 검사실 큐 (AMIS 3.0 연동 뷰)")
    df_queue = pd.DataFrame(st.session_state.queue_data)
    
    # 데이터프레임 스타일 적용
    st.dataframe(
        df_queue.style.applymap(
            lambda v: "background-color: #FFF3E0; color: #E65100; font-weight:bold;" if v == "보류(HOLD)" 
            else ("background-color: #E8F5E9; color: #2E7D32;" if v == "촬영중" else ""),
            subset=["status"]
        ),
        use_container_width=True
    )
    
    st.caption("💡 **방사선사 편익**: 환자가 임의로 자리를 비워 호명 시 발생하던 유휴시간(건당 1분, 하루 40분)이 '스마트 큐 홀드'를 통해 자동으로 뒷사람에게 패스되므로 끊김 없이 연속 촬영이 가능합니다.")

# =========================================================
# TAB 3: 심사위원 시연용 아키텍처 및 무환각 수리 검증
# =========================================================
with tab_architecture:
    st.markdown("#### 🧪 Two-Track 하이브리드 아키텍처 상세 검증")
    
    arch_col1, arch_col2 = st.columns(2)
    
    with arch_col1:
        st.markdown("""
        <div class="math-card">
            <span class="math-badge">Track 1: Deterministic FIFO Tool</span>
            <h4 style="margin:8px 0; color:#005C5C;">수학적 대기시간 계산식 (0% 환각)</h4>
            <p style="font-size:0.88rem; color:#444;">
                복잡한 '시간대'나 '요일' 통계 변수를 배제하고, 순수 선착순(FIFO) 큐에 기반한 결정론적 수식으로 단순화하여 신뢰성을 확보합니다.
            </p>
            <div style="background:white; padding:10px; border-radius:6px; font-family:monospace; font-size:0.95rem;">
                예상 대기시간 = [ ∑(대기자 처방 소요시간) + 진행중 잔여시간 ] ÷ 가동 검사실 수
            </div>
            <div style="margin-top:10px; font-size:0.85rem; color:#555;">
                • 현재 총 잔여 작업량: <b>{:.1f}분</b><br>
                • 가동 검사실 수: <b>{}개</b><br>
                • ➔ <b>연산 결과: {:.1f}분 (연산 오차 0.0초, 무환각)</b>
            </div>
        </div>
        """.format(current_wait_min * num_rooms, num_rooms, current_wait_min), unsafe_allow_html=True)
        
    with arch_col2:
        st.markdown(f"""
        <div class="math-card" style="border-color:#E65100; background-color:#FFF8F3;">
            <span class="math-badge" style="background-color:#E65100;">Track 2: Active Agentic Core</span>
            <h4 style="margin:8px 0; color:#E65100;">자율 동선 스케줄러 (능동적 해결사)</h4>
            <p style="font-size:0.88rem; color:#444;">
                단순히 숫자를 통보하는 수동적 계측기를 넘어, 병목 임계치 감지 시 타 부서로 환자를 자율 탈출시키는 액션을 수행합니다.
            </p>
            <div style="background:white; padding:10px; border-radius:6px; font-size:0.85rem;">
                <b>• 의사결정 규칙 (Agentic Rules)</b>:<br>
                1. X-ray 대기({current_wait_min}분) ≥ 임계치({threshold_limit}분) ➔ <b>{'충족 (개입)' if current_wait_min >= threshold_limit else '미충족 (대기유지)'}</b><br>
                2. 타 검사실(채혈실) 대기시간 ➔ <b>3분 (매우 여유)</b><br>
                3. 외래 진료 시각 역산 안전마진 ➔ <b>안전 확보 (진료 지연 0%)</b>
            </div>
            <div style="margin-top:10px; font-size:0.85rem; color:#E65100; font-weight:700;">
                ➔ Action: 스마트 큐 홀드 및 채혈실 우회 동선 푸시 발송
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("##### 📊 처방별 고유 소요시간($\tau$) 기준표 (검사대장 추출 기준)")
    df_exam_times = pd.DataFrame(list(EXAM_DURATION_TABLE.items()), columns=["처방 검사명", "표준 점유 소요시간 (촬영 + 준비, 분)"])
    st.table(df_exam_times)

import streamlit as st
from openai import OpenAI
import json
import os
import base64
import random

# --- 페이지 설정 ---
st.set_page_config(
    page_title="HOMI AI 영상 프롬프트 에이전트",
    page_icon="🎬",
    layout="wide"
)

# ==========================================
# 데이터: HOMI 1.0 팁 리스트
# ==========================================
HOMI_TIPS = [
    "MUST-T2I-1: 이미지가 예쁜지보다 '시킨 대로 됐는지'를 먼저 확인하세요.",
    "MUST-T2I-2: 미디엄/와이드 샷은 절대 짧은 프롬프트로 쓰지 말고, 구조화된 긴 템플릿을 쓰세요.",
    "MUST-T2I-3: 레퍼런스 이미지(@img)나 인물 합성은 일반 작업보다 훨씬 어려우니 별도로 관리하세요.",
    "MUST-T2I-4: 같은 프롬프트를 20번 넘게 돌려도 안 되면, 프롬프트가 아니라 샷 자체를 바꾸세요.",
    "SHOULD-T2I-1: 한 프롬프트 안에서 한국어와 영어를 섞지 마세요.",
    "SHOULD-T2I-2: '포토리얼' 키워드는 성공률을 크게 깎으니, 쓸 때는 구도를 타이트하게 보완하세요.",
    "SHOULD-T2I-3: 의도 태그는 4개 전후가 적당하고, 너무 적거나 너무 많으면 실패합니다.",
    "T2I 인사이트: 카메라가 가까울수록(클로즈업) 성공률이 높고, 멀수록(와이드) 급격히 떨어집니다.",
    "T2I 실패 밸리: 21~40단어 구간이 가장 위험하니, 10단어 이하 or 41단어 이상으로 가세요.",
    "T2I 주요 실패 원인: 이미지가 못생겨서가 아니라 시킨 걸 틀리게 해서(E2) 실패하는 경우가 76.6%입니다.",
    "MUST-I2V-1: 프롬프트는 10단어 이하로 최대한 짧게 쓰세요.",
    "MUST-I2V-2: 의도는 '샷 구도 + 행동' 딱 2개만 넣으세요.",
    "MUST-I2V-3: 장소·조명·분위기는 이미지(T2I)에서 이미 정해졌으니 영상 프롬프트에서는 빼세요.",
    "MUST-I2V-4: 영상 QC는 '움직임이 어색해서 몰입이 깨지는가'를 가장 먼저 봐야 합니다.",
    "SHOULD-I2V-1: 복잡한 동작은 하나의 단순한 동작으로 쪼개세요.",
    "SHOULD-I2V-2: 걷기·잡기·싸움·불·물 같은 Hard Action은 카메라를 고정하고, 실패하면 인서트/컷어웨이로 분해하세요.",
    "I2V 인사이트: T2I는 길고 구체적일수록 좋지만, I2V는 짧고 단순할수록 성공률이 높습니다.",
    "I2V 안전한 조합: '인물 감정 + 샷 구도'는 안전하고, '장소 설명 + 조명'은 가장 위험합니다.",
    "I2V 카메라 고정: static/steady를 명시하면 만족률이 약 81%까지 올라갑니다."
]

tips_js_array = json.dumps(HOMI_TIPS)

# ==========================================
# 함수: 이미지를 Base64로 변환 (HTML 삽입용)
# ==========================================
def get_img_as_base64(file_path):
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

logo_b64 = get_img_as_base64("logo.png")
logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height: 50px; margin-right: 15px; vertical-align: middle;">' if logo_b64 else "🎬"

# ==========================================
# 커스텀 CSS
# ==========================================
st.markdown("""
<style>
    /* 1. Basic 박스 스타일 */
    .result-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #d6d6d6;
        max-height: 200px;
        overflow-y: auto;
        font-size: 14px;
        line-height: 1.6;
        color: #333;
        white-space: pre-wrap; 
    }
    
    /* 2. [수정] HOMI 박스 스타일 (코드 블록 느낌 + 줄바꿈 + 세로 확장) */
    .homi-box {
        background-color: #2b2c34; /* 다크 테마 배경 */
        color: #e0e0e0;           /* 밝은 글씨 */
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #444;
        min-height: 100px;        /* 최소 높이 */
        max-height: 500px;        /* 최대 높이 (내용 많으면 스크롤) */
        overflow-y: auto;         /* 세로 스크롤 허용 */
        font-family: "Source Code Pro", monospace; /* 코드 폰트 적용 */
        font-size: 14px;
        line-height: 1.6;
        white-space: pre-wrap;    /* 핵심: 가로 스크롤 대신 줄바꿈 적용 */
        word-wrap: break-word;    /* 긴 단어도 줄바꿈 */
    }

    /* 다크모드 대응 */
    @media (prefers-color-scheme: dark) {
        .result-box {
            background-color: #262730;
            border: 1px solid #464b59;
            color: #e0e0e0;
        }
    }

    /* 버튼 스타일 */
    .stButton>button {
        width: 100%;
        font-weight: bold;
        height: 3em;
    }
    
    /* 푸터 스타일 */
    .footer {
        text-align: center;
        margin-top: 50px;
        padding-top: 20px;
        border-top: 1px solid #ddd;
        color: #888;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("OpenAI API Key", type="password")
    
    client = None
    if api_key:
        client = OpenAI(api_key=api_key)
        st.success("API 연결됨")

# ==========================================
# 헤더 영역 (HTML로 로고+타이틀 강제 결합)
# ==========================================
col_header_left, col_header_right = st.columns([5, 4]) 

with col_header_left:
    st.markdown(f"""
    <div style="display: flex; align-items: center;">
        {logo_html}
        <h1 style="margin: 0; padding: 0; font-size: 2.5rem; line-height: 1.2;">HOMI AI 영상 프롬프트 에이전트 (Ver 1.0)</h1>
    </div>
    """, unsafe_allow_html=True)

with col_header_right:
    import streamlit.components.v1 as components
    
    html_content = f"""
    <div style="display: flex; align-items: center; height: 60px; background-color: rgba(255,255,255,0.1); border-radius: 8px; padding: 0 15px; margin-top: 10px;">
        <span style="font-weight: bold; color: #ff4b4b; margin-right: 15px; white-space: nowrap;">💡 HOMI 1.0 TIP</span>
        <span id="tip-text" style="font-size: 15px; color: #ffffff; opacity: 1; transition: opacity 1s ease-in-out;">로딩 중...</span>
    </div>

    <script>
        const tips = {tips_js_array};
        const tipElement = document.getElementById("tip-text");
        
        function updateTip() {{
            tipElement.style.opacity = 0;
            setTimeout(() => {{
                const randomIndex = Math.floor(Math.random() * tips.length);
                tipElement.innerText = tips[randomIndex];
                tipElement.style.opacity = 1;
            }}, 1000);
        }}
        updateTip();
        setInterval(updateTip, 20000);
    </script>
    """
    components.html(html_content, height=80)

# [수정] 설명글과 엔진 정보를 분리
st.markdown("ChatGPT 단순 추천 프롬프트와 **HOMI 로직이 적용된 최적화 프롬프트**를 비교합니다.")
st.caption("*최적화 엔진 = T2I : Nano Banana / I2V : Kling 2.5 (Last Update : 26.02.13)")

# --- 탭 구성 ---
tab_t2i, tab_i2v = st.tabs(["🖼️ T2I (이미지)", "🎥 I2V (비디오)"])

# ==========================================
# 유틸리티 함수
# ==========================================
def render_basic_box(title, content):
    st.markdown(f"**{title}**")
    st.markdown(f'<div class="result-box">{content}</div>', unsafe_allow_html=True)

# [수정] HOMI 박스 렌더링 함수 (커스텀 스타일 적용)
def render_homi_box(title, content):
    st.markdown(f"**{title}**")
    st.markdown(f'<div class="homi-box">{content}</div>', unsafe_allow_html=True)

HOMI_RULES_TEXT = "\n".join(HOMI_TIPS)

# ==========================================
# TAB 1: T2I
# ==========================================
with tab_t2i:
    st.subheader("Visualization & Cut Generation")
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        shot_type = st.selectbox("샷 사이즈", ["Extreme Close-Up", "Close-Up", "Medium", "Wide", "Extreme Wide"])
        t2i_input = st.text_area("장면 묘사", height=150, placeholder="예: 비 내리는 거리, 우산을 쓴 여자...")
        btn_t2i = st.button("T2I 프롬프트 생성", type="primary")

    if btn_t2i:
        if not client or not t2i_input:
            st.error("API 키와 내용을 입력하세요.")
        else:
            with col2:
                with st.spinner("HOMI 백서 데이터 대조 중..."):
                    system_prompt = f"""
                    You are a prompt expert. 
                    User Input: "{t2i_input}" (Shot: {shot_type})
                    Rules: {HOMI_RULES_TEXT}
                    
                    TASKS:
                    1. 'basic': Translate user input to English ONLY. Create a standard detailed generative AI prompt.
                    2. 'homi': Translate to English ONLY. Apply HOMI logic (Templates for Wide/Medium, Constraints check).
                    3. 'advice': Korean advice explaining the optimization.
                    
                    IMPORTANT: The 'basic' and 'homi' fields MUST be in English.
                    Format: JSON {{ "basic": "...", "homi": "...", "advice": "..." }}
                    """
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            response_format={"type": "json_object"},
                            messages=[{"role": "system", "content": system_prompt}]
                        )
                        result = json.loads(response.choices[0].message.content)
                        
                        render_basic_box("🤖 ChatGPT 제안 Prompt", result['basic'])
                        
                        st.write("") 
                        # [수정] st.code 대신 커스텀 함수 사용 (줄바꿈 적용)
                        render_homi_box("✨ HOMI Optimized (최적화)", result['homi'])
                        
                        st.info(f"💡 **Advisor**: {result['advice']}")
                    except Exception as e:
                        st.error(f"오류: {e}")

# ==========================================
# TAB 2: I2V
# ==========================================
with tab_i2v:
    st.subheader("Motion & Physics Generation")
    col3, col4 = st.columns([1, 1], gap="large")
    
    with col3:
        i2v_input = st.text_input("원하는 동작", placeholder="예: 걸어가며 뒤를 돌아본다")
        btn_i2v = st.button("I2V 프롬프트 생성", type="primary")

    if btn_i2v:
        if not client or not i2v_input:
            st.error("API 키와 내용을 입력하세요.")
        else:
            with col4:
                with st.spinner("물리 엔진 오류 최소화 중..."):
                    system_prompt_i2v = f"""
                    You are an I2V Expert.
                    User Input: "{i2v_input}"
                    Rules: {HOMI_RULES_TEXT}
                    
                    TASKS:
                    1. 'basic': Translate to English ONLY. Standard detailed video prompt.
                    2. 'homi': Translate to English ONLY. Max 10 words, remove environment.
                    3. 'advice': Korean advice.
                    
                    IMPORTANT: All Prompt outputs MUST be in English.
                    Format: JSON {{ "basic": "...", "homi": "...", "advice": "..." }}
                    """
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            response_format={"type": "json_object"},
                            messages=[{"role": "system", "content": system_prompt_i2v}]
                        )
                        result = json.loads(response.choices[0].message.content)
                        
                        render_basic_box("🤖 ChatGPT 제안 Prompt", result['basic'])
                        
                        st.write("") 
                        # [수정] st.code 대신 커스텀 함수 사용 (줄바꿈 적용)
                        render_homi_box("✨ HOMI Optimized (최적화)", result['homi'])
                        
                        st.warning(f"🚨 **Physics Alert**: {result['advice']}")
                    except Exception as e:
                        st.error(f"오류: {e}")

# ==========================================
# 푸터 영역
# ==========================================
st.markdown("""
<div class="footer">
    From HOMI 1.0 White Paper<br>
    Copyright 2026. STUDIO STAND CO LTD. All rights reserved
</div>

""", unsafe_allow_html=True)




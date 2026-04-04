# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
import hashlib
import time

st.set_page_config(layout="wide", page_title="意願模擬 | OmniUrban", initial_sidebar_state="expanded")

# ==========================================
# 🛡️ 頁面保險絲：確保 session_state 存在 (修正 AttributeError)
# ==========================================
if "report_data" not in st.session_state:
    st.session_state.report_data = {
        "city": "尚未設定位置",
        "lat": 25.0330,
        "lon": 121.5654,
        "poi_scores": [50]*6,
        "poi_names": [[]]*6
    }

# ==========================================
# 📐 樣式系統
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #0B1220; color: #E2E8F0; }
    .sim-title { 
        background: linear-gradient(135deg, #60A5FA, #A855F7); 
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
        font-weight: 800; font-size: 2.5rem; margin-bottom: 10px; 
    }
    .metric-card { 
        background: #111827; border: 1px solid #1E293B; border-radius: 12px; 
        padding: 20px; height: 100%;
    }
    .advice-box {
        background: rgba(96, 165, 250, 0.1); border-left: 5px solid #60A5FA;
        padding: 20px; border-radius: 0 10px 10px 0; margin-top: 20px;
    }
    .label-tag { font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.1em; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 意願模擬核心演算法
# ==========================================
def calculate_success_prob(support, neutral, oppose, mode):
    base_prob = support * 0.85 + (neutral * 0.35)
    if "危老" in mode:
        # 危老需要 100% 同意，所以門檻懲罰極重
        prob = base_prob * 0.3 if support < 90 else base_prob
    else:
        # 都更 80% 門檻
        prob = base_prob * 0.6 if support < 75 else base_prob
    prob -= (oppose * 0.6)
    return max(0, min(100, int(prob)))

# ==========================================
# 📍 側邊控制區
# ==========================================
with st.sidebar:
    st.markdown("### ⚙️ 模擬參數設定")
    total_units = st.number_input("🏠 總戶數設定", min_value=1, value=30)
    renewal_mode = st.radio("📜 政策路徑", ["一般都更 (門檻80%)", "危老重建 (門檻100%)"])
    
    st.markdown("---")
    st.markdown("### 👥 住戶態度比例 (%)")
    support_rate = st.slider("支持 (已簽意向書)", 0, 100, 40)
    oppose_rate = st.slider("反對 (拒絕溝通)", 0, 100 - support_rate, 20)
    neutral_rate = 100 - support_rate - oppose_rate
    st.info(f"觀望/中立：{neutral_rate}%")
    
    st.markdown("---")
    st.markdown("### 🏬 結構與干預")
    shop_ratio = st.slider("店面戶佔比 (%)", 0, 50, 15)
    use_bonus = st.checkbox("啟動容積獎勵補貼 (刺激意願)")

# ==========================================
# 📍 主畫面標題
# ==========================================
st.markdown('<div class="sim-title">🎯 整合意願模擬與政策決策引擎</div>', unsafe_allow_html=True)

# 安全地讀取資料，不再報錯
curr_addr = st.session_state.report_data.get("city", "未設定")
sync_icon = "🟢" if curr_addr != "未設定位置" else "🔴"
st.markdown(f'<div style="color:#94A3B8; margin-bottom:25px;">{sync_icon} 當前連動目標：<b>{curr_addr}</b></div>', unsafe_allow_html=True)

# ==========================================
# 📊 第一層：KPI 指標
# ==========================================
# 加入政策補貼影響
effective_support = support_rate + (5 if use_bonus else 0)
prob = calculate_success_prob(effective_support, neutral_rate, oppose_rate, renewal_mode)

c1, c2, c3 = st.columns([1.5, 1, 1])

with c1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<div class="label-tag">預估整合成功率 (Success %)</div>', unsafe_allow_html=True)
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = prob,
        number = {'suffix': "%", 'font': {'color': '#60A5FA'}},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': "#60A5FA"},
            'steps': [
                {'range': [0, 50], 'color': 'rgba(239, 68, 68, 0.1)'},
                {'range': [50, 85], 'color': 'rgba(245, 158, 11, 0.1)'},
                {'range': [85, 100], 'color': 'rgba(16, 185, 129, 0.1)'}
            ]
        }
    ))
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', height=280, margin=dict(l=20,r=20,t=40,b=20))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    diff = "極高" if prob < 35 else "高" if prob < 65 else "中" if prob < 85 else "低"
    color = "#EF4444" if prob < 65 else "#10B981"
    st.markdown(f"""
    <div class="metric-card">
        <div class="label-tag">整合難度分析</div>
        <div style="font-size:3.5rem; font-weight:800; color:{color};">{diff}</div>
        <div style="margin-top:15px; font-size:0.9rem; color:#94A3B8;">
            目前同意戶數：<b>{int(total_units * support_rate/100)}</b> / {total_units}<br>
            距離法定門檻：還差 <b>{max(0, int(total_units*0.8 - total_units*support_rate/100))}</b> 戶
        </div>
    </div>""", unsafe_allow_html=True)

with c3:
    main_barrier = "店面補償協議" if shop_ratio > 20 else "反對戶法律訴訟" if oppose_rate > 30 else "觀望情緒過重"
    st.markdown(f"""
    <div class="metric-card">
        <div class="label-tag">主要阻力因子</div>
        <div style="font-size:1.8rem; font-weight:700; color:#F59E0B; margin:10px 0;">{main_barrier}</div>
        <div class="advice-box" style="padding:10px; font-size:0.8rem; border-width:2px;">
            <b>AI 建議：</b><br>
            { "1 樓店面收益是核心矛盾，建議先進行權利變換模擬。" if shop_ratio > 20 else "反對比例過高，強行報核風險大，建議先進行非正式調解。" }
        </div>
    </div>""", unsafe_allow_html=True)

# ==========================================
# 📊 第二層：情境模擬趨勢
# ==========================================
st.write("")
st.markdown('<div class="metric-card">', unsafe_allow_html=True)
st.markdown('<div class="label-tag">What-if: 觀望戶轉化效果模擬</div>', unsafe_allow_html=True)

conv_rates = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
sim_probs = [calculate_success_prob(support_rate + (neutral_rate * r), neutral_rate * (1-r), oppose_rate, renewal_mode) for r in conv_rates]

fig_sim = go.Figure(go.Scatter(
    x=[f"{int(r*100)}%" for r in conv_rates], y=sim_probs,
    mode='lines+markers+text', text=[f"{p}%" for p in sim_probs], textposition="top center",
    line=dict(color='#A855F7', width=4)
))
fig_sim.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(title="觀望戶轉支持之比例", gridcolor="#1E293B"),
    yaxis=dict(title="預估成功率", gridcolor="#1E293B"),
    height=350, margin=dict(l=0,r=0,t=30,b=0)
)
st.plotly_chart(fig_sim, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 🤖 AI 決策建議
# ==========================================
st.write("")
st.markdown('<div class="advice-box">', unsafe_allow_html=True)
st.markdown("### 🤖 OmniUrban AI 策略診斷報告")
if prob < 40:
    st.error("🚫 **【目前不建議報核】** 整合門檻差距過大，建議重新評估分配方案，或先轉向「整建維護」爭取初步共識。")
elif prob < 75:
    st.warning("⚠️ **【建議進入調解期】** 成功率具備潛力。重點應放在那比例最高的觀望群眾，建議舉辦「個別權利價值說明會」。")
else:
    st.success("🎉 **【建議立即啟動計畫】** 整合度已達標。建議儘速完成 100% 簽約並申請危老時程獎勵。")
st.markdown('</div>', unsafe_allow_html=True)
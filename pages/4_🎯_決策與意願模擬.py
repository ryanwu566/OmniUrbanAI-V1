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
# 🧠 意願模擬核心演算法（整合防災韌性評分）
# ==========================================
def calculate_success_prob(support, neutral, oppose, mode):
    # 🚀 【新增】防災韌性加權因子
    # 假設此地址的防災評分已從 session_state 取得
    poi_scores = st.session_state.report_data.get("poi_scores", [60]*6)
    disaster_resilience = poi_scores[5] if len(poi_scores) > 5 else 60  # poi_scores[5] = 防災治安
    disaster_boost = (disaster_resilience - 60) * 0.005  # 防災分數越高，成功率越高（+0.5%/分）
    
    base_prob = support * 0.85 + (neutral * 0.35) + disaster_boost * 10
    if "危老" in mode:
        # 危老需要 100% 同意，所以門檻懲罰極重
        prob = base_prob * 0.3 if support < 90 else base_prob
    else:
        # 都更 80% 門檻
        prob = base_prob * 0.6 if support < 75 else base_prob
    prob -= (oppose * 0.6)
    return max(0, min(100, int(prob)))


def calculate_integration_feasibility(age_risk, ownership_simplicity, economic_benefit, storefront_resistance):
    """計算整合阻力與誘因的客觀可行性指標。"""
    return max(0, min(100, int(
        age_risk * 0.25
        + ownership_simplicity * 0.25
        + economic_benefit * 0.30
        + (100 - storefront_resistance) * 0.20
    )))

# ==========================================
# 📍 側邊控制區
# ==========================================
with st.sidebar:
    st.markdown("### ⚙️ 模擬參數設定")
    total_units = st.number_input("🏠 總戶數設定", min_value=1, value=30)
    renewal_mode = st.radio("📜 政策路徑", ["一般都更 (門檻80%)", "危老重建 (門檻100%)"])
    
    # 【新增】防災韌性顯示
    poi_scores = st.session_state.report_data.get("poi_scores", [60]*6)
    disaster_score = poi_scores[5] if len(poi_scores) > 5 else 60
    resilience_color = "#10B981" if disaster_score >= 80 else "#F59E0B" if disaster_score >= 60 else "#EF4444"
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; border-left: 4px solid {resilience_color};">
        <div style="color:#94A3B8; font-size:0.75rem;">🚨 防災韌性評分</div>
        <div style="color:{resilience_color}; font-size:1.8rem; font-weight:700;">{disaster_score}</div>
        <div style="color:#94A3B8; font-size:0.75rem; margin-top:5px;">
            {"⭐ 優秀 - 降低整合阻力" if disaster_score >= 80 else "⚠️ 普通 - 需強調安全改善" if disaster_score >= 60 else "🚫 不足 - 優先進行防灾改善"}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
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
    use_safety_bonus = st.checkbox("⭐ 防災改善補貼 (提升韌性，鼓勵參與)")

# ==========================================
# 📍 主畫面標題
# ==========================================
st.markdown('<div class="sim-title">🎯 整合意願模擬與政策決策引擎<br><span style="font-size:0.55em; color:#34d399;">防災韌性優先 × 社區包容性評估</span></div>', unsafe_allow_html=True)

# 安全地讀取資料，不再報錯
curr_addr = st.session_state.report_data.get("city", "未設定")
sync_icon = "🟢" if curr_addr != "未設定位置" else "🔴"
st.markdown(f'<div style="color:#94A3B8; margin-bottom:25px;">{sync_icon} 當前連動目標：<b>{curr_addr}</b></div>', unsafe_allow_html=True)

# ==========================================
# 📊 整合阻力與誘因評估模型
st.markdown('<div class="label-tag" style="margin-bottom:12px;">🔎 整合阻力與誘因評估模型</div>', unsafe_allow_html=True)
a1, a2, a3, a4 = st.columns(4)
with a1:
    age_risk = st.slider("建物屋齡危險度", 0, 100, 65, help="屋齡越老，安全需求越高，意願上升")
with a2:
    ownership_simplicity = st.slider("產權單純度", 0, 100, 70, help="共有人數越少、無公有地夾雜，意願越高")
with a3:
    economic_benefit = st.slider("改建經濟效益", 0, 100, 55, help="周邊新舊屋溢價率越高，意願上升")
with a4:
    storefront_resistance = st.slider("一樓店面抗性", 0, 100, 30, help="若有高租金店面，因營業損失，意願下降")

objective_index = calculate_integration_feasibility(age_risk, ownership_simplicity, economic_benefit, storefront_resistance)

# 將客觀指標與原本支持機率加權結合
st.info("本系統之意願推估，係基於經濟誘因與客觀產權條件所計算之『整合可行性指標』，非直接量化主觀心理因素。")

# ==========================================
# 📊 第一層：KPI 指標
# ==========================================
# 加入政策補貼影響（包括防災補貼）
effective_support = support_rate + (5 if use_bonus else 0) + (3 if use_safety_bonus else 0)
prob = calculate_success_prob(effective_support, neutral_rate, oppose_rate, renewal_mode)
final_integration_rate = int((objective_index * 0.55) + (prob * 0.45))

st.metric("最終推估整合率", f"{final_integration_rate}%", "依客觀誘因與住戶支持情境加權計算")

c1, c2, c3 = st.columns([1.5, 1, 1])

with c1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<div class="label-tag">預估整合成功率 (防災韌性優先版本)</div>', unsafe_allow_html=True)
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
    # 🚀 【修改】主要阻力因子 - 融合防灾評估
    poi_scores = st.session_state.report_data.get("poi_scores", [60]*6)
    disaster_score = poi_scores[5] if len(poi_scores) > 5 else 60
    
    if disaster_score < 60:
        main_barrier = "防災韌性不足 (優先)"
        ai_advice = "建議先進行防灾改善評估與補貼宣導，提升居民安全信心與整合意願。（SDG 11.5）"
    elif shop_ratio > 20:
        main_barrier = "店面補償協議"
        ai_advice = "1 樓店面收益是核心矛盾，建議先進行權利變換模擬。"
    elif oppose_rate > 30:
        main_barrier = "反對戶法律訴訟"
        ai_advice = "反對比例過高，強行報核風險大，建議先進行非正式調解。"
    else:
        main_barrier = "觀望情緒過重"
        ai_advice = "核心任務是將中立轉為支持，建議強調防灾與安全改善效益。"
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="label-tag">主要阻力因子</div>
        <div style="font-size:1.8rem; font-weight:700; color:#F59E0B; margin:10px 0;">{main_barrier}</div>
        <div class="advice-box" style="padding:10px; font-size:0.8rem; border-width:2px;">
            <b>AI 建議：</b><br>
            {ai_advice}
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
st.markdown("### 🤖 OmniUrban AI 策略診斷報告 (防災韌性優先)")

# 【新增】融合防災評分的建議邏輯
poi_scores = st.session_state.report_data.get("poi_scores", [60]*6)
disaster_score = poi_scores[5] if len(poi_scores) > 5 else 60

if disaster_score < 60:
    st.error("🚨 **【防災韌性檢警】** 此地區消防/警力資源不足，居民安全是首要關切。建議先進行防灾改善方案，再推動都更吸引參與。")
elif prob < 40:
    st.error("🚫 **【目前不建議報核】** 整合門檻差距過大，建議重新評估分配方案，或先轉向「整建維護」爭取初步共識。")
elif prob < 75:
    st.warning("⚠️ **【建議進入調解期】** 成功率具備潛力。重點應放在那比例最高的觀望群眾，建議舉辦「防灾與權利價值說明會」，強調改善效益。")
else:
    st.success("🎉 **【建議立即啟動計畫】** 整合度已達標。防灾韌性優秀為加分項。建議儘速完成 100% 簽約並申請危老時程獎勵。")
st.markdown('</div>', unsafe_allow_html=True)
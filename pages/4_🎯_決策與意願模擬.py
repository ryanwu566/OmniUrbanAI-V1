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


def calculate_willingness_index(base_willingness, bonus_ratio, landowner_share, has_highrent_shop):
    """
    計算最終整合意願指數（融合容積獎勵、權利變換分回比例、高租金店面因素）
    
    參數：
    - base_willingness: 基礎意願值（%）
    - bonus_ratio: 容積獎勵比例（0-50%）
    - landowner_share: 地主權利變換分回比例（30-70%）
    - has_highrent_shop: 是否有高租金店面（boolean）
    
    計算邏輯：
    1. 基礎意願 50%
    2. 容積獎勵加分：每 1% 容積獎勵 → +0.4% 意願
    3. 權利變換分回加分：以 50% 為中樞，每高於 1% → +0.3% 意願，每低於 1% → -0.3% 意願
    4. 高租金店面扣分：-15% 意願（因營業補償複雜度高）
    """
    willingness = base_willingness
    
    # 容積獎勵加分：每 1% 容積獎勵加 0.4% 意願（最多 +20%）
    bonus_boost = bonus_ratio * 0.4
    willingness += bonus_boost
    
    # 權利變換分回加分/扣分：以 50% 為基準
    # 50% = 不加不扣；60% = +3%；40% = -3%
    share_diff = landowner_share - 50
    share_boost = share_diff * 0.3
    willingness += share_boost
    
    # 高租金店面扣分：-15%（營業補償與接管風險）
    if has_highrent_shop:
        willingness -= 15
    
    # 夾緊在 0-100 範圍內
    return max(0, min(100, willingness))

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
    
    # ── 【新增】開發條件與容積獎勵評估 ──
    st.markdown("---")
    st.markdown("### 📋 開發條件與容積獎勵評估")
    
    # 都市更新地區判定
    is_update_zone = st.checkbox("✅ 位於政府劃定之都市更新地區")
    if is_update_zone:
        st.info("✓ 適用較低之同意門檻 (如 3/4 或 1/2)，且享有時程獎勵。")
    
    # 容積獎勵預估
    st.markdown("#### 容積獎勵預估")
    bonus_ratio = st.slider(
        "容積獎勵比例",
        min_value=0,
        max_value=50,
        value=20,
        step=1,
        help="法定上限 50%。透過綠建築、智慧建築、耐震設計等方案組合而成。"
    )
    
    # 常見容積獎勵項目參考 expander
    with st.expander("📖 常見容積獎勵項目參考"):
        st.markdown("""
        #### 🏆 容積獎勵項目一覽
        
        **1. 綠建築標章**
            - 最高獎勵：10%
            - 申請條件：符合內政部綠建築評估標準
            - 效益：降低建物碳足跡、提升能源效率
        
        **2. 智慧建築標章**
            - 最高獎勵：10%
            - 申請條件：符合內政部智慧建築評估標準
            - 效益：提升住戶生活品質、能源管理自動化
        
        **3. 耐震設計加強**
            - 最高獎勵：10%
            - 申請條件：超越法定耐震標準（SDG 11.5 防災韌性）
            - 效益：增加建物耐震能力，提升防災安全
        
        **4. 時程獎勵（危老條例專屬）**
            - 最高獎勵：10%
            - 申請條件：在期限內完成全體同意書簽署
            - 效益：加速老舊建物重建
        
        **5. 無障礙設計加強**
            - 最高獎勵：5%
            - 申請條件：超越法定無障礙標準
            - 效益：提升全齡友善度（SDG 11.7）
        
        **6. 公益設施**
            - 最高獎勵：5%
            - 申請條件：設置停車場、托兒中心、集會所等
            - 效益：提升社區公共服務水準
        
        **💡 組合示例**：綠建築(10%) + 耐震設計(10%) + 無障礙設計(5%) = 25% 容積獎勵
        """)
    
    st.markdown("---")
    st.markdown("#### 🔄 權利變換與分配")
    
    # 地主權利變換分回比例
    landowner_share = st.slider(
        "地主權利變換分回比例",
        min_value=30,
        max_value=70,
        value=50,
        step=1,
        help="預估地主在權利變換後能分回的樓地板面積或權利比例。50% 為均等分配，越高代表地主拿得越多。"
    )
    st.caption(f"💡 分回比例 {landowner_share}% → 地主可獲得原持有面積比之 {landowner_share}% 新建房地")
    
    # 是否有高租金店面（新增）
    has_highrent_shop_1f = st.checkbox("⚠️ 一樓有高租金店面（營業補償複雜）")
    if has_highrent_shop_1f:
        st.warning("高租金店面意味著營業損失補償、接管權協議等複雜性，會顯著降低整合意願。")
    
    # 將開發條件參數保存至 session_state，供後續計算使用
    st.session_state.update_zone = is_update_zone
    st.session_state.bonus_ratio = bonus_ratio
    st.session_state.landowner_share = landowner_share
    st.session_state.has_highrent_shop = has_highrent_shop_1f

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

# 【新增】容積獎勵效應：若啟動容積獎勵補貼，額外提升成功率
update_zone = st.session_state.get("update_zone", False)
bonus_ratio = st.session_state.get("bonus_ratio", 20)
landowner_share = st.session_state.get("landowner_share", 50)
has_highrent_shop = st.session_state.get("has_highrent_shop", False)

if use_bonus and bonus_ratio > 0:
    # 容積獎勵越高，對整合意願的刺激越強（+0.3% per %容積）
    bonus_boost = bonus_ratio * 0.3
    prob = min(100, prob + bonus_boost)
    final_integration_rate = int((objective_index * 0.55) + (prob * 0.45))

# 【新增】計算最終整合意願指數（融合容積獎勵、權利變換、高租金店面）
base_willingness_score = 50
final_willingness_index = int(calculate_willingness_index(
    base_willingness=base_willingness_score,
    bonus_ratio=bonus_ratio,
    landowner_share=landowner_share,
    has_highrent_shop=has_highrent_shop
))

# 【新增】根據意願指數決定顯示顏色與提示
if final_willingness_index >= 80:
    willingness_color = "#14B8A6"  # 綠色
    willingness_status = "🟢 極具整合潛力"
    willingness_desc = "整合意願指數優秀，推薦立即啟動都更程序"
elif final_willingness_index >= 65:
    willingness_color = "#10B981"  # 淺綠
    willingness_status = "🟡 具備整合基礎"
    willingness_desc = "意願指數尚可，建議加強宣導與說明會"
elif final_willingness_index >= 50:
    willingness_color = "#F59E0B"  # 琥珀色
    willingness_status = "🟠 整合普通"
    willingness_desc = "意願指數中等，需要提升權利變換條件或補貼方案"
else:
    willingness_color = "#EF4444"  # 紅色
    willingness_status = "🔴 建議暫緩"
    willingness_desc = "意願指數偏低，建議先進行密集溝通或重新評估方案"

st.metric("最終推估整合率", f"{final_integration_rate}%", 
          f"依客觀誘因與住戶支持情境加權計算{' (含容積獎勵加成)' if use_bonus else ''}")

st.write("")

# 【新增】第一層：最終整合意願指數以進度條 + 彩色標籤展示
st.markdown('<div style="padding: 20px; background: #111827; border: 1px solid #1E293B; border-radius: 12px;">', unsafe_allow_html=True)
st.markdown(f'<div style="color:#94A3B8; font-size:0.85rem; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.08em;">💡 最終整合意願量化指數 (融合容積獎勵、權利變換、營業補償)</div>', unsafe_allow_html=True)

# 進度條展示
progress_value = final_willingness_index / 100
st.progress(progress_value, text=f"{final_willingness_index}%")

# 彩色狀態標籤 + 詳細建議
col_status, col_details = st.columns([1, 2])
with col_status:
    st.markdown(f"""
    <div style="font-size:2.5rem; font-weight:800; color:{willingness_color}; margin:0;">
        {final_willingness_index}%
    </div>
    <div style="font-size:1rem; font-weight:700; color:{willingness_color}; margin-top:8px;">
        {willingness_status}
    </div>
    """, unsafe_allow_html=True)

with col_details:
    st.markdown(f"""
    <div style="color:#cbd5e1; line-height:1.7;">
        <b>{willingness_desc}</b><br><br>
        <div style="font-size:0.9rem; color:#94A3B8;">
        • 容積獎勵加成：+{int(bonus_ratio * 0.4)}%<br>
        • 權利變換分配加成：{'+' if landowner_share >= 50 else ''}{int((landowner_share - 50) * 0.3)}%<br>
        • 高租金店面扣分：{'-15%' if has_highrent_shop else '無'}<br>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

st.write("")

c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.2])

with c1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<div class="label-tag">預估整合成功率</div>', unsafe_allow_html=True)
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
    # 【新增】容積獎勵視覺化卡片
    bonus_color = "#14B8A6" if bonus_ratio >= 30 else "#F59E0B" if bonus_ratio >= 15 else "#94A3B8"
    update_zone_icon = "✅" if update_zone else "⭕"
    st.markdown(f"""
    <div class="metric-card">
        <div class="label-tag">📐 容積獎勵評估</div>
        <div style="font-size:2.5rem; font-weight:800; color:{bonus_color};">{bonus_ratio}%</div>
        <div style="margin-top:12px; font-size:0.85rem; color:#94A3B8;">
            都市更新地區：<b>{update_zone_icon}</b><br>
            建議刺激效應：<b>{'中等' if bonus_ratio < 30 else '高'}</b>
        </div>
    </div>""", unsafe_allow_html=True)

with c4:
    # 權利變換分回比例視覺化卡片（新增）
    share_color = "#14B8A6" if landowner_share >= 55 else "#F59E0B" if landowner_share >= 45 else "#EF4444"
    share_assessment = "地主優惠" if landowner_share >= 55 else "公平分配" if landowner_share >= 45 else "地主吃虧"
    st.markdown(f"""
    <div class="metric-card">
        <div class="label-tag">🔄 權利變換分配</div>
        <div style="font-size:2.5rem; font-weight:800; color:{share_color};">{landowner_share}%</div>
        <div style="margin-top:12px; font-size:0.85rem; color:#94A3B8;">
            地主分回評估：<b>{share_assessment}</b><br>
            店面風險：<b>{'⚠️ 高' if has_highrent_shop else '✓ 低'}</b>
        </div>
    </div>""", unsafe_allow_html=True)
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
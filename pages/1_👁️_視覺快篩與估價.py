import streamlit as st
import time
import re
import plotly.graph_objects as go
from PIL import Image

st.set_page_config(layout="wide", page_title="視覺快篩與 XAI 估價", page_icon="👁️")

st.markdown("""
    <style>
    .stApp { background: #020617; color: #f8fafc; }
    .neon-card { background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(12px); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 12px; padding: 20px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3); transition: 0.3s; height: 100%;}
    .neon-card:hover { border-color: #38bdf8; transform: translateY(-2px); }
    .module-title { color: #38bdf8; font-size: 1.1rem; font-weight: bold; margin-bottom: 10px; display: flex; align-items: center;}
    .module-value { font-size: 1.5rem; font-weight: 900; color: #f8fafc; margin-bottom: 5px; }
    .module-desc { font-size: 0.8rem; color: #94a3b8; }
    .tag-green { background: #064e3b; color: #34d399; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold;}
    .tag-red { background: #7f1d1d; color: #f87171; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold;}
    .tag-yellow { background: #78350f; color: #fbbf24; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold;}
    
    /* 調整輸入框樣式使其融入深色主題 */
    div[data-baseweb="base-input"] { background-color: #0f172a; border: 1px solid #1e293b; color: #f8fafc; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 style="background: linear-gradient(90deg, #a855f7, #38bdf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight:900;">👁️ 視覺快篩與 XAI 估價引擎</h1>', unsafe_allow_html=True)

if "report_data" not in st.session_state or not st.session_state.report_data.get("city"):
    st.warning("⚠️ 尚未偵測到分析目標！請先至「🏠 儀表板」輸入地址並啟動分析，再進行視覺快篩。")
    st.stop()

# 取得第一頁存下來的全域資料
data = st.session_state.report_data
m = data.get("moltke_data", {})
addr = data.get("city", "未知地址")
base_age = m.get("age", 35)
base_elevator = m.get("elevator", "無")
val_str = m.get("core_summary", {}).get("valuation", "50 ~ 60 萬/坪")

match = re.search(r'(\d+)', val_str)
regional_base = int(match.group(1)) if match else 50

st.markdown(f"<h4 style='color:#cbd5e1; margin-bottom:20px;'>📍 當前分析標的：<span style='color:#34d399;'>{addr}</span></h4>", unsafe_allow_html=True)

# --- 上傳區塊 ---
uploaded_file = st.file_uploader("📸 上傳街景或建物外觀照片 (啟動分析)", type=["jpg", "png", "jpeg"])

if uploaded_file is None:
    st.info("👆 請上傳該地址的建築物照片，以啟動 Omni-Vision 萃取隱藏的影響因子。")
    st.stop()

# --- 模擬 AI 分析過場動畫 ---
with st.spinner("🔄 正在載入底層圖資... 啟動 Omni-Vision 卷積神經網路進行影像特徵交叉比對..."):
    time.sleep(1.5) 
st.success("✅ 視覺特徵萃取完成！")

st.divider()

# ==========================================
# 🚀 專家協同校正區 (Human-in-the-Loop)
# ==========================================
st.markdown("### 🛠️ 隱性特徵專家微調 (Human-in-the-Loop)")
st.markdown("<p style='font-size:0.85rem; color:#94a3b8; margin-top:-10px;'>💡 由於 AI 無法透視建築內部，系統已根據環境圖資進行初步推估，您可依實地勘查狀況覆寫以下參數，估價模型將即時連動重算。</p>", unsafe_allow_html=True)

c_adj1, c_adj2, c_adj3 = st.columns(3)
with c_adj1:
    # 預設帶入第一頁算出來的結果，但允許手動切換
    user_elevator = st.radio("🛗 實際電梯設備", ["無電梯", "有電梯"], index=0 if base_elevator == "無" else 1, horizontal=True)
with c_adj2:
    user_age = st.number_input("⏳ 精確屋齡修正 (年)", min_value=1, max_value=100, value=int(base_age), step=1)
with c_adj3:
    user_community = st.text_input("🏢 社區或大樓名稱 (選填)", placeholder="例：大安國宅 (私人公寓免填)")

# --- 動態計算瀑布圖因子 (依據使用者微調結果重算) ---
poi_bonus = int(sum(data.get("poi_scores", [0]*6)) / 60) 
elevator_adj = -5 if user_elevator == "無電梯" else 4     # 🚀 這裡用使用者確認過的電梯狀態！
age_adj = -int((user_age - 10) / 6) if user_age > 10 else 0 # 🚀 這裡用使用者確認過的精確屋齡！
wall_adj = -3                                            
alley_adj = 2                                            
nimby_adj = 0                                            

final_val = regional_base + poi_bonus + elevator_adj + age_adj + wall_adj + alley_adj + nimby_adj

st.write("")

# --- 核心佈局：左邊照片 + 右邊 XAI 瀑布圖 ---
col_img, col_chart = st.columns([1, 1.5])

with col_img:
    st.markdown('<div class="neon-card">', unsafe_allow_html=True)
    st.markdown('<div class="module-title">📷 AI 判讀原始影像</div>', unsafe_allow_html=True)
    image = Image.open(uploaded_file)
    st.image(image, use_container_width=True, caption=f"分析目標：{addr} {user_community}")
    st.markdown('</div>', unsafe_allow_html=True)

with col_chart:
    st.markdown('<div class="neon-card">', unsafe_allow_html=True)
    st.markdown('<div class="module-title">📊 XAI 可解釋性估價瀑布圖 (即時連動)</div>', unsafe_allow_html=True)
    
    fig = go.Figure(go.Waterfall(
        name="估價影響因子",
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "relative", "relative", "relative", "total"],
        x=["區域基準價", "周邊機能", "有無電梯", "屋齡折舊", "外牆與違建", "巷弄條件", "嫌惡設施", "精算預估單價"],
        textposition="outside",
        text=[regional_base, f"+{poi_bonus}", elevator_adj if elevator_adj<0 else f"+{elevator_adj}", 
              age_adj, wall_adj, f"+{alley_adj}", nimby_adj, final_val],
        y=[regional_base, poi_bonus, elevator_adj, age_adj, wall_adj, alley_adj, nimby_adj, final_val],
        connector={"line":{"color":"#475569", "dash":"dot"}},
        decreasing={"marker":{"color":"#f87171"}},  
        increasing={"marker":{"color":"#34d399"}},  
        totals={"marker":{"color":"#38bdf8"}}       
    ))
    
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(title="單價 (萬/坪)", gridcolor="#1e293b")
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.write("")
st.markdown("### 🧱 建築物理特徵與估價狀態")
c1, c2, c3, c4 = st.columns(4)
with c1:
    b_type = "社區/大樓" if user_community else "一般住宅/公寓"
    st.markdown(f"""
    <div class="neon-card">
        <div class="module-title">🏢 1. 建物與社區型態</div>
        <div class="module-value" style="font-size:1.2rem;">{b_type}</div>
        <div class="module-desc">專案標籤：{user_community if user_community else "無特別命名"}<br>AI 信心值：92%</div>
    </div>""", unsafe_allow_html=True)
with c2:
    # 🚀 動態顯示電梯狀態 (跟隨使用者的微調)
    ele_color = "#f87171" if user_elevator == "無電梯" else "#34d399"
    ele_tag = '<span class="tag-red">高齡不友善 (-5萬/坪)</span>' if user_elevator == "無電梯" else '<span class="tag-green">具備無障礙價值 (+4萬/坪)</span>'
    st.markdown(f"""
    <div class="neon-card">
        <div class="module-title">🛗 5. 電梯設備</div>
        <div class="module-value" style="color:{ele_color};">{user_elevator}</div>
        <div class="module-desc">狀態來源：專家實勘校正<br>狀態：{ele_tag}</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown("""
    <div class="neon-card">
        <div class="module-title">🏚️ 3. 外牆老化度</div>
        <div class="module-value" style="color:#fbbf24; font-size:1.2rem;">中度老化 (65分)</div>
        <div class="module-desc">特徵：水漬、磁磚剝落<br>狀態：<span class="tag-yellow">建議立面拉皮 (-3萬/坪)</span></div>
    </div>""", unsafe_allow_html=True)
with c4:
    # 🚀 動態顯示屋齡狀態 (跟隨使用者的微調)
    age_tag = '<span class="tag-red">符合危老重建條件</span>' if user_age >= 30 else '<span class="tag-yellow">暫無立即重建急迫性</span>'
    st.markdown(f"""
    <div class="neon-card">
        <div class="module-title">⏳ 9. 屋齡與更新急迫</div>
        <div class="module-value">{user_age} 年</div>
        <div class="module-desc">狀態來源：專家實勘校正<br>狀態：{age_tag}</div>
    </div>""", unsafe_allow_html=True)

st.write("")
st.markdown("### 🏘️ 空間與環境特徵解析")
c5, c6, c7, c8 = st.columns(4)
with c5:
    st.markdown("""
    <div class="neon-card">
        <div class="module-title">🛣️ 4. 巷弄寬度</div>
        <div class="module-value" style="font-size:1.2rem;">約 6~8 公尺</div>
        <div class="module-desc">特徵：影像判讀雙向單車道<br>狀態：<span class="tag-green">消防車可通行 (+2萬/坪)</span></div>
    </div>""", unsafe_allow_html=True)
with c6:
    st.markdown("""
    <div class="neon-card">
        <div class="module-title">🏪 6. 一樓使用型態</div>
        <div class="module-value" style="font-size:1.2rem;">純住宅 / 封閉</div>
        <div class="module-desc">特徵：鐵捲門、無招牌<br>狀態：<span class="tag-green">營業補償風險低</span></div>
    </div>""", unsafe_allow_html=True)
with c7:
    st.markdown("""
    <div class="neon-card">
        <div class="module-title">☢️ 7. 嫌惡設施</div>
        <div class="module-value" style="color:#34d399; font-size:1.2rem;">未偵測到</div>
        <div class="module-desc">掃描半徑：影像內 50 公尺<br>狀態：<span class="tag-green">無扣分項目</span></div>
    </div>""", unsafe_allow_html=True)
with c8:
    st.markdown("""
    <div class="neon-card">
        <div class="module-title">🏗️ 2. 屋頂加蓋</div>
        <div class="module-value" style="color:#f87171; font-size:1.2rem;">疑似鐵皮頂加</div>
        <div class="module-desc">特徵：頂層材質與主體不符<br>狀態：<span class="tag-red">整合抗性風險</span></div>
    </div>""", unsafe_allow_html=True)
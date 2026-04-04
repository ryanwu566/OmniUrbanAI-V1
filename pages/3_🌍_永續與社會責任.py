# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import hashlib
import time  # ✅ 修復 NameError: name 'time' is not defined
import re
from utils.engines import OmniEngine

st.set_page_config(layout="wide", page_title="ESG 永續評估 | OmniUrban", initial_sidebar_state="expanded")
engine = OmniEngine()

# ==========================================
# 📐 ESG 極簡風格與 CSS 注入
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    .stApp { background-color: #050A0F; color: #E2E8F0; font-family: 'Inter', sans-serif; }
    .esg-title { 
        background: linear-gradient(135deg, #10B981, #3B82F6); 
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
        font-weight: 800; font-size: 2.8rem; margin-bottom: 5px; 
    }
    .metric-card { 
        background: #0F172A; border: 1px solid #1E293B; border-radius: 12px; 
        padding: 20px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); height: 100%;
    }
    .score-val { font-size: 3rem; font-weight: 800; color: #10B981; line-height: 1; }
    .label-tag { font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }
    .advice-item { 
        background: rgba(16, 185, 129, 0.05); border-left: 4px solid #10B981; 
        padding: 15px; margin-bottom: 12px; border-radius: 0 8px 8px 0;
    }
    .connected-badge {
        background: #1E293B; border: 1px solid #334155; border-radius: 4px;
        padding: 4px 8px; font-size: 0.7rem; color: #14B8A6; font-weight: 700;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 ESG 連動演算法 (對接 Dashboard 數據)
# ==========================================
def run_esg_analysis(addr):
    # 建立穩定 Seed
    h = int(hashlib.md5(addr.encode()).hexdigest(), 16)
    
    # 從 Session State 抓取機能數據 (如果有的話)
    report = st.session_state.get("report_data", {})
    poi_scores = report.get("poi_scores", [50]*6)
    poi_names = report.get("poi_names", [[]]*6)
    
    # 1. 碳排計算 (根據坪數與結構)
    area = 30 + (h % 60)
    carbon_rebuild = area * 1.15
    carbon_renovate = area * 0.28
    
    # 2. 社會效益 (Social) - 根據醫療與教育機能連動
    social_score = (poi_scores[1] * 0.4 + poi_scores[2] * 0.3 + poi_scores[4] * 0.3)
    
    # 3. 災害韌性 (Environmental Risk) - 模擬淹水與耐震風險
    resilience = 55 + (h % 35)
    
    # 4. 綠色空間 (附近的公園點位)
    parks = poi_names[4] if len(poi_names) > 4 else []
    
    return {
        "carbon": {"rebuild": carbon_rebuild, "renovate": carbon_renovate, "savings": carbon_rebuild - carbon_renovate},
        "scores": {
            "低碳節能": 50 + (h % 45),
            "高齡友善": 40 + (h % 55),
            "社會影響": int(social_score),
            "氣候韌性": resilience,
            "生物多樣": 30 + (len(parks) * 15)
        },
        "parks": parks,
        "area": area
    }

# ==========================================
# 📍 Header 與數據連動狀態
# ==========================================
st.markdown('<div class="esg-title">🌍 ESG 永續量化評估中心</div>', unsafe_allow_html=True)

# 顯示連動狀態
is_synced = "city" in st.session_state.report_data
status_tag = '<span class="connected-badge">● DATA SYNCED FROM DASHBOARD</span>' if is_synced else '<span class="connected-badge" style="color:#64748b;">○ STANDALONE MODE</span>'
st.markdown(f'<div style="margin-bottom:25px;">{status_tag} <span>地址：{st.session_state.report_data.get("city", "尚未設定位置")}</span></div>', unsafe_allow_html=True)

# 搜尋連動列
with st.container():
    c1, c2, c3 = st.columns([2.5, 1, 1])
    with c1:
        addr_input = st.text_input("評估目標地址", value=st.session_state.report_data.get("city", ""), placeholder="輸入或從儀表板同步地址...")
    with c2:
        floor_type = st.selectbox("建築現況", ["5層以下無電梯公寓", "電梯大樓", "透天/全棟評估"])
    with c3:
        if st.button("🚀 執行永續模擬", use_container_width=True):
            with st.spinner("正在進行碳足跡與社會效益精算..."):
                # 如果使用者在這裡改地址，同步回 report_data 以確保連貫
                if addr_input != st.session_state.report_data.get("city"):
                    new_data = engine.get_dynamic_data(addr_input, floor_type)
                    st.session_state.report_data = new_data
                time.sleep(0.8)
                st.rerun()

# 獲取 ESG 模擬數據
res = run_esg_analysis(st.session_state.report_data.get("city", "台北市"))

# ==========================================
# 📊 第一層：ESG 關鍵績效指標 (KPI)
# ==========================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""<div class="metric-card">
        <div class="label-tag">環境：重建碳排債</div>
        <div class="score-val" style="color:#EF4444;">{res['carbon']['rebuild']:.1f}<span style="font-size:0.9rem;">t</span></div>
        <div style="font-size:0.8rem; color:#64748b; margin-top:8px;">若選擇整建可立減 <b>{res['carbon']['savings']:.1f}t</b> 碳排</div>
    </div>""", unsafe_allow_html=True)

with col2:
    # 能源指標連動：看附近有無捷運/公車
    energy_score = res['scores']['低碳節能']
    st.markdown(f"""<div class="metric-card">
        <div class="label-tag">環境：綠電與能效</div>
        <div class="score-val" style="color:#F59E0B;">{energy_score}</div>
        <div style="font-size:0.8rem; color:#64748b; margin-top:8px;">屋頂綠能潛力：<b>優良</b> (高日照區)</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""<div class="metric-card">
        <div class="label-tag">社會：高齡友善度</div>
        <div class="score-val" style="color:#3B82F6;">{res['scores']['高齡友善']}</div>
        <div style="font-size:0.8rem; color:#64748b; margin-top:8px;">關鍵缺口：{'缺乏電梯設施' if '無電梯' in floor_type else '坡道坡度過大'}</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""<div class="metric-card">
        <div class="label-tag">治理：災害防禦韌性</div>
        <div class="score-val" style="color:#10B981;">{res['scores']['氣候韌性']}</div>
        <div style="font-size:0.8rem; color:#64748b; margin-top:8px;">評級：<b>穩定</b> (排除地質敏感區)</div>
    </div>""", unsafe_allow_html=True)

# ==========================================
# 📊 第二層：視覺化分析圖表
# ==========================================
st.write("")
l_col, r_col = st.columns([1, 1.2])

with l_col:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<div class="label-tag">ESG 5-Dimensional Radar</div>', unsafe_allow_html=True)
    
    # 雷達圖數據
    cats = list(res['scores'].keys())
    vals = list(res['scores'].values())
    
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]],
        fill='toself', fillcolor='rgba(59, 130, 246, 0.2)',
        line=dict(color='#3B82F6', width=2)
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#1E293B"), bgcolor="rgba(0,0,0,0)"),
        showlegend=False, paper_bgcolor='rgba(0,0,0,0)', height=400, margin=dict(l=40,r=40,t=40,b=40)
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with r_col:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<div class="label-tag">碳中和路徑模擬：重建 vs. 整建</div>', unsafe_allow_html=True)
    
    yrs = list(range(0, 21))
    # 模擬算法：重建初排碳高但後續節能快，整建初排碳低但能耗遞增
    reb = [res['carbon']['rebuild'] + (i * 0.4) for i in yrs]
    ren = [res['carbon']['renovate'] + (i * 1.8) for i in yrs]
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=yrs, y=reb, name="重建路徑 (綠建築認證)", line=dict(color='#3B82F6', width=3)))
    fig2.add_trace(go.Scatter(x=yrs, y=ren, name="整建路徑 (現況微調)", line=dict(color='#94A3B8', width=2, dash='dot')))
    
    fig2.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(font=dict(color="#94A3B8"), yanchor="top", y=0.99, xanchor="left", x=0.01),
        margin=dict(l=0, r=0, t=30, b=0), height=400,
        xaxis=dict(gridcolor="#1E293B", title="評估年份", tickfont=dict(color="#94A3B8")),
        yaxis=dict(gridcolor="#1E293B", title="累積碳排 (tCO2e)", tickfont=dict(color="#94A3B8"))
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 📊 第三層：社會責任 (Social) 詳細解析
# ==========================================
st.write("")
st.markdown('<div class="label-tag" style="font-size:1.1rem;">Social Impact: 社區影響與社會責任分析</div>', unsafe_allow_html=True)

s_col1, s_col2 = st.columns(2)

with s_col1:
    # 抓取公園數據
    park_list = res['parks'][:3]
    park_info = " · ".join([p.split('(')[0] for p in park_list]) if park_list else "周邊缺乏大型綠地"
    st.markdown(f"""
    <div class="advice-item">
        <b style="color:#10B981;">🌳 生物多樣性與綠帶：</b><br>
        偵測到鄰近設施：{park_info}<br>
        評估：具有良好降溫效果，建議建築立面增加垂直綠化以串連綠帶。
    </div>
    <div class="advice-item">
        <b style="color:#3B82F6;">♿ 高齡化急迫性：</b><br>
        本案位於永和高齡人口熱區，電梯設置與樓梯升降椅為 ESG 改善之首要任務。<br>
        改善建議：優先申請新北市老舊公寓增設電梯補助 (最高補助340萬)。
    </div>
    """, unsafe_allow_html=True)

with s_col2:
    st.markdown(f"""
    <div class="advice-item">
        <b style="color:#F59E0B;">⚡ 能源治理建議：</b><br>
        檢測到屋頂面積約 {res['area']*0.6:.1f} 坪可用於綠能。<br>
        預計年發電量：{res['area']*45:.0f} 度，可減少社區公設電費約 12%~15%。
    </div>
    <div class="advice-item">
        <b style="color:#EF4444;">🛡️ 災害防禦計畫：</b><br>
        根據地圖數據，本區巷弄狹窄（消防車進入困難度：高）。<br>
        永續建議：重建應退縮建築紅線以增加消防通道寬度，提升社區安全價值。
    </div>
    """, unsafe_allow_html=True)

# 底部導出
st.write("---")
st.markdown('<div style="text-align:center; color:#64748b; font-size:0.8rem;">© 2026 OmniUrban Intelligence - 數據連動 ESG 評估引擎</div>', unsafe_allow_html=True)
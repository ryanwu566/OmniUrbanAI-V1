# -*- coding: utf-8 -*-
"""
OmniUrban Decision Dashboard v10.1 (The Ultimate B2B Edition)
=============================================================
1. 滿版橫式街景 (高度 500px)。
2. 三圖連動：點擊地圖 -> 反查地址 -> 街景轉向 -> 估價與機能全部同步重算。
3. 完美復刻「AI 特徵估價 & 風險合併卡片」(修復長地址破版)。
4. 橫向 3x2 Grid 數據瀑布流。
5. 開放完整地址手動輸入。
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import re
from utils.engines import OmniEngine

engine = OmniEngine()
st.set_page_config(layout="wide", page_title="OmniUrban Intelligence", initial_sidebar_state="expanded")

# ==========================================
# 📐 B2B 專業級樣式系統 (深色 SaaS 質感)
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp { background-color: #0B1220; color: #E5E7EB; font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }
    
    .metric-card { 
        background: #111827; border: 1px solid #334155; border-radius: 12px; 
        padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2); 
        height: 100%; position: relative; overflow: hidden; 
    }
    
    .hero-title { 
        background: linear-gradient(135deg, #ffffff, #94a3b8); 
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
        font-weight: 800; font-size: 2.8rem; letter-spacing: -0.03em; margin-bottom: 5px; 
    }
    
    .lbl { font-size: 0.85rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; display: block; }
    .val { font-size: 3.5rem; font-weight: 700; line-height: 1.1; margin-bottom: 4px; color: #38BDF8; } 
    .val-risk { font-size: 2.5rem; font-weight: 700; line-height: 1.1; margin-bottom: 4px; } 
    .val-text { font-size: 1.8rem; font-weight: 700; line-height: 1.2; margin-bottom: 4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .unit { font-size: 1.2rem; color: #94A3B8; font-weight: 400; }
    .sub { font-size: 0.95rem; color: #64748b; margin-top: 8px; }

    .color-primary { color: #38BDF8; }
    .color-success { color: #14B8A6; } 
    .color-danger { color: #EF4444; }
    .color-warning { color: #F59E0B; }

    .status-capsule { 
        background: #111827; border: 1px solid #334155; border-radius: 99px; 
        padding: 8px 16px; display: inline-flex; gap: 16px; align-items: center; 
        margin-bottom: 24px; font-size: 0.8rem; color: #94A3B8; 
    }
    
    .stTextInput>div>div>input, .stSelectbox>div>div>div { background-color: #111827 !important; border: 1px solid #334155 !important; color: #E5E7EB !important; border-radius: 6px !important; }
    .stButton>button { background: #38BDF8 !important; color: #0B1220 !important; border-radius: 6px !important; font-weight: 600 !important; border: none !important; width: 100%; padding: 0.6rem !important; }
    .stButton>button:hover { background: #7DD3FC !important; }
    
    .bar-bg { background: #334155; height: 6px; border-radius: 3px; margin: 12px 0; overflow: hidden; }
    .bar-fg { height: 100%; background: #38BDF8; border-radius: 3px; }
    .divider { border-top: 1px solid #334155; margin: 24px 0; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🚀 處理地圖點擊的「三圖連動」邏輯
# ==========================================
if st.session_state.get("pending_map_update"):
    with st.spinner("📍 偵測到地圖點擊，正在反查地址並同步街景與估價模型..."):
        new_addr = st.session_state.pending_map_update["addr"]
        floor = st.session_state.pending_map_update["floor"]
        res = engine.get_dynamic_data(new_addr, floor)
        if res: 
            st.session_state.report_data = res
            engine.save_to_history()
    st.session_state.pending_map_update = None
    st.rerun()

data = st.session_state.report_data
m = data.get("moltke_data", {})
w = data.get("weather_data", {})
env = data.get("env_data", {})
yb = data.get("yb_data", {})
bus = data.get("bus_data", {})
api_health = m.get("api_health", {})

# ==========================================
# 📍 Header & 萬能搜尋列
# ==========================================
st.markdown('<div class="hero-title">OmniUrban Spatial Engine</div>', unsafe_allow_html=True)

status_html = f"""
<div class="status-capsule">
    <div style="color:#14B8A6; font-weight:700;">● SYSTEM ONLINE</div>
    <div>|</div>
    <div>API: {api_health.get('Google','--')}</div>
    <div>Weather: {w.get('temp','--')}</div>
    <div>AQI: {env.get('aqi','--')} ({env.get('api_status','--')})</div>
</div>
"""
st.markdown(status_html, unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="lbl" style="font-size:1rem;">Target Location (目標基地設定)</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    
    with c1:
        manual_addr = st.text_input("直接輸入完整地址 (若填寫此欄，將優先解析)", placeholder="例如：臺北市文山區指南路二段64號", label_visibility="collapsed")
    with c2:
        sel_floor = st.selectbox("評估類型", ["全棟評估", "1樓店面", "4~5樓公寓", "電梯大樓"], label_visibility="collapsed")
        
    st.markdown('<div style="color:#64748b; font-size:0.85rem; margin:10px 0;">或使用下方選單快速定位：</div>', unsafe_allow_html=True)
    
    c3, c4, c5, c6 = st.columns([1, 1, 1.5, 1])
    with c3: sel_city = st.selectbox("縣市", ["--"] + list(engine.taiwan_data.keys()), label_visibility="collapsed")
    with c4: sel_dist = st.selectbox("行政區", engine.taiwan_data.get(sel_city, ["--"]) if sel_city != "--" else ["--"], disabled=(sel_city == "--"), label_visibility="collapsed")
    with c5:
        roads = engine.get_roads_list(sel_city, sel_dist)
        sel_road = st.selectbox("路段", roads if roads else ["--"], disabled=(sel_dist == "--" or not roads), label_visibility="collapsed")
    with c6: sel_num = st.text_input("門牌", placeholder="門牌號碼 (選填)", label_visibility="collapsed")
    
    st.write("")
    if st.button("啟動特徵空間分析 (RUN ANALYSIS)"):
        final_target = manual_addr if manual_addr else f"{sel_city}{sel_dist}{sel_road if not sel_road.startswith('--') else ''}{sel_num}"
        if final_target.strip() and final_target != "--":
            with st.spinner("Synchronizing Government Open Data & Geospatial APIs..."):
                res = engine.get_dynamic_data(final_target, sel_floor)
                if res: st.session_state.report_data = res; engine.save_to_history(); st.rerun()

if not data.get("city"): st.stop()
st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

# ==========================================
# 📍 第一層：合併專家估價卡 + 歷史實價趨勢
# ==========================================
cs_data = m.get("core_summary", {})
c1, c2 = st.columns([1, 1])

with c1:
    r_status = m.get('risks',{}).get('高風險','--')
    r_color = "color-success" if r_status == "無顯著異常" else "color-danger"
    st.markdown(f"""
    <div class="metric-card">
        <span class="lbl">AI MODEL VALUATION (特徵估價)</span>
        <div style="font-size:0.95rem; color:#94A3B8; margin-bottom:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{data['city']} ({sel_floor})">
            {data['city']} ({sel_floor})
        </div>
        <div class="val">{cs_data.get('valuation', '--')} <span class="unit">萬/坪</span></div>
        <div class="sub">模型：{cs_data.get('valuation_source', '--')}</div>
        <div class="divider"></div>
        <span class="lbl">RISK STATUS (風險判定)</span>
        <div class="val-risk {r_color}">{r_status}</div>
        <div class="sub">產權：{m.get('risks',{}).get('低風險','--')}</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<span class="lbl">Historical Trend (區域實價歷史軌跡)</span>', unsafe_allow_html=True)
    hist = m.get("historical_prices", [50, 55, 60, 65, 70, 75])
    fig = go.Figure(data=go.Scatter(
        x=['2021','2022','2023','2024','2025','2026'], y=hist, mode='lines+markers', 
        line=dict(color='#38BDF8', width=3), marker=dict(color='#0B1220', size=8, line=dict(color='#38BDF8', width=2))
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=10,b=0), height=380, 
        xaxis=dict(showgrid=False, tickfont=dict(color='#94A3B8')), yaxis=dict(showgrid=True, gridcolor='#1e293b', tickfont=dict(color='#94A3B8'))
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

# ==========================================
# 📍 第二層：滿版巨型 360 街景
# ==========================================
g_key = data.get("google_key", "")
sv_html = f"""<iframe width="100%" height="500" style="border:0; border-radius:12px;" loading="lazy" allowfullscreen src="https://www.google.com/maps/embed/v1/streetview?key={g_key}&location={data['lat']},{data['lon']}&heading=0&pitch=0&fov=90"></iframe>""" if g_key else "<div style='color:#64748b; height:500px; display:flex; align-items:center; justify-content:center; border:1px solid #334155; border-radius:12px;'>Street View Loading...</div>"
st.markdown(f"""<div class="metric-card" style="padding:16px;"><span class="lbl" style="margin-left:8px;">Street View 360° (基地實境)</span>{sv_html}</div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

# ==========================================
# 🗺️ 第三層：巨型雙重圖資雷達 (攔截點擊事件)
# ==========================================
st.markdown('<div class="lbl" style="font-size: 1.1rem; margin-bottom:12px;">Dual-Map Spatial Radar (點擊地圖任意處可同步解析新位置)</div>', unsafe_allow_html=True)
st.markdown('<div class="metric-card" style="padding: 0; overflow:hidden;">', unsafe_allow_html=True)

d_map = engine.create_dual_map(data["lat"], data["lon"], data.get("raw_pois", []))
map_out = st_folium(d_map, width="100%", height=750, returned_objects=["last_clicked"], key=f"dmap_{data['lat']}_{data['lon']}")

if map_out and map_out.get("last_clicked"):
    click_lat = map_out["last_clicked"]["lat"]
    click_lon = map_out["last_clicked"]["lng"]
    if engine.calc_real_dist(data['lat'], data['lon'], click_lat, click_lon) > 30:
        new_addr = engine.reverse_geocode(click_lat, click_lon)
        if new_addr:
            st.session_state.pending_map_update = {"addr": new_addr, "floor": sel_floor}
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

# ==========================================
# 📊 第四層：外部機能與環境指標
# ==========================================
c_left, c_mid, c_right = st.columns(3)

with c_left:
    yb_val = yb.get('bikes','0')
    yb_color = "color-danger" if yb_val == "0" or yb_val == "--" else "color-primary"
    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">Transit: YouBike 2.0</span>
        <div class="val-text {yb_color}" style="margin-bottom:12px;">{yb.get('station', '--')}</div>
        <div class="sub">可用車輛：<span style="color:#fff; font-weight:bold;">{yb_val}</span> 台</div>
        <div class="sub">直線距離：{yb.get('dist', '--')}m</div>
    </div>""", unsafe_allow_html=True)

with c_mid:
    bus_dist = bus.get('dist', '--')
    bus_color = "color-danger" if bus_dist == "--" else "color-primary"
    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">Transit: Bus Station (全台公車)</span>
        <div class="val-text {bus_color}" style="margin-bottom:12px;">{bus.get('station', '--')}</div>
        <div class="sub">覆蓋範圍：全台資料庫連線</div>
        <div class="sub">直線距離：{bus_dist}{"m" if bus_dist != "--" else ""}</div>
    </div>""", unsafe_allow_html=True)
    
with c_right:
    aqi_val = env.get('aqi','--')
    aqi_color = "color-success" if aqi_val != "--" and int(aqi_val) <= 50 else "color-warning"
    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">Environment: US AQI</span>
        <div class="val-risk {aqi_color}" style="margin-bottom:12px;">{aqi_val}</div>
        <div class="sub">空氣狀態：{env.get('status', '--')}</div>
        <div class="sub">觀測站：衛星精確定位</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

# ==========================================
# 📊 第五層：機能瀑布流
# ==========================================
st.markdown('<div class="lbl" style="font-size: 1.1rem; margin-bottom:12px;">Area Capabilities (生活圈 6 大機能解析)</div>', unsafe_allow_html=True)

s = data.get("poi_scores", [0]*6); n = data.get("poi_names", [[]]*6)
lbls = ["交通樞紐", "醫療網絡", "學區教育", "商業聚落", "休閒綠地", "消防治安"]

html_skills = '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">'
for i in range(6):
    items_str = " · ".join([re.sub(r'\(.*?\)', '', x).strip() for x in n[i][:3]]) if n[i] else "無偵測數據"
    html_skills += f"""
    <div class="metric-card" style="padding: 20px; height:auto;">
        <div style="display: flex; justify-content: space-between; align-items: baseline;">
            <span class="lbl" style="margin:0; color:#E5E7EB; font-size:1rem;">{lbls[i]}</span>
            <span style="font-size: 1.6rem; font-weight: 700; color: #38BDF8;">{s[i]}<span style="font-size:0.8rem; color:#94A3B8; font-weight:400;"> 分</span></span>
        </div>
        <div class="bar-bg"><div class="bar-fg" style="width:{s[i]}%;"></div></div>
        <div class="sub" style="font-size:0.85rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">點位：{items_str}</div>
    </div>"""
html_skills += '</div>'
st.markdown(html_skills, unsafe_allow_html=True)
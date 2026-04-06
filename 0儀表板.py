# -*- coding: utf-8 -*-
"""
OmniUrban Decision Dashboard v10.9
=====================================
升級項目：
1. 修復 HTML 標籤因 Markdown 縮排被誤判為程式碼區塊的 Bug。
(其餘功能與版面完全不動)
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import re
from utils.engines import OmniEngine

engine = OmniEngine()
st.set_page_config(layout="wide", page_title="OmniUrban Intelligence", initial_sidebar_state="expanded")

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
    .lbl { font-size: 0.85rem; font-weight: 600; color: #94A3B8; text-transform: uppercase;
           letter-spacing: 0.05em; margin-bottom: 12px; display: block; }
    .val { font-size: 3.5rem; font-weight: 700; line-height: 1.1; margin-bottom: 4px; color: #38BDF8; }
    .val-risk { font-size: 2.5rem; font-weight: 700; line-height: 1.1; margin-bottom: 4px; }
    .val-text { font-size: 1.6rem; font-weight: 700; line-height: 1.2; margin-bottom: 4px;
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .unit { font-size: 1.2rem; color: #94A3B8; font-weight: 400; }
    .sub { font-size: 0.9rem; color: #64748b; margin-top: 6px; }
    .color-primary { color: #38BDF8; }
    .color-success { color: #14B8A6; }
    .color-danger  { color: #EF4444; }
    .color-warning { color: #F59E0B; }
    .status-capsule {
        background: #111827; border: 1px solid #334155; border-radius: 99px;
        padding: 8px 16px; display: inline-flex; gap: 16px; align-items: center;
        margin-bottom: 20px; font-size: 0.8rem; color: #94A3B8;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #111827 !important; border: 1px solid #334155 !important;
        color: #E5E7EB !important; border-radius: 6px !important;
    }
    .stButton>button {
        background: #38BDF8 !important; color: #0B1220 !important;
        border-radius: 6px !important; font-weight: 600 !important;
        border: none !important; width: 100%; padding: 0.6rem !important;
    }
    .stButton>button:hover { background: #7DD3FC !important; }
    .bar-bg { background: #334155; height: 6px; border-radius: 3px; margin: 12px 0; overflow: hidden; }
    .bar-fg { height: 100%; background: #38BDF8; border-radius: 3px; }
    .divider { border-top: 1px solid #334155; margin: 20px 0; }

    /* ── 公車與單車看板通用樣式 ── */
    .bus-board {
        background: #0B1220; border: 1px solid #1e293b; border-radius: 8px;
        padding: 5px 0;
    }
    .bus-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 7px 14px; border-bottom: 1px solid #1e293b;
        font-size: 0.88rem;
    }
    .bus-row:last-child { border-bottom: none; }
    .bus-route { font-weight: 700; color: #E5E7EB; min-width: 60px; }
    .bus-dir   { color: #64748b; font-size: 0.78rem; margin-left: 6px; }
    .eta-0  { color: #14B8A6; font-weight: 800; }   /* 即將進站 */
    .eta-1  { color: #38BDF8; font-weight: 700; }   /* ≤3分 */
    .eta-2  { color: #E5E7EB; font-weight: 600; }   /* 一般 */
    .eta-9  { color: #475569; font-weight: 400; }   /* 末班/未知 */
    .source-tag {
        display: inline-block; font-size: 0.72rem; color: #64748b;
        border: 1px solid #334155; border-radius: 4px; padding: 1px 6px; margin-left: 8px;
    }
    
    details > summary { list-style: none; }
    details > summary::-webkit-details-marker { display: none; }
    .bus-board::-webkit-scrollbar { width: 5px; }
    .bus-board::-webkit-scrollbar-track { background: transparent; }
    .bus-board::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }

    /* ── YouBike 數字格 ── */
    .yb-stats { display: flex; gap: 20px; margin-top: 14px; }
    .yb-cell { text-align: center; }
    .yb-num  { font-size: 2rem; font-weight: 800; }
    .yb-lbl  { font-size: 0.75rem; color: #64748b; margin-top: 2px; }

    /* ── 評分圖例 / expander ── */
    .score-badge { border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.03em; }
    .badge-a { background: #0f3d2e; color: #14B8A6; border: 1px solid #14B8A6; }
    .badge-b { background: #1a3a5c; color: #38BDF8; border: 1px solid #38BDF8; }
    .badge-c { background: #3a2f00; color: #F59E0B; border: 1px solid #F59E0B; }
    .badge-d { background: #3a1a1a; color: #EF4444; border: 1px solid #EF4444; }
    .streamlit-expanderHeader { background: #111827 !important; border: 1px solid #334155 !important; border-radius: 8px !important; color: #E5E7EB !important; margin-top: 20px !important; }
    .streamlit-expanderContent { background: #0f1a2e !important; border: 1px solid #334155 !important; border-top: none !important; border-radius: 0 0 8px 8px !important; }
    </style>
""", unsafe_allow_html=True)

if st.session_state.get("pending_map_update"):
    with st.spinner("📍 偵測到地圖點擊，正在反查地址並同步街景與估價模型..."):
        new_addr = st.session_state.pending_map_update["addr"]
        floor    = st.session_state.pending_map_update["floor"]
        res = engine.get_dynamic_data(new_addr, floor)
        if res:
            st.session_state.report_data = res
            engine.save_to_history()
    st.session_state.pending_map_update = None
    st.rerun()

data     = st.session_state.report_data
m        = data.get("moltke_data", {})
w        = data.get("weather_data", {})
env      = data.get("env_data", {})
yb       = data.get("yb_data", {})
bus      = data.get("bus_data", {})
api_health = m.get("api_health", {})

# ══════════════════════════════════════════════
# 🔧 Sidebar：TDX API 診斷面板
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🔧 TDX API 診斷")
    diag = engine.tdx_diagnose()

    # Client ID
    if diag["cid_set"]:
        st.success(f"✅ TDX_CLIENT_ID：`{diag['cid_preview']}`")
    else:
        st.error("❌ TDX_CLIENT_ID **未設定**")
        st.code('[secrets]\nTDX_CLIENT_ID = "你的ID"\nTDX_CLIENT_SECRET = "你的Secret"', language="toml")

    # Client Secret
    if diag["csec_set"]:
        st.success("✅ TDX_CLIENT_SECRET：已設定")
    else:
        st.error("❌ TDX_CLIENT_SECRET **未設定**")

    # Token
    if diag["token_ok"]:
        st.success(f"✅ Token 取得成功：`{diag['token_preview']}`")
    else:
        st.error("❌ Token 取得失敗")

    # 錯誤訊息
    if diag["last_error"]:
        st.markdown("**錯誤詳情：**")
        st.code(diag["last_error"], language="text")
        # 常見錯誤提示
        err = diag["last_error"]
        if "401" in err or "Unauthorized" in err:
            st.warning("💡 Client ID 或 Secret 錯誤，請至 TDX 會員中心確認金鑰")
        elif "找不到" in err:
            st.warning("💡 請在 Streamlit Cloud → Settings → Secrets 加入 TDX_CLIENT_ID 和 TDX_CLIENT_SECRET")
        elif "逾時" in err or "Timeout" in err:
            st.warning("💡 網路無法連到 TDX，請確認部署環境可對外連線")

    # 手動重置 Token 快取
    if st.button("🔄 重置 Token 快取並重試"):
        st.session_state.tdx_token     = None
        st.session_state.tdx_token_exp = 0
        st.session_state["tdx_last_error"] = ""
        st.rerun()

    st.divider()
    st.markdown("**🔍 Streamlit 實際讀到的 Secrets**")
    try:
        all_keys = list(st.secrets.keys())
        st.caption(f"所有 key：`{all_keys}`")
        cid_raw  = st.secrets.get("TDX_CLIENT_ID",    "")
        csec_raw = st.secrets.get("TDX_CLIENT_SECRET", "")
        st.code(
            f'TDX_CLIENT_ID     = "{cid_raw[:10]}…" (len={len(cid_raw)})\n'
            f'TDX_CLIENT_SECRET = "{csec_raw[:8]}…"  (len={len(csec_raw)})',
            language="text"
        )
    except Exception as ex:
        st.error(f"讀取 secrets 失敗：{ex}")

    st.divider()
    st.markdown("**secrets.toml 範本**")
    st.code(
        'GOOGLE_MAPS_API_KEY = "AIza..."\n'
        'TDX_CLIENT_ID       = "你的ClientId"\n'
        'TDX_CLIENT_SECRET   = "你的ClientSecret"',
        language="toml"
    )

st.markdown('<div class="hero-title">OmniUrban Spatial Engine</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="status-capsule">
    <div style="color:#14B8A6; font-weight:700;">● SYSTEM ONLINE</div>
    <div>|</div>
    <div>API: {api_health.get('Google','--')}</div>
    <div>Weather: {w.get('temp','--')}</div>
    <div>AQI: {env.get('aqi','--')} ({env.get('api_status','--')})</div>
    <div>YouBike: {yb.get('source','--')}</div>
</div>
""", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="lbl" style="font-size:1rem;">Target Location (目標基地設定)</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c1:
        manual_addr = st.text_input("直接輸入完整地址", placeholder="例如：臺北市文山區指南路二段64號", label_visibility="collapsed")
    with c2:
        sel_floor = st.selectbox("評估類型", ["全棟評估", "1樓店面", "4~5樓公寓", "電梯大樓"], label_visibility="collapsed")
    
    st.write("") 
    
    st.markdown('<div style="color:#64748b; font-size:0.85rem; margin:8px 0;">或使用下方選單快速定位：</div>', unsafe_allow_html=True)
    c3, c4, c5, c6 = st.columns([1, 1, 1.5, 1])
    with c3: sel_city = st.selectbox("縣市", ["--"] + list(engine.taiwan_data.keys()), label_visibility="collapsed")
    with c4: sel_dist = st.selectbox("行政區", engine.taiwan_data.get(sel_city, ["--"]) if sel_city != "--" else ["--"], disabled=(sel_city == "--"), label_visibility="collapsed")
    with c5:
        roads = engine.get_roads_list(sel_city, sel_dist)
        sel_road = st.selectbox("路段", roads if roads else ["--"], disabled=(sel_dist == "--" or not roads), label_visibility="collapsed")
    with c6: sel_num = st.text_input("門牌", placeholder="巷/弄/門牌號 (選填)", label_visibility="collapsed")
    
    st.write("") 
    
    if st.button("啟動特徵空間分析 (RUN ANALYSIS)"):
        final_target = manual_addr if manual_addr else f"{sel_city}{sel_dist}{sel_road if not sel_road.startswith('--') else ''}{sel_num}"
        if final_target.strip() and final_target != "--":
            with st.spinner("Synchronizing Government Open Data & Geospatial APIs..."):
                res = engine.get_dynamic_data(final_target, sel_floor)
                if res:
                    st.session_state.report_data = res
                    engine.save_to_history()
                    st.rerun()

if not data.get("city"): st.stop()
st.write("")
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

cs_data = m.get("core_summary", {})
col1, col2 = st.columns(2)
with col1:
    r_status = m.get('risks', {}).get('高風險', '--')
    r_color  = "color-success" if r_status == "無顯著異常" else "color-danger"
    st.markdown(f"""
    <div class="metric-card">
        <span class="lbl">AI MODEL VALUATION (特徵估價)</span>
        <div style="font-size:0.95rem;color:#94A3B8;margin-bottom:8px;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
             title="{data['city']} ({sel_floor})">{data['city']} ({sel_floor})</div>
        <div class="val">{cs_data.get('valuation','--')} <span class="unit">萬/坪</span></div>
        <div class="sub">模型：{cs_data.get('valuation_source','--')}</div>
        <div class="divider"></div>
        <span class="lbl">RISK STATUS (風險判定)</span>
        <div class="val-risk {r_color}">{r_status}</div>
        <div class="sub">產權：{m.get('risks',{}).get('低風險','--')}</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<span class="lbl">Historical Trend (區域實價歷史軌跡)</span>', unsafe_allow_html=True)
    hist = m.get("historical_prices", [50, 55, 60, 65, 70, 75])
    fig = go.Figure(go.Scatter(
        x=['2021','2022','2023','2024','2025','2026'], y=hist, mode='lines+markers',
        line=dict(color='#38BDF8', width=3),
        marker=dict(color='#0B1220', size=8, line=dict(color='#38BDF8', width=2))
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=10, b=0), height=380,
        xaxis=dict(showgrid=False, tickfont=dict(color='#94A3B8')),
        yaxis=dict(showgrid=True, gridcolor='#1e293b', tickfont=dict(color='#94A3B8'))
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

st.write("") 

g_key      = data.get("google_key", "")
sv_heading = data.get("sv_heading", 0)
sv_html = (
    f'<iframe width="100%" height="500" style="border:0;border-radius:12px;" '
    f'loading="lazy" allowfullscreen '
    f'src="https://www.google.com/maps/embed/v1/streetview?key={g_key}'
    f'&location={data["lat"]},{data["lon"]}&heading={sv_heading}&pitch=10&fov=90"></iframe>'
) if g_key else (
    "<div style='color:#64748b;height:500px;display:flex;align-items:center;"
    "justify-content:center;border:1px solid #334155;border-radius:12px;'>Street View Loading...</div>"
)
st.markdown(
    f'<div class="metric-card" style="padding:16px;">'
    f'<span class="lbl" style="margin-left:8px;">Street View 360° (基地實境) — Heading {sv_heading}°</span>'
    f'{sv_html}</div>',
    unsafe_allow_html=True
)

st.write("") 

st.markdown('<div class="lbl" style="font-size:1.1rem;margin-bottom:10px;">Dual-Map Spatial Radar (點擊地圖任意處可同步解析新位置)</div>', unsafe_allow_html=True)
st.markdown('<div class="metric-card" style="padding:0;overflow:hidden;">', unsafe_allow_html=True)
d_map = engine.create_dual_map(data["lat"], data["lon"], data.get("raw_pois", []))
map_out = st_folium(d_map, width="100%", height=750,
                    returned_objects=["last_clicked"],
                    key=f"dmap_{data['lat']}_{data['lon']}")
if map_out and map_out.get("last_clicked"):
    click_lat = map_out["last_clicked"]["lat"]
    click_lon = map_out["last_clicked"]["lng"]
    if engine.calc_real_dist(data['lat'], data['lon'], click_lat, click_lon) > 30:
        new_addr = engine.reverse_geocode(click_lat, click_lon)
        if new_addr:
            st.session_state.pending_map_update = {"addr": new_addr, "floor": sel_floor}
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.write("") 

c_left, c_mid, c_right = st.columns(3)

with c_left:
    yb_bikes = str(yb.get('bikes', '0'))
    yb_empty = str(yb.get('empty_slots', '--'))
    yb_dist  = yb.get('dist', '--')
    yb_src   = yb.get('source', '')
    has_bikes = yb_bikes not in ('0', '--', '')
    yb_color = "color-primary" if has_bikes else "color-danger"
    yb_dist_str = f"{yb_dist}m" if yb_dist not in ('--', '') else "--"

    # 🚀 壓平字串，防止 Markdown 縮排錯誤
    yb_nearby = yb.get('nearby_stations', [])
    yb_board = ""
    if yb_nearby and len(yb_nearby) > 1:
        yb_rows = ""
        for s in yb_nearby[1:]: 
            c = "#14B8A6" if int(s['bikes']) > 0 else "#EF4444"
            yb_rows += f"<div class='bus-row'><div><span class='bus-route'>{s['name']}</span><span class='bus-dir'>({s['dist']}m)</span></div><div style='color:{c}; font-weight:700; font-size:0.9rem;'>{s['bikes']} 輛 <span style='color:#64748b;font-weight:400;font-size:0.75rem;'>/ {s['empty']} 空</span></div></div>"
            
        yb_board = f"<details style='margin-top: 12px;'><summary style='cursor: pointer; color: #38BDF8; font-size: 0.85rem; font-weight: 600; padding: 6px 0; outline: none;'>👇 附近其他 {len(yb_nearby)-1} 個站點</summary><div class='bus-board' style='max-height: 160px; overflow-y: auto; margin-top: 4px;'>{yb_rows}</div></details>"

    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">🚲 YouBike 2.0 <span class="source-tag">{yb_src}</span></span>
        <div class="val-text {yb_color}">{yb.get('station','--')}</div>
        <div class="sub">直線距離：{yb_dist_str}</div>
        <div class="yb-stats">
            <div class="yb-cell">
                <div class="yb-num" style="color:{'#14B8A6' if has_bikes else '#EF4444'};">{yb_bikes}</div>
                <div class="yb-lbl">可借車輛</div>
            </div>
            <div class="yb-cell">
                <div class="yb-num" style="color:#94A3B8;">{yb_empty}</div>
                <div class="yb-lbl">可還空位</div>
            </div>
        </div>
        {yb_board}
    </div>""", unsafe_allow_html=True)

with c_mid:
    bus_dist   = bus.get('dist', '--')
    bus_src    = bus.get('source', '')
    arrivals   = bus.get('arrivals', [])
    bus_dist_str = f"{bus_dist}m" if bus_dist not in ('--', '') else "--"

    # 🚀 壓平字串，防止 Markdown 縮排錯誤
    if arrivals:
        rows_html = ""
        for a in arrivals:
            urgency = a.get("urgency", 9)
            eta_cls = {0: "eta-0", 1: "eta-1", 2: "eta-2", 3: "eta-2"}.get(urgency, "eta-9") if urgency <= 3 else "eta-9"
            plate   = a.get('plate', '')
            plate_str = f"<span style='color:#475569;font-size:0.75rem;'> [{plate}]</span>" if plate and plate != "noPlate" else ""
            dir_str = f"<span class='bus-dir'>({a.get('dir','')})</span>"
            rows_html += f"<div class='bus-row'><div><span class='bus-route'>{a['route']}</span>{dir_str}{plate_str}</div><div class='{eta_cls}'>{a['label']}</div></div>"
            
        board = f"<details style='margin-top: 8px;'><summary style='cursor: pointer; color: #38BDF8; font-size: 0.85rem; font-weight: 600; padding: 6px 0; outline: none;'>👇 點擊展開所有路線 ({len(arrivals)} 班次)</summary><div class='bus-board' style='max-height: 200px; overflow-y: auto; margin-top: 4px;'>{rows_html}</div></details>"
    else:
        no_data_msg = "TDX 未設定，顯示靜態站名" if "Google" in bus_src else "此區域暫無動態資料"
        board = f'<div class="bus-board"><div class="bus-row" style="color:#475569;">{no_data_msg}</div></div>'

    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">🚌 公車動態 <span class="source-tag">{bus_src}</span></span>
        <div class="val-text color-primary" style="margin-bottom:4px;">{bus.get('station','--')}</div>
        <div class="sub" style="margin-bottom:0;">直線距離：{bus_dist_str}</div>
        {board}
    </div>""", unsafe_allow_html=True)

with c_right:
    aqi_val = env.get('aqi', '--')
    try:
        aqi_int = int(aqi_val)
        aqi_color = ("color-success" if aqi_int <= 50
                     else "color-warning" if aqi_int <= 100 else "color-danger")
    except:
        aqi_color = "color-warning"
    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">🌫️ Environment: US AQI</span>
        <div class="val-risk {aqi_color}" style="margin-bottom:12px;">{aqi_val}</div>
        <div class="sub">空氣狀態：{env.get('status','--')}</div>
        <div class="sub">氣溫：{w.get('temp','--')} ／ 濕度：{w.get('humidity','--')}</div>
        <div class="sub">觀測站：衛星精確定位</div>
    </div>""", unsafe_allow_html=True)

st.write("") 

st.markdown("""
<div style="margin-bottom:10px;">
  <span class="lbl" style="font-size:1.1rem;display:inline-block;margin-right:16px;">Area Capabilities (生活圈 6 大機能解析)</span>
  <span style="display:inline-flex;gap:10px;align-items:center;flex-wrap:wrap;vertical-align:middle;">
    <span class="score-badge badge-a">85~100 優異</span>
    <span class="score-badge badge-b">60~84 良好</span>
    <span class="score-badge badge-c">35~59 普通</span>
    <span class="score-badge badge-d">0~34 不足</span>
    <span style="font-size:0.75rem;color:#64748b;margin-left:4px;">* 基於 Google Places 500m~1.5km 掃描密度換算</span>
  </span>
</div>
""", unsafe_allow_html=True)

s    = data.get("poi_scores", [0]*6)
n    = data.get("poi_names", [[]]*6)
lbls  = ["交通樞紐", "醫療網絡", "學區教育", "商業聚落", "休閒綠地", "消防治安"]
icons = ["🚌", "🏥", "🎓", "🏪", "🌳", "🚒"]

def score_color(sc):
    if sc >= 85: return "#14B8A6"
    if sc >= 60: return "#38BDF8"
    if sc >= 35: return "#F59E0B"
    return "#EF4444"

html_grid = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px;">'
for i in range(6):
    items = " · ".join([re.sub(r'\(.*?\)', '', x).strip() for x in n[i][:3]]) if n[i] else "無偵測數據"
    clr   = score_color(s[i])
    html_grid += f"""
    <div class="metric-card" style="padding:20px;height:auto;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <span class="lbl" style="margin:0;color:#E5E7EB;font-size:1rem;">{icons[i]} {lbls[i]}</span>
            <span style="font-size:1.6rem;font-weight:700;color:{clr};">{s[i]}<span style="font-size:0.8rem;color:#94A3B8;font-weight:400;"> 分</span></span>
        </div>
        <div class="bar-bg"><div class="bar-fg" style="width:{s[i]}%;background:{clr};"></div></div>
        <div class="sub" style="font-size:0.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">點位：{items}</div>
    </div>"""
html_grid += '</div>'
st.markdown(html_grid, unsafe_allow_html=True)

with st.expander("📋 點此查看：六大機能詳細點位資訊 & 評分標準", expanded=True):
    st.markdown('<div style="padding:8px 0 16px 0;color:#94A3B8;font-size:0.85rem;">各機能完整偵測點位清單（依距離排序）。資料來源：Google Places API 即時掃描。</div>', unsafe_allow_html=True)
    dc = st.columns(2)
    for i in range(6):
        clr = score_color(s[i])
        poi_html = ""
        if n[i]:
            for item in n[i]:
                dm = re.search(r'\((\d+)m\)', item)
                ds = f'<span style="color:#64748b;font-size:0.8rem;"> {dm.group(0)}</span>' if dm else ''
                nm = re.sub(r'\(\d+m\)', '', item).strip()
                poi_html += f'<div style="padding:6px 0;border-bottom:1px solid #1e293b;color:#E5E7EB;">• {nm}{ds}</div>'
        else:
            poi_html = '<div style="color:#64748b;padding:6px 0;">無偵測到相關設施</div>'
        with dc[i % 2]:
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:16px;padding:18px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <span style="font-weight:700;font-size:1rem;color:#E5E7EB;">{icons[i]} {lbls[i]}</span>
                    <span style="font-size:1.4rem;font-weight:700;color:{clr};">{s[i]} 分</span>
                </div>
                <div class="bar-bg"><div class="bar-fg" style="width:{s[i]}%;background:{clr};"></div></div>
                {poi_html}
            </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#111827;border:1px solid #334155;border-radius:10px;padding:20px;
                margin-top:10px;color:#94A3B8;font-size:0.85rem;line-height:1.8;">
        <div style="color:#E5E7EB;font-weight:600;font-size:1rem;margin-bottom:12px;">📐 六大機能生活圈評分標準與權重</div>
        <div>本系統依據 <b>Google Places API</b> 在指定半徑內掃描各類設施的「密度」進行換算：</div>
        <div style="margin:12px 0;padding:10px 14px;background:#0B1220;border-radius:6px;
                    font-family:monospace;color:#38BDF8;font-size:0.95rem;">
            綜合分數 = min( 98, (掃描到設施數量 / 4) × 100 + 35 )
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:15px;">
            <div style="background:#0F172A;padding:10px;border-radius:6px;border-left:4px solid #38BDF8;">
                🚌 <b>交通樞紐 (權重 25%)</b><br>搜尋參數：transit_station<br>偵測半徑：800m
            </div>
            <div style="background:#0F172A;padding:10px;border-radius:6px;border-left:4px solid #14B8A6;">
                🏥 <b>醫療網絡 (權重 15%)</b><br>搜尋參數：hospital<br>偵測半徑：800m
            </div>
            <div style="background:#0F172A;padding:10px;border-radius:6px;border-left:4px solid #F59E0B;">
                🎓 <b>學區教育 (權重 15%)</b><br>搜尋參數：school<br>偵測半徑：1200m
            </div>
            <div style="background:#0F172A;padding:10px;border-radius:6px;border-left:4px solid #EF4444;">
                🏪 <b>商業聚落 (權重 20%)</b><br>搜尋參數：convenience_store<br>偵測半徑：800m
            </div>
            <div style="background:#0F172A;padding:10px;border-radius:6px;border-left:4px solid #8B5CF6;">
                🌳 <b>休閒綠地 (權重 15%)</b><br>搜尋參數：park (排除餐廳/咖啡廳)<br>偵測半徑：1000m
            </div>
            <div style="background:#0F172A;padding:10px;border-radius:6px;border-left:4px solid #EAB308;">
                🚒 <b>消防治安 (權重 10%)</b><br>搜尋參數：police<br>偵測半徑：1500m
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
# -*- coding: utf-8 -*-
"""
OmniUrban Decision Dashboard v11.0
=====================================
修復與新增項目：
1. 【修復】新增停車場資訊卡（呼叫 engines.get_parking_data()）
2. 【修復】新增自行車道資訊卡（呼叫 engines.get_bike_lanes()）
3. 【修復】YouBike bikes 數值安全轉型（防止 '?' 導致 int() 崩潰）
4. 【修復】Sidebar 新增歷史查詢紀錄，可一鍵重新載入
5. 【修復】Status Capsule 新增停車場與自行車道狀態
6. 【修復】分析按鈕後同步取得停車場與自行車道資料並存入 session_state
7. 【其餘原有功能與版面完全不動】
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
    .eta-0  { color: #14B8A6; font-weight: 800; }
    .eta-1  { color: #38BDF8; font-weight: 700; }
    .eta-2  { color: #E5E7EB; font-weight: 600; }
    .eta-9  { color: #475569; font-weight: 400; }
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

    /* ── 停車場格 ── */
    .park-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 7px 14px; border-bottom: 1px solid #1e293b; font-size: 0.88rem;
    }
    .park-row:last-child { border-bottom: none; }
    .park-name { font-weight: 600; color: #E5E7EB; }
    .park-avail { font-size: 1.1rem; font-weight: 800; }

    /* ── 評分圖例 / expander ── */
    .score-badge { border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.03em; }
    .badge-a { background: #0f3d2e; color: #14B8A6; border: 1px solid #14B8A6; }
    .badge-b { background: #1a3a5c; color: #38BDF8; border: 1px solid #38BDF8; }
    .badge-c { background: #3a2f00; color: #F59E0B; border: 1px solid #F59E0B; }
    .badge-d { background: #3a1a1a; color: #EF4444; border: 1px solid #EF4444; }
    .streamlit-expanderHeader { background: #111827 !important; border: 1px solid #334155 !important; border-radius: 8px !important; color: #E5E7EB !important; margin-top: 20px !important; }
    .streamlit-expanderContent { background: #0f1a2e !important; border: 1px solid #334155 !important; border-top: none !important; border-radius: 0 0 8px 8px !important; }

    /* ── 歷史紀錄按鈕 ── */
    .hist-btn { background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                padding: 8px 12px; margin-bottom: 6px; cursor: pointer;
                font-size: 0.82rem; color: #94A3B8; width: 100%; text-align: left; }
    </style>
""", unsafe_allow_html=True)

# ── 初始化新增的 session_state 欄位 ──
if "parking_data" not in st.session_state:
    st.session_state.parking_data = {"status": "待機", "lots": [], "source": ""}
if "bike_data" not in st.session_state:
    st.session_state.bike_data = {"status": "待機", "count": 0, "nearest": "--", "source": ""}
if "train_data" not in st.session_state:
    st.session_state.train_data = {"status": "待機", "message": "", "delays": [], "source": ""}

if st.session_state.get("pending_map_update"):
    with st.spinner("📍 偵測到地圖點擊，正在反查地址並同步街景與估價模型..."):
        new_addr = st.session_state.pending_map_update["addr"]
        floor    = st.session_state.pending_map_update["floor"]
        res = engine.get_dynamic_data(new_addr, floor)
        if res:
            st.session_state.report_data = res
            engine.save_to_history()
            lat = res.get("lat", 25.0330)
            lon = res.get("lon", 121.5654)
            st.session_state.parking_data = engine.get_parking_data(lat, lon)
            st.session_state.bike_data    = engine.get_bike_lanes(lat, lon)
    st.session_state.pending_map_update = None
    st.rerun()

data       = st.session_state.report_data
m          = data.get("moltke_data", {})
w          = data.get("weather_data", {})
env        = data.get("env_data", {})
yb         = data.get("yb_data", {})
bus        = data.get("bus_data", {})
api_health = m.get("api_health", {})
pk         = st.session_state.parking_data
bk         = st.session_state.bike_data
tr         = st.session_state.train_data

# ══════════════════════════════════════════════
# 🔧 Sidebar：系統狀態
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 📊 系統連線狀態")
    diag = engine.tdx_diagnose()

    if diag["cid_set"] and diag["csec_set"]:
        if diag["token_ok"]:
            st.success("🟢 TDX API：連線正常")
        else:
            st.error("🔴 TDX API：連線失敗")
            if diag["last_error"]:
                with st.expander("查看錯誤提示"):
                    st.caption(diag["last_error"])
    else:
        st.warning("🟡 TDX API：未設定金鑰")
        st.caption("請確認 Secrets 中已填寫 TDX 資訊。")

    if st.button("🔄 重新連線 TDX"):
        st.session_state.tdx_token     = None
        st.session_state.tdx_token_exp = 0
        st.session_state["tdx_last_error"] = ""
        with st.spinner("正在重新連線..."):
            res = engine.tdx_test_token()
            if res["ok"]:
                st.toast("✅ 連線成功！", icon="🎉")
            else:
                st.toast(f"❌ {res['error']}", icon="🚨")
        st.rerun()

    st.divider()
    _d = st.session_state.report_data
    _lat = _d.get("lat", 25.0330)
    _lon = _d.get("lon", 121.5654)
    _city = _d.get("city", "（尚未查詢）")
    st.code(f"地址：{_city}\nlat = {_lat}\nlon = {_lon}", language="text")
    if _lat == 25.0330 and _lon == 121.5654:
        st.warning("⚠️ 座標是預設值 — 地址未成功 Geocode，請確認 GOOGLE_MAPS_API_KEY 已設定")

    st.markdown("### 🔬 TDX API 直接測試")
    st.caption("⚠️ 過於頻繁會觸發限流 (429)。每次測試間隔建議 5 秒以上。")
    
    # 初始化測試冷卻時間
    if "last_tdx_test_time" not in st.session_state:
        st.session_state.last_tdx_test_time = 0
    
    _test_lat = st.number_input("測試緯度", value=float(_lat), format="%.6f", key="test_lat")
    _test_lon = st.number_input("測試經度", value=float(_lon), format="%.6f", key="test_lon")
    
    # 防頻繁點擊檢查函數
    def _check_rate_limit(min_interval=5):
        import time as _time_module
        _now = _time_module.time()
        _elapsed = _now - st.session_state.last_tdx_test_time
        if _elapsed < min_interval:
            st.warning(f"⏳ 請稍候 {min_interval - int(_elapsed)} 秒後再測試（防止 API 限流）")
            return False
        st.session_state.last_tdx_test_time = _now
        return True
    
    if st.button("🚲 測試 YouBike NearBy"):
        if not _check_rate_limit(5):
            st.stop()
        
        import requests as _req
        _tok = engine._get_tdx_token()
        if _tok:
            try:
                _r = _req.get(
                    "https://tdx.transportdata.tw/api/basic/v2/Bike/Station/NearBy",
                    headers={"Authorization": f"Bearer {_tok}", "Accept": "application/json"},
                    params={"$spatialFilter": f"nearby({_test_lat},{_test_lon},1200)",
                            "$format": "JSON", "$top": 5,
                            "$select": "StationUID,StationName,StationPosition"},
                    timeout=10
                )
                
                if _r.status_code == 429:
                    st.error("❌ HTTP 429 — API 限流中。請等待 30 秒後重試。")
                    st.code("響應：API rate limit exceeded", language="text")
                else:
                    st.code(f"HTTP {_r.status_code} ✓", language="text")
                    try:
                        _j = _r.json()
                        if isinstance(_j, list):
                            st.success(f"✅ 找到 {len(_j)} 個站點")
                            for _s in _j[:3]:
                                _n = _s.get("StationName", {}).get("Zh_tw", "?")
                                _p = _s.get("StationPosition", {})
                                st.caption(f"• {_n} ({_p.get('PositionLat'):.4f}, {_p.get('PositionLon'):.4f})")
                        else:
                            st.json(_j)
                    except Exception as _e:
                        st.code(_r.text[:400])
            except Exception as _e:
                st.error(f"❌ 請求失敗：{str(_e)}")
        else:
            st.error("Token 無效")
    
    if st.button("🚌 測試公車 Stop NearBy"):
        if not _check_rate_limit(5):
            st.stop()
        
        import requests as _req
        _tok = engine._get_tdx_token()
        if _tok:
            try:
                _r = _req.get(
                    "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/NearBy",
                    headers={"Authorization": f"Bearer {_tok}", "Accept": "application/json"},
                    params={"$spatialFilter": f"nearby({_test_lat},{_test_lon},800)",
                            "$format": "JSON", "$top": 5,
                            "$select": "StopUID,StopName,StopPosition"},
                    timeout=10
                )
                
                if _r.status_code == 429:
                    st.error("❌ HTTP 429 — API 限流中。請等待 30 秒後重試。")
                    st.code("響應：API rate limit exceeded", language="text")
                else:
                    st.code(f"HTTP {_r.status_code} ✓", language="text")
                    try:
                        _j = _r.json()
                        if isinstance(_j, list):
                            st.success(f"✅ 找到 {len(_j)} 個站牌")
                            for _s in _j[:3]:
                                st.caption(f"• {_s.get('StopName',{}).get('Zh_tw','?')}")
                        else:
                            st.json(_j)
                    except Exception as _e:
                        st.code(_r.text[:400])
            except Exception as _e:
                st.error(f"❌ 請求失敗：{str(_e)}")
        else:
            st.error("Token 無效")

    # ── 歷史查詢紀錄 ──
    history = st.session_state.get("history", [])
    if history:
        st.divider()
        st.markdown("### 📂 歷史查詢紀錄")
        for i, h in enumerate(history):
            city_label = h.get("city", "")
            val = h.get("moltke_data", {}).get("core_summary", {}).get("valuation", "--")
            if st.button(f"📍 {city_label[:18]}\n💰 {val} 萬/坪", key=f"hist_{i}"):
                st.session_state.report_data = h
                st.session_state.parking_data = engine.get_parking_data(h["lat"], h["lon"])
                st.session_state.bike_data    = engine.get_bike_lanes(h["lat"], h["lon"])
                st.rerun()

# ══════════════════════════════════════════════
# 🏠 主頁面
# ══════════════════════════════════════════════
st.markdown('<div class="hero-title">OmniUrban Spatial Engine</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="status-capsule">
    <div style="color:#14B8A6; font-weight:700;">● SYSTEM ONLINE</div>
    <div>|</div>
    <div>API: {api_health.get('Google','--')}</div>
    <div>Weather: {w.get('temp','--')}</div>
    <div>AQI: {env.get('aqi','--')} ({env.get('api_status','--')})</div>
    <div>YouBike: {yb.get('source','--')}</div>
    <div>公車: {bus.get('source','--')}</div>
    <div>列車: {tr.get('source','--')}</div>
    <div>停車: {pk.get('status','--')}</div>
    <div>單車道: {bk.get('status','--')}</div>
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
                    lat = res.get("lat", 25.0330)
                    lon = res.get("lon", 121.5654)
                    # ✅ 修復：同步取得停車場、自行車道、列車延誤資料
                    st.session_state.parking_data = engine.get_parking_data(lat, lon)
                    st.session_state.bike_data    = engine.get_bike_lanes(lat, lon)
                    st.session_state.train_data   = engine.get_train_delay_data()
                    st.rerun()

if not data.get("city"): st.stop()
st.write("")
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# ── 估價 + 歷史走勢 ──
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

# ── Street View ──
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

# ── Dual Map ──
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

# ══════════════════════════════════════════════
# 交通資訊列（YouBike / 公車 / 環境）
# ══════════════════════════════════════════════
c_left, c_mid, c_right = st.columns(3)

with c_left:
    yb_bikes = str(yb.get('bikes', '0'))
    yb_empty = str(yb.get('empty_slots', '--'))
    yb_dist  = yb.get('dist', '--')
    yb_src   = yb.get('source', '')
    # ✅ 修復：安全轉型，避免 '?' 導致 int() 崩潰
    try:
        has_bikes = int(yb_bikes) > 0
    except:
        has_bikes = False
    yb_color = "color-primary" if has_bikes else "color-danger"
    yb_dist_str = f"{yb_dist}m" if yb_dist not in ('--', '') else "--"

    yb_nearby = yb.get('nearby_stations', [])
    yb_board = ""
    if yb_nearby and len(yb_nearby) > 1:
        yb_rows = ""
        for s in yb_nearby[1:]:
            try:
                c_color = "#14B8A6" if int(s['bikes']) > 0 else "#EF4444"
            except:
                c_color = "#64748b"
            yb_rows += f"<div class='bus-row'><div><span class='bus-route'>{s['name']}</span><span class='bus-dir'>({s['dist']}m)</span></div><div style='color:{c_color}; font-weight:700; font-size:0.9rem;'>{s['bikes']} 輛 <span style='color:#64748b;font-weight:400;font-size:0.75rem;'>/ {s['empty']} 空</span></div></div>"
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
    bus_dist     = bus.get('dist', '--')
    bus_src      = bus.get('source', '')
    arrivals     = bus.get('arrivals', [])
    bus_dist_str = f"{bus_dist}m" if bus_dist not in ('--', '') else "--"

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

# ══════════════════════════════════════════════
# 🆕 新增資訊列：停車場 + 自行車道 + 列車延誤
# ══════════════════════════════════════════════
cp1, cp2, cp3 = st.columns(3)

with cp1:
    pk_src   = pk.get('source', '--')
    pk_lots  = pk.get('lots', [])
    pk_status = pk.get('status', '🔴')

    if pk_lots:
        pk_rows = ""
        for lot in pk_lots:
            avail = lot.get('available', '--')
            total = lot.get('total', '--')
            try:
                avail_int = int(avail)
                pk_color = "#14B8A6" if avail_int > 20 else "#F59E0B" if avail_int > 5 else "#EF4444"
            except:
                pk_color = "#64748b"
            avail_label = f"{avail} / {total}" if total != '--' else str(avail)
            pk_rows += f"<div class='park-row'><span class='park-name'>{lot.get('name','--')}</span><span class='park-avail' style='color:{pk_color};'>{avail_label} 格</span></div>"
        pk_board = f"<div class='bus-board' style='margin-top:12px;'>{pk_rows}</div>"
    else:
        pk_board = "<div class='bus-board'><div class='bus-row' style='color:#475569;'>附近無即時停車資料</div></div>"

    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">🅿️ 附近停車場 <span class="source-tag">{pk_src}</span></span>
        <div class="val-text {'color-primary' if pk_lots else 'color-danger'}" style="margin-bottom:4px;">
            {'即時車位' if pk_lots else '暫無資料'}
        </div>
        <div class="sub" style="margin-bottom:0;">顯示 1km 內停車場即時剩餘格數</div>
        {pk_board}
    </div>""", unsafe_allow_html=True)

with cp2:
    bk_src    = bk.get('source', '--')
    bk_count  = bk.get('count', 0)
    bk_nearest = bk.get('nearest', '--')
    bk_status  = bk.get('status', '🔴')
    bk_color   = "color-primary" if bk_count > 0 else "color-danger"
    bk_label   = f"偵測到 {bk_count} 處" if bk_count > 0 else "附近無資料"

    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">🚴 自行車道 / 單車設施 <span class="source-tag">{bk_src}</span></span>
        <div class="val-text {bk_color}" style="margin-bottom:4px;">{bk_label}</div>
        <div class="sub">最近設施：{bk_nearest}</div>
        <div class="sub" style="margin-top:12px;">偵測半徑：1000m 內自行車道與租賃站</div>
        <div class="bus-board" style="margin-top:12px;">
            <div class="bus-row">
                <span style="color:#94A3B8;font-size:0.85rem;">🚲 YouBike 最近站</span>
                <span style="color:#38BDF8;font-weight:600;">{yb.get('station','--')}</span>
            </div>
            <div class="bus-row">
                <span style="color:#94A3B8;font-size:0.85rem;">📍 距離</span>
                <span style="color:#E5E7EB;">{str(yb.get('dist','--')) + 'm' if yb.get('dist','--') not in ('--','') else '--'}</span>
            </div>
            <div class="bus-row">
                <span style="color:#94A3B8;font-size:0.85rem;">🛣️ 附近車道數</span>
                <span style="color:#{'14B8A6' if bk_count > 0 else '475569'};">{bk_count} 條</span>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

with cp3:
    tr_src    = tr.get('source', '--')
    tr_message = tr.get('message', '載入中...')
    tr_delays = tr.get('delays', [])
    tr_status  = tr.get('status', '🟡')
    tr_label   = f"偵測 {len(tr_delays)} 班延誤列車" if tr_delays else "列車準點"
    tr_color   = "color-danger" if len(tr_delays) > 5 else "color-warning" if tr_delays else "color-success"

    if tr_delays:
        tr_rows = ""
        for delay in tr_delays[:5]:  # 最多顯示5班延誤列車
            train_no = delay.get('train_no', '--')
            delay_mins = delay.get('delay_mins', 0)
            severity = delay.get('severity', '--')
            station = delay.get('station', '--')  # 修復：改用 station 欄位
            
            # 顏色根據延誤分級
            if "嚴重" in severity:
                delay_color = "#EF4444"
            elif "中等" in severity:
                delay_color = "#F59E0B"
            else:
                delay_color = "#38BDF8"
            
            tr_rows += f"""<div class='bus-row'>
                <span style='color:#E5E7EB;font-weight:600;'>{train_no}</span>
                <span style='color:{delay_color};font-weight:700;'>{delay_mins}分 {severity}</span>
            </div>
            <div class='bus-row' style='border-bottom:none;padding-top:2px;'>
                <span style='color:#64748b;font-size:0.75rem;'>📍 {station}</span>
            </div>"""
        
        tr_detail = f"<div class='bus-board' style='margin-top:12px;'>{tr_rows}</div>"
    else:
        tr_detail = "<div class='bus-board'><div class='bus-row' style='color:#14B8A6;text-align:center;justify-content:center;font-weight:600;'>✅ 列車準點運行</div></div>"

    st.markdown(f"""
    <div class="metric-card" style="padding:24px;">
        <span class="lbl">🚆 台鐵列車即時 <span class="source-tag">{tr_src}</span></span>
        <div class="val-text {tr_color}" style="margin-bottom:4px;">{tr_label}</div>
        <div class="sub">{tr_message}</div>
        {tr_detail}
    </div>""", unsafe_allow_html=True)

st.write("")

# ══════════════════════════════════════════════
# 生活圈 6 大機能解析
# ══════════════════════════════════════════════
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
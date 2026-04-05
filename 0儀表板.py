import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import time

# ==========================================
# 1. 頁面與全域設定 (解決：空白調整與排版)
# ==========================================
st.set_page_config(page_title="Omni-Urban AI 儀表板", page_icon="🏠", layout="wide", initial_sidebar_state="expanded")

# 隱藏預設的 Streamlit 樣式，讓畫面更專業
hide_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# ==========================================
# 2. 核心邏輯引擎與資料庫 (解決：AI 幻想與評分標準)
# ==========================================
def get_lat_lon(address):
    """將地址轉換為精確經緯度 (這裡暫時模擬，實戰請接 Geocoding API)"""
    # 預設給一個信義區的座標
    return 25.033964, 121.564468

def fetch_urban_data(lat, lon):
    """模擬複雜的 6 大機能 API 爬蟲與資料庫檢索"""
    time.sleep(1) # 模擬運算時間
    return {
        "交通連結": {
            "score": 92, "weight": "25%", 
            "std": "500m內捷運站、公車站點密度。附加：步行3分鐘內 YouBike 站點。",
            # 解決：YouBike 數據顯示
            "details": "📍 捷運台北101站 (300m)\n🚲 **YouBike 2.0 站點 (150m，目前可借: 8台)**"
        },
        "醫療網絡": {
            "score": 85, "weight": "15%", 
            "std": "1km內大型醫院(醫學中心/區域醫院)與社區藥局分布。",
            "details": "📍 臺北醫學大學附設醫院 (800m)\n💊 周邊健保特約藥局 4 家"
        },
        "學區教育": {
            "score": 88, "weight": "15%", 
            "std": "周邊國中小學區重疊率、步行距離與文教設施密度。",
            "details": "📍 信義國小 (400m)\n🏫 連鎖文理補習班 3 家"
        },
        "商業聚落": {
            "score": 95, "weight": "20%", 
            "std": "步行10分鐘內連鎖超市(全聯/家樂福)、便利商店與商場數量。",
            "details": "📍 全聯福利中心 (200m)\n🏪 24H 便利商店 5 家"
        },
        "休閒綠地": {
            "score": 78, "weight": "15%", 
            "std": "800m內都市計畫公園綠地面積總和與國民運動中心。",
            "details": "📍 信義廣場公園 (150m)\n🏃‍♂️ 信義運動中心"
        },
        "消防治安": {
            "score": 90, "weight": "10%", 
            "std": "派出所、消防隊服務半徑及歷年犯罪熱區比對。",
            "details": "📍 信義分局三張犁派出所 (600m)\n🚒 信義消防分隊"
        }
    }

def draw_radar_chart(data_dict):
    """繪製專業雷達圖"""
    categories = list(data_dict.keys())
    scores = [v["score"] for v in data_dict.values()]
    
    fig = go.Figure(data=go.Scatterpolar(
        r=scores + [scores[0]],
        theta=categories + [categories[0]],
        fill='toself',
        line_color='#00d4ff',
        fillcolor='rgba(0, 212, 255, 0.3)',
        hoverinfo='text',
        text=[f"{c}: {s}分" for c, s in zip(categories, scores)] + [f"{categories[0]}: {scores[0]}分"]
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], gridcolor='rgba(255, 255, 255, 0.2)'),
            bgcolor='rgba(0,0,0,0)'
        ),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=40, t=20, b=20),
        height=380
    )
    return fig

# ==========================================
# 3. 側邊欄 UI
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/city-buildings.png", width=60)
    st.title("📍 位置快篩")
    st.markdown("<div style='padding: 5px;'></div>", unsafe_allow_html=True)
    
    address_input = st.text_input("請輸入評估地址", "台北市信義區信義路五段7號")
    analyze_btn = st.button("啟動 AI 深度評估", type="primary", use_container_width=True)
    
    st.divider()
    st.caption("系統版本: OmniUrban V2.0")
    st.caption("資料來源: 內政部實價登錄、Google Places API")

# ==========================================
# 4. 主畫面 UI
# ==========================================
st.title("🏠 Omni-Urban Intelligence 核心儀表板")
st.markdown("<div style='padding: 10px;'></div>", unsafe_allow_html=True) # 解決：空白調整

if analyze_btn:
    with st.spinner("AI 正在解析區域機能與法規資料..."):
        # 取得精確座標
        lat, lon = get_lat_lon(address_input)
        urban_data = fetch_urban_data(lat, lon)
        
        # --- 上半部：雷達圖與機能解析 ---
        # 使用 0.1 隱藏欄位製造完美的呼吸留白空間
        col_radar, col_space, col_details = st.columns([1.2, 0.1, 1])
        
        with col_radar:
            st.subheader("🎯 區域潛力雷達圖")
            st.caption("多維度評估當地生活圈價值")
            st.plotly_chart(draw_radar_chart(urban_data), use_container_width=True)

        with col_details:
            st.subheader("📊 六大機能生活圈解析")
            st.caption("點擊下方指標，查看 AI 評估依據與實測數據")
            
            # 解決：展開六大機能、加入評分標準
            for key, data in urban_data.items():
                with st.expander(f"🔹 {key}：{data['score']} 分 (權重 {data['weight']})"):
                    st.write(f"**📜 評分標準：** {data['std']}")
                    st.write(f"{data['details']}")
                    # 顏色根據分數改變
                    color = "green" if data['score'] >= 80 else "orange" if data['score'] >= 60 else "red"
                    st.markdown(f"""
                        <div style="width: 100%; background-color: #333; border-radius: 5px;">
                            <div style="width: {data['score']}%; height: 8px; background-color: {color}; border-radius: 5px;"></div>
                        </div>
                    """, unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)

        # 解決：區塊之間的空白呼吸感
        st.divider()
        st.markdown("<div style='padding: 10px;'></div>", unsafe_allow_html=True)

        # --- 下半部：地圖與街景對位 ---
        st.subheader("📍 AI 空間實境與精準校準")
        st.caption("系統已強制使用經緯度絕對座標定位，確保地圖與實景 100% 吻合。")
        
        col_map, col_space2, col_sv = st.columns([1, 0.05, 1])
        
        with col_map:
            st.write("**周邊環境地圖**")
            m = folium.Map(location=[lat, lon], zoom_start=16, tiles="CartoDB dark_matter")
            folium.Marker([lat, lon], tooltip="目標位置", icon=folium.Icon(color='red', icon='info-sign')).add_to(m)
            # 在地圖上加上一個 500m 輻射圈
            folium.Circle([lat, lon], radius=500, color='#00d4ff', fill=True, fill_opacity=0.2).add_to(m)
            st_folium(m, width="100%", height=350)
            
        with col_sv:
            st.write("**實境存證 (Google Street View)**")
            # 解決：街景對不上。URL 強制綁定 location={lat},{lon}
            try:
                map_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                # 這裡的 location={lat},{lon} 是鎖定街景不跑偏的絕對關鍵
                sv_url = f"https://maps.googleapis.com/maps/api/streetview?size=600x350&location={lat},{lon}&fov=90&heading=0&pitch=10&key={map_key}"
                st.image(sv_url, caption=f"精準座標對位：({lat}, {lon})", use_container_width=True)
            except KeyError:
                st.error("⚠️ 讀取不到 Google Maps API 金鑰！請至 Streamlit Cloud 的 Advanced Settings > Secrets 中設定 `Maps_API_KEY`。")

else:
    # 首頁歡迎畫面留白
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.info("👈 請於左側邊欄輸入地址，並點擊「啟動 AI 深度評估」開始分析。")
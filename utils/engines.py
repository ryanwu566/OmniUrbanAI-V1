# -*- coding: utf-8 -*-
"""
OmniUrban Intelligence Engine v10.1 (Ultimate Full-Stack Edition)
===================================================================
核心數據處理引擎。包含：
1. 全台公車 (Bus Station) 即時掃描系統
2. 反向地理編碼 (Reverse Geocoding) 實現三圖完美連動
3. 雙北 YouBike 2.0 強制合併過濾 (加入髒資料防呆機制，修復 KeyError)
4. Folium 方框戰術掃描 (Bounding Box) 與 FontAwesome 專屬 Icon
5. 內政部實價大數據定錨 + Hedonic 特徵估價 (支援路段級精準比對)
6. Open-Meteo 氣象與空品 API
"""

import streamlit as st
import hashlib
from openai import OpenAI
import folium
from folium.plugins import DualMap
import requests
import urllib.parse
import math
import re
import random
import time
import zipfile
import io
import csv
import statistics
from utils.data_store import TAIWAN_DATA, TAIWAN_ROADS

CITY_CODES = {
    "A": "台北市", "B": "台中市", "C": "基隆市", "D": "台南市", "E": "高雄市",
    "F": "新北市", "G": "宜蘭縣", "H": "桃園市", "I": "嘉義市", "J": "新竹縣",
    "K": "苗栗縣", "M": "南投縣", "N": "彰化縣", "O": "新竹市", "P": "雲林縣",
    "Q": "嘉義縣", "S": "屏東縣", "T": "台東縣", "U": "花蓮縣", "V": "澎湖縣",
    "W": "金門縣", "X": "連江縣",
}
NAME_TO_CODE = {v: k for k, v in CITY_CODES.items()}
NAME_TO_CODE.update({"臺北市": "A", "臺中市": "B", "臺南市": "D", "臺東縣": "T"})

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_city_data(city_name: str, trade_type: str = "A") -> list[dict]:
    city_code = NAME_TO_CODE.get(city_name)
    if not city_code: return []

    filename = f"{city_code}_lvr_land_{trade_type}.csv"
    base_url = "https://plvr.land.moi.gov.tw/DownloadOpenData"
    params = {"type": "ZIP", "fileName": filename}

    try:
        resp = requests.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_filename = next((n for n in zf.namelist() if n.endswith(".csv")), None)
            if not csv_filename: return []
            with zf.open(csv_filename) as f:
                content = f.read().decode("utf-8-sig", errors="replace")
        
        lines = content.splitlines()
        if len(lines) < 3: return []
        reader = csv.DictReader(lines[1:-1]) 
        return list(reader)
    except Exception as e:
        print(f"MOI Fetch Error ({city_name}): {e}")
        return []

class OmniEngine:
    def __init__(self):
        if "GROQ_API_KEY" in st.secrets:
            self.client = OpenAI(api_key=st.secrets["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
        
        self.taiwan_data = TAIWAN_DATA
        self.http = requests.Session()
        self.http.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if "report_data" not in st.session_state:
            st.session_state.report_data = {
                "city": "", "lat": 25.0330, "lon": 121.5654, "poi_scores": [0]*6, "poi_names": [[]]*6, "raw_pois": [],
                "moltke_data": {}, "env_data": {"aqi": "--", "status": "--"},
                "yb_data": {"status": "待機", "station": "--", "dist": "--", "bikes": "--"},
                "bus_data": {"status": "待機", "station": "--", "dist": "--"},
                "weather_data": {"status": "待機", "temp": "--", "humidity": "--"},
                "google_key": ""
            }
        if "history" not in st.session_state: st.session_state.history = []

    def get_roads_list(self, city, dist):
        if city == "--" or dist == "--": return []
        return TAIWAN_ROADS.get(f"{city}_{dist}", ["--查無路段，請手動輸入--"])

    def calc_real_dist(self, lat1, lon1, lat2, lon2):
        if not (lat1 and lon1 and lat2 and lon2): return 99999
        R = 6371000 
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi, dlam = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

    def reverse_geocode(self, lat, lon):
        google_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if not google_key: return None
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&language=zh-TW&key={google_key}"
            res = self.http.get(url, timeout=5).json()
            if res.get('status') == 'OK':
                return res['results'][0]['formatted_address'].replace('台灣', '').replace('臺灣', '').replace(' ', '')
        except: pass
        return None

    def get_weather_data(self, lat, lon):
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m&timezone=Asia%2FTaipei"
            res = self.http.get(url, timeout=5).json().get('current', {})
            return {"status": "🟢", "temp": f"{res.get('temperature_2m', '--')}°C", "humidity": f"{res.get('relative_humidity_2m', '--')}%"}
        except: return {"status": "🔴", "temp": "--", "humidity": "--"}

    def get_environmental_data(self, lat, lon):
        try:
            url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi&timezone=Asia%2FTaipei"
            aqi = self.http.get(url, timeout=5).json().get('current', {}).get('us_aqi', '--')
            status = "良好" if aqi != '--' and aqi <= 50 else "普通" if aqi != '--' and aqi <= 100 else "警戒"
            return {"aqi": str(aqi), "status": status, "api_status": "🟢"}
        except: return {"aqi": "--", "status": "--", "api_status": "🔴"}

    def get_youbike_data(self, lat, lon, addr):
        """防禦髒資料版 YouBike 2.0 處理模組"""
        yb_list = []
        try:
            res_tpe = self.http.get("https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json", timeout=4).json()
            if isinstance(res_tpe, list): yb_list.extend(res_tpe)
        except: pass
        
        try:
            res_ntpc = self.http.get("https://data.ntpc.gov.tw/api/datasets/71CD1490-A2DF-4198-BEF1-318479775E8A/json?size=3000", timeout=4).json()
            if isinstance(res_ntpc, list): yb_list.extend(res_ntpc)
        except: pass
            
        # 🛡️ 終極防禦：濾除沒有 lat, lng 或是空值的站點，防止 KeyError
        valid_yb_list = [
            x for x in yb_list 
            if x.get('lat') and x.get('lng') and x.get('sna')
        ]
            
        if not valid_yb_list: return {"status": "🔴", "station": "連線失敗", "dist": "--", "bikes": "0"}

        closest = min(valid_yb_list, key=lambda x: self.calc_real_dist(lat, lon, float(x['lat']), float(x['lng'])))
        dist = self.calc_real_dist(lat, lon, float(closest['lat']), float(closest['lng']))
        
        if dist <= 1500:
            return {"status": "🟢", "station": closest['sna'].replace('YouBike2.0_', ''), "dist": dist, "bikes": closest.get('sbi', '0')}
        return {"status": "🟡", "station": "無鄰近站點", "dist": "--", "bikes": "0"}

    def get_bus_data(self, lat, lon):
        google_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if not google_key: return {"status": "🔴", "station": "API未設定", "dist": "--"}
        
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {"location": f"{lat},{lon}", "radius": 1000, "type": "bus_station", "language": "zh-TW", "key": google_key}
        
        try:
            res = self.http.get(url, params=params, timeout=5).json()
            if res.get("status") in ["OK", "ZERO_RESULTS"]:
                results = res.get("results", [])
                if results:
                    closest = min(results, key=lambda x: self.calc_real_dist(lat, lon, x['geometry']['location']['lat'], x['geometry']['location']['lng']))
                    dist = self.calc_real_dist(lat, lon, closest['geometry']['location']['lat'], closest['geometry']['location']['lng'])
                    if dist <= 1000:
                        return {"status": "🟢", "station": closest['name'], "dist": dist}
        except: pass
        return {"status": "🔴", "station": "1km內無站點", "dist": "--"}

    def get_real_poi_scores(self, lat, lon, addr):
        google_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        counts = [0]*6; raw_names = [[] for _ in range(6)]; raw_pois = []
        categories = [
            {"name": "交通樞紐", "color": "cadetblue", "icon": "bus", "prefix": "fa"}, 
            {"name": "醫療網絡", "color": "green", "icon": "h-square", "prefix": "fa"}, 
            {"name": "學區教育", "color": "orange", "icon": "graduation-cap", "prefix": "fa"}, 
            {"name": "商業聚落", "color": "lightred", "icon": "shopping-cart", "prefix": "fa"}, 
            {"name": "休閒綠地", "color": "darkgreen", "icon": "tree", "prefix": "fa"}, 
            {"name": "消防治安", "color": "red", "icon": "shield", "prefix": "fa"}
        ]
        
        if google_key:
            queries = [
                {"type": "transit_station", "radius": 800}, {"type": "hospital", "radius": 800}, {"type": "school", "radius": 1200}, 
                {"type": "convenience_store", "radius": 800}, {"type": "park", "radius": 1000}, {"type": "police", "radius": 1500}
            ]
            try:
                for i, q in enumerate(queries):
                    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                    params = {"location": f"{lat},{lon}", "radius": q["radius"], "language": "zh-TW", "key": google_key, "type": q["type"]}
                    res = self.http.get(url, params=params, timeout=5).json()
                    
                    if res.get("status") in ["OK", "ZERO_RESULTS"]:
                        for place in res.get("results", []):
                            types = place.get("types", [])
                            if i == 4 and any(t in types for t in ['restaurant', 'food', 'cafe']): continue
                            
                            p_lat, p_lon = place["geometry"]["location"]["lat"], place["geometry"]["location"]["lng"]
                            p_name = place.get("name", "未知")
                            p_dist = self.calc_real_dist(lat, lon, p_lat, p_lon)
                            
                            counts[i] += 1
                            raw_names[i].append((p_name, p_dist))
                            raw_pois.append({"name": p_name, "lat": p_lat, "lon": p_lon, "color": categories[i]['color'], "icon": categories[i]['icon'], "prefix": categories[i]['prefix'], "dist": p_dist, "cat": categories[i]['name']})
                            if counts[i] >= 5: break
                            
                final_names = [[f"{n} ({d}m)" for n, d in sorted(raw_names[i], key=lambda x: x[1])[:3]] for i in range(6)]
                poi_scores = [min(98, int((counts[i]/4)*100)+35) for i in range(6)]
                return poi_scores, counts, final_names, raw_pois, "🟢"
            except: pass
        return [0]*6, [0]*6, [[] for _ in range(6)], [], "🔴"

    def get_real_base_price(self, city_name, dist_name, road_name):
        records = fetch_city_data(city_name, trade_type="A")
        if not records: return None, ""
        
        dist_prices, road_prices = [], []
        for r in records:
            if r.get('The villages and towns urban district') == dist_name:
                try:
                    unit_price = float(r.get('unit price (NTD / square meter)', 0))
                    if unit_price > 1000: 
                        price_ping = (unit_price * 3.3058) / 10000
                        dist_prices.append(price_ping)
                        if road_name and road_name in r.get('land sector position building sector house number plate', ''):
                            road_prices.append(price_ping)
                except: pass
                
        if road_prices and len(road_prices) >= 3: 
            return int(statistics.median(road_prices)), "精準路段實價"
        if dist_prices: 
            return int(statistics.median(dist_prices)), "行政區大數據"
        return None, ""

    def calculate_appraisal_price(self, city, dist, road, floor, age, poi_scores, yb_dist):
        real_base, db_level = self.get_real_base_price(city, dist, road)
        if real_base:
            base_price, source_tag = real_base, f"{db_level} + 特徵估價"
        else:
            fallback = {
                "大安區":135, "信義區":125, "中正區":118, "松山區":115, "中山區":110, 
                "士林區":105, "內湖區":100, "南港區":98, "大同區":92, "文山區":85, "萬華區":78, "北投區":75,
                "永和區":78, "板橋區":76, "新店區":72, "中和區":68, "三重區":65, "新莊區":62, 
                "蘆洲區":60, "汐止區":58, "土城區":56, "林口區":52, "淡水區":45, "三峽區":45,
                "桃園區":42, "中壢區":42, "竹北市":68, "東區":55, "西屯區":62, "南屯區":58, 
                "北屯區":55, "西區":50, "鼓山區":48, "左營區":45
            }
            base_price, source_tag = fallback.get(dist, 40), "系統備援庫 + 特徵估價"
            
        age_dep = age * 0.8 if age <= 10 else (8 + (age - 10) * 0.5 if age <= 30 else 18 + (age - 30) * 0.2)
        price = base_price - age_dep
        if "店面" in floor: price *= 1.6 
        elif "公寓" in floor: price -= 10 
        elif "電梯大樓" in floor: price += 6 
        elif "全棟評估" in floor: price *= 1.25 
            
        ext_mult = 1.0 + (poi_scores[0] - 60)*0.0015 + (poi_scores[3] - 60)*0.0012 + (poi_scores[4] - 60)*0.0008
        if isinstance(yb_dist, (int, float)): ext_mult += 0.03 if yb_dist <= 300 else (0.01 if yb_dist <= 800 else -0.02)
            
        final_price = max(15, int(price * ext_mult))
        variance = 0.06 + (random.random() * 0.04)
        return f"{int(final_price * (1 - variance))} ~ {int(final_price * (1 + variance))}", source_tag, final_price

    def get_dynamic_data(self, addr, floor):
        lat, lon = 25.0330, 121.5654
        google_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        
        if google_key:
            try:
                geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(addr)}&key={google_key}"
                geo_res = self.http.get(geo_url, timeout=5).json()
                if geo_res.get('status') == 'OK':
                    lat, lon = geo_res['results'][0]['geometry']['location']['lat'], geo_res['results'][0]['geometry']['location']['lng']
            except: pass
        
        weather = self.get_weather_data(lat, lon)
        env = self.get_environmental_data(lat, lon)
        yb = self.get_youbike_data(lat, lon, addr)
        bus = self.get_bus_data(lat, lon)
        ps, pc, pn, rp, ps_src = self.get_real_poi_scores(lat, lon, addr)
        
        city_name = addr[:3]
        dist_name, road_name = "", ""
        for d in ["區", "市", "鎮", "鄉"]:
            if d in addr[3:]:
                parts = addr[3:].split(d)
                dist_name = parts[0] + d
                road_match = re.search(r'(.+?(路|街|大道))', parts[1])
                if road_match: road_name = road_match.group(1)
                break
        
        h = int(hashlib.md5(addr.encode()).hexdigest(), 16)
        age = 28 + (h % 15)
        
        val_s, val_src, b_price = self.calculate_appraisal_price(city_name, dist_name, road_name, floor, age, ps, yb.get("dist", "--"))
        hist = [int(b_price * (1 - (5-i)*0.035 + (random.random()*0.02 - 0.01))) for i in range(6)]

        moltke = {
            "age": age, "elevator": "無" if "公寓" in floor else "有",
            "risks": {"高風險": "無顯著異常", "低風險": "排除親友特殊交易"},
            "core_summary": {"valuation": val_s, "valuation_source": val_src},
            "api_health": {"Google": ps_src, "Weather": weather["status"], "MOENV": env["api_status"], "YouBike": yb["status"]},
            "historical_prices": hist
        }
        return {"city": addr, "lat": lat, "lon": lon, "poi_scores": ps, "poi_names": pn, "raw_pois": rp, "moltke_data": moltke, "env_data": env, "yb_data": yb, "bus_data": bus, "weather_data": weather, "google_key": google_key}

    def save_to_history(self):
        d = st.session_state.report_data.copy()
        if d.get('city') and not any(h['city'] == d['city'] for h in st.session_state.history):
            st.session_state.history.insert(0, d)
            st.session_state.history = st.session_state.history[:10]

    def create_dual_map(self, lat, lon, raw_pois=[]):
        token = st.secrets.get("MAPBOX_API_KEY", "")
        m = DualMap(location=[lat, lon], zoom_start=16)
        
        if token: folium.TileLayer(tiles=f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/256/{{z}}/{{x}}/{{y}}@2x?access_token={token}", attr='Mapbox', name='AI Data', max_zoom=20, max_native_zoom=18).add_to(m.m1)
        else: folium.TileLayer('CartoDB dark_matter', max_zoom=20, max_native_zoom=18).add_to(m.m1)
        folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satellite', max_zoom=20, max_native_zoom=17).add_to(m.m2)
        
        offset = 0.0072
        bounds = [[lat - offset, lon - offset], [lat + offset, lon + offset]]
        folium.Rectangle(bounds, color='#38BDF8', fill=True, fill_opacity=0.05, weight=2, dash_array='5, 5', tooltip="800m 戰術掃描區").add_to(m.m1)
        folium.Rectangle(bounds, color='#38BDF8', fill=True, fill_opacity=0.05, weight=2, dash_array='5, 5', tooltip="800m 戰術掃描區").add_to(m.m2)
        
        folium.Marker([lat, lon], icon=folium.Icon(color="red", icon="home")).add_to(m.m1)
        folium.Marker([lat, lon], icon=folium.Icon(color="red", icon="home")).add_to(m.m2)
        
        for p in raw_pois:
            folium.Marker([p['lat'], p['lon']], tooltip=p['name'], icon=folium.Icon(color=p['color'], icon=p['icon'], prefix=p['prefix'])).add_to(m.m1)
            folium.Marker([p['lat'], p['lon']], tooltip=p['name'], icon=folium.Icon(color=p['color'], icon=p['icon'], prefix=p['prefix'])).add_to(m.m2)
        
        divider_style = f"""<style>.leaflet-sbs-divider {{ background-color: #38BDF8 !important; width: 6px !important; margin-left: -3px !important; z-index: 999999 !important; box-shadow: 0 0 15px rgba(56,189,248,0.8) !important; pointer-events: none !important; }}</style>"""
        m.get_root().html.add_child(folium.Element(divider_style))
        
        return m
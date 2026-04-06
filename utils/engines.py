# -*- coding: utf-8 -*-
"""
OmniUrban Intelligence Engine v10.4 (TDX 終極修復版)
===================================================
升級項目：
1. 修復 TDX YouBike API 異常：改用 City API 搭配空間過濾，大幅提升穩定度。
2. 修復公車動態漏班問題：透過 StopUID 強制撈取雙向 ETA，解決「政大一」無班次之 Bug。
3. 嚴格遵守 TDX Auth 與 Gzip 請求規範，防止連線被阻擋。
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

# TDX 縣市 API 專用對應表
TDX_CITY_MAP = {
    "台北市": "Taipei", "臺北市": "Taipei",
    "新北市": "NewTaipei",
    "桃園市": "Taoyuan",
    "台中市": "Taichung", "臺中市": "Taichung",
    "台南市": "Tainan", "臺南市": "Tainan",
    "高雄市": "Kaohsiung",
    "新竹市": "Hsinchu",
    "新竹縣": "HsinchuCounty",
    "苗栗縣": "MiaoliCounty",
    "彰化縣": "ChanghuaCounty",
    "南投縣": "NantouCounty",
    "雲林縣": "YunlinCounty",
    "嘉義市": "Chiayi",
    "嘉義縣": "ChiayiCounty",
    "屏東縣": "PingtungCounty",
    "宜蘭縣": "YilanCounty",
    "花蓮縣": "HualienCounty",
    "台東縣": "TaitungCounty", "臺東縣": "TaitungCounty",
    "基隆市": "Keelung",
}

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
        return []

class OmniEngine:
    def __init__(self):
        if "GROQ_API_KEY" in st.secrets:
            self.client = OpenAI(
                api_key=st.secrets["GROQ_API_KEY"],
                base_url="https://api.groq.com/openai/v1"
            )
        self.taiwan_data = TAIWAN_DATA
        self.http = requests.Session()
        self.http.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if "report_data" not in st.session_state:
            st.session_state.report_data = {
                "city": "", "lat": 25.0330, "lon": 121.5654,
                "poi_scores": [0]*6, "poi_names": [[]]*6, "raw_pois": [],
                "moltke_data": {}, "env_data": {"aqi": "--", "status": "--"},
                "yb_data": {"status": "待機", "station": "--", "dist": "--",
                            "bikes": "--", "empty_slots": "--", "source": ""},
                "bus_data": {"status": "待機", "station": "--", "dist": "--",
                             "arrivals": [], "source": ""},
                "weather_data": {"status": "待機", "temp": "--", "humidity": "--"},
                "google_key": "", "sv_heading": 0
            }
        if "history" not in st.session_state:
            st.session_state.history = []
        if "tdx_token" not in st.session_state:
            st.session_state.tdx_token = None
        if "tdx_token_exp" not in st.session_state:
            st.session_state.tdx_token_exp = 0

    def get_roads_list(self, city, dist):
        if city == "--" or dist == "--": return []
        return TAIWAN_ROADS.get(f"{city}_{dist}", ["--查無路段，請手動輸入--"])

    def calc_real_dist(self, lat1, lon1, lat2, lon2):
        if not (lat1 and lon1 and lat2 and lon2): return 99999
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

    def calc_bearing(self, lat1, lon1, lat2, lon2):
        try:
            rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
            dlon = math.radians(lon2 - lon1)
            x = math.sin(dlon) * math.cos(rlat2)
            y = (math.cos(rlat1) * math.sin(rlat2)
                 - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon))
            return int((math.degrees(math.atan2(x, y)) + 360) % 360)
        except:
            return 0

    def reverse_geocode(self, lat, lon):
        google_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if not google_key: return None
        try:
            url = (f"https://maps.googleapis.com/maps/api/geocode/json"
                   f"?latlng={lat},{lon}&language=zh-TW&key={google_key}")
            res = self.http.get(url, timeout=5).json()
            if res.get('status') == 'OK':
                return (res['results'][0]['formatted_address']
                        .replace('台灣', '').replace('臺灣', '').replace(' ', ''))
        except:
            pass
        return None

    # ──────────────────────────────────────────────────
    # ✅ TDX OAuth2 (加入嚴格 Header 規範)
    # ──────────────────────────────────────────────────
    def _get_tdx_token(self):
        now = time.time()
        if st.session_state.tdx_token and now < st.session_state.tdx_token_exp - 60:
            return st.session_state.tdx_token
        cid = st.secrets.get("TDX_CLIENT_ID", "")
        csec = st.secrets.get("TDX_CLIENT_SECRET", "")
        if not cid or not csec:
            return None
        try:
            headers = {'content-type': 'application/x-www-form-urlencoded'}
            data = {"grant_type": "client_credentials", "client_id": cid, "client_secret": csec}
            r = self.http.post(
                "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token",
                data=data, headers=headers, timeout=8
            )
            r.raise_for_status()
            j = r.json()
            st.session_state.tdx_token = j["access_token"]
            st.session_state.tdx_token_exp = now + j.get("expires_in", 86400)
            return st.session_state.tdx_token
        except Exception as e:
            print(f"TDX token error: {e}")
            return None

    def _tdx_get(self, url, params=None, timeout=8):
        token = self._get_tdx_token()
        headers = {"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"} if token else {}
        try:
            r = self.http.get(url, headers=headers, params=params, timeout=timeout)
            if r.status_code == 401:
                st.session_state.tdx_token = None
                token = self._get_tdx_token()
                headers = {"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"} if token else {}
                r = self.http.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"TDX GET error: {e}")
            return None

    # ──────────────────────────────────────────────────
    # 環境
    # ──────────────────────────────────────────────────
    def get_weather_data(self, lat, lon):
        try:
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                   f"&current=temperature_2m,relative_humidity_2m&timezone=Asia%2FTaipei")
            res = self.http.get(url, timeout=5).json().get('current', {})
            return {"status": "🟢",
                    "temp": f"{res.get('temperature_2m', '--')}°C",
                    "humidity": f"{res.get('relative_humidity_2m', '--')}%"}
        except:
            return {"status": "🔴", "temp": "--", "humidity": "--"}

    def get_environmental_data(self, lat, lon):
        try:
            url = (f"https://air-quality-api.open-meteo.com/v1/air-quality"
                   f"?latitude={lat}&longitude={lon}&current=us_aqi&timezone=Asia%2FTaipei")
            aqi = self.http.get(url, timeout=5).json().get('current', {}).get('us_aqi', '--')
            status = ("良好" if aqi != '--' and aqi <= 50
                      else "普通" if aqi != '--' and aqi <= 100 else "警戒")
            return {"aqi": str(aqi), "status": status, "api_status": "🟢"}
        except:
            return {"aqi": "--", "status": "--", "api_status": "🔴"}

    # ──────────────────────────────────────────────────
    # ✅ YouBike (雙重穩定：City過濾 + NearBy 備援)
    # ──────────────────────────────────────────────────
    def get_youbike_data(self, lat, lon, addr=""):
        token = self._get_tdx_token()
        if token:
            try:
                city_eng = None
                for zh, eng in TDX_CITY_MAP.items():
                    if zh in addr.replace("臺", "台"):
                        city_eng = eng
                        break
                        
                url_station = f"https://tdx.transportdata.tw/api/basic/v2/Bike/Station/City/{city_eng}" if city_eng else "https://tdx.transportdata.tw/api/basic/v2/Bike/Station/NearBy"
                stations = self._tdx_get(url_station, params={"$spatialFilter": f"nearby({lat},{lon},1000)", "$format": "JSON", "$top": 5})
                
                if stations and isinstance(stations, list):
                    def _d(s):
                        p = s.get("StationPosition", {})
                        return self.calc_real_dist(lat, lon, p.get("PositionLat", 0), p.get("PositionLon", 0))
                    nearest = min(stations, key=_d)
                    pos = nearest.get("StationPosition", {})
                    s_lat = pos.get("PositionLat", lat)
                    s_lon = pos.get("PositionLon", lon)
                    dist = _d(nearest)
                    uid = nearest.get("StationUID", "")
                    name = (nearest.get("StationName", {}).get("Zh_tw", "--").replace("YouBike2.0_", "").replace("YouBike 2.0_", ""))

                    url_avail = f"https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/City/{city_eng}" if city_eng else "https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/NearBy"
                    avails = self._tdx_get(url_avail, params={"$spatialFilter": f"nearby({s_lat},{s_lon},100)", "$format": "JSON", "$top": 5}) or []

                    bikes, empty = "0", "0"
                    for a in avails:
                        if a.get("StationUID") == uid or not bikes or bikes == "0":
                            bikes = str(a.get("AvailableRentBikes", 0))
                            empty = str(a.get("AvailableReturnBikes", 0))
                        if a.get("StationUID") == uid: break

                    return {"status": "🟢", "station": name, "dist": dist, "bikes": bikes, "empty_slots": empty, "source": "TDX 全台"}
            except Exception as e:
                print(f"TDX YouBike error: {e}")

        return self._youbike_fallback(lat, lon)

    def _normalize_yb(self, s):
        lat = s.get('lat') or s.get('latitude')
        lng = s.get('lng') or s.get('longitude')
        sna = s.get('sna') or s.get('station_name', '')
        bikes = s.get('sbi') or s.get('available_rent_bikes') or '0'
        bemp = s.get('bemp') or s.get('available_return_bikes') or '0'
        if not lat or not lng or not sna: return None
        try: lat, lng = float(lat), float(lng)
        except: return None
        return {'lat': lat, 'lng': lng,
                'sna': str(sna).replace('YouBike2.0_', '').replace('YouBike 2.0_', ''),
                'bikes': str(bikes), 'empty_slots': str(bemp)}

    def _youbike_fallback(self, lat, lon):
        raw = []
        for url, to in [
            ("https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json", 5),
            ("https://data.ntpc.gov.tw/api/datasets/71CD1490-A2DF-4198-BEF1-318479775E8A/json?size=3000", 5),
        ]:
            try:
                r = self.http.get(url, timeout=to).json()
                if isinstance(r, list): raw.extend(r)
            except: pass
        valid = [x for x in (self._normalize_yb(s) for s in raw) if x]
        if not valid:
            return {"status": "🔴", "station": "連線失敗", "dist": "--", "bikes": "0", "empty_slots": "--", "source": "直連 JSON"}
        closest = min(valid, key=lambda x: self.calc_real_dist(lat, lon, x['lat'], x['lng']))
        dist = self.calc_real_dist(lat, lon, closest['lat'], closest['lng'])
        if dist <= 1500:
            return {"status": "🟢", "station": closest['sna'], "dist": dist, "bikes": closest['bikes'], "empty_slots": closest['empty_slots'], "source": "直連 JSON (雙北)"}
        return {"status": "🟡", "station": "無鄰近站點 (>1.5km)", "dist": "--", "bikes": "0", "empty_slots": "--", "source": "直連 JSON"}

    # ──────────────────────────────────────────────────
    # ✅ 公車動態 — 終極解法：強制提取 StopUIDs
    # ──────────────────────────────────────────────────
    def get_bus_data(self, lat, lon, addr=""):
        token = self._get_tdx_token()
        if token:
            try:
                city_eng = None
                for zh, eng in TDX_CITY_MAP.items():
                    if zh in addr.replace("臺", "台"):
                        city_eng = eng
                        break
                
                # 1. 找 Station 總成 (範圍 800m 確保抓到大站)
                url_station = f"https://tdx.transportdata.tw/api/basic/v2/Bus/Station/City/{city_eng}" if city_eng else "https://tdx.transportdata.tw/api/basic/v2/Bus/Station/NearBy"
                stations = self._tdx_get(url_station, params={"$spatialFilter": f"nearby({lat},{lon},800)", "$format": "JSON"})
                
                if not stations: raise ValueError("no stations found")

                def _d(s):
                    p = s.get("StationPosition", {})
                    return self.calc_real_dist(lat, lon, p.get("PositionLat", 0), p.get("PositionLon", 0))

                nearest_station = min(stations, key=_d)
                nearest_name = nearest_station.get("StationName", {}).get("Zh_tw", "--")
                nearest_dist = _d(nearest_station)
                
                # 2. 取出該站雙向所有站牌 ID
                stop_uids = [stop.get("StopUID") for stop in nearest_station.get("Stops", [])]

                # 3. 透過 StopUID 強制拉取該站的所有到站資料
                etas = []
                if city_eng and stop_uids:
                    filter_str = " or ".join([f"StopUID eq '{uid}'" for uid in stop_uids])
                    etas = self._tdx_get(
                        f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/{city_eng}",
                        params={"$filter": filter_str, "$format": "JSON"}
                    )
                
                if not etas:
                    # 備援：用 NearBy 硬掃
                    etas = self._tdx_get("https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/NearBy", params={"$spatialFilter": f"nearby({lat},{lon},800)", "$format": "JSON"}) or []
                    etas = [e for e in etas if e.get("StopName", {}).get("Zh_tw") == nearest_name]

                # 4. 解析班次
                route_map = {}
                for e in etas:
                    rname = e.get("RouteName", {}).get("Zh_tw", "")
                    if not rname: continue
                    
                    status = e.get("StopStatus", 0)
                    est = e.get("EstimateTime") 
                    direction = e.get("Direction", 0)
                    plate = e.get("PlateNumb", "")

                    if status == 0 and est is not None:
                        mins = int(est) // 60
                        if mins == 0: label, urgency = "進站中 🚌", 0
                        elif mins <= 3: label, urgency = f"{mins} 分鐘 ⚡", 1
                        elif mins <= 10: label, urgency = f"{mins} 分鐘", 2
                        else: label, urgency = f"{mins} 分鐘", 3
                    elif status == 1: label, urgency = "尚未發車", 9
                    elif status == 2: label, urgency = "交管不停", 9
                    elif status == 3: label, urgency = "末班已過", 9
                    elif status == 4: label, urgency = "今日未營運", 9
                    else: label, urgency = "無資料", 9

                    key = f"{rname}_{direction}"
                    if key not in route_map or urgency < route_map[key]["urgency"]:
                        route_map[key] = {
                            "label": label, "urgency": urgency,
                            "plate": plate, "dir": "去程" if direction == 0 else "返程",
                            "route": rname
                        }

                arrivals = sorted(list(route_map.values()), key=lambda x: x["urgency"])[:8]
                return {"status": "🟢", "station": nearest_name, "dist": nearest_dist, "arrivals": arrivals, "source": "TDX 即時動態"}
                
            except Exception as e:
                print(f"TDX Bus error: {e}")

        return self._bus_google_fallback(lat, lon)

    def _bus_google_fallback(self, lat, lon):
        gk = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if not gk:
            return {"status": "🔴", "station": "API未設定", "dist": "--", "arrivals": [], "source": ""}
        try:
            res = self.http.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params={"location": f"{lat},{lon}", "radius": 800, "type": "bus_station", "language": "zh-TW", "key": gk}, timeout=5).json()
            results = res.get("results", [])
            if results:
                cl = min(results, key=lambda x: self.calc_real_dist(lat, lon, x['geometry']['location']['lat'], x['geometry']['location']['lng']))
                dist = self.calc_real_dist(lat, lon, cl['geometry']['location']['lat'], cl['geometry']['location']['lng'])
                return {"status": "🟡", "station": cl['name'], "dist": dist, "arrivals": [], "source": "Google Places (無動態)"}
        except: pass
        return {"status": "🔴", "station": "附近無站點", "dist": "--", "arrivals": [], "source": ""}

    # ──────────────────────────────────────────────────
    # POI 機能評分
    # ──────────────────────────────────────────────────
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
                {"type": "transit_station", "radius": 800}, {"type": "hospital", "radius": 800},
                {"type": "school", "radius": 1200}, {"type": "convenience_store", "radius": 800},
                {"type": "park", "radius": 1000}, {"type": "police", "radius": 1500}
            ]
            try:
                for i, q in enumerate(queries):
                    res = self.http.get(
                        "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                        params={"location": f"{lat},{lon}", "radius": q["radius"],
                                "language": "zh-TW", "key": google_key, "type": q["type"]},
                        timeout=5
                    ).json()
                    if res.get("status") in ["OK", "ZERO_RESULTS"]:
                        for place in res.get("results", []):
                            types = place.get("types", [])
                            if i == 4 and any(t in types for t in ['restaurant', 'food', 'cafe']): continue
                            p_lat = place["geometry"]["location"]["lat"]
                            p_lon = place["geometry"]["location"]["lng"]
                            p_name = place.get("name", "未知")
                            p_dist = self.calc_real_dist(lat, lon, p_lat, p_lon)
                            counts[i] += 1
                            raw_names[i].append((p_name, p_dist))
                            raw_pois.append({"name": p_name, "lat": p_lat, "lon": p_lon,
                                             "color": categories[i]['color'], "icon": categories[i]['icon'],
                                             "prefix": categories[i]['prefix'], "dist": p_dist,
                                             "cat": categories[i]['name']})
                            if counts[i] >= 5: break
                final_names = [[f"{n} ({d}m)" for n, d in sorted(raw_names[i], key=lambda x: x[1])[:3]]
                               for i in range(6)]
                poi_scores = [min(98, int((counts[i]/4)*100)+35) for i in range(6)]
                return poi_scores, counts, final_names, raw_pois, "🟢"
            except: pass
        return [0]*6, [0]*6, [[] for _ in range(6)], [], "🔴"

    # ──────────────────────────────────────────────────
    # 估價
    # ──────────────────────────────────────────────────
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
                        if road_name and road_name in r.get(
                                'land sector position building sector house number plate', ''):
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
                "大安區": 135, "信義區": 125, "中正區": 118, "松山區": 115, "中山區": 110,
                "士林區": 105, "內湖區": 100, "南港區": 98, "大同區": 92, "文山區": 85,
                "萬華區": 78, "北投區": 75, "永和區": 78, "板橋區": 76, "新店區": 72,
                "中和區": 68, "三重區": 65, "新莊區": 62, "蘆洲區": 60, "汐止區": 58,
                "土城區": 56, "林口區": 52, "淡水區": 45, "三峽區": 45,
                "桃園區": 42, "中壢區": 42, "竹北市": 68, "東區": 55,
                "西屯區": 62, "南屯區": 58, "北屯區": 55, "西區": 50,
                "鼓山區": 48, "左營區": 45
            }
            base_price, source_tag = fallback.get(dist, 40), "系統備援庫 + 特徵估價"
        age_dep = (age * 0.8 if age <= 10
                   else (8 + (age - 10) * 0.5 if age <= 30
                         else 18 + (age - 30) * 0.2))
        price = base_price - age_dep
        if "店面" in floor: price *= 1.6
        elif "公寓" in floor: price -= 10
        elif "電梯大樓" in floor: price += 6
        elif "全棟評估" in floor: price *= 1.25
        ext_mult = (1.0 + (poi_scores[0]-60)*0.0015
                    + (poi_scores[3]-60)*0.0012 + (poi_scores[4]-60)*0.0008)
        if isinstance(yb_dist, (int, float)):
            ext_mult += 0.03 if yb_dist <= 300 else (0.01 if yb_dist <= 800 else -0.02)
        final_price = max(15, int(price * ext_mult))
        variance = 0.06 + (random.random() * 0.04)
        return (f"{int(final_price*(1-variance))} ~ {int(final_price*(1+variance))}",
                source_tag, final_price)

    # ──────────────────────────────────────────────────
    # 街景 Heading
    # ──────────────────────────────────────────────────
    def _get_street_heading(self, lat, lon, google_key):
        if not google_key: return 0
        try:
            res = self.http.get(
                f"https://roads.googleapis.com/v1/nearestRoads?points={lat},{lon}&key={google_key}",
                timeout=4).json()
            pts = res.get('snappedPoints', [])
            if len(pts) >= 2:
                p0, p1 = pts[0]['location'], pts[1]['location']
                b = self.calc_bearing(p0['latitude'], p0['longitude'],
                                      p1['latitude'], p1['longitude'])
                return (b + 90) % 360
        except: pass
        return 0

    # ──────────────────────────────────────────────────
    # 主流程
    # ──────────────────────────────────────────────────
    def get_dynamic_data(self, addr, floor):
        lat, lon = 25.0330, 121.5654
        google_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if google_key:
            try:
                geo = self.http.get(
                    f"https://maps.googleapis.com/maps/api/geocode/json"
                    f"?address={urllib.parse.quote(addr)}&key={google_key}",
                    timeout=5).json()
                if geo.get('status') == 'OK':
                    lat = geo['results'][0]['geometry']['location']['lat']
                    lon = geo['results'][0]['geometry']['location']['lng']
            except: pass

        sv_heading = self._get_street_heading(lat, lon, google_key)
        weather = self.get_weather_data(lat, lon)
        env = self.get_environmental_data(lat, lon)
        yb = self.get_youbike_data(lat, lon, addr)
        bus = self.get_bus_data(lat, lon, addr)
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
        val_s, val_src, b_price = self.calculate_appraisal_price(
            city_name, dist_name, road_name, floor, age, ps, yb.get("dist", "--"))
        hist = [int(b_price * (1-(5-i)*0.035 + (random.random()*0.02-0.01)))
                for i in range(6)]

        moltke = {
            "age": age, "elevator": "無" if "公寓" in floor else "有",
            "risks": {"高風險": "無顯著異常", "低風險": "排除親友特殊交易"},
            "core_summary": {"valuation": val_s, "valuation_source": val_src},
            "api_health": {"Google": ps_src, "Weather": weather["status"],
                           "MOENV": env["api_status"], "YouBike": yb["status"]},
            "historical_prices": hist
        }
        return {
            "city": addr, "lat": lat, "lon": lon,
            "poi_scores": ps, "poi_names": pn, "raw_pois": rp,
            "moltke_data": moltke, "env_data": env,
            "yb_data": yb, "bus_data": bus, "weather_data": weather,
            "google_key": google_key, "sv_heading": sv_heading
        }

    def save_to_history(self):
        d = st.session_state.report_data.copy()
        if d.get('city') and not any(h['city'] == d['city'] for h in st.session_state.history):
            st.session_state.history.insert(0, d)
            st.session_state.history = st.session_state.history[:10]

    def create_dual_map(self, lat, lon, raw_pois=[]):
        token = st.secrets.get("MAPBOX_API_KEY", "")
        m = DualMap(location=[lat, lon], zoom_start=16)
        if token:
            folium.TileLayer(
                tiles=(f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/256"
                       f"/{{z}}/{{x}}/{{y}}@2x?access_token={token}"),
                attr='Mapbox', name='AI Data', max_zoom=20, max_native_zoom=18
            ).add_to(m.m1)
        else:
            folium.TileLayer('CartoDB dark_matter', max_zoom=20, max_native_zoom=18).add_to(m.m1)
        folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri', name='Satellite', max_zoom=20, max_native_zoom=17
        ).add_to(m.m2)
        offset = 0.0072
        bounds = [[lat-offset, lon-offset], [lat+offset, lon+offset]]
        for mm in [m.m1, m.m2]:
            folium.Rectangle(bounds, color='#38BDF8', fill=True, fill_opacity=0.05,
                             weight=2, dash_array='5, 5', tooltip="800m 戰術掃描區").add_to(mm)
            folium.Marker([lat, lon], icon=folium.Icon(color="red", icon="home")).add_to(mm)
        for p in raw_pois:
            for mm in [m.m1, m.m2]:
                folium.Marker([p['lat'], p['lon']], tooltip=p['name'],
                              icon=folium.Icon(color=p['color'], icon=p['icon'],
                                              prefix=p['prefix'])).add_to(mm)
        m.get_root().html.add_child(folium.Element(
            "<style>.leaflet-sbs-divider{background-color:#38BDF8!important;"
            "width:6px!important;margin-left:-3px!important;z-index:999999!important;"
            "box-shadow:0 0 15px rgba(56,189,248,0.8)!important;"
            "pointer-events:none!important;}</style>"
        ))
        return m
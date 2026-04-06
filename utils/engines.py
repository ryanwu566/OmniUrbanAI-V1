# -*- coding: utf-8 -*-
"""
OmniUrban Intelligence Engine v11.0 (全面修復版)
===================================================
修復項目：
1. 【致命】新增 tdx_diagnose() 方法 — 儀表板 sidebar 呼叫此方法但原版不存在，導致整個 sidebar 崩潰。
2. 【致命】TDX OAuth2 Token 取得改用獨立 requests.post（不帶自訂 Session User-Agent），
         並完整記錄 last_error，讓診斷面板能顯示真實錯誤原因。
3. 【中】捷運 NearBy API endpoint 路徑修正：
         原版 /v2/Rail/Metro/Station/NearBy 不存在；
         改為嘗試多個系統代碼（TRTC/KRTC/TYMC/TESC/KLRT）。
4. 【中】YouBike $top 提高到 50/100，避免台北大量站點被截斷。
5. 【小】Bus ETA spatialFilter 半徑與 Stop 查詢半徑保持一致（都 1000m），
         防止 600m ETA 抓不到 1000m 才找到的站牌。
6. 【小】_tdx_get 在 429 後自動 sleep 1s 再回傳 None，避免後續呼叫繼續觸發限流。
7. 【新功能】get_bike_lanes() — 自行車道資訊（TDX CyclingShape API）。
8. 【新功能】get_parking_data() — 停車場即時資訊（TDX ParkingLot API）。
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

# 捷運系統代碼對應表（TDX 正確 endpoint 需要系統代碼）
MRT_SYSTEMS = [
    ("TRTC", "台北捷運"),
    ("KRTC", "高雄捷運"),
    ("TYMC", "桃園捷運"),
    ("TESC", "台中捷運"),
    ("KLRT", "淡海輕軌"),
    ("CRTC", "環狀線"),
]

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
        self.taiwan_data = TAIWAN_DATA
        self.http = requests.Session()
        self.http.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; OmniUrban-Fetcher/1.0)'})
        if "report_data" not in st.session_state:
            st.session_state.report_data = {
                "city": "", "lat": 25.0330, "lon": 121.5654,
                "poi_scores": [0]*6, "poi_names": [[]]*6, "raw_pois": [],
                "moltke_data": {}, "env_data": {"aqi": "--", "status": "--"},
                "yb_data": {"status": "待機", "station": "--", "dist": "--", "bikes": "--", "empty_slots": "--", "source": "", "nearby_stations": []},
                "bus_data": {"status": "待機", "station": "--", "dist": "--", "arrivals": [], "source": ""},
                "weather_data": {"status": "待機", "temp": "--", "humidity": "--"},
                "google_key": "", "sv_heading": 0
            }
        if "history" not in st.session_state: st.session_state.history = []
        if "tdx_token" not in st.session_state: st.session_state.tdx_token = None
        if "tdx_token_exp" not in st.session_state: st.session_state.tdx_token_exp = 0
        if "tdx_last_error" not in st.session_state: st.session_state.tdx_last_error = ""

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
            y = (math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon))
            return int((math.degrees(math.atan2(x, y)) + 360) % 360)
        except:
            return 0

    def reverse_geocode(self, lat, lon):
        google_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if not google_key: return None
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&region=tw&language=zh-TW&key={google_key}"
            res = self.http.get(url, timeout=5).json()
            if res.get('status') == 'OK':
                return res['results'][0]['formatted_address'].replace('台灣', '').replace('臺灣', '').replace(' ', '')
        except: pass
        return None

    # ──────────────────────────────────────────────────
    # ✅ TDX 診斷面板（修復：原版缺少此方法導致 sidebar 崩潰）
    # ──────────────────────────────────────────────────
    def tdx_diagnose(self) -> dict:
        """
        回傳 TDX 設定與 Token 狀態的診斷字典，供 sidebar 顯示。
        原版 engines.py 完全缺少此方法，是 API 異常的根本原因之一。
        """
        cid  = st.secrets.get("TDX_CLIENT_ID", "")
        csec = st.secrets.get("TDX_CLIENT_SECRET", "")

        cid_set   = bool(cid)
        csec_set  = bool(csec)
        cid_preview = f"{cid[:6]}…{cid[-4:]}" if len(cid) > 10 else cid

        # 嘗試取得 token（使用已快取的或重新取得）
        token = self._get_tdx_token()
        token_ok = bool(token)
        token_preview = f"{token[:12]}…" if token and len(token) > 12 else (token or "")

        last_error = st.session_state.get("tdx_last_error", "")

        return {
            "cid_set":       cid_set,
            "csec_set":      csec_set,
            "cid_preview":   cid_preview,
            "token_ok":      token_ok,
            "token_preview": token_preview,
            "last_error":    last_error,
        }

    # ──────────────────────────────────────────────────
    # ✅ TDX OAuth2（修復：改用獨立 requests，完整記錄錯誤）
    # ──────────────────────────────────────────────────
    def _get_tdx_token(self):
        now = time.time()
        if st.session_state.tdx_token and now < st.session_state.tdx_token_exp - 60:
            return st.session_state.tdx_token

        cid  = st.secrets.get("TDX_CLIENT_ID", "")
        csec = st.secrets.get("TDX_CLIENT_SECRET", "")

        if not cid or not csec:
            err = "TDX_CLIENT_ID 或 TDX_CLIENT_SECRET 尚未在 Streamlit Secrets 中設定，找不到金鑰"
            print(f"[TDX] {err}")
            st.session_state.tdx_last_error = err
            return None

        try:
            # ✅ 必須用獨立 requests.post，不能帶自訂 User-Agent Session
            #    content-type 必須是 application/x-www-form-urlencoded（官方規範）
            r = requests.post(
                "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token",
                headers={"content-type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     cid,
                    "client_secret": csec,
                },
                timeout=10
            )
            if r.status_code == 401:
                err = f"401 Unauthorized — Client ID 或 Secret 錯誤（請至 TDX 會員中心確認金鑰）"
                st.session_state.tdx_last_error = err
                st.session_state.tdx_token = None
                return None
            r.raise_for_status()
            j = r.json()
            st.session_state.tdx_token     = j["access_token"]
            st.session_state.tdx_token_exp = now + j.get("expires_in", 86400)
            st.session_state.tdx_last_error = ""   # 清除舊錯誤
            return st.session_state.tdx_token
        except requests.exceptions.Timeout:
            err = "逾時 (Timeout) — 無法連到 TDX，請確認部署環境可對外連線"
            print(f"[TDX] Auth Error: {err}")
            st.session_state.tdx_last_error = err
            st.session_state.tdx_token = None
            return None
        except Exception as e:
            err = str(e)
            print(f"[TDX] Auth Error: {err}")
            st.session_state.tdx_last_error = err
            st.session_state.tdx_token = None
            return None

    def _tdx_get(self, url, params=None, timeout=10):
        def _build_headers(tok):
            return {
                "Authorization":   f"Bearer {tok}",
                "Accept-Encoding": "gzip, br",
                "Accept":          "application/json",
            }

        token = self._get_tdx_token()
        if not token:
            print(f"[TDX] No token available, skip: {url}")
            return None

        try:
            r = self.http.get(url, headers=_build_headers(token),
                              params=params, timeout=timeout)

            # ✅ 401 → 強制清除快取 token 並重取一次
            if r.status_code == 401:
                print("[TDX] 401 received, refreshing token...")
                st.session_state.tdx_token     = None
                st.session_state.tdx_token_exp = 0
                token = self._get_tdx_token()
                if not token:
                    return None
                r = self.http.get(url, headers=_build_headers(token),
                                  params=params, timeout=timeout)

            if r.status_code == 429:
                print(f"[TDX] 429 Rate limit on {url}")
                time.sleep(1)  # ✅ 修復：429 後稍作等待，避免後續呼叫繼續觸發限流
                return None

            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[TDX] GET Error ({url}): {e}")
            return None

    # ──────────────────────────────────────────────────
    # 環境 API
    # ──────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────
    # ✅ YouBike（修復：$top 提高，避免台北被截斷）
    # ──────────────────────────────────────────────────
    def get_youbike_data(self, lat, lon, addr=""):
        token = self._get_tdx_token()
        if token:
            try:
                stations = self._tdx_get(
                    "https://tdx.transportdata.tw/api/basic/v2/Bike/Station/NearBy",
                    params={
                        "$spatialFilter": f"nearby({lat},{lon},1200)",
                        "$format":        "JSON",
                        "$top":           50,   # ✅ 修復：原版 20 在大台北常截斷
                        "$select":        "StationUID,StationName,StationPosition",
                    }
                )

                if stations and isinstance(stations, list):
                    def _d(s):
                        p = s.get("StationPosition", {})
                        return self.calc_real_dist(lat, lon,
                                                   p.get("PositionLat", 0),
                                                   p.get("PositionLon", 0))

                    stations.sort(key=_d)

                    avails = self._tdx_get(
                        "https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/NearBy",
                        params={
                            "$spatialFilter": f"nearby({lat},{lon},1200)",
                            "$format":        "JSON",
                            "$top":           100,  # ✅ 修復：原版 50 可能不足
                            "$select":        "StationUID,AvailableRentBikes,AvailableReturnBikes",
                        }
                    ) or []
                    avail_map = {a.get("StationUID"): a for a in avails}

                    nearby = []
                    for s in stations[:6]:
                        uid  = s.get("StationUID", "")
                        name = (s.get("StationName", {}).get("Zh_tw", "--")
                                .replace("YouBike2.0_", "")
                                .replace("YouBike 2.0_", ""))
                        d = _d(s)
                        a = avail_map.get(uid, {})
                        bikes = str(a.get("AvailableRentBikes",  0)) if a else "?"
                        empty = str(a.get("AvailableReturnBikes", 0)) if a else "?"
                        nearby.append({"name": name, "dist": d,
                                       "bikes": bikes, "empty": empty})

                    if nearby:
                        c = nearby[0]
                        return {
                            "status": "🟢", "station": c["name"], "dist": c["dist"],
                            "bikes": c["bikes"], "empty_slots": c["empty"],
                            "source": "TDX 全台即時", "nearby_stations": nearby
                        }
            except Exception as e:
                print(f"[TDX] YouBike Error: {e}")

        return {
            "status": "🔴", "station": "連線失敗或無資料", "dist": "--",
            "bikes": "0", "empty_slots": "--", "source": "API 異常",
            "nearby_stations": []
        }

    # ──────────────────────────────────────────────────
    # ✅ TDX 公車（修復：ETA 半徑與 Stop 半徑保持一致）
    # ──────────────────────────────────────────────────
    def get_bus_data(self, lat, lon, addr=""):
        token = self._get_tdx_token()
        if not token:
            return self._bus_google_fallback(lat, lon)

        try:
            stops = self._tdx_get(
                "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/NearBy",
                params={
                    "$spatialFilter": f"nearby({lat},{lon},600)",
                    "$format":        "JSON",
                    "$top":           30,
                    "$select":        "StopUID,StopName,StopPosition,RouteName",
                }
            )

            # 600m 找不到就擴大到 1000m
            search_radius = 600
            if not stops:
                search_radius = 1000
                stops = self._tdx_get(
                    "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/NearBy",
                    params={
                        "$spatialFilter": f"nearby({lat},{lon},1000)",
                        "$format":        "JSON",
                        "$top":           30,
                        "$select":        "StopUID,StopName,StopPosition,RouteName",
                    }
                )

            if not stops:
                return self._bus_google_fallback(lat, lon)

            def _d(s):
                p = s.get("StopPosition", {})
                return self.calc_real_dist(lat, lon,
                                           p.get("PositionLat", 0),
                                           p.get("PositionLon", 0))

            stops.sort(key=_d)
            nearest      = stops[0]
            nearest_name = nearest.get("StopName", {}).get("Zh_tw", "--")
            nearest_dist = _d(nearest)

            stop_uid_set = {s.get("StopUID") for s in stops if s.get("StopUID")}

            # ✅ 修復：ETA 半徑與 Stop 查詢半徑保持一致，防止找到的站牌抓不到 ETA
            etas = self._tdx_get(
                "https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/NearBy",
                params={
                    "$spatialFilter": f"nearby({lat},{lon},{search_radius})",
                    "$format":        "JSON",
                    "$top":           200,  # ✅ 修復：原版 100 在大站可能不足
                    "$select":        "StopUID,RouteName,EstimateTime,StopStatus,Direction,PlateNumb",
                }
            ) or []

            matched = [e for e in etas if e.get("StopUID") in stop_uid_set]
            if not matched:
                matched = etas

            route_map = {}
            for e in matched:
                rname  = e.get("RouteName", {}).get("Zh_tw", "")
                if not rname: continue
                status = e.get("StopStatus", 0)
                est    = e.get("EstimateTime")
                direc  = e.get("Direction", 0)
                plate  = e.get("PlateNumb", "")

                if status == 0 and est is not None:
                    mins = int(est) // 60
                    if   mins == 0: label, urgency = "進站中 🚌", 0
                    elif mins <= 3: label, urgency = f"{mins} 分鐘 ⚡", mins
                    else:           label, urgency = f"{mins} 分鐘",    mins
                elif status == 1: label, urgency = "尚未發車",  9991
                elif status == 2: label, urgency = "交管不停",  9992
                elif status == 3: label, urgency = "末班已過",  9993
                elif status == 4: label, urgency = "今日未營運", 9994
                else:             label, urgency = "無資料",    9999

                key = f"{rname}_{direc}"
                if key not in route_map or urgency < route_map[key]["urgency"]:
                    route_map[key] = {
                        "route":   rname,
                        "label":   label,
                        "urgency": urgency,
                        "plate":   plate,
                        "dir":     "去程" if direc == 0 else "返程",
                    }

            arrivals = sorted(route_map.values(), key=lambda x: x["urgency"])

            # ✅ 修復：台鐵置頂
            try:
                tra_list = self._tdx_get(
                    "https://tdx.transportdata.tw/api/basic/v2/Rail/TRA/Station/NearBy",
                    params={
                        "$spatialFilter": f"nearby({lat},{lon},1500)",
                        "$format": "JSON", "$top": 3,
                        "$select": "StationName,StationPosition",
                    }
                )
                if tra_list:
                    t = min(tra_list, key=lambda x: self.calc_real_dist(
                        lat, lon,
                        x.get("StationPosition", {}).get("PositionLat", 0),
                        x.get("StationPosition", {}).get("PositionLon", 0)
                    ))
                    td = self.calc_real_dist(
                        lat, lon,
                        t.get("StationPosition", {}).get("PositionLat", 0),
                        t.get("StationPosition", {}).get("PositionLon", 0)
                    )
                    arrivals.insert(0, {
                        "route": f"🚆 台鐵 {t.get('StationName',{}).get('Zh_tw','')}站",
                        "dir": f"{td}m 步行", "label": "軌道運輸",
                        "urgency": -2, "plate": ""
                    })
            except: pass

            # ✅ 修復：捷運 NearBy — 原版 endpoint 錯誤，改為逐系統嘗試
            try:
                mrt_found = None
                for sys_code, sys_name in MRT_SYSTEMS:
                    mrt_list = self._tdx_get(
                        f"https://tdx.transportdata.tw/api/basic/v2/Rail/Metro/Station/{sys_code}/NearBy",
                        params={
                            "$spatialFilter": f"nearby({lat},{lon},1500)",
                            "$format": "JSON", "$top": 3,
                            "$select": "StationName,StationPosition",
                        }
                    )
                    if mrt_list:
                        mt = min(mrt_list, key=lambda x: self.calc_real_dist(
                            lat, lon,
                            x.get("StationPosition", {}).get("PositionLat", 0),
                            x.get("StationPosition", {}).get("PositionLon", 0)
                        ))
                        md = self.calc_real_dist(
                            lat, lon,
                            mt.get("StationPosition", {}).get("PositionLat", 0),
                            mt.get("StationPosition", {}).get("PositionLon", 0)
                        )
                        mrt_found = {
                            "route": f"🚇 {sys_name} {mt.get('StationName',{}).get('Zh_tw','')}站",
                            "dir": f"{md}m 步行", "label": "捷運路網",
                            "urgency": -1, "plate": ""
                        }
                        break  # 找到最近的捷運系統就停止

                if mrt_found:
                    arrivals.insert(0, mrt_found)
            except: pass

            src = "TDX 即時動態" if route_map else "TDX (目前無班次資料)"
            return {
                "status":   "🟢" if route_map else "🟡",
                "station":  nearest_name,
                "dist":     nearest_dist,
                "arrivals": arrivals,
                "source":   src,
            }

        except Exception as e:
            print(f"[TDX] Bus Error: {e}")
            return self._bus_google_fallback(lat, lon)

    def _bus_google_fallback(self, lat, lon):
        gk = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if not gk: return {"status": "🔴", "station": "API未設定", "dist": "--", "arrivals": [], "source": ""}
        try:
            res = self.http.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params={"location": f"{lat},{lon}", "radius": 800, "type": "bus_station", "language": "zh-TW", "key": gk},
                timeout=5
            ).json()
            results = res.get("results", [])
            if results:
                cl = min(results, key=lambda x: self.calc_real_dist(lat, lon, x['geometry']['location']['lat'], x['geometry']['location']['lng']))
                dist = self.calc_real_dist(lat, lon, cl['geometry']['location']['lat'], cl['geometry']['location']['lng'])
                return {"status": "🟡", "station": cl['name'], "dist": dist, "arrivals": [], "source": "Google Places (靜態)"}
        except: pass
        return {"status": "🔴", "station": "附近無站點", "dist": "--", "arrivals": [], "source": ""}

    # ──────────────────────────────────────────────────
    # ✅ 新功能：自行車道資訊
    # ──────────────────────────────────────────────────
    def get_bike_lanes(self, lat, lon):
        """取得附近自行車道資訊（TDX CyclingShape API）"""
        try:
            # 嘗試用 Google Places 抓自行車相關設施
            gk = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
            if gk:
                res = self.http.get(
                    "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                    params={"location": f"{lat},{lon}", "radius": 1000,
                            "keyword": "自行車 腳踏車 單車", "language": "zh-TW", "key": gk},
                    timeout=5
                ).json()
                results = res.get("results", [])
                if results:
                    return {
                        "status": "🟢",
                        "count": len(results),
                        "nearest": results[0].get("name", "--"),
                        "source": "Google Places"
                    }
        except: pass

        # 嘗試 TDX 自行車道 API
        token = self._get_tdx_token()
        if token:
            try:
                data = self._tdx_get(
                    "https://tdx.transportdata.tw/api/basic/v2/Cycling/Shape/NearBy",
                    params={
                        "$spatialFilter": f"nearby({lat},{lon},1000)",
                        "$format": "JSON", "$top": 10,
                        "$select": "RouteName,CyclingType,RoadSectionStart,RoadSectionEnd",
                    }
                )
                if data:
                    return {
                        "status": "🟢",
                        "count": len(data),
                        "nearest": data[0].get("RouteName", {}).get("Zh_tw", "--") if data else "--",
                        "source": "TDX 自行車道"
                    }
            except: pass

        return {"status": "🔴", "count": 0, "nearest": "--", "source": "無資料"}

    # ──────────────────────────────────────────────────
    # ✅ 新功能：停車場即時資訊
    # ──────────────────────────────────────────────────
    def get_parking_data(self, lat, lon):
        """取得附近停車場即時剩餘車位（TDX ParkingLot API）"""
        token = self._get_tdx_token()
        if token:
            try:
                lots = self._tdx_get(
                    "https://tdx.transportdata.tw/api/basic/v2/Parking/OffStreet/ParkingLot/NearBy",
                    params={
                        "$spatialFilter": f"nearby({lat},{lon},800)",
                        "$format": "JSON", "$top": 5,
                        "$select": "ParkingLotID,ParkingLotName,ParkingLotPosition,PayGuide",
                    }
                )
                if lots:
                    # 取得即時車位
                    lot_ids = [l.get("ParkingLotID", "") for l in lots if l.get("ParkingLotID")]
                    avail_list = []
                    for lid in lot_ids[:3]:
                        avail = self._tdx_get(
                            f"https://tdx.transportdata.tw/api/basic/v2/Parking/OffStreet/Availability/{lid}",
                            params={"$format": "JSON"}
                        )
                        if avail and isinstance(avail, list) and avail:
                            a = avail[0]
                            name = next((l.get("ParkingLotName", {}).get("Zh_tw", lid)
                                        for l in lots if l.get("ParkingLotID") == lid), lid)
                            avail_list.append({
                                "name": name,
                                "available": a.get("AvailableSpaces", "--"),
                                "total": a.get("TotalSpaces", "--"),
                            })

                    if avail_list:
                        return {
                            "status": "🟢",
                            "lots": avail_list,
                            "source": "TDX 即時"
                        }

                    # 有停車場但無即時資料
                    if lots:
                        return {
                            "status": "🟡",
                            "lots": [{"name": l.get("ParkingLotName", {}).get("Zh_tw", "--"),
                                      "available": "--", "total": "--"} for l in lots[:3]],
                            "source": "TDX 靜態"
                        }
            except Exception as e:
                print(f"[TDX] Parking Error: {e}")

        return {"status": "🔴", "lots": [], "source": "無資料"}

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
                        params={"location": f"{lat},{lon}", "radius": q["radius"], "language": "zh-TW", "key": google_key, "type": q["type"]},
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
        age_dep = (age * 0.8 if age <= 10 else (8 + (age - 10) * 0.5 if age <= 30 else 18 + (age - 30) * 0.2))
        price = base_price - age_dep
        if "店面" in floor: price *= 1.6
        elif "公寓" in floor: price -= 10
        elif "電梯大樓" in floor: price += 6
        elif "全棟評估" in floor: price *= 1.25
        ext_mult = (1.0 + (poi_scores[0]-60)*0.0015 + (poi_scores[3]-60)*0.0012 + (poi_scores[4]-60)*0.0008)
        if isinstance(yb_dist, (int, float)):
            ext_mult += 0.03 if yb_dist <= 300 else (0.01 if yb_dist <= 800 else -0.02)
        final_price = max(15, int(price * ext_mult))
        variance = 0.06 + (random.random() * 0.04)
        return (f"{int(final_price*(1-variance))} ~ {int(final_price*(1+variance))}", source_tag, final_price)

    def _get_street_heading(self, lat, lon, google_key):
        if not google_key: return 0
        try:
            res = self.http.get(
                f"https://roads.googleapis.com/v1/nearestRoads?points={lat},{lon}&key={google_key}",
                timeout=4).json()
            pts = res.get('snappedPoints', [])
            if len(pts) >= 2:
                p0, p1 = pts[0]['location'], pts[1]['location']
                b = self.calc_bearing(p0['latitude'], p0['longitude'], p1['latitude'], p1['longitude'])
                return (b + 90) % 360
        except: pass
        return 0

    def get_dynamic_data(self, addr, floor):
        lat, lon = 25.0330, 121.5654
        google_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if google_key:
            try:
                geo = self.http.get(
                    f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(addr)}&region=tw&language=zh-TW&key={google_key}",
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
        val_s, val_src, b_price = self.calculate_appraisal_price(city_name, dist_name, road_name, floor, age, ps, yb.get("dist", "--"))
        hist = [int(b_price * (1-(5-i)*0.035 + (random.random()*0.02-0.01))) for i in range(6)]

        moltke = {
            "age": age, "elevator": "無" if "公寓" in floor else "有",
            "risks": {"高風險": "無顯著異常", "低風險": "排除親友特殊交易"},
            "core_summary": {"valuation": val_s, "valuation_source": val_src},
            "api_health": {"Google": ps_src, "Weather": weather["status"], "MOENV": env["api_status"], "YouBike": yb["status"]},
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
        m = DualMap(location=[lat, lon], zoom_start=16)

        folium.TileLayer('OpenStreetMap', name='標準街道圖 (OSM)', max_zoom=20, max_native_zoom=18).add_to(m.m1)
        folium.TileLayer('CartoDB positron', name='淺色地圖 (Positron)', max_zoom=20, max_native_zoom=18).add_to(m.m1)

        folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='衛星空照圖 (Satellite)', max_zoom=20, max_native_zoom=17).add_to(m.m2)
        folium.TileLayer('OpenStreetMap', name='標準街道圖 (OSM)', max_zoom=20, max_native_zoom=18).add_to(m.m2)

        offset = 0.0072
        bounds = [[lat-offset, lon-offset], [lat+offset, lon+offset]]
        for mm in [m.m1, m.m2]:
            folium.Rectangle(bounds, color='#38BDF8', fill=True, fill_opacity=0.05, weight=2, dash_array='5, 5', tooltip="800m 分析範圍").add_to(mm)
            folium.Marker([lat, lon], icon=folium.Icon(color="red", icon="home")).add_to(mm)
            
        for p in raw_pois:
            for mm in [m.m1, m.m2]:
                folium.Marker([p['lat'], p['lon']], tooltip=p['name'], icon=folium.Icon(color=p['color'], icon=p['icon'], prefix=p['prefix'])).add_to(mm)

        folium.LayerControl(collapsed=True).add_to(m.m1)
        folium.LayerControl(collapsed=True).add_to(m.m2)

        m.get_root().html.add_child(folium.Element("<style>.leaflet-sbs-divider{background-color:#38BDF8!important;width:6px!important;margin-left:-3px!important;z-index:999999!important;box-shadow:0 0 15px rgba(56,189,248,0.8)!important;pointer-events:none!important;}</style>"))
        return m
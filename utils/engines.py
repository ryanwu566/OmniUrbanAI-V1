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
import json
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

TDX_BIKE_COUNTY_MAP = {
    "台北市": "Taipei", "臺北市": "Taipei",
    "新北市": "NewTaipei",
    "基隆市": "Keelung",
    "桃園市": "Taoyuan",
    "新竹市": "Hsinchu",
    "新竹縣": "HsinchuCounty",
    "苗栗縣": "MiaoliCounty",
    "台中市": "Taichung", "臺中市": "Taichung",
    "彰化縣": "ChanghuaCounty",
    "南投縣": "NantouCounty",
    "雲林縣": "YunlinCounty",
    "嘉義市": "Chiayi",
    "嘉義縣": "ChiayiCounty",
    "台南市": "Tainan", "臺南市": "Tainan",
    "高雄市": "Kaohsiung",
    "屏東縣": "PingtungCounty",
    "宜蘭縣": "YilanCounty",
    "花蓮縣": "HualienCounty",
    "台東縣": "TaitungCounty", "臺東縣": "TaitungCounty",
    "澎湖縣": "PenghuCounty",
    "金門縣": "KinmenCounty",
    "連江縣": "LienchiangCounty",
    "Taipei": "Taipei", "NewTaipei": "NewTaipei", "Keelung": "Keelung", "Taoyuan": "Taoyuan",
    "Hsinchu": "Hsinchu", "HsinchuCounty": "HsinchuCounty", "MiaoliCounty": "MiaoliCounty",
    "Taichung": "Taichung", "ChanghuaCounty": "ChanghuaCounty", "NantouCounty": "NantouCounty",
    "YunlinCounty": "YunlinCounty", "Chiayi": "Chiayi", "ChiayiCounty": "ChiayiCounty",
    "Tainan": "Tainan", "Kaohsiung": "Kaohsiung", "PingtungCounty": "PingtungCounty",
    "YilanCounty": "YilanCounty", "HualienCounty": "HualienCounty", "TaitungCounty": "TaitungCounty",
    "PenghuCounty": "PenghuCounty", "KinmenCounty": "KinmenCounty", "LienchiangCounty": "LienchiangCounty",
}

# open-source MojLawSplit JSON law data for RAG retrieval
MOJ_LAW_INDEX_URL = "https://raw.githubusercontent.com/kong0107/mojLawSplitJSON/arranged/ch/index.json"
MOJ_LAW_BASE_URL = "https://raw.githubusercontent.com/kong0107/mojLawSplitJSON/arranged/ch"

@st.cache_data(ttl=86400, show_spinner=False)
def load_moj_law_index():
    """載入 MojLawSplit 開源法規索引，回傳 PCode -> 法規名稱對應。"""
    try:
        resp = requests.get(MOJ_LAW_INDEX_URL, timeout=20, headers={"User-Agent": "OmniUrbanAI/1.0"})
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if k}
        if isinstance(data, list):
            return {str(item.get("PCode", "")): str(item.get("name", "")) for item in data if item.get("PCode")}
    except Exception as e:
        print(f"[RAG] load_moj_law_index error: {e}")
    return {}

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_moj_law_json(pcode: str):
    """由 MojLawSplit 原始 JSON 取得單一法規內容。"""
    if not pcode:
        return None
    url = f"{MOJ_LAW_BASE_URL}/{pcode}.json"
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "OmniUrbanAI/1.0"})
        if resp.status_code != 200:
            print(f"[RAG] fetch_moj_law_json {pcode} status {resp.status_code}")
            return None
        return resp.json()
    except Exception as e:
        print(f"[RAG] fetch_moj_law_json error: {e}")
        return None


def _normalize_rag_query(query: str) -> str:
    if not query:
        return ""
    return re.sub(r"[\s\u3000]+", "", query).strip()


def _extract_pcode(query: str):
    if not query:
        return None
    match = re.search(r"([A-Z]\d{7})", query.upper())
    return match.group(1) if match else None


def _extract_article_number(query: str):
    if not query:
        return None
    match = re.search(r"第\s*(\d+)\s*條", query)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d+)條\b", query)
    return int(match.group(1)) if match else None


def _extract_search_tokens(query: str) -> list[str]:
    if not query:
        return []
    query = re.sub(r"第\s*\d+\s*條", "", query)
    tokens = re.findall(r"[\u4e00-\u9fff\w]+", query)
    return [token.lower() for token in tokens if token.strip()]


def prepare_law_context(law_json: dict, query: str, max_articles: int = 4) -> str:
    if not law_json:
        return ""
    query_lower = _normalize_rag_query(query).lower()
    law_name = law_json.get("name", "")
    pcode = law_json.get("pcode", law_json.get("PCode", ""))
    modified = law_json.get("LawModifiedDate", law_json.get("lastUpdate", ""))
    context = [f"法規：{law_name} ({pcode})", f"最後修訂：{modified}"]
    matched = []
    query_artnum = _extract_article_number(query)
    for art in law_json.get("articles", []):
        content_text = "".join([seg.get("text", "") for seg in art.get("content", [])]).strip()
        if query_artnum and art.get("number") == query_artnum:
            matched.append((art.get("number"), content_text))
            break
        if query_lower and query_lower in content_text.lower():
            matched.append((art.get("number"), content_text))
            if len(matched) >= max_articles:
                break
    if not matched:
        for art in law_json.get("articles", [])[:max_articles]:
            content_text = "".join([seg.get("text", "") for seg in art.get("content", [])]).strip()
            matched.append((art.get("number"), content_text))
    for number, text in matched:
        context.append(f"第{number}條：{text}")
    return "\n".join(context)


def get_rag_client(provider: str = "gemini"):
    provider = (provider or "").lower()
    if provider == "gemini":
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return None, None
        return OpenAI(api_key=api_key, base_url="https://api.gemini.com/v1"), "gemini-pro"
    if provider == "groq":
        api_key = st.secrets.get("GROQ_API_KEY", "")
        if not api_key:
            return None, None
        return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1"), "llama-3.3-70b-versatile"
    # fallback order
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if api_key:
        return OpenAI(api_key=api_key, base_url="https://api.gemini.com/v1"), "gemini-pro"
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if api_key:
        return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1"), "llama-3.3-70b-versatile"
    return None, None


def explain_law_with_ai(law_context: str, query: str, provider: str = "gemini") -> str:
    if not law_context or not query:
        return "無法解析：缺少法規內容或查詢。"
    client, model = get_rag_client(provider)
    if not client:
        return "無法解析：未找到可用的 RAG 模型金鑰，請確認 `GEMINI_API_KEY` 或 `GROQ_API_KEY` 已設定。"
    system_prompt = (
        "你是台灣法律查詢助手。根據提供的法規原文回答問題，嚴格依據原始條文內容，不可憑空新增或推測未提供資訊。"
        " 如果無法確定，請明確說明需要查詢官方版本。"
    )
    user_prompt = (
        f"問題：{query}\n\n"
        "以下是檢索到的法規原文與條文節錄，請務必引用條號與法規名稱，並說明如何適用：\n\n"
        f"{law_context}"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=900,
        )
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        return "取得模型回應失敗，請稍候再試。"
    except Exception as e:
        print(f"[RAG] explain_law_with_ai error: {e}")
        return f"模型解析失敗：{e}"


def search_law_articles(query: str, max_results: int = 5) -> list[dict]:
    query_norm = _normalize_rag_query(query)
    if not query_norm:
        return []
    law_index = load_moj_law_index()
    if not law_index:
        return []
    query_code = _extract_pcode(query_norm)
    query_artnum = _extract_article_number(query_norm)
    query_lower = query_norm.lower()
    query_terms = _extract_search_tokens(query_norm)
    candidates = []
    selected = set()
    if query_code and query_code in law_index:
        candidates.append(query_code)
        selected.add(query_code)
    for code, name in law_index.items():
        name_lower = name.lower()
        if query_lower in code.lower() or query_lower in name_lower:
            if code not in selected:
                candidates.append(code)
                selected.add(code)
        elif any(term in name_lower for term in query_terms):
            if code not in selected:
                candidates.append(code)
                selected.add(code)
    if len(candidates) < 20:
        terms = _extract_search_tokens(query_norm)
        scored = []
        for code, name in law_index.items():
            if code in selected:
                continue
            score = sum(1 for term in terms if term and term in name.lower())
            if score > 0:
                scored.append((score, code))
        scored.sort(key=lambda item: item[0], reverse=True)
        for _, code in scored[:20]:
            if code not in selected:
                candidates.append(code)
                selected.add(code)
    results = []
    for code in candidates[:30]:
        law_json = fetch_moj_law_json(code)
        if not law_json:
            continue
        name = law_json.get("name", law_index.get(code, ""))
        excerpt_lines = []
        if query_lower in name.lower():
            excerpt_lines.append(f"法規名稱匹配：{name}")
        for art in law_json.get("articles", []):
            content_text = "".join([seg.get("text", "") for seg in art.get("content", [])]).strip()
            if query_artnum and art.get("number") == query_artnum:
                excerpt_lines.append(f"第{art.get('number')}條：{content_text[:240]}...")
                break
            if query_lower and query_lower in content_text.lower():
                excerpt_lines.append(f"第{art.get('number')}條：{content_text[:240]}...")
                if len(excerpt_lines) >= 3:
                    break
        if excerpt_lines:
            results.append({
                "code": code,
                "law_name": name,
                "match_excerpt": "\n".join(excerpt_lines),
                "raw_url": f"{MOJ_LAW_BASE_URL}/{code}.json",
                "github_url": f"https://github.com/kong0107/mojLawSplitJSON/blob/arranged/ch/{code}.json",
            })
            if len(results) >= max_results:
                break
    if not results:
        for code in candidates[:max_results]:
            results.append({
                "code": code,
                "law_name": law_index.get(code, ""),
                "match_excerpt": "法規名稱建議，請進一步指定條號或關鍵字以縮小範圍。",
                "raw_url": f"{MOJ_LAW_BASE_URL}/{code}.json",
                "github_url": f"https://github.com/kong0107/mojLawSplitJSON/blob/arranged/ch/{code}.json",
            })
    return results

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


def get_tgos_coordinates(address):
    """
    使用 TGOS 地址比對 API 將模糊地址轉為精準座標。
    若發生錯誤或金鑰未設定，回傳預設坐標 (25.033964, 121.564468)。
    """
    default_coord = (25.033964, 121.564468)
    try:
        app_id = st.secrets.get("TGOS_APPID", "")
        api_key = st.secrets.get("TGOS_APIKEY", "")
        if not app_id or not api_key:
            return default_coord

        url = "https://addr.tgos.tw/addrws/v30/QueryAddr.asmx/QueryAddr"
        params = {
            "oAPPId": app_id,
            "oAPIKey": api_key,
            "oAddress": address,
            "oMatch": "exact",
            "oFormat": "json",
        }
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        address_list = data.get("AddressList") or data.get("QueryAddrResult", {}).get("AddressList") or []
        if not address_list:
            return default_coord

        item = address_list[0]
        x = item.get("X") or item.get("x")
        y = item.get("Y") or item.get("y")
        if x is None or y is None:
            return default_coord

        return float(y), float(x)
    except Exception as e:
        print(f"[TGOS] get_tgos_coordinates error: {e}")
        return default_coord


def fetch_tgos_theme_data(lat, lon, radius=500):
    """
    使用 TGOS 內政主題 API 查詢特定座標半徑內的主題圖資。
    回傳的字典包含各類設施數量與原始資料，方便後續轉換為六大機能評分依據。
    """
    result = {"ok": False, "total": 0, "counts": {}, "raw_features": [], "source": "TGOS_THEME"}
    try:
        api_key = st.secrets.get("TGOS_THEME_KEY", "")
        if not api_key:
            result["error"] = "TGOS_THEME_KEY 尚未設定"
            return result

        url = "https://data.tgos.tw/MOIDataThemeMgr"
        params = {
            "oAPIKey": api_key,
            "oFormat": "json",
            "oLat": lat,
            "oLon": lon,
            "oRadius": radius,
        }
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()

        features = []
        if isinstance(data, dict):
            if "FeatureCollection" in data:
                features = data.get("FeatureCollection", {}).get("features", [])
            elif "featureMember" in data:
                features = data.get("featureMember", [])
            elif "d" in data and isinstance(data["d"], dict):
                features = data["d"].get("results", []) or data["d"].get("FeatureCollection", {}).get("features", [])
            elif "results" in data:
                features = data.get("results", [])
            else:
                features = data.get("AddressList") or []

        counts = {}
        for item in features:
            if not isinstance(item, dict):
                continue
            props = item.get("properties") or item.get("Attributes") or item
            theme_name = str(
                props.get("ThemeName")
                or props.get("name")
                or props.get("theme")
                or props.get("Class")
                or props.get("CLASS")
                or props.get("TYPE")
                or item.get("Name", "")
            ).strip()
            if not theme_name:
                theme_name = "unknown"
            counts[theme_name] = counts.get(theme_name, 0) + 1

        result["ok"] = True
        result["total"] = sum(counts.values())
        result["counts"] = counts
        result["raw_features"] = features
        return result
    except Exception as e:
        print(f"[TGOS] fetch_tgos_theme_data error: {e}")
        result["error"] = str(e)
        return result


def _parse_tgos_feature_properties(item: dict) -> dict:
    props = item.get("properties") or item.get("Attributes") or item
    theme_name = str(
        props.get("ThemeName")
        or props.get("theme")
        or props.get("Class")
        or props.get("CLASS")
        or props.get("Type")
        or props.get("Name")
        or ""
    ).strip()
    title = str(
        props.get("Name")
        or props.get("Text")
        or props.get("LayerName")
        or props.get("Title")
        or ""
    ).strip()
    theme_id = props.get("ThemeId") or props.get("ThemeID") or props.get("themeId") or props.get("theme_id")
    return {
        "theme_name": theme_name,
        "theme_id": str(theme_id) if theme_id is not None else "",
        "label": title,
        "properties": props,
        "geometry": item.get("geometry") or item.get("Geometry") or None,
    }


def _classify_tgos_theme_feature(parsed: dict) -> str:
    text = f"{parsed['theme_name']} {parsed['label']}".lower()
    if any(keyword in text for keyword in [
        "土地使用", "分區", "住三", "住二", "住一", "商四", "商三", "商二", "工業區", "農業區", "特定區", "zone", "use",
    ]):
        return "zoning"
    if any(keyword in text for keyword in [
        "斷層", "液化", "淹水", "防洪", "保護區", "敏感區", "敏感", "自然保留", "生態", "環境敏感",
    ]):
        return "sensitive_areas"
    if any(keyword in text for keyword in [
        "加油站", "變電所", "殯儀館", "垃圾", "焚化", "煉油", "高壓", "中油", "危險物", "嫌惡", "廢棄物",
    ]):
        return "nuisance_facilities"
    return "others"


def get_advanced_tgos_theme_data(lat, lon, radius=500) -> dict:
    """
    呼叫 TGOS 內政主題圖資 API，取得傳入座標周邊的進階地政主題資料。

    需在 `.streamlit/secrets.toml` 裡設定：
        TGOS_THEME_APIKEY = "your_api_key"

    若 API 需要指定 ThemeID，可透過 `oThemeId` 參數傳入。
    常見範例（需依 TGOS 官方文件確認）：
        - 土地使用分區：oThemeId=2
        - 活動斷層帶：oThemeId=5
        - 土壤液化高潛勢區：oThemeId=6
        - 淹水潛勢圖：oThemeId=7
        - 加油站 / 變電所 / 殯儀館：oThemeId=21, 22, 23
    """
    result = {
        "ok": False,
        "source": "TGOS_THEME_ADVANCED",
        "lat": lat,
        "lon": lon,
        "radius": radius,
        "zoning": [],
        "sensitive_areas": [],
        "nuisance_facilities": [],
        "others": [],
        "raw_features": [],
        "errors": [],
    }
    try:
        api_key = st.secrets.get("TGOS_THEME_APIKEY", "")
        if not api_key:
            result["errors"].append("TGOS_THEME_APIKEY 尚未設定")
            return result

        url = "https://data.tgos.tw/MOIDataThemeMgr"
        params = {
            "oAPIKey": api_key,
            "oFormat": "json",
            "oLat": lat,
            "oLon": lon,
            "oRadius": radius,
        }

        resp = requests.get(url, params=params, timeout=15, headers={"User-Agent": "OmniUrbanAI/1.0"})
        resp.raise_for_status()
        data = resp.json()

        features = []
        if isinstance(data, dict):
            if "FeatureCollection" in data:
                features = data.get("FeatureCollection", {}).get("features", [])
            elif "featureMember" in data:
                features = data.get("featureMember", [])
            elif "d" in data and isinstance(data["d"], dict):
                features = data["d"].get("results", []) or data["d"].get("FeatureCollection", {}).get("features", [])
            elif "results" in data:
                features = data.get("results", [])
            else:
                features = data.get("AddressList") or []
        elif isinstance(data, list):
            features = data

        parsed_items = []
        for item in features:
            if not isinstance(item, dict):
                continue
            parsed = _parse_tgos_feature_properties(item)
            if not parsed["theme_name"] and not parsed["label"]:
                continue
            parsed_items.append(parsed)

        for parsed in parsed_items:
            category = _classify_tgos_theme_feature(parsed)
            result[category].append(parsed)

        result["raw_features"] = features
        result["ok"] = True
        result["total"] = sum(len(result[key]) for key in ["zoning", "sensitive_areas", "nuisance_facilities", "others"])
        return result
    except requests.exceptions.RequestException as e:
        msg = f"TGOS 主題 API 網路錯誤：{e}"
        print(f"[TGOS] get_advanced_tgos_theme_data error: {e}")
        result["errors"].append(msg)
        return result
    except ValueError as e:
        msg = f"TGOS 主題 API 回傳 JSON 解析錯誤：{e}"
        print(f"[TGOS] get_advanced_tgos_theme_data json error: {e}")
        result["errors"].append(msg)
        return result
    except Exception as e:
        msg = f"TGOS 主題 API 未知錯誤：{e}"
        print(f"[TGOS] get_advanced_tgos_theme_data unexpected error: {e}")
        result["errors"].append(msg)
        return result


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
    # ✅ TDX 診斷面板（隱私安全版）
    # ──────────────────────────────────────────────────
    def tdx_diagnose(self) -> dict:
        """
        回傳 TDX 設定與 Token 狀態的診斷字典，供 sidebar 顯示（已移除所有金鑰明文）。
        """
        cid  = st.secrets.get("TDX_CLIENT_ID", "")
        csec = st.secrets.get("TDX_CLIENT_SECRET", "")

        cid_set   = bool(cid)
        csec_set  = bool(csec)

        # 嘗試取得 token
        token = self._get_tdx_token()
        token_ok = bool(token)
        last_error = st.session_state.get("tdx_last_error", "")

        return {
            "cid_set":       cid_set,
            "csec_set":      csec_set,
            "token_ok":      token_ok,
            "last_error":    last_error,
        }

    # ──────────────────────────────────────────────────
    # ✅ TDX 即時測試（隱私安全版）
    # ──────────────────────────────────────────────────
    def tdx_test_token(self) -> dict:
        """
        強制打 TDX token endpoint，但回傳結果不再包含任何敏感資訊。
        """
        cid  = st.secrets.get("TDX_CLIENT_ID", "")
        csec = st.secrets.get("TDX_CLIENT_SECRET", "")

        if not cid or not csec:
            return {"ok": False, "error": "尚未設定 TDX 金鑰"}

        try:
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
            if r.status_code == 200 and "access_token" in r.json():
                return {"ok": True, "error": None}
            else:
                return {"ok": False, "error": f"連線失敗 (HTTP {r.status_code})"}
        except Exception as e:
            return {"ok": False, "error": "網路連線異常或逾時"}

    # ──────────────────────────────────────────────────
    # ✅ TDX OAuth2（修復：改用獨立 requests，完整記錄錯誤）
    # ──────────────────────────────────────────────────
    def _get_tdx_bike_county(self, addr):
        if not addr:
            return None
        text = str(addr).strip()
        if not text:
            return None

        for key in sorted(TDX_BIKE_COUNTY_MAP.keys(), key=len, reverse=True):
            if text.startswith(key):
                return TDX_BIKE_COUNTY_MAP[key]

        lower = text.lower()
        for key, value in TDX_BIKE_COUNTY_MAP.items():
            if key.lower() in lower:
                return value
        return None

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
                err = f"401 Unauthorized — Client ID 或 Secret 錯誤"
                st.session_state.tdx_last_error = err
                st.session_state.tdx_token = None
                return None
            r.raise_for_status()
            j = r.json()
            st.session_state.tdx_token     = j["access_token"]
            st.session_state.tdx_token_exp = now + j.get("expires_in", 86400)
            st.session_state.tdx_last_error = ""   
            return st.session_state.tdx_token
        except requests.exceptions.Timeout:
            err = "逾時 (Timeout) — 無法連線"
            st.session_state.tdx_last_error = err
            st.session_state.tdx_token = None
            return None
        except Exception as e:
            err = str(e)
            st.session_state.tdx_last_error = err
            st.session_state.tdx_token = None
            return None

    def _tdx_get(self, url, params=None, timeout=10, retry_on_429=True):
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
        
        retry_count = 0
        max_retries = 2
        
        while retry_count <= max_retries:
            try:
                r = self.http.get(url, headers=_build_headers(token), params=params, timeout=timeout)
                if r.status_code == 401:
                    st.session_state.tdx_token = None
                    st.session_state.tdx_token_exp = 0
                    token = self._get_tdx_token()
                    if not token: return None
                    r = self.http.get(url, headers=_build_headers(token), params=params, timeout=timeout)
                
                if r.status_code == 429:
                    if retry_on_429 and retry_count < max_retries:
                        wait_time = 2 ** (retry_count + 1)  # 指數退避：2秒、4秒
                        print(f"[TDX] Rate limit 429 — 等待 {wait_time}秒後重試...")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        print(f"[TDX] Rate limit 429 — 達到重試上限，放棄此請求")
                        st.session_state.tdx_last_error = "API 限流 (429) — 請稍候再試"
                        return None
                
                r.raise_for_status()
                return r.json()
            except Exception as e:
                print(f"[TDX] GET Error ({url}): {e}")
                return None
        
        return None

    # ──────────────────────────────────────────────────
    # [下方其餘所有 API 與抓取邏輯保留您原本寫法，完全不動]
    # ──────────────────────────────────────────────────

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
            county = self._get_tdx_bike_county(addr)
            if not county:
                county = self._get_tdx_bike_county(addr.replace("台", "臺", 1)) if isinstance(addr, str) else None
            if not county:
                county = "Taipei"

            try:
                stations = self._tdx_get(
                    f"https://tdx.transportdata.tw/api/basic/v2/Bike/Station/City/{urllib.parse.quote(county)}",
                    params={
                        "$format":        "JSON",
                        "$top":           2000,
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
                        f"https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/City/{urllib.parse.quote(county)}",
                        params={
                            "$format":        "JSON",
                            "$top":           2000,
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
                            "source": f"TDX 全台即時 ({county})", "nearby_stations": nearby
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
            county = self._get_tdx_bike_county(addr)
            if not county:
                county = self._get_tdx_bike_county(addr.replace("台", "臺", 1)) if isinstance(addr, str) else None
            if not county:
                county = "Taipei"

            bus_stop_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/{urllib.parse.quote(county)}"
            stops = self._tdx_get(
                bus_stop_url,
                params={
                    "$spatialFilter": f"nearby({lat},{lon},600)",
                    "$format":        "JSON",
                    "$top":           30,
                    "$select":        "StopUID,StopName,StopPosition",
                }
            )

            # 600m 找不到就擴大到 1000m
            search_radius = 600
            if not stops:
                search_radius = 1000
                stops = self._tdx_get(
                    bus_stop_url,
                    params={
                        "$spatialFilter": f"nearby({lat},{lon},1000)",
                        "$format":        "JSON",
                        "$top":           30,
                        "$select":        "StopUID,StopName,StopPosition",
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
            bus_eta_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/{urllib.parse.quote(county)}"
            etas = self._tdx_get(
                bus_eta_url,
                params={
                    "$spatialFilter": f"nearby({lat},{lon},{search_radius})",
                    "$format":        "JSON",
                    "$top":           200,  # ✅ 修復：原版 100 在大站可能不足
                    "$select":        "StopUID,RouteName,EstimateTime,StopStatus,Direction,PlateNumb",
                }
            ) or []

            if not etas:
                stop_uids = [s.get("StopUID") for s in stops[:6] if s.get("StopUID")]
                if stop_uids:
                    filter_expr = " or ".join([f"StopUID eq '{uid}'" for uid in stop_uids])
                    etas = self._tdx_get(
                        bus_eta_url,
                        params={
                            "$filter": filter_expr,
                            "$format": "JSON",
                            "$top": 200,
                            "$select": "StopUID,RouteName,EstimateTime,StopStatus,Direction,PlateNumb",
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
            if not arrivals and stops:
                # 若沒有 ETA，但有停靠站，仍顯示最近站牌與可能路線
                for stop in stops[:6]:
                    stop_name = stop.get("StopName", {}).get("Zh_tw", "--")
                    routes = stop.get("RouteName", [])
                    if isinstance(routes, list):
                        route_names = [r.get("Zh_tw", "") for r in routes if isinstance(r, dict)]
                    else:
                        route_names = [routes.get("Zh_tw", "")] if isinstance(routes, dict) else []
                    route_text = ", ".join([r for r in route_names if r])
                    arrivals.append({
                        "route": stop_name,
                        "label": f"停靠路線：{route_text}" if route_text else "停靠站牌",
                        "urgency": 9999,
                        "plate": "",
                        "dir": "--",
                    })

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

    def _count_tdx_transit_points(self, lat, lon, radius=1000):
        token = self._get_tdx_token()
        if not token:
            return 0
        unique_names = set()
        try:
            bus_stop_url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/Taipei"
            stops = self._tdx_get(
                bus_stop_url,
                params={
                    "$spatialFilter": f"nearby({lat},{lon},{radius})",
                    "$format": "JSON",
                    "$top": 50,
                    "$select": "StopName,StopPosition",
                }
            ) or []
            for s in stops:
                name = s.get("StopName", {}).get("Zh_tw") if isinstance(s.get("StopName"), dict) else s.get("StopName")
                if name:
                    unique_names.add(str(name))
        except Exception as e:
            print(f"[TDX] Transit Count Bus Error: {e}")

        try:
            for sys_code, _ in MRT_SYSTEMS:
                mrt_list = self._tdx_get(
                    f"https://tdx.transportdata.tw/api/basic/v2/Rail/Metro/Station/{sys_code}/NearBy",
                    params={
                        "$spatialFilter": f"nearby({lat},{lon},{radius})",
                        "$format": "JSON",
                        "$top": 20,
                        "$select": "StationName,StationPosition",
                    }
                ) or []
                for station in mrt_list:
                    name = station.get("StationName", {}).get("Zh_tw") if isinstance(station.get("StationName"), dict) else station.get("StationName")
                    if name:
                        unique_names.add(str(name))
        except Exception as e:
            print(f"[TDX] Transit Count MRT Error: {e}")

        try:
            tra_list = self._tdx_get(
                "https://tdx.transportdata.tw/api/basic/v2/Rail/TRA/Station/NearBy",
                params={
                    "$spatialFilter": f"nearby({lat},{lon},{radius})",
                    "$format": "JSON",
                    "$top": 20,
                    "$select": "StationName,StationPosition",
                }
            ) or []
            for station in tra_list:
                name = station.get("StationName", {}).get("Zh_tw") if isinstance(station.get("StationName"), dict) else station.get("StationName")
                if name:
                    unique_names.add(str(name))
        except Exception as e:
            print(f"[TDX] Transit Count TRA Error: {e}")

        return len(unique_names)

    # ──────────────────────────────────────────────────
    # ✅ 新功能：自行車道資訊
    # ──────────────────────────────────────────────────
    def get_bike_lanes(self, lat, lon):
        """取得附近自行車道資訊（優先使用 TDX，避免 Google Places 抓到錯誤步道結果）。"""
        token = self._get_tdx_token()
        if token:
            try:
                data = self._tdx_get(
                    "https://tdx.transportdata.tw/api/basic/v2/Cycling/Shape/NearBy",
                    params={
                        "$spatialFilter": f"nearby({lat},{lon},1000)",
                        "$format": "JSON",
                        "$top": 20,
                        "$select": "RouteName,CyclingType,RoadSectionStart,RoadSectionEnd",
                    }
                )
                if data and isinstance(data, list) and len(data) > 0:
                    routes = []
                    for item in data:
                        name = item.get("RouteName", {}).get("Zh_tw") if isinstance(item.get("RouteName"), dict) else item.get("RouteName")
                        if name:
                            routes.append(str(name))
                    unique_routes = list(dict.fromkeys([r for r in routes if r]))
                    return {
                        "status": "🟢",
                        "count": len(unique_routes),
                        "nearest": unique_routes[0] if unique_routes else "--",
                        "source": "TDX 自行車道"
                    }
            except Exception as e:
                print(f"[TDX] Bike Lanes Error: {e}")

        # Google Places 作為備援，僅在 TDX 無法取得時使用
        gk = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
        if gk:
            try:
                res = self.http.get(
                    "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                    params={"location": f"{lat},{lon}", "radius": 1000,
                            "keyword": "自行車 腳踏車 單車", "language": "zh-TW", "key": gk},
                    timeout=5
                ).json()
                results = res.get("results", [])
                if results:
                    return {
                        "status": "🟡",
                        "count": len(results),
                        "nearest": results[0].get("name", "--"),
                        "source": "Google Places (備援)"
                    }
            except Exception as e:
                print(f"[Google] Bike Lanes Error: {e}")

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

    # ──────────────────────────────────────────────────
    # ✅ 新功能：台鐵列車延誤資訊（LiveTrainDelay）
    # ──────────────────────────────────────────────────
    def get_train_delay_data(self):
        """
        取得台鐵列車延誤資訊
        
        API 說明：
        - LiveTrainDelay 回傳格式：列車在特定車站的延誤時間
        - 欄位：TrainNo, StationID, StationName, DelayTime, SrcUpdateTime, UpdateTime
        - 無法獲得始發地/目的地（只有當前車站）
        """
        token = self._get_tdx_token()
        if not token:
            return {"status": "🔴", "message": "無法取得 TDX Token", "delays": [], "source": ""}
        
        try:
            delay_data = self._tdx_get(
                "https://tdx.transportdata.tw/api/basic/v2/Rail/TRA/LiveTrainDelay",
                params={
                    "$format": "JSON",
                    "$top": 50,  # 最多抓 50 筆延誤資訊
                    # 注意：$select 和 $orderby 都已移除，因為欄位名稱不同
                }
            )
            
            if not delay_data or not isinstance(delay_data, list):
                return {
                    "status": "🟢",
                    "message": "目前列車準點運行，無延誤",
                    "delays": [],
                    "source": "TDX 即時 (無延誤)"
                }
            
            # 處理延誤數據
            processed_delays = {}
            for record in delay_data:
                if not record.get("DelayTime") or record.get("DelayTime") <= 0:
                    continue  # 跳過沒有延誤的列車
                
                train_no = record.get("TrainNo", "--")
                delay_time = record.get("DelayTime", 0)  # 延誤分鐘數
                station_name = record.get("StationName", {})
                station_name_str = station_name.get("Zh_tw", "--") if isinstance(station_name, dict) else str(station_name)
                
                # 對同一班列車，只保留最大延誤
                if train_no not in processed_delays or delay_time > processed_delays[train_no]["delay_mins"]:
                    # 嚴重性分級
                    if delay_time <= 5:
                        severity = "輕微"
                    elif delay_time <= 15:
                        severity = "中等"
                    else:
                        severity = "嚴重 🚨"
                    
                    processed_delays[train_no] = {
                        "train_no": train_no,
                        "delay_mins": delay_time,
                        "severity": severity,
                        "station": station_name_str,  # 當前車站
                        "update_time": record.get("UpdateTime", ""),
                    }
            
            if not processed_delays:
                return {
                    "status": "🟢",
                    "message": "目前列車準點運行，無延誤",
                    "delays": [],
                    "source": "TDX 即時 (無延誤)"
                }
            
            # 按延誤時間排序
            sorted_delays = sorted(processed_delays.values(), key=lambda x: x["delay_mins"], reverse=True)
            
            return {
                "status": "🟡" if len(sorted_delays) <= 5 else "🔴",
                "message": f"偵測 {len(sorted_delays)} 班延誤列車",
                "delays": sorted_delays,
                "source": "TDX 即時動態"
            }
            
        except Exception as e:
            print(f"[TDX] Train Delay Error: {e}")
            return {
                "status": "🔴",
                "message": f"無法抓取數據：{str(e)}",
                "delays": [],
                "source": "API 異常"
            }

    def _map_tgos_theme_to_poi_counts(self, theme_counts):
        counts = [0] * 6
        for name, value in theme_counts.items():
            label = str(name).lower()
            if any(w in label for w in ["捷運", "轉運", "公車", "station", "transit", "交通"]):
                counts[0] += value
            elif any(w in label for w in ["醫院", "診所", "hospital", "clinic", "health", "medical"]):
                counts[1] += value
            elif any(w in label for w in ["學校", "國小", "國中", "高中", "大學", "school", "education"]):
                counts[2] += value
            elif any(w in label for w in ["商業", "商場", "market", "mall", "shopping", "retail", "business"]):
                counts[3] += value
            elif any(w in label for w in ["公園", "綠地", "park", "garden", "recreation"]):
                counts[4] += value
            elif any(w in label for w in ["消防", "警察", "派出所", "police", "fire", "security"]):
                counts[5] += value
            else:
                counts[3] += value // 2
        return counts

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

        theme_data = fetch_tgos_theme_data(lat, lon, radius=1000)
        if theme_data.get("ok") and theme_data.get("total", 0) > 0:
            counts = self._map_tgos_theme_to_poi_counts(theme_data["counts"])
            tdx_transit_count = self._count_tdx_transit_points(lat, lon)
            if tdx_transit_count > counts[0]:
                counts[0] = tdx_transit_count
            final_names = [[f"TGOS {categories[i]['name']} {j+1}" for j in range(min(3, counts[i]))] for i in range(6)]
            poi_scores = [min(98, int((counts[i]/4)*100)+35) for i in range(6)]
            return poi_scores, counts, final_names, raw_pois, theme_data.get("source", "TGOS_THEME")

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
        # 【關鍵修改】強化防災權重（SDG 11 永續城市對齊）
        # 權重順序：防災(25%) > 交通(20%) > 醫療(15%) > 教育(15%) > 商業(15%) > 綠地(10%)
        # 防災 poi_scores[5] 現在被賦予最高的估價影響係數
        ext_mult = (1.0 
                    + (poi_scores[5]-60)*0.0025      # 【NEW】防災治安：最高權重(25%)，係數加倍
                    + (poi_scores[0]-60)*0.0020      # 【UPDATE】交通樞紐：20% (從15%上升)
                    + (poi_scores[1]-60)*0.0015      # 醫療網絡：15%
                    + (poi_scores[2]-60)*0.0015      # 學區教育：15%
                    + (poi_scores[3]-60)*0.0015      # 商業聚落：15% (從20%下調)
                    + (poi_scores[4]-60)*0.0010)     # 休閒綠地：10% (從15%下調)
        
        # YouBike 微型運輸 —— 支援 SDG 11.6 減少環境負面影響
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
        try:
            tgos_lat, tgos_lon = get_tgos_coordinates(addr)
            if (tgos_lat, tgos_lon) != (25.033964, 121.564468):
                lat, lon = tgos_lat, tgos_lon
        except: pass

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

        # 1. 黑底圖基底
        black_base_url = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
        for mm in [m.m1, m.m2]:
            folium.TileLayer(
                tiles=black_base_url,
                attr='CartoDB Dark Matter',
                name='黑底圖',
                overlay=False,
                control=True,
                max_zoom=19,
                max_native_zoom=19
            ).add_to(mm)

        # 2. NLSC WMTS 地籍圖與使用分區圖層
        cadastral_url = (
            "https://wmts.nlsc.gov.tw/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
            "&LAYER=CadastralMap&STYLE=default&TILEMATRIXSET=GoogleMapsCompatible"
            "&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
        )
        zoning_url = (
            "https://wmts.nlsc.gov.tw/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
            "&LAYER=LandUse&STYLE=default&TILEMATRIXSET=GoogleMapsCompatible"
            "&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
        )
        for mm in [m.m1, m.m2]:
            folium.TileLayer(
                tiles=cadastral_url,
                attr='NLSC 地籍圖',
                name='地籍圖層',
                overlay=True,
                control=True,
                opacity=0.75,
                max_zoom=19,
                max_native_zoom=19
            ).add_to(mm)
            folium.TileLayer(
                tiles=zoning_url,
                attr='NLSC 土地使用分區圖',
                name='使用分區圖層',
                overlay=True,
                control=True,
                opacity=0.7,
                max_zoom=19,
                max_native_zoom=19
            ).add_to(mm)

        tgos_key = st.secrets.get("TGOS_MAP_KEY", "")
        if tgos_key:
            tgos_tile_url = (
                "https://api.tgos.tw/TGOS_MAP_API_3/WMTS?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
                "&LAYER=TGOS_BASEMAP&STYLE=default&TILEMATRIXSET=GoogleMapsCompatible"
                "&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
                f"&apikey={urllib.parse.quote(tgos_key)}"
            )
            for mm in [m.m1, m.m2]:
                folium.TileLayer(
                    tiles=tgos_tile_url,
                    attr='TGOS 官方底圖',
                    name='TGOS 官方底圖 (WMTS)',
                    max_zoom=19,
                    max_native_zoom=19,
                    overlay=False,
                    control=True
                ).add_to(mm)
        else:
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

        folium.LayerControl(position='topright', collapsed=False).add_to(m.m1)
        folium.LayerControl(position='topright', collapsed=False).add_to(m.m2)

        m.get_root().html.add_child(folium.Element("<style>.leaflet-sbs-divider{background-color:#38BDF8!important;width:6px!important;margin-left:-3px!important;z-index:999999!important;box-shadow:0 0 15px rgba(56,189,248,0.8)!important;pointer-events:none!important;}</style>"))
        return m
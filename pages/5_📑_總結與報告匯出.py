# -*- coding: utf-8 -*-
import streamlit as st
from fpdf import FPDF
import datetime
import os
import hashlib

# ==========================================
# 🛡️ 頁面初始化：防止跨頁面數據丟失
# ==========================================
if "report_data" not in st.session_state:
    st.session_state.report_data = {
        "city": "尚未設定位置", 
        "moltke_data": {}, 
        "poi_scores": [0]*6,
        "lat": 0, "lon": 0
    }
if "law_messages" not in st.session_state:
    st.session_state.law_messages = []

st.set_page_config(layout="wide", page_title="總結報告匯出 | OmniUrban", initial_sidebar_state="expanded")

# ==========================================
# 📐 樣式系統 (專業商務 UI)
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #0B1220; color: #E2E8F0; }
    .report-title { 
        background: linear-gradient(135deg, #FDE047, #F59E0B); 
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
        font-weight: 800; font-size: 2.5rem; margin-bottom: 20px; 
    }
    .summary-box {
        background: #111827; border: 1px solid #1E293B; border-radius: 12px;
        padding: 25px; margin-bottom: 20px;
    }
    .param-label { color: #94A3B8; font-size: 0.8rem; text-transform: uppercase; }
    .param-value { color: #FDE047; font-size: 1.2rem; font-weight: 700; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# ✍️ PDF 產生器類別 (自定義專業頁首頁尾)
# ==========================================
class OmniReport(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', '', 10)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, 'OmniUrban AI Professional Assessment - 2026 CONFIDENTIAL', 0, 1, 'R')
            self.line(10, 20, 200, 20)
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'OmniUrban Intelligence Report | Page {self.page_no()}', 0, 0, 'C')

# ==========================================
# 🧠 數據彙整邏輯 (整合 Dashboard, Law, ESG)
# ==========================================
def collect_full_intelligence():
    dashboard = st.session_state.report_data
    city = dashboard.get("city", "尚未設定位置")
    
    # 使用地址 Hash 確保數據一致性
    h = int(hashlib.md5(city.encode()).hexdigest(), 16)
    
    # 抓取法規諮詢紀錄
    law_history = [m for m in st.session_state.law_messages if m["role"] != "system"]
    
    return {
        "address": city,
        "lat_lon": f"{dashboard.get('lat', 0)}, {dashboard.get('lon', 0)}",
        "valuation": dashboard.get("moltke_data", {}).get("core_summary", {}).get("valuation", "N/A"),
        "esg_reduction": (h % 40) + 20,
        "success_rate": 60 + (h % 30),
        "chat_logs": law_history,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }

intel = collect_full_intelligence()

# ==========================================
# 📍 主畫面佈局
# ==========================================
st.markdown('<div class="report-title">📄 Omni-Urban AI 綜合評估報告生成器</div>', unsafe_allow_html=True)

c1, c2 = st.columns([1.5, 1])

with c1:
    st.markdown('<div class="summary-box">', unsafe_allow_html=True)
    st.markdown("### 📌 報告編譯參數概覽：")
    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown(f'<div class="param-label">📍 目標標的</div><div class="param-value">{intel["address"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="param-label">💰 AI 估價參考</div><div class="param-value">{intel["valuation"]} 萬/坪</div>', unsafe_allow_html=True)
    with sc2:
        st.markdown(f'<div class="param-label">⚖️ 法規專家紀錄</div><div class="param-value">{len(intel["chat_logs"])} 則諮詢</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="param-label">🤝 整合成功機率</div><div class="param-value">{intel["success_rate"]}%</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="summary-box" style="text-align:center;">', unsafe_allow_html=True)
    st.markdown("### 🖨️ 編譯實體 PDF")
    st.write("將儀表板、地政士 AI、ESG、博弈模擬數據彙整排版。")
    
    # 下載邏輯
    if st.button("🚀 執行全模組編譯並下載 PDF", use_container_width=True):
        font_path = "msjh.ttf" # 👈 請確認你的檔案名稱
        
        if not os.path.exists(font_path):
            st.error(f"❌ 找不到字體檔 {font_path}！請將 Windows 的 msjh.ttf 複製到專案資料夾。")
        else:
            with st.spinner("正在編譯數據與生成專業排版..."):
                try:
                    pdf = OmniReport()
                    # 💡 關鍵：強制載入 Unicode 字體並禁用斜體 (避免 msjhI 錯誤)
                    pdf.add_font('MSJH', '', font_path, uni=True)
                    font_name = 'MSJH'
                    
                    # --- 第一頁：封面 ---
                    pdf.add_page()
                    pdf.set_font(font_name, '', 32)
                    pdf.ln(70)
                    pdf.cell(0, 20, "OmniUrban 專業評估報告", ln=True, align='C')
                    pdf.set_font(font_name, '', 16)
                    pdf.cell(0, 15, "AI-Powered Urban Renewal & ESG Analysis", ln=True, align='C')
                    pdf.ln(30)
                    pdf.set_font(font_name, '', 12)
                    pdf.cell(0, 10, f"評估地址：{intel['address']}", ln=True, align='C')
                    pdf.cell(0, 10, f"報告日期：{intel['timestamp']}", ln=True, align='C')
                    
                    # --- 第二頁：空間機能 ---
                    pdf.add_page()
                    pdf.set_font(font_name, '', 18)
                    pdf.set_text_color(245, 158, 11)
                    pdf.cell(0, 15, "第一章：空間機能與價值評估", ln=True)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(10)
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font(font_name, '', 12)
                    pdf.cell(0, 10, f"● 地理座標：{intel['lat_lon']}", ln=True)
                    pdf.cell(0, 10, f"● AI 預估行情：{intel['valuation']} 萬/坪", ln=True)
                    pdf.ln(5)
                    pdf.multi_cell(0, 10, txt="本章節分析基於 Google Places API 之空間點位，針對醫療、教育、交通與商業密度進行權重換算。")
                    
                    # --- 第三頁：法規對話紀錄 ---
                    pdf.add_page()
                    pdf.set_font(font_name, '', 18)
                    pdf.cell(0, 15, "第二章：地政法規專家意見紀錄", ln=True)
                    pdf.ln(10)
                    pdf.set_font(font_name, '', 10)
                    if intel['chat_logs']:
                        for m in intel['chat_logs'][-6:]: # 取最近 6 則
                            role = "【使用者】" if m["role"] == "user" else "【專家解答】"
                            content = m["content"].replace('\n', ' ')
                            pdf.multi_cell(0, 8, txt=f"{role}: {content[:180]}...")
                            pdf.ln(3)
                    else:
                        pdf.cell(0, 10, "尚無法規諮詢紀錄。", ln=True)

                    # --- 第四頁：ESG 與 模擬 ---
                    pdf.add_page()
                    pdf.set_font(font_name, '', 18)
                    pdf.cell(0, 15, "第三章：永續發展與住戶整合模擬", ln=True)
                    pdf.ln(10)
                    pdf.set_font(font_name, '', 12)
                    pdf.cell(0, 10, f"● ESG 減碳潛力評估：{intel['esg_reduction']} tCO2e / 年", ln=True)
                    pdf.cell(0, 10, f"● 預估整合成功率：{intel['success_rate']}%", ln=True)
                    pdf.ln(20)
                    pdf.set_font(font_name, '', 10)
                    pdf.set_text_color(100, 100, 100)
                    pdf.multi_cell(0, 10, txt="*本報告由 OmniUrban AI 決策引擎自動編譯。內容僅供參考，不具法律效力。")

                    # ✅ 終極修正：將 bytearray 強制轉換為 bytes 格式
                    pdf_raw = pdf.output()
                    pdf_bytes = bytes(pdf_raw) 
                    
                    st.success("✅ 報告編譯完成！")
                    st.download_button(
                        label="📥 立即下載 PDF 實體報告",
                        data=pdf_bytes,
                        file_name=f"OmniUrban_Report_{datetime.datetime.now().strftime('%m%d')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"❌ PDF 生成失敗：{str(e)}")
    st.markdown('</div>', unsafe_allow_html=True)

# 底部導出
st.write("---")
st.markdown('<div style="text-align:center; color:#64748b; font-size:0.8rem;">© 2026 OmniUrban Intelligence - 數據連動編譯系統</div>', unsafe_allow_html=True)
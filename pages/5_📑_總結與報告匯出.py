# -*- coding: utf-8 -*-
import streamlit as st
from fpdf import FPDF
import datetime
import os
import hashlib
import plotly.graph_objects as go
import tempfile

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
# 🧠 數據彙整邏輯 (整合 Dashboard, Law, ESG, SDG 11)
# ==========================================
def collect_full_intelligence():
    dashboard = st.session_state.report_data
    city = dashboard.get("city", "尚未設定位置")
    
    # 使用地址 Hash 確保數據一致性
    h = int(hashlib.md5(city.encode()).hexdigest(), 16)
    
    # 抓取法規諮詢紀錄
    law_history = [m for m in st.session_state.law_messages if m["role"] != "system"]
    
    # 【新增】SDG 11 相關數據
    poi_scores = dashboard.get("poi_scores", [60]*6)
    disaster_resilience = poi_scores[5] if len(poi_scores) > 5 else 60
    
    return {
        "address": city,
        "lat_lon": f"{dashboard.get('lat', 0)}, {dashboard.get('lon', 0)}",
        "valuation": dashboard.get("moltke_data", {}).get("core_summary", {}).get("valuation", "N/A"),
        "esg_reduction": (h % 40) + 20,
        "success_rate": 60 + (h % 30),
        "disaster_resilience": disaster_resilience,
        "chat_logs": law_history,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }

# ==========================================
# 📊 圖表生成函數 (用於PDF嵌入)
# ==========================================
def generate_esg_charts(intel):
    # 模擬ESG數據
    h = int(hashlib.md5(intel["address"].encode()).hexdigest(), 16)
    area = 30 + (h % 60)
    carbon_rebuild = area * 1.15
    carbon_renovate = area * 0.28
    
    poi_scores = st.session_state.report_data.get("poi_scores", [50]*6)
    social_score = (poi_scores[1] * 0.35 + poi_scores[2] * 0.25 + poi_scores[4] * 0.25 + poi_scores[5] * 0.30)
    elderly_friendly = poi_scores[1] * 0.6 + poi_scores[4] * 0.4
    
    # 雷達圖數據
    radar_dims = ["低碳節能", "高齡友善", "社會影響", "防災韌性", "生物多樣"]
    radar_vals = [50 + (h % 45), int(elderly_friendly), int(social_score), poi_scores[5] if len(poi_scores) > 5 else 60, 30 + (len([]) * 12)]
    
    # 生成雷達圖
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_vals + [radar_vals[0]], theta=radar_dims + [radar_dims[0]],
        fill='toself', fillcolor='rgba(16, 185, 129, 0.2)',
        line=dict(color='#10B981', width=2.5)
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False, paper_bgcolor='white', plot_bgcolor='white',
        width=400, height=300, margin=dict(l=20,r=20,t=20,b=20)
    )
    
    # 碳中和圖
    yrs = list(range(0, 21))
    reb = [carbon_rebuild + (i * 0.4) for i in yrs]
    ren = [carbon_renovate + (i * 1.8) for i in yrs]
    
    fig_carbon = go.Figure()
    fig_carbon.add_trace(go.Scatter(x=yrs, y=reb, name="重建路徑", line=dict(color='#3B82F6', width=3)))
    fig_carbon.add_trace(go.Scatter(x=yrs, y=ren, name="整建路徑", line=dict(color='#94A3B8', width=2, dash='dot')))
    fig_carbon.update_layout(
        paper_bgcolor='white', plot_bgcolor='white',
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        width=400, height=250, margin=dict(l=20,r=20,t=20,b=20),
        xaxis=dict(title="評估年份"),
        yaxis=dict(title="累積碳排 (tCO2e)")
    )
    
    # 保存圖表為臨時文件
    with tempfile.TemporaryDirectory() as temp_dir:
        radar_path = os.path.join(temp_dir, "radar_chart.png")
        carbon_path = os.path.join(temp_dir, "carbon_chart.png")
        
        try:
            fig_radar.write_image(radar_path, format="png", scale=2)
            fig_carbon.write_image(carbon_path, format="png", scale=2)
            return radar_path, carbon_path
        except Exception as e:
            print(f"[PDF] Plotly image export failed: {e}")
            return None, None

intel = collect_full_intelligence()

# ==========================================
# 📍 主畫面佈局
# ==========================================
st.markdown('<div class="report-title">📄 Omni-Urban AI 綜合評估報告<br><span style="font-size:0.55em; color:#34d399;">SDG 11 永續城市貢獻度量化與決策文件</span></div>', unsafe_allow_html=True)

c1, c2 = st.columns([1.5, 1])

with c1:
    st.markdown('<div class="summary-box">', unsafe_allow_html=True)
    st.markdown("### 📌 報告編譯參數概覽（SDG 11 導向）：")
    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown(f'<div class="param-label">📍 目標標的</div><div class="param-value">{intel["address"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="param-label">💰 AI 估價參考</div><div class="param-value">{intel["valuation"]} 萬/坪</div>', unsafe_allow_html=True)
    with sc2:
        st.markdown(f'<div class="param-label">⚖️ 法規專家紀錄</div><div class="param-value">{len(intel["chat_logs"])} 則諮詢</div>', unsafe_allow_html=True)
        disaster_color = "#10B981" if intel["disaster_resilience"] >= 80 else "#F59E0B" if intel["disaster_resilience"] >= 60 else "#EF4444"
        st.markdown(f'<div class="param-label">🚨 防災韌性評分 (SDG 11.5)</div><div style="font-size:1.2rem; font-weight:700; color:{disaster_color};">{intel["disaster_resilience"]}</div>', unsafe_allow_html=True)
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
                    # 生成圖表
                    radar_chart_path, carbon_chart_path = generate_esg_charts(intel)
                    
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
                    pdf.multi_cell(0, 10, txt="本章節分析基於 TGOS 內政主題 API 之空間點位，針對醫療、教育、交通與商業密度進行權重換算。")
                    
                    # --- 第三頁：ESG 圖表 ---
                    pdf.add_page()
                    pdf.set_font(font_name, '', 18)
                    pdf.set_text_color(16, 185, 129)
                    pdf.cell(0, 15, "第二章：ESG 永續評估視覺化", ln=True)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(10)
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font(font_name, '', 12)
                    pdf.cell(0, 10, "SDG 11 五維度永續評估雷達圖：", ln=True)
                    pdf.ln(5)
                    if radar_chart_path and carbon_chart_path:
                        pdf.image(radar_chart_path, x=10, y=pdf.get_y(), w=90)
                        pdf.ln(80)
                        pdf.cell(0, 10, "碳中和路徑比較圖：", ln=True)
                        pdf.ln(5)
                        pdf.image(carbon_chart_path, x=10, y=pdf.get_y(), w=90)
                    else:
                        pdf.set_font(font_name, '', 11)
                        pdf.multi_cell(0, 8, txt="⚠️ 目前無法生成圖表圖檔。請安裝 Kaleido 或更新環境後重新生成 PDF。")
                    
                    # --- 第四頁：法規對話紀錄 ---
                    pdf.add_page()
                    pdf.set_font(font_name, '', 18)
                    pdf.cell(0, 15, "第三章：地政法規專家意見紀錄", ln=True)
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

                    # --- 第五頁：ESG 與 模擬 ---
                    pdf.add_page()
                    pdf.set_font(font_name, '', 18)
                    pdf.set_text_color(245, 158, 11)
                    pdf.cell(0, 15, "第四章：聯合國永續發展目標（SDG 11）貢獻度", ln=True)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(10)
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font(font_name, '', 11)
                    pdf.multi_cell(0, 8, txt="OmniUrban 系統將都市更新評估深度整合聯合國 SDG 11「永續城市與社區」框架，確保以下貢獻：")
                    pdf.ln(5)
                    pdf.set_font(font_name, '', 10)
                    pdf.cell(0, 6, "✓ 11.1 安全可負擔住房（防灾韌性優先評估，提升居家安全）", ln=True)
                    pdf.cell(0, 6, "✓ 11.3 包容性永續都市規劃（資訊透明化，多方利益相關者參與）", ln=True)
                    pdf.cell(0, 6, "✓ 11.5 減少災害損失（消防通行能力評估，防灾改善補貼）", ln=True)
                    pdf.cell(0, 6, "✓ 11.6 環境影響與綠色運輸（碳排減量、公共運輸整合分析）", ln=True)
                    pdf.cell(0, 6, "✓ 11.7 安全包容綠色公共空間（高齡友善設計，社區參與）", ln=True)
                    pdf.ln(10)
                    pdf.set_font(font_name, '', 10)
                    pdf.cell(0, 8, f"● ESG 減碳潛力評估：{intel['esg_reduction']} tCO2e / 年", ln=True)
                    pdf.cell(0, 8, f"● 預估整合成功率：{intel['success_rate']}%", ln=True)
                    pdf.cell(0, 8, "● 防災韌性評等：已整合至決策模型，優先考量消防、警力、地震防災", ln=True)

                    # --- 第六頁：永續與社會責任 ---
                    pdf.add_page()
                    pdf.set_font(font_name, '', 18)
                    pdf.cell(0, 15, "第五章：永續發展與住戶整合模擬", ln=True)
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
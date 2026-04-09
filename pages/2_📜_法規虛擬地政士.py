# -*- coding: utf-8 -*-
import streamlit as st
from openai import OpenAI
import time
from utils.engines import search_law_articles, fetch_moj_law_json, prepare_law_context, explain_law_with_ai

st.set_page_config(layout="wide", page_title="法規虛擬地政士 | OmniUrban", initial_sidebar_state="expanded")

# ==========================================
# 📐 樣式與動畫系統
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #0B1220; color: #E5E7EB; font-family: 'Inter', sans-serif; }
    .hero-title { 
        background: linear-gradient(135deg, #FDE047, #F59E0B);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 900; font-size: 2.8rem; letter-spacing: -0.04em; margin-bottom: 8px;
    }
    .hero-subtitle { color: #94A3B8; font-size: 0.95rem; margin-bottom: 24px; line-height: 1.6; }
    .section-card {
        background: #111827; border: 1px solid #334155; border-radius: 18px;
        padding: 24px; box-shadow: 0 20px 50px rgba(0,0,0,0.15); margin-bottom: 24px;
    }
    .token-card {
        background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
        border: 1px solid #334155; border-radius: 16px;
        padding: 18px; margin-top: 20px; text-align: center;
    }
    .token-val { font-size: 2rem; font-weight: 800; color: #14B8A6; }
    .status-pill {
        display: inline-flex; align-items: center; gap: 8px;
        padding: 8px 12px; border-radius: 999px; background: #111827;
        color: #94a3b8; font-size: 0.85rem; border: 1px solid #334155;
    }
    .sidebar-note { color: #94A3B8; font-size: 0.85rem; margin-top: 10px; }
    .stChatMessage { background-color: transparent !important; }
    .stChatMessage[data-testid="chatAvatarIcon-assistant"] {
        background-color: #111827 !important; border-left: 4px solid #F59E0B;
        border-radius: 0 12px 12px 0; padding: 18px; box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    }
    .stChatMessage[data-testid="chatAvatarIcon-user"] {
        background-color: #111827 !important; border-right: 4px solid #38BDF8;
        border-radius: 12px 0 0 12px; padding: 18px; box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }
    .stChatMessage p { margin: 0; color: #E5E7EB; }
    .model-card { background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 18px; }
    .model-title { font-size: 0.95rem; color: #94A3B8; margin-bottom: 8px; }
    .model-item { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .model-badge { font-size: 0.8rem; color: #94A3B8; }
    .model-badge.active { color: #34D399; }
    .model-badge.offline { color: #F97316; }
    .streamlit-expanderHeader { background: #111827 !important; border: 1px solid #334155 !important; border-radius: 10px !important; color: #E5E7EB !important; }
    .streamlit-expanderContent { background: #0f172a !important; border: 1px solid #334155 !important; border-top: none !important; border-radius: 0 0 10px 10px !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero-title">⚖️ 專業法規虛擬地政士<br><span class="hero-subtitle">整合多模型共識、法條驗證、實務建議與透明報告，讓都更與權利分析不留任何模糊空間。</span></div>', unsafe_allow_html=True)

# ==========================================
# 📊 Token 用量初始化
# ==========================================
if "session_tokens" not in st.session_state:
    st.session_state.session_tokens = 0

# ==========================================
# 🧠 2026 專家核心：自動修正 API 路由
# ==========================================
def get_client(provider):
    try:
        keys = st.secrets
        
        # 1. Groq 
        if provider == "⚡ Groq (Llama 3.3)":
            api_key = keys.get("GROQ_API_KEY", "")
            if not api_key: return None, None
            return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1"), "llama-3.3-70b-versatile"
        
        # (已將 Gemini 徹底剔除)

        # 2. GitHub (GPT-4o)
        elif provider == "🐙 GitHub (GPT-4o)":
            api_key = keys.get("GITHUB_TOKEN", "")
            if not api_key: return None, None
            return OpenAI(api_key=api_key, base_url="https://models.inference.ai.azure.com"), "gpt-4o"
            
        # 3. Cohere 
        elif provider == "🪶 Cohere (Command-R)":
            api_key = keys.get("COHERE_API_KEY", "")
            if not api_key: return None, None
            return OpenAI(api_key=api_key, base_url="https://api.cohere.ai/compatibility/v1"), "command-r-plus-08-2024"
        
        # 4. OpenRouter 
        elif provider == "🌌 OpenRouter (聚合神器)":
            api_key = keys.get("OPENROUTER_API_KEY", "")
            if not api_key: return None, None
            return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1"), "qwen/qwen3.6-plus:free"
        
        # 5. SambaNova 
        elif provider == "🚀 SambaNova (DeepSeek-R1)":
            api_key = keys.get("SAMBANOVA_API_KEY", "")
            if not api_key: return None, None
            return OpenAI(api_key=api_key, base_url="https://api.sambanova.ai/v1"), "DeepSeek-R1"
            
        # 6. Cerebras
        elif provider == "🧠 Cerebras (極速算力)":
            api_key = keys.get("CEREBRAS_API_KEY", "")
            if not api_key: return None, None
            return OpenAI(api_key=api_key, base_url="https://api.cerebras.ai/v1"), "llama3.1-8b"

    except Exception as e:
        return None, None
    return None, None

# ==========================================
# 側邊欄配置
# ==========================================
st.sidebar.markdown("### 🧠 專家委員會")
use_groq = st.sidebar.checkbox("⚡ Groq (Llama 3.3)", value=True)
# Google 選單已刪除
use_github = st.sidebar.checkbox("🐙 GitHub (GPT-4o)", value=True)
use_cohere = st.sidebar.checkbox("🪶 Cohere (Command-R)", value=False)
use_openrouter = st.sidebar.checkbox("🌌 OpenRouter (聚合神器)", value=False)
use_sambanova = st.sidebar.checkbox("🚀 SambaNova (DeepSeek-R1)", value=True)
use_cerebras = st.sidebar.checkbox("🧠 Cerebras (極速算力)", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ 操作設定")
enable_ensemble = st.sidebar.checkbox("🔥 啟動「多模型共識決合議」", value=True)

st.sidebar.markdown(f"""
    <div class="token-card">
        <div style="color:#64748b; font-size:0.78rem; letter-spacing:0.08em;">SESSION TOKENS</div>
        <div class="token-val">{st.session_state.session_tokens:,}</div>
    </div>
    <div class="sidebar-note">請先確認所有 API 金鑰已於 `.streamlit/secrets.toml` 正確設定。若未設定，將自動跳過該模型。</div>
""", unsafe_allow_html=True)

# ==========================================
# 📜 指令系統 (Prompts)
# ==========================================
EXPERT_PROMPT = """你是一位經驗豐富的台灣地政士，專長於《土地法》與《都更條例》。
請精確指出法條，並給予實務建議。若涉及比例，請嘗試以數據描述。

【重點指引】本系統遵循聯合國 SDG 11.3（包容性與可持續都市規劃），強調：
- 資訊完全透明化：所有法規解釋需附加條文編號
- 利益相關者包容：重視弱勢住戶、租戶、及周邊社區之聲音
- 防災優先：都市更新應首先考慮建物安全與災害韌性

【嚴格準確性要求】：
- 絕對禁止生成虛構或錯誤的法律條文
- 每個法條引用必須包含完整名稱和條號，例如：《土地法》第12條
- 如果不確定某條文，請明確說明「需要查詢官方來源」
- 優先使用台灣現行有效法律，避免引用已廢止條文
- 所有建議必須基於現實法律框架，不得編造"""

SYNTHESIZER_PROMPT = """你現在是 OmniUrban 首席總編輯。
我會提供數位專家的法律分析，請你：
1. 交叉比對找出共識。
2. 修正任何明顯的法條誤植（防幻覺），特別檢查條文編號是否正確。
3. 統合成一份給客戶的最終權威報告。
4. 如果發現任何不一致或潛在錯誤，請在報告中明確標註並建議查詢官方來源。
5. 確保所有法條引用都包含完整名稱和條號。"""

# ==========================================
# 💬 對話與邏輯
# ==========================================
if "law_messages" not in st.session_state:
    st.session_state.law_messages = [{"role": "assistant", "content": "你好！我是 OmniUrban 專家合議地政士，由全球 AI 顧問團隊支持。\n\n本系統遵循「資訊透明化與包容性都市規劃」原則（聯合國 SDG 11.3），確保：\n✅ 所有法規解釋都 100% 透明（附條文編號）\n✅ 充分考慮所有利益相關者（住戶、租戶、社區）\n✅ 防災與安全優先（SDG 11.5）\n\n⚠️ **重要免責聲明**：本系統提供的資訊僅供參考，不構成正式法律意見。所有法規解釋均應以官方公布版本為準，建議諮詢專業地政士或律師取得最終確認。\n\n現在，你可以詢問任何關於土地法規、都市更新、產權糾紛的問題！"}]

st.markdown('<div class="section-card"><div class="model-title">📌 使用說明</div><div style="color:#cbd5e1; font-size:0.93rem; line-height:1.8;">選擇可用模型後，請直接在下方輸入法規問題。系統將自動呼叫多模型合議，並以「法條編號+實務建議」方式回應。</div></div>', unsafe_allow_html=True)

# ==========================================
# 🔎 法規檢索與 AI 解析（RAG 架構）
# ==========================================
if "rag_query" not in st.session_state:
    st.session_state.rag_query = ""
if "rag_results" not in st.session_state:
    st.session_state.rag_results = []
if "rag_analysis" not in st.session_state:
    st.session_state.rag_analysis = ""
if "rag_selected_code" not in st.session_state:
    st.session_state.rag_selected_code = ""

with st.expander("🔎 法規檢索與 AI 解析（RAG 架構）", expanded=True):
    st.markdown(
        "本模組使用開源 MojLawSplit 法規 JSON 進行精確檢索，再由 LLM 解析結果。\n"
        "- 先搜尋法規標題與條文內容，避免單純憑空產生。\n"
        "- 若搜尋到法條，請點選「解析此法規」取得依據原文的解釋。\n"
        "- 目前支援 `GEMINI_API_KEY`、`GROQ_API_KEY`。"
    )
    cols = st.columns([4, 1])
    with cols[0]:
        rag_query = st.text_input("法規檢索關鍵字或條號", value=st.session_state.rag_query,
                                  placeholder="例如：土地法 第6條、不動產登記、A0060001")
    with cols[1]:
        rag_provider = st.selectbox("解析模型", ["Gemini", "Groq"], index=0)
    if st.button("執行檢索", key="rag_search"):
        st.session_state.rag_query = rag_query
        st.session_state.rag_results = search_law_articles(rag_query, max_results=5)
        st.session_state.rag_analysis = ""
        st.session_state.rag_selected_code = ""

    if st.session_state.rag_results:
        st.markdown("### 檢索結果：")
        for idx, item in enumerate(st.session_state.rag_results):
            with st.expander(f"{item['code']} {item['law_name']}"):
                st.markdown(item['match_excerpt'].replace("\n", "  \n"))
                st.markdown(f"- GitHub JSON：[{item['code']}]({item['github_url']})")
                if st.button(f"解析此法規 {item['code']}", key=f"rag_parse_{item['code']}"):
                    law_json = fetch_moj_law_json(item['code'])
                    if law_json:
                        context = prepare_law_context(law_json, st.session_state.rag_query)
                        st.session_state.rag_analysis = explain_law_with_ai(context, st.session_state.rag_query, provider=rag_provider)
                        st.session_state.rag_selected_code = item['code']
                    else:
                        st.session_state.rag_analysis = "無法載入法規原文，請稍後再試。"
    elif st.session_state.rag_query:
        st.markdown("⚠️ 找不到符合的法規，請改用更具體的條號或關鍵字，例如：土地法 第6條、地政士法、A0060001。")

    if st.session_state.rag_analysis:
        st.markdown("### AI 解析結果（依據 MojLawSplit 原始法條）")
        st.markdown(st.session_state.rag_analysis)

for msg in st.session_state.law_messages:
    avatar = "⚖️" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

if prompt := st.chat_input("請詢問法規問題..."):
    providers = []
    if use_groq: providers.append("⚡ Groq (Llama 3.3)")
    if use_github: providers.append("🐙 GitHub (GPT-4o)")
    if use_cohere: providers.append("🪶 Cohere (Command-R)")
    if use_openrouter: providers.append("🌌 OpenRouter (聚合神器)")
    if use_sambanova: providers.append("🚀 SambaNova (DeepSeek-R1)")
    if use_cerebras: providers.append("🧠 Cerebras (極速算力)")

    st.session_state.law_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): st.markdown(prompt)

    with st.chat_message("assistant", avatar="⚖️"):
        placeholder = st.empty()
        
        # 🛡️ 防呆檢查：如果完全沒選模型
        if not providers:
            placeholder.markdown("⚠️ **請至少在側邊欄選擇一位專家！**")
        
        elif enable_ensemble:
            expert_responses = {}
            for p in providers:
                client, model = get_client(p)
                if not client: 
                    expert_responses[p] = "該專家目前無回應（金鑰未設定或連線異常）。"
                    continue
                
                placeholder.markdown(f"⏳ **{p}** 正在檢索法條中...")
                try:
                    res = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": EXPERT_PROMPT}, {"role": "user", "content": prompt}],
                        temperature=0.1
                    )
                    if res.choices and len(res.choices) > 0:
                        expert_responses[p] = res.choices[0].message.content
                        st.session_state.session_tokens += res.usage.total_tokens if res.usage else 500
                    else:
                        expert_responses[p] = "該專家目前無回應（內容過濾中）。"
                except Exception as e:
                    expert_responses[p] = f"連線異常：{str(e)}"
            
            # 總編輯統整
            placeholder.markdown("🧠 正在進行 **跨模型共識分析與幻覺修復**...")
            chief_client, chief_model = get_client("⚡ Groq (Llama 3.3)") 
            
            synthesis_input = f"問題：{prompt}\n\n專家意見如下：\n"
            for p, ans in expert_responses.items(): synthesis_input += f"--- {p} ---\n{ans}\n\n"
            
            # 🛡️ 防呆檢查：如果總編輯 Groq 未就緒，啟用回退機制 (Fallback)
            if not chief_client:
                valid_responses = [ans for p, ans in expert_responses.items() if "連線異常" not in ans and "無回應" not in ans]
                if valid_responses:
                    full_res = f"> ⚠️ **總編輯 (Groq) 連線異常，啟用備援輸出：**\n\n{valid_responses[0]}"
                else:
                    full_res = "❌ 所有專家皆無法連線，請檢查 API 金鑰設定是否正確。"
                
                placeholder.markdown(full_res)
                st.session_state.law_messages.append({"role": "assistant", "content": full_res})
            else:
                try:
                    stream = chief_client.chat.completions.create(
                        model=chief_model,
                        messages=[{"role": "system", "content": SYNTHESIZER_PROMPT}, {"role": "user", "content": synthesis_input}],
                        stream=True
                    )
                    full_res = "> **⚖️ OmniUrban 跨模型專家合議報告**\n\n"
                    for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            full_res += chunk.choices[0].delta.content
                            placeholder.markdown(full_res + "▌")
                    placeholder.markdown(full_res)
                    st.session_state.law_messages.append({"role": "assistant", "content": full_res})
                except Exception as e:
                    placeholder.markdown(f"❌ 統整失敗：{e}")

        else:
            # 單一模式
            p = providers[0]
            client, model = get_client(p)
            
            # 🛡️ 防呆檢查：單一模式連線失敗阻斷
            if not client:
                placeholder.markdown(f"❌ 無法載入 **{p}**，請確認 `.streamlit/secrets.toml` 中是否正確設定了對應的 API 金鑰。")
            else:
                try:
                    stream = client.chat.completions.create(model=model, messages=[{"role": "system", "content": EXPERT_PROMPT}, {"role": "user", "content": prompt}], stream=True)
                    full_res = f"*(由 {p} 提供)*\n\n"
                    for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            full_res += chunk.choices[0].delta.content
                            placeholder.markdown(full_res + "▌")
                    placeholder.markdown(full_res)
                    st.session_state.law_messages.append({"role": "assistant", "content": full_res})
                except Exception as e:
                    placeholder.markdown(f"❌ {p} 連線失敗：{e}")
# -*- coding: utf-8 -*-
import streamlit as st
from openai import OpenAI
import time

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
        font-weight: 800; font-size: 2.5rem; letter-spacing: -0.03em; margin-bottom: 10px; 
    }
    .stChatMessage { background-color: transparent !important; }
    .stChatMessage[data-testid="chatAvatarIcon-assistant"] {
        background-color: #1E293B !important; border-left: 4px solid #F59E0B; 
        border-radius: 0 12px 12px 0; padding: 15px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .token-card {
        background: #111827; border: 1px solid #334155; border-radius: 8px;
        padding: 15px; margin-top: 20px; text-align: center;
    }
    .token-val { font-size: 1.8rem; font-weight: 700; color: #14B8A6; }
    </style>
""", unsafe_allow_html=True)

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
enable_ensemble = st.sidebar.checkbox("🔥 啟動「多模型共識決合議」", value=True)

st.sidebar.markdown(f"""
    <div class="token-card">
        <div style="color:#64748b; font-size:0.7rem;">SESSION TOKENS</div>
        <div class="token-val">{st.session_state.session_tokens:,}</div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 📜 指令系統 (Prompts)
# ==========================================
EXPERT_PROMPT = """你是一位經驗豐富的台灣地政士，專長於《土地法》與《都更條例》。
請精確指出法條，並給予實務建議。若涉及比例，請嘗試以數據描述。"""

SYNTHESIZER_PROMPT = """你現在是 OmniUrban 首席總編輯。
我會提供數位專家的法律分析，請你：
1. 交叉比對找出共識。
2. 修正任何明顯的法條誤植（防幻覺）。
3. 統合成一份給客戶的最終權威報告。"""

# ==========================================
# 💬 對話與邏輯
# ==========================================
if "law_messages" not in st.session_state:
    st.session_state.law_messages = [{"role": "assistant", "content": "你好，奕陽！我已經召集了全球各大 AI 專家。現在你可以問我任何關於土地法規、永和都更或是產權糾紛的問題了！"}]

st.markdown('<div class="hero-title">⚖️ 專家合議地政士 (2026)</div>', unsafe_allow_html=True)

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
import streamlit as st
import pandas as pd
import random
import time
import json
import os
import re
import base64
from gtts import gTTS
from io import BytesIO
try:
    import docx
except ImportError:
    st.error("請先安裝套件: pip install python-docx")

# ==========================================
# 1. 設定與 CSS (仿照 App 視覺風格)
# ==========================================
st.set_page_config(page_title="PET 魔法森林", page_icon="🌱", layout="centered")

ghibli_css = """
<style>
    /* 全局設定 */
    .stApp {
        background-color: #f0f2f5 !important; /* 淺灰底色，更像 App */
        background-image: none !important;
    }
    .stApp, p, h1, h2, h3, div, span, button {
        font-family: 'Fredoka One', 'Microsoft JhengHei', sans-serif !important;
        color: #4a4a4a;
    }

    /* --- 頂部進度條 (Step Indicator) --- */
    .step-container {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 20px;
        padding: 10px;
    }
    .step-circle {
        width: 40px; height: 40px;
        border-radius: 50%;
        background-color: #e0e0e0;
        color: #fff;
        display: flex; align-items: center; justify-content: center;
        font-weight: bold; margin: 0 10px;
        position: relative;
        font-size: 16px;
    }
    .step-active {
        background-color: #4caf50; /* 亮綠色 */
        transform: scale(1.2);
        box-shadow: 0 4px 10px rgba(76, 175, 80, 0.4);
    }
    .step-line {
        height: 4px; width: 30px; background-color: #e0e0e0; border-radius: 2px;
    }
    .step-line-active { background-color: #4caf50; }

    /* --- 單字卡片 (仿 iOS 卡片) --- */
    .word-card {
        background-color: #ffffff;
        padding: 30px 20px;
        border-radius: 25px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 20px;
        position: relative;
        border: 1px solid #f0f0f0;
    }

    /* --- 彩色音節文字 --- */
    .colored-word {
        font-size: 3rem;
        font-weight: 900;
        letter-spacing: 2px;
        margin-bottom: 15px;
    }
    .char-vowel { color: #ff5252; } /* 母音紅 */
    .char-consonant { color: #29b6f6; } /* 子音藍 */
    .syllable-dot { color: #e0e0e0; font-size: 1.5rem; vertical-align: middle; margin: 0 5px; }

    /* --- 圓形發音按鈕 --- */
    .audio-btn-container {
        display: flex; justify-content: center; gap: 20px; margin-top: 15px;
    }
    /* 這裡我們無法直接改 st.button 形狀到完美圓形，
       所以我們用 CSS hack 讓特定按鈕變圓 */
    
    /* --- 字母方塊 (大按鈕) --- */
    .stButton>button {
        background-color: #ffffff !important;
        color: #555 !important;
        border: 2px solid #e0e0e0 !important;
        border-bottom: 5px solid #e0e0e0 !important; /* 立體感 */
        border-radius: 16px !important;
        height: 65px !important;
        font-size: 26px !important;
        font-weight: bold !important;
        transition: all 0.1s;
        margin-bottom: 8px !important;
    }
    .stButton>button:active {
        border-bottom: 2px solid #e0e0e0 !important;
        transform: translateY(3px);
    }
    
    /* 底部導航欄按鈕 (特殊色) */
    div[data-testid="column"] .stButton>button {
       /* 預設樣式 */
    }

    /* --- 拼字底線樣式 --- */
    .spelling-box {
        display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; margin-bottom: 20px;
    }
    .letter-slot {
        width: 40px; height: 50px;
        border-bottom: 4px solid #ccc;
        text-align: center;
        font-size: 30px; font-weight: bold; color: #333;
        line-height: 50px;
    }
    .letter-filled {
        border-bottom: 4px solid #4caf50;
        color: #4caf50;
    }

    /* 手機橫排強制 */
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 6px !important;
            justify-content: center !important;
        }
        div[data-testid="column"] {
            flex: 0 0 22% !important; /* 一排4個 */
            max-width: 22% !important;
            min-width: 0px !important;
        }
    }
</style>
"""
st.markdown(ghibli_css, unsafe_allow_html=True)

# ==========================================
# 2. 核心功能
# ==========================================
DB_FILE = 'pet_database.csv'
SAVE_FILE = 'user_save.json'

def load_save_state():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {}

def save_current_state():
    state = {
        "current_day": st.session_state.current_day,
        "word_index": st.session_state.word_index,
        "stage": st.session_state.stage,
        "notebook": list(st.session_state.notebook),
        "completed_days": list(st.session_state.completed_days),
        "stage2_pool": st.session_state.stage2_pool,
        "stage2_ans": st.session_state.stage2_ans,
        "stage3_pool": st.session_state.stage3_pool,
        "stage3_ans": st.session_state.stage3_ans
    }
    with open(SAVE_FILE, 'w', encoding='utf-8') as f: json.dump(state, f)

# HTML5 播放器
def play_audio_html(text=None, slow_mode=False):
    if text:
        try:
            tts = gTTS(text=text, lang='en', slow=slow_mode)
            fp = BytesIO()
            tts.write_to_fp(fp)
            b64 = base64.b64encode(fp.getvalue()).decode()
            # 隱藏播放器，自動播放
            sound_html = f"""<audio autoplay style="display:none;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>"""
            st.markdown(sound_html, unsafe_allow_html=True)
        except: pass

def play_click():
    pop = """<audio autoplay style="display:none;"><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mp3"></audio>"""
    st.markdown(pop, unsafe_allow_html=True)

# 音節拆分 (模擬)
def split_syllables_chunk(word):
    if " " in word: return word.split(" ")
    chunks = []
    temp = word
    while len(temp) > 0:
        cut = 3 if len(temp) > 5 else 2
        if len(temp) <= 3: chunks.append(temp); break
        chunks.append(temp[:cut])
        temp = temp[cut:]
    return chunks

# 🌈 彩色單字生成器 (母音紅，子音藍)
def get_colored_word_html(word):
    chunks = split_syllables_chunk(word)
    html = ""
    vowels = "aeiouAEIOU"
    
    for i, chunk in enumerate(chunks):
        for char in chunk:
            if char in vowels:
                html += f'<span class="char-vowel">{char}</span>'
            elif char.isalpha():
                html += f'<span class="char-consonant">{char}</span>'
            else:
                html += f'<span>{char}</span>'
        
        # 加音節點 (最後一個音節後不加)
        if i < len(chunks) - 1:
            html += '<span class="syllable-dot">•</span>'
            
    return f'<div class="colored-word">{html}</div>'

# 拼字底線生成器
def get_spelling_slots_html(target_word, current_ans):
    html = '<div class="spelling-box">'
    target_len = len(target_word.replace(" ", ""))
    ans_len = len(current_ans)
    
    # 這裡的邏輯：顯示與目標單字等長的格子
    # 已填入的顯示字母，未填入的顯示底線
    
    for i in range(target_len):
        if i < ans_len:
            char = current_ans[i]
            html += f'<div class="letter-slot letter-filled">{char}</div>'
        else:
            html += '<div class="letter-slot">&nbsp;</div>'
            
    html += '</div>'
    return html

# ==========================================
# 3. Word 解析器
# ==========================================
def parse_word_file(uploaded_file):
    doc = docx.Document(uploaded_file)
    data = []
    day_counter = 1
    for table in doc.tables:
        if len(table.rows) < 2: continue
        for row in table.rows[1:]:
            cells = row.cells
            if len(cells) >= 4:
                raw_word = cells[1].text.strip()
                if not raw_word: continue
                match = re.match(r"([a-zA-Z\s\-\/']+)[\s]*(\(.*\))?", raw_word)
                clean_word = raw_word
                pos = ""
                if match:
                    clean_word = match.group(1).strip()
                    pos = match.group(2).strip() if match.group(2) else ""
                
                raw_ipa = cells[2].text.strip() if len(cells) > 2 else ""
                raw_meaning = cells[3].text.strip() if len(cells) > 3 else ""
                raw_example = cells[4].text.strip() if len(cells) > 4 else ""
                ipa = raw_ipa.replace("/", "")
                data.append({
                    "day": day_counter, "word": clean_word, "pos": pos, "ipa": ipa, "meaning": raw_meaning, "example": raw_example
                })
        day_counter += 1
        if day_counter > 28: day_counter = 28
    return pd.DataFrame(data)

# ==========================================
# 4. 初始化
# ==========================================
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        st.session_state.df = pd.read_csv(DB_FILE)
        st.session_state.data_loaded = True
    else:
        st.session_state.df = pd.DataFrame()
        st.session_state.data_loaded = False

if 'initialized' not in st.session_state:
    saved = load_save_state()
    st.session_state.current_day = saved.get("current_day", 1)
    st.session_state.word_index = saved.get("word_index", 0)
    st.session_state.stage = saved.get("stage", 1)
    st.session_state.notebook = set(saved.get("notebook", []))
    st.session_state.completed_days = set(saved.get("completed_days", []))
    st.session_state.stage2_pool = saved.get("stage2_pool", [])
    st.session_state.stage2_ans = saved.get("stage2_ans", [])
    st.session_state.stage3_pool = saved.get("stage3_pool", [])
    st.session_state.stage3_ans = saved.get("stage3_ans", [])
    st.session_state.initialized = True

if 'stage2_pool' not in st.session_state: st.session_state.stage2_pool = []
if 'stage2_ans' not in st.session_state: st.session_state.stage2_ans = []
if 'stage3_pool' not in st.session_state: st.session_state.stage3_pool = []
if 'stage3_ans' not in st.session_state: st.session_state.stage3_ans = []
if 'mode' not in st.session_state: st.session_state.mode = 'normal'
if 'trigger_audio' not in st.session_state: st.session_state.trigger_audio = None
if 'trigger_audio_slow' not in st.session_state: st.session_state.trigger_audio_slow = False
if 'trigger_click' not in st.session_state: st.session_state.trigger_click = False

# ==========================================
# 5. 側邊欄
# ==========================================
with st.sidebar:
    st.title("🎒 設定")
    if st.session_state.data_loaded:
        if st.button("🗑️ 換檔案"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
            st.session_state.data_loaded = False
            st.session_state.initialized = False
            st.rerun()
            
    if not st.session_state.data_loaded:
        uploaded_file = st.file_uploader("上傳 Word 檔", type=['docx'])
        if uploaded_file:
            try:
                with st.spinner("讀取中..."):
                    df_new = parse_word_file(uploaded_file)
                    df_new.to_csv(DB_FILE, index=False)
                    st.session_state.df = df_new
                    st.session_state.data_loaded = True
                    st.session_state.current_day = 1
                    save_current_state()
                    st.rerun()
            except Exception as e: st.error(f"錯誤: {e}")

    mode_selection = st.radio("前往", ["🌲 森林闖關", "📕 筆記本"], index=0)
    new_mode = 'normal' if "森林" in mode_selection else 'notebook'
    if new_mode != st.session_state.mode:
        st.session_state.mode = new_mode
        st.session_state.word_index = 0
        st.session_state.stage = 1
        st.rerun()

    if st.session_state.mode == 'normal' and st.session_state.data_loaded:
        st.markdown("---")
        st.write(f"目前: Day {st.session_state.current_day}")
        cols = st.columns(4)
        for i in range(1, 31):
            has_data = not st.session_state.df.empty and i in st.session_state.df['day'].values
            btn_type = "primary" if i == st.session_state.current_day else "secondary"
            if cols[(i-1)%4].button(f"{i}", key=f"day_{i}", disabled=not has_data, type=btn_type):
                st.session_state.current_day = i
                st.session_state.word_index = 0
                st.session_state.stage = 1
                save_current_state()
                st.rerun()

# ==========================================
# 6. 主程式邏輯
# ==========================================
if st.session_state.trigger_audio:
    play_audio_html(text=st.session_state.trigger_audio, slow_mode=st.session_state.trigger_audio_slow)
    st.session_state.trigger_audio = None
    st.session_state.trigger_audio_slow = False
if st.session_state.trigger_click:
    play_click()
    st.session_state.trigger_click = False

if not st.session_state.data_loaded:
    st.info("👈 請先在側邊欄上傳檔案")
    st.stop()

if st.session_state.mode == 'normal':
    current_words = st.session_state.df[st.session_state.df['day'] == st.session_state.current_day].reset_index(drop=True)
else:
    if len(st.session_state.notebook) == 0:
        st.info("筆記本是空的。")
        st.stop()
    current_words = st.session_state.df[st.session_state.df['word'].isin(st.session_state.notebook)].reset_index(drop=True)

if current_words.empty:
    st.warning("無資料")
    st.stop()

if st.session_state.word_index >= len(current_words):
    st.balloons()
    st.success("🎉 完成！")
    if st.session_state.mode == 'normal':
        if st.button("🚀 下一天"):
            if st.session_state.current_day not in st.session_state.completed_days:
                st.session_state.completed_days.add(st.session_state.current_day)
            st.session_state.current_day += 1
            st.session_state.word_index = 0
            st.session_state.stage = 1
            save_current_state()
            st.rerun()
    else:
        if st.button("🔄 重來"):
            st.session_state.word_index = 0
            st.session_state.stage = 1
            st.rerun()
    st.stop()

w_data = current_words.iloc[st.session_state.word_index]
target = str(w_data['word'])
meaning = str(w_data['meaning'])
pos = str(w_data.get('pos', ''))
ipa = str(w_data.get('ipa', ''))
example = str(w_data.get('example', ''))
if example == 'nan': example = ""
if ipa == 'nan': ipa = ""

# --- 頂部進度條 (Step Indicator) ---
steps_html = """
<div class="step-container">
    <div class="step-circle {s1}">學</div>
    <div class="step-line {l1}"></div>
    <div class="step-circle {s2}">拆</div>
    <div class="step-line {l2}"></div>
    <div class="step-circle {s3}">拼</div>
</div>
""".format(
    s1="step-active" if st.session_state.stage == 1 else "",
    l1="step-line-active" if st.session_state.stage > 1 else "",
    s2="step-active" if st.session_state.stage == 2 else "",
    l2="step-line-active" if st.session_state.stage > 2 else "",
    s3="step-active" if st.session_state.stage == 3 else ""
)
st.markdown(steps_html, unsafe_allow_html=True)

st.caption(f"Progress: {st.session_state.word_index + 1} / {len(current_words)}")

# --- Stage 1: 認知 (彩色音節 + 例句) ---
if st.session_state.stage == 1:
    # 第一次進入自動發音
    play_audio_html(target, slow_mode=False)

    # 彩色單字卡片
    colored_word = get_colored_word_html(target)
    
    st.markdown(f"""
    <div class="word-card">
        {colored_word}
        <div style="color:#888; margin-top:5px;">{pos} <span style="color:#d81b60; margin-left:10px;">/{ipa}/</span></div>
        
        <br>
    </div>
    """, unsafe_allow_html=True)
    
    # 發音按鈕 (獨立出來以便綁定事件)
    c_play, c_slow = st.columns(2)
    with c_play:
        if st.button("🔊 一般", key="play_normal"):
            st.session_state.trigger_audio = target
            st.session_state.trigger_audio_slow = False
            st.rerun()
    with c_slow:
        if st.button("🐌 慢速", key="play_slow"):
            st.session_state.trigger_audio = target
            st.session_state.trigger_audio_slow = True
            st.rerun()

    # 釋義與例句
    st.markdown(f"""
    <div style="background:white; padding:15px; border-radius:15px; margin-top:10px; border:1px solid #f0f0f0;">
        <h3 style="margin:0; color:#333;">{meaning}</h3>
        <div class="example-sentence">
            {example}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    in_note = target in st.session_state.notebook
    if col1.button("💔 移除" if in_note else "❤️ 收藏"):
        st.session_state.trigger_click = True
        if in_note: st.session_state.notebook.remove(target)
        else: st.session_state.notebook.add(target)
        save_current_state()
        st.rerun()

    if col2.button("下一步 ➡"):
        st.session_state.trigger_click = True
        chunks = split_syllables_chunk(target)
        st.session_state.stage2_pool = random.sample(chunks, len(chunks))
        st.session_state.stage2_ans = []
        st.session_state.stage = 2
        save_current_state()
        st.rerun()

# --- Stage 2: 音節拼圖 ---
elif st.session_state.stage == 2:
    st.markdown(f"""
    <div class="word-card">
        <h2 style="color:#555;">{meaning}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # 答案區 (空心框)
    curr = "".join(st.session_state.stage2_ans)
    # 這裡可以做美化，暫時維持橫條
    st.markdown(f'<div class="answer-column">{curr}</div>', unsafe_allow_html=True)
    
    if not st.session_state.stage2_pool and not st.session_state.stage2_ans:
         chunks = split_syllables_chunk(target)
         st.session_state.stage2_pool = random.sample(chunks, len(chunks))

    cols = st.columns(3)
    for i, s in enumerate(st.session_state.stage2_pool):
        if s not in st.session_state.stage2_ans:
            if cols[i%3].button(s, key=f"s2_{i}"):
                st.session_state.stage2_ans.append(s)
                st.session_state.trigger_click = True
                save_current_state()
                st.rerun()
            
    c1, c2 = st.columns(2)
    if c1.button("↺ 重來"):
        st.session_state.stage2_ans = []
        st.session_state.trigger_click = True
        save_current_state()
        st.rerun()
    if c2.button("✅ 確認"):
        if "".join(st.session_state.stage2_ans) == target.replace(" ", ""):
            st.success("Correct!")
            chars = list(target.replace(" ", ""))
            random.shuffle(chars)
            st.session_state.stage3_pool = chars
            st.session_state.stage3_ans = []
            st.session_state.stage = 3
            save_current_state()
            st.rerun()
        else: st.error("錯誤")

# --- Stage 3: 字母拼寫 (視覺化底線) ---
elif st.session_state.stage == 3:
    st.markdown(f"""
    <div class="word-card">
        <h2 style="color:#555;">{meaning}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # 視覺化底線區
    spelling_html = get_spelling_slots_html(target, st.session_state.stage3_ans)
    st.markdown(spelling_html, unsafe_allow_html=True)
    
    # 檢查完成
    user_word = "".join(st.session_state.stage3_ans)
    target_clean = target.replace(" ", "")
    is_finished = len(user_word) >= len(target_clean)
    
    if not st.session_state.stage3_pool and not st.session_state.stage3_ans:
        chars = list(target.replace(" ", ""))
        random.shuffle(chars)
        st.session_state.stage3_pool = chars

    if not is_finished:
        pool_cols = st.columns(4)
        for i, char in enumerate(st.session_state.stage3_pool):
            if pool_cols[i % 4].button(char, key=f"s3_char_{i}"):
                st.session_state.stage3_ans.append(char)
                st.session_state.stage3_pool.pop(i)
                st.session_state.trigger_click = True
                save_current_state()
                st.rerun()
    else:
        st.info("拼寫完成！請送出")

    st.markdown("<br>", unsafe_allow_html=True)
    ctrl_c1, ctrl_c2, ctrl_c3 = st.columns(3)
    
    if ctrl_c1.button("⌫"): 
        if st.session_state.stage3_ans:
            last_char = st.session_state.stage3_ans.pop()
            st.session_state.stage3_pool.append(last_char)
            st.session_state.trigger_click = True
            save_current_state()
            st.rerun()
            
    if ctrl_c2.button("↺"): 
        st.session_state.stage3_pool.extend(st.session_state.stage3_ans)
        st.session_state.stage3_ans = []
        st.session_state.trigger_click = True
        save_current_state()
        st.rerun()
    
    with ctrl_c3:
        st.markdown('<div class="confirm-btn">', unsafe_allow_html=True)
        if st.button("👑"): 
            if user_word.lower() == target_clean.lower():
                st.balloons()
                st.success("Perfect!")
                time.sleep(0.5)
                st.session_state.word_index += 1
                st.session_state.stage = 1
                save_current_state()
                st.rerun()
            else:
                st.error("拼錯囉！")
                if target not in st.session_state.notebook:
                    st.session_state.notebook.add(target)
                    st.toast("已加入筆記本📕")
                    save_current_state()
        st.markdown('</div>', unsafe_allow_html=True)
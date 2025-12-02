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
# 1. 設定與 CSS (加大按鈕，優化觸控)
# ==========================================
st.set_page_config(page_title="PET 魔法森林", page_icon="🌱", layout="centered")

ghibli_css = """
<style>
    /* 強制背景與文字顏色 */
    .stApp {
        background-color: #fcfef1 !important;
        background-image: linear-gradient(120deg, #f0f9e8 0%, #fcfef1 100%) !important;
    }
    .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp div, .stApp span, .stApp label, .stMarkdown {
        color: #4a4a4a !important; 
        font-family: 'Comic Sans MS', 'Microsoft JhengHei', sans-serif !important;
    }

    /* --- 按鈕超級加大版 (符合需求1) --- */
    .stButton>button {
        background-color: #88b04b; 
        color: white !important;
        border-radius: 15px; /* 更圓潤 */
        border: none; 
        padding: 20px 0px; /* 垂直高度加大，更好按 */
        font-weight: bold; 
        font-size: 24px; /* 字體加大 */
        width: 100%; 
        box-shadow: 0 6px 0 #556b2f; /* 厚實立體感 */
        transition: transform 0.05s;
        touch-action: manipulation;
        margin-bottom: 8px;
    }
    .stButton>button:active {
        transform: translateY(6px);
        box-shadow: none;
        background-color: #6a8a3a;
    }
    
    /* 送出/確認按鈕 (紅色) */
    .confirm-btn > button {
        background-color: #ff6f69 !important;
        box-shadow: 0 6px 0 #d45d58 !important;
    }

    /* 手機版面修正 */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] {
            gap: 6px !important; /* 按鈕間距 */
        }
        [data-testid="column"] {
            min-width: 0px !important;
            flex: 1 1 0px !important;
            padding: 0 2px !important;
        }
    }

    /* 單字卡 */
    .word-card {
        background-color: #ffffff; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1); border: 2px solid #e0e0e0;
        text-align: center; margin-bottom: 15px;
    }
    
    /* 答案列 */
    .answer-column {
        background-color: #fff9c4; padding: 15px; border-radius: 10px;
        border: 3px dashed #fbc02d; text-align: center; font-size: 2.2rem;
        color: #333 !important; 
        font-weight: bold; min-height: 70px; margin-bottom: 15px;
        letter-spacing: 2px;
    }
    
    /* PASS 過關標示 */
    .pass-banner {
        background-color: #66bb6a; color: white; padding: 20px;
        border-radius: 15px; text-align: center; font-size: 2rem;
        font-weight: bold; border: 4px solid #2e7d32;
        margin-bottom: 20px; animation: pop 0.3s ease;
    }
    
    .example-sentence {
        background-color: #f0f4c3; padding: 10px; border-radius: 8px;
        margin-top: 10px; font-style: italic; text-align: left;
        border-left: 4px solid #c0ca33; font-size: 0.9rem;
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

# HTML5 播放器 (支援自動播放)
def play_audio_html(text=None, slow_mode=False):
    if text:
        try:
            tts = gTTS(text=text, lang='en', slow=slow_mode)
            fp = BytesIO()
            tts.write_to_fp(fp)
            b64 = base64.b64encode(fp.getvalue()).decode()
            sound_html = f"""<audio autoplay style="display:none;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>"""
            st.markdown(sound_html, unsafe_allow_html=True)
        except: pass

# 點擊音效
def play_click():
    pop = """<audio autoplay style="display:none;"><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mp3"></audio>"""
    st.markdown(pop, unsafe_allow_html=True)

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
if 'show_answer' not in st.session_state: st.session_state.show_answer = False
if 'daily_quiz_active' not in st.session_state: st.session_state.daily_quiz_active = False
if 'quiz_q_index' not in st.session_state: st.session_state.quiz_q_index = 0
if 'quiz_score' not in st.session_state: st.session_state.quiz_score = 0
if 'quiz_data' not in st.session_state: st.session_state.quiz_data = []
if 'trigger_audio' not in st.session_state: st.session_state.trigger_audio = None
if 'trigger_click' not in st.session_state: st.session_state.trigger_click = False

# ==========================================
# 5. 側邊欄
# ==========================================
with st.sidebar:
    st.title("🎒 冒險背包")
    slow_audio = st.checkbox("🐢 慢速發音", value=False)
    mask_mode = st.checkbox("🫣 遮住中文", value=False)
    st.markdown("---")

    if st.session_state.data_loaded:
        if st.button("🗑️ 清除舊資料 (換檔)"):
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

    st.write("### 🎯 模式")
    mode_selection = st.radio("前往", ["🌲 森林闖關", "📕 魔法筆記本"], index=0)
    new_mode = 'normal' if "森林" in mode_selection else 'notebook'
    if new_mode != st.session_state.mode:
        st.session_state.mode = new_mode
        st.session_state.word_index = 0
        st.session_state.stage = 1
        st.session_state.daily_quiz_active = False 
        st.rerun()

    if st.session_state.mode == 'normal' and st.session_state.data_loaded:
        st.markdown("---")
        st.write(f"目前: Day {st.session_state.current_day}")
        cols = st.columns(4)
        for i in range(1, 31):
            is_done = i in st.session_state.completed_days
            label = f"✅\n{i}" if is_done else f"{i}"
            has_data = not st.session_state.df.empty and i in st.session_state.df['day'].values
            btn_type = "primary" if i == st.session_state.current_day else "secondary"
            if cols[(i-1)%4].button(label, key=f"day_{i}", disabled=not has_data, type=btn_type):
                st.session_state.current_day = i
                st.session_state.word_index = 0
                st.session_state.stage = 1
                st.session_state.daily_quiz_active = False 
                save_current_state()
                st.rerun()

# ==========================================
# 6. 主程式邏輯
# ==========================================
if st.session_state.trigger_audio:
    play_audio_html(text=st.session_state.trigger_audio, slow_mode=slow_audio)
    st.session_state.trigger_audio = None
if st.session_state.trigger_click:
    play_click()
    st.session_state.trigger_click = False

if not st.session_state.data_loaded:
    st.info("👈 請先上傳檔案")
    st.stop()

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

if st.session_state.mode == 'normal':
    current_words = st.session_state.df[st.session_state.df['day'] == st.session_state.current_day].reset_index(drop=True)
    header_text = f"Day {st.session_state.current_day} - 闖關"
else:
    if len(st.session_state.notebook) == 0:
        st.info("筆記本是空的。")
        st.stop()
    current_words = st.session_state.df[st.session_state.df['word'].isin(st.session_state.notebook)].reset_index(drop=True)
    header_text = f"📕 筆記本"

if current_words.empty:
    st.warning("無資料")
    st.stop()

# 每日聽力測驗
if st.session_state.daily_quiz_active:
    st.markdown(f"## ⚔️ Day {st.session_state.current_day} 驗收")
    total_q = len(st.session_state.quiz_data)
    current_q_idx = st.session_state.quiz_q_index
    st.markdown(f"""<div style='background:#fff3e0;padding:8px;border-radius:10px;text-align:center;font-weight:bold;color:#e65100;border:2px solid #ffb74d;margin-bottom:10px;'>第 {current_q_idx + 1} / {total_q} 題 | 得分: {st.session_state.quiz_score}</div>""", unsafe_allow_html=True)

    if current_q_idx < total_q:
        q = st.session_state.quiz_data[current_q_idx]
        col_p, col_info = st.columns([1, 4])
        with col_p:
            if st.button("🔊", type="primary", key=f"q_play_{current_q_idx}"):
                st.session_state.trigger_audio = q['word']
                st.rerun()
        with col_info: st.info("選出正確意思：")

        for opt in q['options']:
            if st.button(opt, use_container_width=True, key=f"opt_{opt}_{current_q_idx}"):
                st.session_state.trigger_click = True
                if opt == q['correct']:
                    st.toast("🎉 答對了！")
                    st.session_state.quiz_score += 1
                else:
                    st.error(f"❌ 錯囉！是 {q['word']} ({q['correct']})")
                    if q['word'] not in st.session_state.notebook:
                        st.session_state.notebook.add(q['word'])
                        st.toast(f"已加入筆記本📕")
                        save_current_state()
                    time.sleep(1.5)
                st.session_state.quiz_q_index += 1
                st.rerun()
    else:
        st.markdown('<div class="pass-banner">✅ PASS</div>', unsafe_allow_html=True)
        st.success(f"驗收完成！得分: {st.session_state.quiz_score}")
        if st.session_state.mode == 'normal':
            if st.button("🚀 下一天"):
                if st.session_state.current_day not in st.session_state.completed_days:
                    st.session_state.completed_days.add(st.session_state.current_day)
                st.session_state.current_day += 1
                st.session_state.word_index = 0
                st.session_state.stage = 1
                st.session_state.daily_quiz_active = False 
                save_current_state()
                st.rerun()
        else:
            if st.button("🔙 筆記本"):
                st.session_state.daily_quiz_active = False
                st.rerun()
    st.stop()

# 正常學習
if st.session_state.word_index >= len(current_words):
    st.success("🎉 單字學習完畢！")
    if st.button("⚔️ 進入聽力驗收 (Quiz)", type="primary"):
        questions = []
        all_meanings = st.session_state.df['meaning'].unique().tolist()
        for idx, row in current_words.iterrows():
            target = row['word']
            correct = row['meaning']
            distractors = random.sample([m for m in all_meanings if m != correct], 3)
            options = distractors + [correct]
            random.shuffle(options)
            questions.append({"word": target, "correct": correct, "options": options})
        random.shuffle(questions)
        st.session_state.quiz_data = questions
        st.session_state.quiz_q_index = 0
        st.session_state.quiz_score = 0
        st.session_state.daily_quiz_active = True
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

st.subheader(f"{header_text}")
st.progress((st.session_state.word_index) / len(current_words))

# Stage 1: 認知 (自動發音)
if st.session_state.stage == 1:
    # 進入 Stage 1 時自動觸發一次發音 (如果是剛切換過來)
    # 為了避免每次點擊按鈕都重播，這裡可以加個 flag，或直接放著讓它播
    play_audio_html(target, slow_mode=slow_audio)

    st.markdown(f"""
    <div class="word-card">
        <h1 style="color:#2c5e2e;">{target}</h1>
        <p style='color:#888; font-size: 1.2em;'>{pos} <span style="color:#d81b60;">/{ipa}/</span></p>
    """, unsafe_allow_html=True)
    
    if mask_mode and not st.session_state.show_answer:
        st.warning("🫣 點擊查看")
        if st.button("👀 顯示"):
            st.session_state.show_answer = True
            st.rerun()
    else:
        st.markdown(f"""<h2 style='margin-top:10px;'>{meaning}</h2><div class="example-sentence"><b>Ex:</b> {example}</div>""", unsafe_allow_html=True)
        if mask_mode:
            if st.button("🙈 隱藏"):
                st.session_state.show_answer = False
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,1,2])
    in_note = target in st.session_state.notebook
    if col1.button("💔" if in_note else "❤️"): # 簡化按鈕文字
        st.session_state.trigger_click = True
        if in_note: st.session_state.notebook.remove(target)
        else: st.session_state.notebook.add(target)
        save_current_state()
        st.rerun()

    if col2.button("🔊"):
        st.session_state.trigger_audio = target
        st.rerun()

    if col3.button("下一步 ➡"):
        st.session_state.trigger_click = True
        chunks = split_syllables_chunk(target)
        st.session_state.stage2_pool = random.sample(chunks, len(chunks))
        st.session_state.stage2_ans = []
        st.session_state.stage = 2
        st.session_state.show_answer = False
        save_current_state()
        st.rerun()

# Stage 2: 音節拼圖
elif st.session_state.stage == 2:
    st.subheader("🧩 音節拼圖")
    st.info(f"提示：{meaning}")
    if st.button("🔊 聽發音", key="s2_audio"): 
        st.session_state.trigger_audio = target
        st.rerun()
    
    curr = "".join(st.session_state.stage2_ans)
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
    if c1.button("↺"):
        st.session_state.stage2_ans = []
        st.session_state.trigger_click = True
        save_current_state()
        st.rerun()
    if c2.button("✅", key="confirm_s2"):
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

# Stage 3: 字母拼寫
elif st.session_state.stage == 3:
    st.subheader("✍️ 字母拼寫")
    st.info(f"請拼出：{meaning}")
    if st.button("🔊 聽發音", key="s3_audio"): 
        st.session_state.trigger_audio = target
        st.rerun()

    curr_ans_str = "".join(st.session_state.stage3_ans)
    st.markdown(f'<div class="answer-column">{curr_ans_str}</div>', unsafe_allow_html=True)
    
    # 判斷是否已拼完
    is_finished = "".join(st.session_state.stage3_ans) == target.replace(" ", "")
    
    if not st.session_state.stage3_pool and not st.session_state.stage3_ans:
        chars = list(target.replace(" ", ""))
        random.shuffle(chars)
        st.session_state.stage3_pool = chars

    if not is_finished:
        st.write("👇 點擊字母：")
        # 改為 4 欄，讓按鈕更大
        pool_cols = st.columns(4)
        for i, char in enumerate(st.session_state.stage3_pool):
            if pool_cols[i % 4].button(char, key=f"s3_char_{i}"):
                st.session_state.stage3_ans.append(char)
                st.session_state.stage3_pool.pop(i)
                st.session_state.trigger_click = True
                save_current_state()
                st.rerun()
    else:
        st.info("拼寫完成！請按右下方紅色按鈕送出")

    st.markdown("<br>", unsafe_allow_html=True)
    ctrl_c1, ctrl_c2, ctrl_c3 = st.columns(3)
    if ctrl_c1.button("⌫"): # 退格
        if st.session_state.stage3_ans:
            last_char = st.session_state.stage3_ans.pop()
            st.session_state.stage3_pool.append(last_char)
            st.session_state.trigger_click = True
            save_current_state()
            st.rerun()
    if ctrl_c2.button("↺"): # 清空
        st.session_state.stage3_pool.extend(st.session_state.stage3_ans)
        st.session_state.stage3_ans = []
        st.session_state.trigger_click = True
        save_current_state()
        st.rerun()
    
    # 使用 container 包裹按鈕以套用紅色樣式
    with ctrl_c3:
        st.markdown('<div class="confirm-btn">', unsafe_allow_html=True)
        if st.button("👑"): # 送出
            user_word = "".join(st.session_state.stage3_ans)
            target_clean = target.replace(" ", "")
            if user_word.lower() == target_clean.lower():
                # 改為顯示 PASS Banner，不使用氣球
                st.markdown('<div class="pass-banner">✅ PASS</div>', unsafe_allow_html=True)
                time.sleep(0.5)
                st.session_state.word_index += 1
                st.session_state.stage = 1
                save_current_state()
                st.rerun()
            else:
                st.error(f"拼錯囉！正確答案: {target}")
                if target not in st.session_state.notebook:
                    st.session_state.notebook.add(target)
                    st.toast(f"已加入筆記本📕")
                    save_current_state()
        st.markdown('</div>', unsafe_allow_html=True)
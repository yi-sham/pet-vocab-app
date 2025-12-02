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
import streamlit.components.v1 as components

try:
    import docx
except ImportError:
    st.error("請先安裝套件: pip install python-docx")

# ==========================================
# 1. 設定與 CSS
# ==========================================
st.set_page_config(page_title="PET 魔法森林", page_icon="🌱", layout="centered")

# 我們將使用 Streamlit 的 session state 來處理 HTML 按鈕的回傳值
if 'clicked_char' not in st.session_state: st.session_state.clicked_char = None

ghibli_css = """
<style>
    .stApp {
        background-color: #fcfef1 !important;
        background-image: linear-gradient(120deg, #f0f9e8 0%, #fcfef1 100%) !important;
    }
    .stApp * {
        color: #4a4a4a !important; 
        font-family: 'Comic Sans MS', 'Microsoft JhengHei', sans-serif !important;
    }
    
    /* 隱藏預設按鈕樣式，因為我們會用自定義 HTML 按鈕 */
    
    /* 單字卡 */
    .word-card {
        background-color: #ffffff; padding: 25px; border-radius: 25px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.08); border: 2px solid #e0e0e0;
        text-align: center; margin-bottom: 20px;
    }
    
    /* 答案列 */
    .answer-column {
        background-color: #fff; padding: 15px; border-radius: 20px;
        border: 3px solid #88b04b; text-align: center; 
        font-size: 3rem; color: #2c5e2e !important; font-weight: bold; 
        min-height: 80px; margin-bottom: 20px; letter-spacing: 2px;
        box-shadow: inset 0 3px 6px rgba(0,0,0,0.1);
        display: flex; align-items: center; justify-content: center;
    }
    
    .example-sentence {
        background-color: #f0f4c3; padding: 12px; border-radius: 10px;
        margin-top: 15px; font-style: italic; text-align: left;
        border-left: 5px solid #c0ca33; font-size: 1.1rem; line-height: 1.5;
    }
    
    /* 普通按鈕優化 */
    .stButton>button {
        background-color: #ffffff !important;
        color: #4a4a4a !important;
        border: 3px solid #88b04b !important;
        border-radius: 12px !important;
        height: 50px !important;
        font-weight: bold !important; 
        font-size: 20px !important;
        width: 100%; 
        box-shadow: 0 4px 0 #88b04b !important;
        margin-top: 5px;
    }
    .stButton>button:active {
        transform: translateY(4px);
        box-shadow: none !important;
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

def play_audio_html(text=None, slow_mode=False):
    if text:
        try:
            tts = gTTS(text=text, lang='en', slow=slow_mode)
            fp = BytesIO()
            tts.write_to_fp(fp)
            b64 = base64.b64encode(fp.getvalue()).decode()
            sound_html = f"""<audio autoplay style="width:0;height:0;display:none;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>"""
            st.markdown(sound_html, unsafe_allow_html=True)
        except: pass

def play_click():
    pop = """<audio autoplay style="display:none;"><source src="https://www.soundjay.com/buttons/sounds/button-16.mp3" type="audio/mp3"></audio>"""
    st.markdown(pop, unsafe_allow_html=True)

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

def get_colored_word_html(word):
    chunks = split_syllables_chunk(word)
    html = ""
    vowels = "aeiouAEIOU"
    for i, chunk in enumerate(chunks):
        for char in chunk:
            if char in vowels: html += f'<span style="color:#ff5252;">{char}</span>'
            elif char.isalpha(): html += f'<span style="color:#29b6f6;">{char}</span>'
            else: html += f'<span>{char}</span>'
        if i < len(chunks) - 1: html += '<span style="color:#ddd;margin:0 2px;">•</span>'
    return f'<div style="font-size:3.5rem;font-weight:900;letter-spacing:1px;margin-bottom:10px;">{html}</div>'

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
if 'trigger_audio' not in st.session_state: st.session_state.trigger_audio = None
if 'trigger_click' not in st.session_state: st.session_state.trigger_click = False
if 'daily_quiz_active' not in st.session_state: st.session_state.daily_quiz_active = False
if 'quiz_q_index' not in st.session_state: st.session_state.quiz_q_index = 0
if 'quiz_score' not in st.session_state: st.session_state.quiz_score = 0
if 'quiz_data' not in st.session_state: st.session_state.quiz_data = []

# ==========================================
# 5. 側邊欄
# ==========================================
with st.sidebar:
    st.title("🎒 設定")
    slow_audio = st.checkbox("🐢 慢速發音", value=False)
    
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

    mode_selection = st.radio("前往", ["🌲 森林闖關", "📕 魔法筆記本"], index=0)
    new_mode = 'normal' if "森林" in mode_selection else 'notebook'
    if new_mode != st.session_state.mode:
        st.session_state.mode = new_mode
        st.session_state.word_index = 0
        st.session_state.stage = 1
        st.rerun()

    if st.session_state.mode == 'normal' and st.session_state.data_loaded:
        st.markdown("---")
        st.write(f"目前: Day {st.session_state.current_day}")
        
        # 這裡依然使用 columns，因為側邊欄本來就很窄
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
    header_text = f"Day {st.session_state.current_day}"
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
        st.markdown('<div class="pass-banner" style="background:#66bb6a;color:white;padding:15px;border-radius:15px;text-align:center;font-size:1.8rem;font-weight:bold;">✅ PASS</div>', unsafe_allow_html=True)
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
    with st.container():
        st.markdown('<div class="confirm-btn">', unsafe_allow_html=True)
        if st.button("⚔️ 進入聽力驗收 (Quiz)"):
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
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

w_data = current_words.iloc[st.session_state.word_index]
target = str(w_data['word'])
meaning = str(w_data['meaning'])
pos = str(w_data.get('pos', ''))
ipa = str(w_data.get('ipa', ''))
example = str(w_data.get('example', ''))
if example == 'nan': example = ""
if ipa == 'nan': ipa = ""

# 進度圓圈
steps_html = """
<div style="display:flex;justify-content:center;margin-bottom:20px;">
    <div style="width:40px;height:40px;border-radius:50%;background:{c1};color:white;display:flex;align-items:center;justify-content:center;font-weight:bold;margin:0 10px;box-shadow:{s1};">學</div>
    <div style="width:40px;height:40px;border-radius:50%;background:{c2};color:white;display:flex;align-items:center;justify-content:center;font-weight:bold;margin:0 10px;box-shadow:{s2};">拆</div>
    <div style="width:40px;height:40px;border-radius:50%;background:{c3};color:white;display:flex;align-items:center;justify-content:center;font-weight:bold;margin:0 10px;box-shadow:{s3};">拼</div>
</div>
""".format(
    c1="#4caf50" if st.session_state.stage==1 else "#e0e0e0", s1="0 4px 10px rgba(76,175,80,0.4)" if st.session_state.stage==1 else "none",
    c2="#4caf50" if st.session_state.stage==2 else "#e0e0e0", s2="0 4px 10px rgba(76,175,80,0.4)" if st.session_state.stage==2 else "none",
    c3="#4caf50" if st.session_state.stage==3 else "#e0e0e0", s3="0 4px 10px rgba(76,175,80,0.4)" if st.session_state.stage==3 else "none"
)
st.markdown(steps_html, unsafe_allow_html=True)
st.caption(f"Progress: {st.session_state.word_index + 1} / {len(current_words)}")

# Stage 1: 認知
if st.session_state.stage == 1:
    play_audio_html(target, slow_mode=slow_audio)
    colored_word = get_colored_word_html(target)
    
    st.markdown(f"""
    <div class="word-card">
        {colored_word}
        <div style="color:#888; margin-top:5px;">{pos} <span style="color:#d81b60; margin-left:10px;">/{ipa}/</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    c_play, c_slow = st.columns(2)
    with c_play:
        if st.button("🔊 一般", key="play_normal"):
            st.session_state.trigger_audio = target
            st.rerun()
    with c_slow:
        if st.button("🐌 慢速", key="play_slow"):
            play_audio_html(target, slow_mode=True)

    if not st.session_state.show_answer:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("👁️ 顯示中文與例句", key="show_mask"):
            st.session_state.show_answer = True
            st.rerun()
    else:
        st.markdown(f"""
        <div style="background:white; padding:15px; border-radius:15px; margin-top:10px; border:2px solid #81c784;">
            <h3 style="margin:0; color:#2e7d32;">{meaning}</h3>
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
        st.session_state.show_answer = False
        save_current_state()
        st.rerun()

# Stage 2: 音節拼圖 (強制橫排處理)
elif st.session_state.stage == 2:
    st.markdown(f"""<div class="word-card"><h2 style="color:#555;">{meaning}</h2></div>""", unsafe_allow_html=True)
    curr = "".join(st.session_state.stage2_ans)
    st.markdown(f'<div class="answer-column">{curr}</div>', unsafe_allow_html=True)
    
    if not st.session_state.stage2_pool and not st.session_state.stage2_ans:
         chunks = split_syllables_chunk(target)
         st.session_state.stage2_pool = random.sample(chunks, len(chunks))

    # 使用 columns 分 3 欄，配合 CSS 強制寬度
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

# Stage 3: 字母拼寫 (強制橫排處理)
elif st.session_state.stage == 3:
    st.markdown(f"""<div class="word-card"><h2 style="color:#555;">{meaning}</h2></div>""", unsafe_allow_html=True)
    curr_ans_str = "".join(st.session_state.stage3_ans)
    st.markdown(f'<div class="answer-column">{curr_ans_str}</div>', unsafe_allow_html=True)
    
    is_finished = "".join(st.session_state.stage3_ans) == target.replace(" ", "")
    
    if not st.session_state.stage3_pool and not st.session_state.stage3_ans:
        chars = list(target.replace(" ", ""))
        random.shuffle(chars)
        st.session_state.stage3_pool = chars

    if not is_finished:
        st.write("👇 點擊字母：")
        # 這裡的 columns 配合 CSS 的強制寬度，可以確保一排 4 個
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
            user_word = "".join(st.session_state.stage3_ans)
            target_clean = target.replace(" ", "")
            if user_word.lower() == target_clean.lower():
                st.markdown('<div class="pass-banner" style="background:#66bb6a;color:white;padding:15px;border-radius:15px;text-align:center;font-size:1.8rem;font-weight:bold;">✅ PASS</div>', unsafe_allow_html=True)
                time.sleep(0.5)
                st.session_state.word_index += 1
                st.session_state.stage = 1
                save_current_state()
                st.rerun()
            else:
                st.error("拼錯囉！")
                if target not in st.session_state.notebook:
                    st.session_state.notebook.add(target)
                    st.toast(f"已加入筆記本📕")
                    save_current_state()
        st.markdown('</div>', unsafe_allow_html=True)
import streamlit as st
import pandas as pd
import random
import time
import json
import os
import re
from gtts import gTTS
from io import BytesIO
try:
    import docx
except ImportError:
    st.error("請先安裝套件: pip install python-docx")

# ==========================================
# 1. 設定與 CSS (宮崎駿風格)
# ==========================================
st.set_page_config(page_title="PET 魔法森林 (智慧版)", page_icon="🌱", layout="centered")

ghibli_css = """
<style>
    .stApp {
        background-color: #fcfef1;
        background-image: linear-gradient(120deg, #f0f9e8 0%, #fcfef1 100%);
    }
    h1, h2, h3, div, button, p { font-family: 'Comic Sans MS', 'Microsoft JhengHei', sans-serif; }
    
    /* 按鈕優化 */
    .stButton>button {
        background-color: #88b04b; color: white; border-radius: 15px;
        border: 2px solid #556b2f; padding: 8px 16px; font-weight: bold; font-size: 18px;
        width: 100%;
    }
    .stButton>button:hover { background-color: #6a8a3a; transform: scale(1.02); color: #fff; }
    
    /* 單字卡 */
    .word-card {
        background-color: #ffffff; padding: 30px; border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1); border: 3px solid #e0e0e0;
        text-align: center; margin-bottom: 20px; position: relative;
    }
    .example-sentence {
        background-color: #f0f4c3; padding: 15px; border-radius: 10px;
        margin-top: 15px; font-style: italic; color: #555; text-align: left;
        border-left: 5px solid #c0ca33;
    }
    
    /* 遮罩樣式 */
    .mask-box {
        background-color: #e0e0e0; color: #757575; padding: 20px;
        border-radius: 10px; text-align: center; cursor: pointer;
        border: 2px dashed #bdbdbd; margin-top: 10px;
    }
    
    /* 答案列 */
    .answer-column {
        background-color: #fff9c4; padding: 15px; border-radius: 12px;
        border: 3px dashed #fbc02d; text-align: center; font-size: 2.0rem;
        color: #333; font-weight: bold; min-height: 80px; margin-bottom: 20px;
        letter-spacing: 3px;
    }
</style>
"""
st.markdown(ghibli_css, unsafe_allow_html=True)

# ==========================================
# 2. 本地記憶系統
# ==========================================
DB_FILE = 'pet_database.csv'
SAVE_FILE = 'user_save.json'

def load_save_state():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "current_day": 1,
        "word_index": 0,
        "stage": 1,
        "notebook": [],
        "completed_days": []
    }

def save_current_state():
    state = {
        "current_day": st.session_state.current_day,
        "word_index": st.session_state.word_index,
        "stage": st.session_state.stage,
        "notebook": list(st.session_state.notebook),
        "completed_days": list(st.session_state.completed_days)
    }
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)

# ==========================================
# 3. Word 解析器
# ==========================================
def parse_word_file(uploaded_file):
    doc = docx.Document(uploaded_file)
    data = []
    
    # 針對新格式優化：跳過第一欄序號
    day_counter = 1
    
    for table in doc.tables:
        if len(table.rows) < 2: continue
        
        for row in table.rows[1:]:
            cells = row.cells
            # 確保欄位足夠 (序號, 單字, 音標, 中文, 例句)
            if len(cells) >= 4:
                raw_word = cells[1].text.strip()
                if not raw_word: continue
                
                # 分離單字與詞性
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
                    "day": day_counter,
                    "word": clean_word,
                    "pos": pos,
                    "ipa": ipa,
                    "meaning": raw_meaning,
                    "example": raw_example
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
    saved_data = load_save_state()
    st.session_state.current_day = saved_data["current_day"]
    st.session_state.word_index = saved_data["word_index"]
    st.session_state.stage = saved_data["stage"]
    st.session_state.notebook = set(saved_data["notebook"])
    st.session_state.completed_days = set(saved_data["completed_days"])
    st.session_state.initialized = True

if 'stage2_pool' not in st.session_state: st.session_state.stage2_pool = []
if 'stage2_ans' not in st.session_state: st.session_state.stage2_ans = []
if 'stage3_pool' not in st.session_state: st.session_state.stage3_pool = []
if 'stage3_ans' not in st.session_state: st.session_state.stage3_ans = []
if 'mode' not in st.session_state: st.session_state.mode = 'normal'
if 'show_answer' not in st.session_state: st.session_state.show_answer = False # 用於遮罩模式

# ==========================================
# 5. 側邊欄 (新增設定)
# ==========================================
with st.sidebar:
    st.title("🎒 冒險背包")
    
    # --- 新增功能：設定區 ---
    st.write("### ⚙️ 學習設定")
    slow_audio = st.checkbox("🐢 慢速發音 (Slow Mode)", value=False)
    mask_mode = st.checkbox("🫣 遮住中文 (Active Recall)", value=False, help="開啟後，第一關會先隱藏中文和例句，點擊後才顯示。")
    st.markdown("---")

    if st.session_state.data_loaded:
        if st.button("🗑️ 清除舊資料 (更換檔案)"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
            st.session_state.data_loaded = False
            st.session_state.initialized = False
            st.rerun()
            
    if not st.session_state.data_loaded:
        st.warning("請上傳 Word 檔")
        uploaded_file = st.file_uploader("選擇檔案...", type=['docx'])
        if uploaded_file:
            try:
                with st.spinner("解析新格式中..."):
                    df_new = parse_word_file(uploaded_file)
                    df_new.to_csv(DB_FILE, index=False)
                    st.session_state.df = df_new
                    st.session_state.data_loaded = True
                    st.session_state.current_day = 1
                    st.session_state.word_index = 0
                    st.session_state.stage = 1
                    save_current_state()
                    st.success("讀取成功！")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"錯誤: {e}")

    # 模式切換
    st.write("### 🎯 模式")
    mode_selection = st.radio("選擇", ["🌲 森林闖關", "📕 筆記本"], 
             index=0 if st.session_state.mode == 'normal' else 1)
    
    new_mode = 'normal' if "森林" in mode_selection else 'notebook'
    if new_mode != st.session_state.mode:
        st.session_state.mode = new_mode
        st.session_state.word_index = 0
        st.session_state.stage = 1
        st.rerun()

    if st.session_state.mode == 'normal' and st.session_state.data_loaded:
        st.markdown("---")
        st.write(f"目前進度: Day {st.session_state.current_day}")
        cols = st.columns(5)
        for i in range(1, 31):
            is_done = i in st.session_state.completed_days
            label = f"✅\n{i}" if is_done else f"{i}"
            has_data = not st.session_state.df.empty and i in st.session_state.df['day'].values
            
            btn_type = "primary" if i == st.session_state.current_day else "secondary"
            if cols[(i-1)%5].button(label, key=f"day_{i}", disabled=not has_data, type=btn_type):
                st.session_state.current_day = i
                st.session_state.word_index = 0
                st.session_state.stage = 1
                save_current_state()
                st.rerun()

# ==========================================
# 6. 主程式
# ==========================================
if not st.session_state.data_loaded:
    st.info("👈 請在左側上傳您的新 Word 檔案")
    st.stop()

if st.session_state.mode == 'normal':
    current_words = st.session_state.df[st.session_state.df['day'] == st.session_state.current_day].reset_index(drop=True)
    header_text = f"Day {st.session_state.current_day} - 闖關中"
else:
    if len(st.session_state.notebook) == 0:
        st.info("筆記本是空的。")
        st.stop()
    current_words = st.session_state.df[st.session_state.df['word'].isin(st.session_state.notebook)].reset_index(drop=True)
    header_text = f"📕 筆記本複習"

if current_words.empty:
    st.warning("無資料")
    st.stop()

if st.session_state.word_index >= len(current_words):
    st.balloons()
    st.success("🎉 完成！")
    if st.session_state.mode == 'normal':
        if st.session_state.current_day not in st.session_state.completed_days:
            st.session_state.completed_days.add(st.session_state.current_day)
            save_current_state()
        if st.button("🚀 下一天"):
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

# 工具函式 (支援慢速)
def play_audio(text, slow_mode=False):
    try:
        tts = gTTS(text=text, lang='en', slow=slow_mode)
        fp = BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp, format='audio/mp3', autoplay=True)
    except: pass

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

st.subheader(f"{header_text}")
st.progress((st.session_state.word_index) / len(current_words))

# --- Stage 1: 認知 (Active Recall) ---
if st.session_state.stage == 1:
    
    # 顯示英文卡片
    st.markdown(f"""
    <div class="word-card">
        <h1 style="color:#2c5e2e;">{target}</h1>
        <p style='color:#888; font-size: 1.2em;'>{pos} <span style="color:#d81b60;">/{ipa}/</span></p>
    """, unsafe_allow_html=True)
    
    # 遮罩邏輯
    if mask_mode and not st.session_state.show_answer:
        st.warning("🫣 嘗試回想中文意思與例句...")
        if st.button("👀 查看答案"):
            st.session_state.show_answer = True
            st.rerun()
    else:
        st.markdown(f"""
        <h2 style='margin-top:10px;'>{meaning}</h2>
        <div class="example-sentence">
            <b>Example:</b><br>
            {example}
        </div>
        """, unsafe_allow_html=True)
        if mask_mode:
            if st.button("🙈 隱藏"):
                st.session_state.show_answer = False
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True) # End card
    
    col1, col2, col3 = st.columns([1,1,2])
    
    in_note = target in st.session_state.notebook
    if col1.button("💔 移除" if in_note else "❤️ 筆記"):
        if in_note: st.session_state.notebook.remove(target)
        else: st.session_state.notebook.add(target)
        save_current_state()
        st.rerun()

    if col2.button("🔊 發音", key="s1_audio"):
        play_audio(target, slow_mode=slow_audio)

    if col3.button("下一步 ➡"):
        chunks = split_syllables_chunk(target)
        st.session_state.stage2_pool = random.sample(chunks, len(chunks))
        st.session_state.stage2_ans = []
        st.session_state.stage = 2
        st.session_state.show_answer = False # 重置遮罩
        save_current_state()
        st.rerun()

# --- Stage 2: 音節拼圖 ---
elif st.session_state.stage == 2:
    st.subheader("🧩 階段二：音節拼圖")
    st.info(f"提示：{meaning}")
    
    if st.button("🔊 聽發音", key="s2_audio"):
        play_audio(target, slow_mode=slow_audio)

    curr = "".join(st.session_state.stage2_ans)
    st.markdown(f'<div class="answer-column">{curr}</div>', unsafe_allow_html=True)
    
    cols = st.columns(4)
    for i, s in enumerate(st.session_state.stage2_pool):
        if s not in st.session_state.stage2_ans:
            if cols[i%4].button(s, key=f"s2_{i}"):
                st.session_state.stage2_ans.append(s)
                st.rerun()
            
    c1, c2 = st.columns(2)
    if c1.button("↺ 重來"):
        st.session_state.stage2_ans = []
        st.rerun()
    if c2.button("✅ 確認"):
        if "".join(st.session_state.stage2_ans) == target.replace(" ", ""):
            st.success("Correct!")
            time.sleep(0.5)
            chars = list(target.replace(" ", ""))
            random.shuffle(chars)
            st.session_state.stage3_pool = chars
            st.session_state.stage3_ans = []
            st.session_state.stage = 3
            save_current_state()
            st.rerun()
        else:
            st.error("錯誤")

# --- Stage 3: 字母拼寫 (自動筆記) ---
elif st.session_state.stage == 3:
    st.subheader("✍️ 階段三：字母拼寫")
    st.info(f"請拼出：{meaning}")
    
    if st.button("🔊 聽發音", key="s3_audio"):
        play_audio(target, slow_mode=slow_audio)

    curr_ans_str = "".join(st.session_state.stage3_ans)
    st.markdown(f'<div class="answer-column">{curr_ans_str}</div>', unsafe_allow_html=True)
    
    st.write("點擊字母：")
    pool_cols = st.columns(6)
    for i, char in enumerate(st.session_state.stage3_pool):
        if pool_cols[i % 6].button(char, key=f"s3_char_{i}"):
            st.session_state.stage3_ans.append(char)
            st.session_state.stage3_pool.pop(i)
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    
    ctrl_c1, ctrl_c2, ctrl_c3 = st.columns(3)
    
    if ctrl_c1.button("⌫ 退格"):
        if st.session_state.stage3_ans:
            last_char = st.session_state.stage3_ans.pop()
            st.session_state.stage3_pool.append(last_char)
            st.rerun()
            
    if ctrl_c2.button("↺ 清空"):
        st.session_state.stage3_pool.extend(st.session_state.stage3_ans)
        st.session_state.stage3_ans = []
        st.rerun()
        
    if ctrl_c3.button("✅ 送出", type="primary"):
        user_word = "".join(st.session_state.stage3_ans)
        target_clean = target.replace(" ", "")
        
        if user_word.lower() == target_clean.lower():
            st.balloons()
            st.success("太棒了！")
            time.sleep(1.0)
            st.session_state.word_index += 1
            st.session_state.stage = 1
            save_current_state()
            st.rerun()
        else:
            st.error(f"拼錯囉！正確答案是: {target}")
            # 自動加入筆記本功能
            if target not in st.session_state.notebook:
                st.session_state.notebook.add(target)
                st.toast(f"已自動加入筆記本 📕: {target}")
                save_current_state()
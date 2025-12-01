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
st.set_page_config(page_title="PET 魔法森林 (筆記本版)", page_icon="🌱", layout="centered")

ghibli_css = """
<style>
    .stApp {
        background-color: #fcfef1;
        background-image: linear-gradient(120deg, #f0f9e8 0%, #fcfef1 100%);
    }
    h1, h2, h3, div, button { font-family: 'Comic Sans MS', 'Microsoft JhengHei', sans-serif; }
    
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
    
    /* 答案列 */
    .answer-column {
        background-color: #fff9c4; padding: 15px; border-radius: 12px;
        border: 3px dashed #fbc02d; text-align: center; font-size: 2.2rem;
        color: #333; font-weight: bold; min-height: 80px; margin-bottom: 20px;
        letter-spacing: 5px;
    }

    /* 收藏按鈕樣式 (紅色) */
    .like-btn { color: #e57373 !important; border-color: #e57373 !important; background: white !important; }
</style>
"""
st.markdown(ghibli_css, unsafe_allow_html=True)

# ==========================================
# 2. 本地記憶系統 (資料庫、進度、筆記本)
# ==========================================
DB_FILE = 'pet_database.csv'
PROGRESS_FILE = 'progress.json'
NOTEBOOK_FILE = 'notebook.json'

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_json(file_path, data_set):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(list(data_set), f)

# ==========================================
# 3. Word 解析器
# ==========================================
def parse_word_file(uploaded_file):
    doc = docx.Document(uploaded_file)
    data = []
    all_rows = []
    
    for table in doc.tables:
        for row in table.rows[1:]:
            cells = row.cells
            if len(cells) >= 2:
                vocab_text = cells[0].text.strip()
                meaning_text = cells[1].text.strip()
                if vocab_text and meaning_text:
                    vocabs = re.split(r'[,，]\s*', vocab_text)
                    meanings = re.split(r'[,，]\s*', meaning_text)
                    for i, v in enumerate(vocabs):
                        clean_word = v.strip()
                        clean_word = re.sub(r'\(.*?\)', '', clean_word).strip()
                        if clean_word:
                            m = meanings[i].strip() if i < len(meanings) else meaning_text
                            all_rows.append({"word": clean_word, "meaning": m, "pos": "單字"})

    total_words = len(all_rows)
    if total_words > 0:
        chunk_size = max(1, total_words // 28 + 1)
        for idx, row in enumerate(all_rows):
            day_num = (idx // chunk_size) + 1
            if day_num > 28: day_num = 28
            row['day'] = day_num
            data.append(row)
            
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

if 'completed_days' not in st.session_state: st.session_state.completed_days = load_json(PROGRESS_FILE)
if 'notebook' not in st.session_state: st.session_state.notebook = load_json(NOTEBOOK_FILE)

if 'current_day' not in st.session_state: st.session_state.current_day = 1
if 'word_index' not in st.session_state: st.session_state.word_index = 0
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'stage3_pool' not in st.session_state: st.session_state.stage3_pool = []
if 'stage3_ans' not in st.session_state: st.session_state.stage3_ans = []
if 'mode' not in st.session_state: st.session_state.mode = 'normal' # normal 或 notebook

# ==========================================
# 5. 側邊欄
# ==========================================
with st.sidebar:
    st.title("🎒 冒險背包")
    
    # 模式切換
    st.write("### 🎯 選擇模式")
    mode_selection = st.radio("模式", ["🌲 森林闖關 (每日進度)", "📕 魔法筆記本 (重點複習)"], 
             index=0 if st.session_state.mode == 'normal' else 1)
    
    new_mode = 'normal' if "森林" in mode_selection else 'notebook'
    if new_mode != st.session_state.mode:
        st.session_state.mode = new_mode
        st.session_state.word_index = 0
        st.session_state.stage = 1
        st.rerun()

    if st.session_state.mode == 'notebook':
        st.info(f"筆記本目前有 **{len(st.session_state.notebook)}** 個單字")
        if len(st.session_state.notebook) == 0:
            st.warning("筆記本是空的！快去闖關把不會的字加入筆記吧！")

    # 檔案上傳 (只在需要時顯示)
    if not st.session_state.data_loaded:
        st.warning("⚠️ 請先上傳檔案")
        uploaded_file = st.file_uploader("上傳 PET 詞彙28天.docx", type=['docx'])
        if uploaded_file:
            try:
                with st.spinner("讀取中..."):
                    df_new = parse_word_file(uploaded_file)
                    df_new.to_csv(DB_FILE, index=False)
                    st.session_state.df = df_new
                    st.session_state.data_loaded = True
                    st.success("成功！")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"錯誤: {e}")
    
    # 30天地圖 (只在普通模式顯示)
    if st.session_state.mode == 'normal' and st.session_state.data_loaded:
        st.markdown("---")
        st.write("### 🗺️ 30天進度")
        cols = st.columns(5)
        for i in range(1, 31):
            is_done = i in st.session_state.completed_days
            label = f"✅\n{i}" if is_done else f"{i}"
            has_data = not st.session_state.df.empty and i in st.session_state.df['day'].values
            
            # 高亮目前天數
            btn_type = "primary" if i == st.session_state.current_day else "secondary"
            
            if cols[(i-1)%5].button(label, key=f"day_{i}", disabled=not has_data, type=btn_type):
                st.session_state.current_day = i
                st.session_state.word_index = 0
                st.session_state.stage = 1
                st.rerun()

# ==========================================
# 6. 主程式
# ==========================================
if not st.session_state.data_loaded:
    st.stop()

# 決定要顯示哪些單字
if st.session_state.mode == 'normal':
    # 顯示當天的單字
    current_words = st.session_state.df[st.session_state.df['day'] == st.session_state.current_day].reset_index(drop=True)
    header_text = f"Day {st.session_state.current_day} - 闖關中"
else:
    # 顯示筆記本中的單字
    if len(st.session_state.notebook) == 0:
        st.header("📕 魔法筆記本")
        st.image("https://cdn-icons-png.flaticon.com/512/7486/7486803.png", width=100)
        st.write("你的筆記本是空的。")
        st.write("去「森林闖關」模式，看到不會的字點擊 ❤️ 就可以加進來喔！")
        st.stop()
        
    # 篩選出筆記本裡的字
    current_words = st.session_state.df[st.session_state.df['word'].isin(st.session_state.notebook)].reset_index(drop=True)
    header_text = f"📕 魔法筆記本 - 複習 ({len(current_words)} 字)"

if current_words.empty:
    st.warning("沒有單字資料。")
    st.stop()

# 檢查是否完成
if st.session_state.word_index >= len(current_words):
    st.balloons()
    st.success("🎉 恭喜！這組單字全部練習完畢！")
    
    # 只有在普通模式才打卡
    if st.session_state.mode == 'normal':
        if st.session_state.current_day not in st.session_state.completed_days:
            st.session_state.completed_days.add(st.session_state.current_day)
            save_json(PROGRESS_FILE, st.session_state.completed_days)
            st.toast("打卡成功！")
        if st.button("🚀 下一天"):
            st.session_state.current_day += 1
            st.session_state.word_index = 0
            st.session_state.stage = 1
            st.rerun()
    else:
        if st.button("🔄 再複習一次"):
            st.session_state.word_index = 0
            st.session_state.stage = 1
            st.rerun()
    st.stop()

# 取得目前單字
w_data = current_words.iloc[st.session_state.word_index]
target = str(w_data['word'])
meaning = str(w_data['meaning'])
pos = str(w_data.get('pos', ''))

# 工具函式
def play_audio(text, autoplay=False):
    try:
        tts = gTTS(text=text, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp, format='audio/mp3', autoplay=autoplay)
    except: pass

def split_syllables(word):
    if " " in word: return word.split(" ")
    syllables = []
    temp = word
    while len(temp) > 0:
        cut = 3 if len(temp) > 5 else 2
        if len(temp) <= 3: syllables.append(temp); break
        syllables.append(temp[:cut])
        temp = temp[cut:]
    return syllables

# 介面顯示
st.subheader(f"{header_text}")
st.progress((st.session_state.word_index) / len(current_words))

# --- Stage 1: 認知 ---
if st.session_state.stage == 1:
    st.markdown(f"""
    <div class="word-card">
        <h1>{target}</h1>
        <p style='color:#666;'>{pos}</p>
        <h2>{meaning}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    play_audio(target, autoplay=True)
    
    # 筆記本操作按鈕
    col_note, col_audio, col_next = st.columns([1, 1, 2])
    
    # 判斷是否在筆記本中
    is_in_notebook = target in st.session_state.notebook
    
    with col_note:
        if is_in_notebook:
            if st.button("💔 移除", help="從筆記本移除"):
                st.session_state.notebook.remove(target)
                save_json(NOTEBOOK_FILE, st.session_state.notebook)
                st.toast(f"已移除 {target}")
                st.rerun()
        else:
            if st.button("❤️ 筆記", help="加入筆記本"):
                st.session_state.notebook.add(target)
                save_json(NOTEBOOK_FILE, st.session_state.notebook)
                st.toast(f"已收藏 {target}！")
                st.rerun()

    with col_audio:
        if st.button("🔊 發音"): play_audio(target)
        
    with col_next:
        if st.button("下一步 ➡"):
            st.session_state.shuffled_syl = random.sample(split_syllables(target), len(split_syllables(target)))
            st.session_state.user_ans = []
            st.session_state.stage = 2
            st.rerun()

# --- Stage 2: 音節拼圖 ---
elif st.session_state.stage == 2:
    st.subheader("🧩 階段二：拼湊音節")
    st.info(f"提示：{meaning}")
    
    curr = "".join(st.session_state.user_ans)
    st.markdown(f'<div class="answer-column">{curr}</div>', unsafe_allow_html=True)
    
    cols = st.columns(4)
    for i, s in enumerate(st.session_state.shuffled_syl):
        if cols[i%4].button(s, key=f"s2_{i}"):
            st.session_state.user_ans.append(s)
            st.rerun()
            
    c1, c2 = st.columns(2)
    if c1.button("↺ 重來"):
        st.session_state.user_ans = []
        st.rerun()
    if c2.button("✅ 確認"):
        if "".join(st.session_state.user_ans) == target.replace(" ", ""):
            st.success("Correct!")
            time.sleep(0.5)
            # 準備 Stage 3
            chars = list(target.replace(" ", ""))
            random.shuffle(chars)
            st.session_state.stage3_pool = chars
            st.session_state.stage3_ans = []
            st.session_state.stage = 3
            st.rerun()
        else:
            st.error("錯誤，請再試試！")

# --- Stage 3: 字母方塊拼寫 (觸控版) ---
elif st.session_state.stage == 3:
    st.subheader("✍️ 階段三：字母拼寫")
    st.info(f"請拼出：{meaning}")
    
    # 答案區
    curr_ans_str = "".join(st.session_state.stage3_ans)
    st.markdown(f'<div class="answer-column">{curr_ans_str}</div>', unsafe_allow_html=True)
    
    # 字母按鈕池
    st.write("點擊下方字母填入：")
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
            st.rerun()
        else:
            st.error(f"拼錯囉！再試試看！")
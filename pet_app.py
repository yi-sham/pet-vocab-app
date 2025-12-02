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
st.set_page_config(page_title="PET 魔法森林 (存檔版)", page_icon="🌱", layout="centered")

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
    
    /* 音節方塊 (Stage 2) */
    .syllable-box {
        display: inline-block; background-color: #ff8c42; color: white;
        padding: 10px 15px; margin: 5px; border-radius: 8px;
        font-size: 1.2rem; font-weight: bold; border-bottom: 3px solid #d85c00;
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
# 2. 強大記憶系統 (資料庫 + 詳細進度)
# ==========================================
DB_FILE = 'pet_database.csv'
SAVE_FILE = 'user_save.json' # 專門存現在測到哪裡

def load_save_state():
    """讀取上次的詳細進度"""
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    # 預設值
    return {
        "current_day": 1,
        "word_index": 0,
        "stage": 1,
        "notebook": [],
        "completed_days": []
    }

def save_current_state():
    """隨時儲存目前的詳細進度"""
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
# 4. 初始化 (載入資料與進度)
# ==========================================
# 1. 載入單字庫
if 'df' not in st.session_state:
    if os.path.exists(DB_FILE):
        st.session_state.df = pd.read_csv(DB_FILE)
        st.session_state.data_loaded = True
    else:
        st.session_state.df = pd.DataFrame()
        st.session_state.data_loaded = False

# 2. 載入使用者進度 (如果是第一次開啟)
if 'initialized' not in st.session_state:
    saved_data = load_save_state()
    st.session_state.current_day = saved_data["current_day"]
    st.session_state.word_index = saved_data["word_index"]
    st.session_state.stage = saved_data["stage"]
    st.session_state.notebook = set(saved_data["notebook"])
    st.session_state.completed_days = set(saved_data["completed_days"])
    st.session_state.initialized = True

# 其他 UI 變數
if 'stage2_pool' not in st.session_state: st.session_state.stage2_pool = []
if 'stage2_ans' not in st.session_state: st.session_state.stage2_ans = []
if 'stage3_pool' not in st.session_state: st.session_state.stage3_pool = []
if 'stage3_ans' not in st.session_state: st.session_state.stage3_ans = []
if 'mode' not in st.session_state: st.session_state.mode = 'normal'

# ==========================================
# 5. 側邊欄 (檔案管理與地圖)
# ==========================================
with st.sidebar:
    st.title("📂 資料中心")
    
    # 更換檔案邏輯
    if st.session_state.data_loaded:
        if st.button("🗑️ 清除舊資料 (更換檔案)"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE) # 也要清除進度，不然會報錯
            st.session_state.data_loaded = False
            st.session_state.initialized = False # 重新初始化
            st.rerun()
            
    # 上傳區
    if not st.session_state.data_loaded:
        st.warning("請上傳 Word 檔")
        uploaded_file = st.file_uploader("選擇檔案...", type=['docx'])
        if uploaded_file:
            try:
                with st.spinner("魔法讀取中..."):
                    df_new = parse_word_file(uploaded_file)
                    df_new.to_csv(DB_FILE, index=False)
                    st.session_state.df = df_new
                    st.session_state.data_loaded = True
                    # 重置進度
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
    st.markdown("---")
    st.write("### 🎯 選擇模式")
    mode_selection = st.radio("模式", ["🌲 森林闖關", "📕 筆記本"], 
             index=0 if st.session_state.mode == 'normal' else 1)
    
    new_mode = 'normal' if "森林" in mode_selection else 'notebook'
    if new_mode != st.session_state.mode:
        st.session_state.mode = new_mode
        st.session_state.word_index = 0
        st.session_state.stage = 1
        st.rerun()

    # 30天地圖
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
                save_current_state() # 切換天數也要存檔
                st.rerun()

# ==========================================
# 6. 主程式
# ==========================================
if not st.session_state.data_loaded:
    st.info("👈 請在左側上傳 Word 檔")
    st.stop()

# 決定單字列表
if st.session_state.mode == 'normal':
    current_words = st.session_state.df[st.session_state.df['day'] == st.session_state.current_day].reset_index(drop=True)
    header_text = f"Day {st.session_state.current_day} - 闖關中"
else:
    if len(st.session_state.notebook) == 0:
        st.info("筆記本是空的，快去收藏單字吧！")
        st.stop()
    current_words = st.session_state.df[st.session_state.df['word'].isin(st.session_state.notebook)].reset_index(drop=True)
    header_text = f"📕 筆記本複習"

if current_words.empty:
    st.warning("無資料")
    st.stop()

# 檢查完成
if st.session_state.word_index >= len(current_words):
    st.balloons()
    st.success("🎉 本日挑戰完成！")
    if st.session_state.mode == 'normal':
        if st.session_state.current_day not in st.session_state.completed_days:
            st.session_state.completed_days.add(st.session_state.current_day)
            save_current_state() # 完成也存檔
        if st.button("🚀 進入下一天"):
            st.session_state.current_day += 1
            st.session_state.word_index = 0
            st.session_state.stage = 1
            save_current_state()
            st.rerun()
    else:
        if st.button("🔄 重頭複習"):
            st.session_state.word_index = 0
            st.session_state.stage = 1
            st.rerun()
    st.stop()

# 取得目前單字
w_data = current_words.iloc[st.session_state.word_index]
target = str(w_data['word'])
meaning = str(w_data['meaning'])
pos = str(w_data.get('pos', ''))

# 工具函式：發音與拆字
def play_audio(text):
    try:
        tts = gTTS(text=text, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp, format='audio/mp3', autoplay=True)
    except: pass

def split_syllables_chunk(word):
    """第二階段用：簡單的音節塊拆分"""
    if " " in word: return word.split(" ")
    chunks = []
    temp = word
    while len(temp) > 0:
        # 簡單邏輯：3個字母或2個字母一組
        cut = 3 if len(temp) > 5 else 2
        if len(temp) <= 3: chunks.append(temp); break
        chunks.append(temp[:cut])
        temp = temp[cut:]
    return chunks

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
    
    # 自動發音 (第一次進入時)
    # 為了避免重整一直念，可以加個 session 判斷，這裡簡化直接放按鈕比較不吵
    
    col1, col2, col3 = st.columns([1,1,2])
    
    # 筆記按鈕
    in_note = target in st.session_state.notebook
    if col1.button("💔 移除" if in_note else "❤️ 筆記"):
        if in_note: st.session_state.notebook.remove(target)
        else: st.session_state.notebook.add(target)
        save_current_state() # 筆記變動也要存
        st.rerun()

    # 發音按鈕 (第一階段)
    if col2.button("🔊 發音", key="s1_audio"):
        play_audio(target)

    if col3.button("下一步 ➡"):
        # 準備 Stage 2 (音節塊)
        chunks = split_syllables_chunk(target)
        st.session_state.stage2_pool = random.sample(chunks, len(chunks))
        st.session_state.stage2_ans = []
        st.session_state.stage = 2
        save_current_state() # 進下一關存檔
        st.rerun()

# --- Stage 2: 音節拼圖 (Syllable Puzzle) ---
elif st.session_state.stage == 2:
    st.subheader("🧩 階段二：音節拼圖")
    st.info(f"提示：{meaning}")
    
    # 發音按鈕 (第二階段)
    if st.button("🔊 聽發音提示", key="s2_audio"):
        play_audio(target)

    # 答案區
    curr = "".join(st.session_state.stage2_ans)
    st.markdown(f'<div class="answer-column">{curr}</div>', unsafe_allow_html=True)
    
    # 選項區
    cols = st.columns(4)
    for i, s in enumerate(st.session_state.stage2_pool):
        if s not in st.session_state.stage2_ans: # 簡單邏輯：點過的隱藏
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
            # 準備 Stage 3 (字母打散)
            chars = list(target.replace(" ", ""))
            random.shuffle(chars)
            st.session_state.stage3_pool = chars
            st.session_state.stage3_ans = []
            st.session_state.stage = 3
            save_current_state() # 進下一關存檔
            st.rerun()
        else:
            st.error("錯誤")

# --- Stage 3: 字母拼寫 (Letter Spelling) ---
elif st.session_state.stage == 3:
    st.subheader("✍️ 階段三：字母拼寫")
    st.info(f"請拼出：{meaning}")
    
    # 發音按鈕 (第三階段)
    if st.button("🔊 聽發音提示", key="s3_audio"):
        play_audio(target)

    # 答案區
    curr_ans_str = "".join(st.session_state.stage3_ans)
    st.markdown(f'<div class="answer-column">{curr_ans_str}</div>', unsafe_allow_html=True)
    
    # 字母按鈕池
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
            save_current_state() # 完成一個字也要存
            st.rerun()
        else:
            st.error(f"拼錯囉！")
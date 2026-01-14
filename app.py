import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter

# ==========================================
# MIRU-PAD: FINAL ARCHITECTURE
# Based on User's Original Logic + Global Sync
# ==========================================

# --- 1. SETTINGS & CONSTANTS ---
DATA_FILE = "miru_global_state.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# オリジナルコードから移植した定数
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# --- 2. STATE MANAGEMENT (JSON) ---
def load_state():
    default_state = {
        "date": "2000-01-01",
        "N4": {"last": "----", "preds": ["----"]*10},
        "N3": {"last": "----", "preds": ["---"]*10},
        "NM": {"last": "----", "preds": ["--"]*10},
    }
    if not os.path.exists(DATA_FILE):
        return default_state
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # マージ（キー不足対策）
            for k in default_state:
                if k not in data: data[k] = default_state[k]
            return data
    except:
        return default_state

def save_state(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- 3. LOGIC ENGINE (Original Port) ---
def fetch_history_logic(game_type):
    # スクレイピングロジック (オリジナル準拠)
    if game_type == 'N4':
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        cols = ['n1', 'n2', 'n3', 'n4']
    elif game_type == 'N3' or game_type == 'NM':
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers3/index.html"
        cols = ['n1', 'n2', 'n3']
    
    headers = {"User-Agent": "Mozilla/5.0"}
    history = []
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        for row in rows:
            data = row.find('td', class_='alnCenter')
            if data:
                val = data.text.strip().replace(' ', '')
                if val.isdigit() and len(val) == len(cols):
                    history.append([int(d) for d in val])
        if not history: return None, None
    except:
        return None, None

    last_val_str = "".join(map(str, history[0]))
    trends = {}
    for i, col in enumerate(cols):
        spins = []
        for j in range(len(history) - 1):
            curr_idx = INDEX_MAP[col][history[j][i]]
            prev_idx = INDEX_MAP[col][history[j+1][i]]
            spins.append((curr_idx - prev_idx) % 10)
        trends[col] = Counter(spins).most_common(1)[0][0] if spins else 0
    
    return last_val_str, trends

def apply_gravity_final(idx, mode):
    if mode == 'chaos': return random.randint(0, 9)
    sectors = GRAVITY_SECTORS if mode == 'ace' else ANTI_GRAVITY_SECTORS
    candidates = [{'idx': idx, 'score': 1.0}]
    for s in [-1, 1, 0]:
        n_idx = (idx + s) % 10
        if n_idx in sectors: candidates.append({'idx': n_idx, 'score': 1.5})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[0]['idx'] if random.random() < 0.7 else candidates[-1]['idx']

def run_prediction_logic(game_type, last_val, trends):
    # オリジナルの予測ロジック
    if not last_val or not trends: return ["ERROR"] * 10
    
    cols = ['n1', 'n2', 'n3', 'n4'] if game_type == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(d) for d in last_val]
    roles = ['ace', 'shift', 'chaos', 'ace', 'shift', 'ace', 'shift', 'ace', 'shift', 'chaos']
    preds = []
    seen = set()

    for role in roles:
        for attempt in range(50):
            row_str = ""
            for i, col in enumerate(cols):
                curr_idx = INDEX_MAP[col][last_nums[i]]
                t_spin = trends[col]
                if attempt > 0: t_spin = (t_spin + random.choice([1, -1, 5, 2, -2])) % 10
                
                if role == 'chaos': spin = random.randint(0, 9)
                elif role == 'shift': spin = (t_spin + random.choice([1, -1, 5])) % 10
                else: spin = t_spin if random.random() > 0.2 else (t_spin + 1) % 10
                
                final_idx = apply_gravity_final((curr_idx + spin) % 10, role)
                row_str += str(WINDMILL_MAP[col][final_idx])
            
            # Miniの場合は下2桁だけで重複チェック
            check_val = row_str[-2:] if game_type == 'NM' else row_str
            
            if check_val not in seen:
                seen.add(check_val)
                # Miniの場合は下2桁だけ格納、他はそのまま
                final_val = row_str[-2:] if game_type == 'NM' else row_str
                preds.append(final_val)
                break
        if len(preds) < roles.index(role) + 1:
            # 埋まらなかった場合の埋め合わせ
            digits = 2 if game_type == 'NM' else len(cols)
            preds.append("".join([str(random.randint(0,9)) for _ in range(digits)]))
            
    return preds

# --- 4. INITIALIZATION & UPDATE ---
if 'game_mode' not in st.session_state: st.session_state.game_mode = 'N4'
if 'count' not in st.session_state: st.session_state.count = 10

state = load_state()
gm = st.session_state.game_mode

# 起動時/切替時にデータがなければ取りに行く
if state[gm]["last"] == "----":
    l_val, trends = fetch_history_logic(gm)
    if l_val:
        state[gm]["last"] = l_val
        save_state(state)
        st.rerun()

# --- 5. UI CONSTRUCTION ---

# CSSでデザインを再現
st.markdown("""
<style>
    .stApp { background-color: #000; color: #fff; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 100%; }
    
    /* 液晶画面 */
    .lcd-box {
        background-color: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        padding: 10px;
        min-height: 180px;
        box-shadow: inset 0 0 15px rgba(0,0,0,0.6);
        text-align: center;
        margin-bottom: 10px;
    }
    .lcd-label { font-size: 10px; color: #444; font-weight: bold; margin-bottom: 5px; }
    .lcd-nums {
        display: grid; grid-template-columns: 1fr 1fr; gap: 5px 20px;
        font-family: 'Courier New', monospace; font-weight: bold; font-size: 24px; color: #000;
        letter-spacing: 3px;
    }
    
    /* コントロールバー */
    .control-row {
        display: flex; align-items: center; justify-content: space-between;
        background: #222; border-radius: 30px; padding: 5px 10px; margin-bottom: 15px;
    }
    .count-text { font-size: 18px; font-weight: bold; color: white; margin: 0 10px; }
    
    /* Streamlitボタンの上書きスタイル */
    div.stButton > button { font-weight: bold; border-radius: 10px; border: none; }
    
    /* 丸ボタン (-/+) */
    div[data-testid="column"]:nth-of-type(1) button, 
    div[data-testid="column"]:nth-of-type(3) button {
        border-radius: 50% !important; width: 40px !important; height: 40px !important;
        background: #444 !important; border: 2px solid #666 !important;
        font-size: 20px !important; padding: 0 !important;
    }
    
    /* CALCボタン (右端) */
    div[data-testid="column"]:nth-of-type(4) button {
        background-color: #009688 !important; color: white !important;
        border-radius: 20px !important; height: 40px !important; width: 100% !important;
    }
    div[data-testid="column"]:nth-of-type(4) button:hover {
        box-shadow: 0 0 10px #00ffcc;
    }
    div[data-testid="column"]:nth-of-type(4) button:disabled {
        background-color: #333 !important; color: #777 !important;
    }

    /* ゲームボタンの色分け (Grid配置) */
    /* Row 1 */
    div[data-testid="column"]:nth-of-type(1) div.row-widget button { background: #E91E63; color: white; } /* Loto */
    div[data-testid="column"]:nth-of-type(2) div.row-widget button { background: #009688; color: white; } /* Num */
    
</style>
""", unsafe_allow_html=True)

# --- PART A: LCD SCREEN ---
current_last = state[gm]["last"]
current_preds = state[gm]["preds"]

# データ未取得時の表示
if current_last == "----":
    display_last = "FETCHING..." 
else:
    display_last = current_last

# 液晶描画 (HTML/Markdown)
st.markdown(f"""
<div class="lcd-box">
    <div class="lcd-label">LAST RESULT ({gm}): {display_last}</div>
    <div class="lcd-nums">
        {''.join([f'<div>{p}</div>' for p in current_preds[:st.session_state.count]])}
    </div>
</div>
""", unsafe_allow_html=True)

# --- PART B: CONTROL BAR ---
# [ - ] [ 10口 ] [ + ] [ CALC ]
c1, c2, c3, c4 = st.columns([1, 2, 1, 2.5])

# CSSハックでボタンを横並び維持
st.markdown("""<style>div[data-testid="column"] { display: flex; justify-content: center; }</style>""", unsafe_allow_html=True)

with c1:
    if st.button("－"):
        if st.session_state.count > 1: st.session_state.count -= 1
        st.rerun()
with c2:
    st.markdown(f"<div class='count-text' style='text-align:center; line-height:40px;'>{st.session_state.count} 口</div>", unsafe_allow_html=True)
with c3:
    if st.button("＋"):
        if st.session_state.count < 10: st.session_state.count += 1
        st.rerun()
with c4:
    # 20:00-22:00はロックするロジック (必要なら有効化)
    now_h = datetime.now(JST).hour
    is_calc_time = (now_h >= 22 or now_h < 20)
    btn_label = "CALC" if is_calc_time else "WAIT"
    
    # データがない場合は強制的にCALCを押させて取得を試みる
    if current_last == "----": is_calc_time = True
    
    if st.button(btn_label, disabled=not is_calc_time):
        # 計算実行
        l_val, trends = fetch_history_logic(gm)
        if l_val:
            state[gm]["last"] = l_val # 最新結果更新
            new_preds = run_prediction_logic(gm, l_val, trends) # 予測実行
            state[gm]["preds"] = new_preds
            save_state(state) # 保存
            st.rerun()
        else:
            st.error("Failed to fetch data.")

# --- PART C: GAME SELECTOR GRID ---
st.write("") # Spacer

# レイアウト用のスタイル上書き (各ボタンの色を強制指定)
st.markdown("""
<style>
/* 特定のボタンの色を上書きするためのCSSクラス指定はStreamlitでは難しいので
   行ごとのボタンに対してCSSを当てる */
   
/* Numbers Mini (3行目右) をオレンジに */
/* Loto系はピンク、Num系は緑 */
</style>
""", unsafe_allow_html=True)

# Grid Layout
r1c1, r1c2 = st.columns(2)
with r1c1: st.button("LOTO 7", disabled=True)
with r1c2: 
    if st.button("Numbers 4"): 
        st.session_state.game_mode = 'N4'
        st.rerun()

r2c1, r2c2 = st.columns(2)
with r2c1: st.button("LOTO 6", disabled=True)
with r2c2: 
    if st.button("Numbers 3"): 
        st.session_state.game_mode = 'N3'
        st.rerun()

r3c1, r3c2 = st.columns(2)
with r3c1: st.button("MINI LOTO", disabled=True)
with r3c2: 
    if st.button("Numbers mini"): 
        st.session_state.game_mode = 'NM'
        st.rerun()

r4c1, r4c2 = st.columns(2)
with r4c1: st.button("BINGO 5", disabled=True)
with r4c2: 
    if st.button("UPDATE DATA"): # 手動更新ボタン
        l_val, trends = fetch_history_logic(gm)
        if l_val:
            state[gm]["last"] = l_val
            save_state(state)
            st.rerun()

# 色の微調整 (Numbers miniをオレンジにするなど)
st.markdown("""
<script>
    // Streamlitのボタンにはクラスがないため、CSSだけで個別指定は限界がある。
    // 色分けは上記のCSSセクションで大まかに行っている (左列ピンク、右列緑)。
    // Miniだけオレンジにしたい場合はPython側でkeyを変えてCSSセレクタで狙う必要があるが、
    // 今回はシンプルに「右列＝緑」で統一してある。
</script>
""", unsafe_allow_html=True)

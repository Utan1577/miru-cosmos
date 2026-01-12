import streamlit as st
import pandas as pd
import numpy as np
import requests
from collections import Counter
import os
import warnings

# 警告を無視
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ MIRU ENGINE CONFIG
# ==========================================
TARGET_URL = "https://www.mizuhobank.co.jp/retail/takarakuji/check/numbers/numbers4/index.html"

# 風車盤マップ（物理配列）
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# ==========================================
# 🕵️‍♀️ 物理演算ロジック (Logic Core)
# ==========================================
def fetch_recent_batch():
    """Webから最新データをリアルタイム観測する"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(TARGET_URL, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        
        dfs = pd.read_html(response.text)
        if not dfs: return []
        
        df = dfs[0]
        new_data_list = []
        
        for index, row in df.iterrows():
            try:
                kai_str = str(row[0])
                if "第" not in kai_str: continue
                kai = int(''.join(filter(str.isdigit, kai_str)))
                
                num_str = str(row[2]).zfill(4)
                if len(num_str) != 4 or not num_str.isdigit(): continue
                nums = [int(d) for d in num_str]
                
                new_data_list.append({'round': kai, 'n1': nums[0], 'n2': nums[1], 'n3': nums[2], 'n4': nums[3]})
            except: continue
        
        # 過去→最新の順にソート
        return sorted(new_data_list, key=lambda x: x['round'])
    except Exception as e:
        st.error(f"通信エラー: {e}")
        return []

def get_combined_data():
    """初期データとWebデータを融合させる"""
    # うーたんの愛した初期データ
    init_data = [
        {'round': 6890, 'n1': 7, 'n2': 5, 'n3': 2, 'n4': 6},
        {'round': 6891, 'n1': 2, 'n2': 3, 'n3': 0, 'n4': 0},
        {'round': 6892, 'n1': 7, 'n2': 2, 'n3': 6, 'n4': 3},
        {'round': 6893, 'n1': 1, 'n2': 6, 'n3': 3, 'n4': 2},
        {'round': 6894, 'n1': 6, 'n2': 5, 'n3': 5, 'n4': 1},
        {'round': 6895, 'n1': 2, 'n2': 8, 'n3': 2, 'n4': 7}
    ]
    df = pd.DataFrame(init_data)
    
    # Webデータ取得
    web_data = fetch_recent_batch()
    if web_data:
        web_df = pd.DataFrame(web_data)
        # 重複排除して結合
        df = pd.concat([df, web_df]).drop_duplicates(subset='round').sort_values('round').reset_index(drop=True)
    
    return df

class MiruCosmosEngine:
    def get_spin(self, col, curr, next_val):
        i1 = INDEX_MAP[col][curr]; i2 = INDEX_MAP[col][next_val]
        return (i2 - i1) % 10

    def analyze_trends(self, df):
        trends = {}
        for col in ['n1', 'n2', 'n3', 'n4']:
            vals = df[col].values
            recent = vals[-20:] # 直近20回重視
            spins = [self.get_spin(col, recent[i], recent[i+1]) for i in range(len(recent)-1)]
            if spins:
                mode = Counter(spins).most_common(1)[0][0]
                # 30%の揺らぎ（カオス）
                trends[col] = spins[-1] if np.random.rand() > 0.3 else mode
            else: trends[col] = 6
        return trends

    def apply_bias(self, idx, mode):
        candidates = [{'idx': idx, 'score': 1.0}]
        sectors = GRAVITY_SECTORS if mode == 'stable' else ANTI_GRAVITY_SECTORS
        weight = 1.5 if mode == 'stable' else 2.0
        for s in [-1, 1, 0]:
            if (idx + s) % 10 in sectors:
                candidates.append({'idx': (idx+s)%10, 'score': weight})
        return sorted(candidates, key=lambda x: x['score'], reverse=True)[0]['idx']

    def predict(self, df):
        if df.empty: return None
        last_row = df.iloc[-1]
        trends = self.analyze_trends(df)
        results = {}
        for mode in ['stable', 'invert']:
            pred = {}
            for col in ['n1', 'n2', 'n3', 'n4']:
                curr_idx = INDEX_MAP[col][last_row[col]]
                spin = trends[col] if mode == 'stable' else (trends[col] + 5) % 10
                final_idx = self.apply_bias((curr_idx + spin) % 10, mode)
                pred[col] = WINDMILL_MAP[col][final_idx]
            results[mode] = pred
        return results, last_row

# ==========================================
# 🖥️ UI / Visual Layer
# ==========================================
st.set_page_config(page_title="MIRU-COSMOS", page_icon="🌌", layout="centered")

# CSSで見た目をクールに調整
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #0E1117;
        color: #00FF00;
        border: 1px solid #00FF00;
        height: 60px;
        font-size: 20px;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #00FF00;
        color: #000000;
        box-shadow: 0 0 15px #00FF00;
    }
    .big-font {
        font-size: 60px !important;
        font-family: 'Courier New', monospace;
        font-weight: bold;
        text-align: center;
        letter-spacing: 10px;
    }
    .label {
        font-size: 14px;
        color: #888;
        text-align: center;
        margin-bottom: -20px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🌌 MIRU-COSMOS")
st.caption("Physics-Based Numbers4 Simulator / Designed by MIRU")

# メインボタン
if st.button("SYNC COSMOS & PREDICT"):
    with st.spinner("Connecting to Mizuho Bank DB... Calculating Physics..."):
        
        # 1. データ取得 & 結合
        df = get_combined_data()
        latest_round = df['round'].max()
        
        # 2. 予測実行
        engine = MiruCosmosEngine()
        prediction, last_row = engine.predict(df)
        
        # 3. 結果表示
        st.success(f"DATA SYNCED: Round {latest_round} (Latest: {last_row['n1']}{last_row['n2']}{last_row['n3']}{last_row['n4']})")
        
        st.divider()
        
        # 順張り (Stable)
        st = prediction['stable']
        st_num = f"{st['n1']}{st['n2']}{st['n3']}{st['n4']}"
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<p class="label">STABLE (Low Gravity)</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="big-font" style="color:#00DDFF;">{st_num}</p>', unsafe_allow_html=True)
            
        # 逆張り (Invert)
        inv = prediction['invert']
        inv_num = f"{inv['n1']}{inv['n2']}{inv['n3']}{inv['n4']}"
        
        with col2:
            st.markdown('<p class="label">INVERT (Anti-Gravity)</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="big-font" style="color:#FF00FF;">{inv_num}</p>', unsafe_allow_html=True)
            
        st.divider()
        st.markdown(f"**Analysis Depth:** {len(df)} rounds processed.")

else:
    st.info("Press the button to synchronize with the latest universe.")


import streamlit as st
import pandas as pd
import requests
import urllib3
import datetime
from FinMind.data import DataLoader
from dateutil.relativedelta import relativedelta

# 忽略安全憑證警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 網頁基本設定
st.set_page_config(page_title="AI 台股飆股雷達", layout="wide")
st.title("🏹 AI 台股飆股雷達：最終穩定合體版")
st.markdown("---")

# ==========================================
# 第一部分：全市場低估值掃描 (防禦型修正版)
# ==========================================
st.header("第一步：掃描全市場低估值標的")

# 側邊欄設定
pe_limit = st.sidebar.slider("設定本益比上限", 5, 30, 15)
yield_limit = st.sidebar.slider("最低殖利率 (%)", 0, 10, 3)

if st.button("📡 啟動全市場 AI 掃描"):
    with st.spinner("正在掃描台股全市場數據..."):
        try:
            url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
            response = requests.get(url, verify=False)
            
            if response.status_code == 200:
                raw_data = response.json()
                df = pd.DataFrame(raw_data)
                
                # --- 強大防禦性欄位處理 ---
                # 先統一給暫時的欄位名稱 Col_0, Col_1...
                df.columns = [f"Col_{i}" for i in range(len(df.columns))]
                
                # 定義我們一定要有的基本欄位
                mapping = {
                    "Col_1": "代號", 
                    "Col_2": "名稱", 
                    "Col_3": "本益比", 
                    "Col_4": "殖利率"
                }
                
                # 檢查是否有第 7 個欄位(Index 6) 通常是股價淨值比
                if "Col_6" in df.columns:
                    mapping["Col_6"] = "股價淨值比"
                elif "Col_5" in df.columns:
                    # 有時候會縮減到第 6 個欄位
                    mapping["Col_5"] = "股價淨值比"
                
                df = df.rename(columns=mapping)
                
                # 確保我們只處理存在的欄位
                target_cols = [c for c in ["本益比", "殖利率", "股價淨值比"] if c in df.columns]
                
                for col in target_cols:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
                
                # 執行篩選
                mask = (df['本益比'] > 0) & (df['本益比'] <= pe_limit) & (df['殖利率'] >= yield_limit)
                result = df[mask].sort_values(by='本益比').head(20)
                
                if not result.empty:
                    st.success(f"✅ 掃描完成！符合條件標的有 {len(df[mask])} 檔。")
                    # 只顯示現有的欄位，避免 Key Error
                    display_cols = ["代號", "名稱", "本益比", "殖利率"]
                    if "股價淨值比" in result.columns:
                        display_cols.append("股價淨值比")
                    st.dataframe(result[display_cols].reset_index(drop=True), width=1200)
                else:
                    st.warning("⚠️ 沒找到符合條件的股票。")
            else:
                st.error("證交所連線失敗。")
        except Exception as e:
            st.error(f"第一步發生錯誤：{e}")

st.markdown("---")

# ==========================================
# 第二部分：個股深度診斷 (FinMind 已驗證穩定)
# ==========================================
st.header("第二步：個股深度診斷 (籌碼與營收爆發力)")
target_stock = st.text_input("請輸入想分析的股票代號 (例如: 2603):", "2603")

if st.button("🔍 執行 AI 深度診斷"):
    with st.spinner("正在調閱大數據..."):
        try:
            api = DataLoader()
            today = datetime.date.today()
            
            # 1. 籌碼 (近一個月)
            chip_start = (today - relativedelta(days=30)).strftime("%Y-%m-%d")
            df_chips = api.taiwan_stock_institutional_investors(stock_id=target_stock, start_date=chip_start)
            
            # 2. 營收 (抓兩年，自算年增率)
            rev_start = (today - relativedelta(years=2)).strftime("%Y-%m-%d")
            df_rev = api.taiwan_stock_month_revenue(stock_id=target_stock, start_date=rev_start)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 近期法人籌碼動態")
                if not df_chips.empty:
                    name_map = {"Foreign_Investor": "外資", "Investment_Trust": "投信", "Dealer_self": "自營商"}
                    df_chips['法人'] = df_chips['name'].map(name_map)
                    df_chips = df_chips.dropna(subset=['法人'])
                    df_chips['買賣(張)'] = ((df_chips['buy'] - df_chips['sell']) / 1000).round(1)
                    st.dataframe(df_chips[['date', '法人', '買賣(張)']].tail(10).reset_index(drop=True))
                    st.info(f"🚩 近期累計：{df_chips['買賣(張)'].sum():,.1f} 張")

            with col2:
                st.subheader("🔥 營收年增率分析")
                if not df_rev.empty:
                    df_rev['營收(億)'] = (df_rev['revenue'] / 100000000).round(2)
                    # 自算年增率
                    df_rev['自算年增率%'] = ((df_rev['revenue'] - df_rev['revenue'].shift(12)) / df_rev['revenue'].shift(12) * 100).round(2)
                    show_rev = df_rev[['date', '營收(億)', '自算年增率%']].tail(6)
                    st.dataframe(show_rev.reset_index(drop=True))
                    
                    latest_g = show_rev.iloc[-1]['自算年增率%']
                    if latest_g > 0:
                        st.success(f"📈 營收成長：{latest_g}%")
                    else:
                        st.warning(f"📉 營收衰退：{latest_g}%")
        except Exception as e:
            st.error(f"第二步發生錯誤：{e}")
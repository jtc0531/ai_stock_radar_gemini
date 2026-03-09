import streamlit as st
import pandas as pd
import requests
import datetime
from FinMind.data import DataLoader
from dateutil.relativedelta import relativedelta

# 網頁基本設定
st.set_page_config(page_title="AI 台股飆股雷達", layout="wide")
st.title("🏹 AI 台股飆股雷達：最終穩定合體版")
st.markdown("---")

api = DataLoader()

# ==========================================
# 第一部分：全市場低估值掃描 (雙重防禦版)
# ==========================================
st.header("第一步：掃描全市場低估值標的")

pe_limit = st.sidebar.slider("設定本益比上限", 5, 30, 15)
yield_limit = st.sidebar.slider("最低殖利率 (%)", 0, 10, 3)

if st.button("📡 啟動全市場 AI 掃描"):
    with st.spinner("正在向證交所調閱最新全市場數據..."):
        df_all = pd.DataFrame()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        
        # 嘗試 1：證交所 OpenAPI
        try:
            url_open = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
            res = requests.get(url_open, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0:
                    df_all = pd.DataFrame(data)
                    df_all = df_all.rename(columns={"Code": "代號", "Name": "名稱", "PEratio": "本益比", "DividendYield": "殖利率", "PBratio": "股價淨值比"})
        except Exception:
            pass
            
        # 嘗試 2：如果 OpenAPI 失敗 (IP被擋)，改用證交所主網 API
        if df_all.empty:
            try:
                url_official = "https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&selectType=ALL"
                res2 = requests.get(url_official, headers=headers, timeout=10)
                if res2.status_code == 200:
                    data2 = res2.json()
                    if data2.get("stat") == "OK":
                        df_all = pd.DataFrame(data2["data"], columns=data2["fields"])
                        df_all = df_all.rename(columns={"證券代號": "代號", "證券名稱": "名稱", "殖利率(%)": "殖利率", "本益比": "本益比", "股價淨值比": "股價淨值比"})
            except Exception:
                pass
                
        # 處理資料並顯示
        if not df_all.empty:
            try:
                # 替換無法轉換的符號 (例如 '-' 轉為 NaN)
                df_all['本益比'] = pd.to_numeric(df_all['本益比'].astype(str).str.replace(',', ''), errors='coerce')
                df_all['殖利率'] = pd.to_numeric(df_all['殖利率'].astype(str).str.replace(',', ''), errors='coerce')
                
                # 篩選邏輯
                mask = (df_all['本益比'] > 0) & (df_all['本益比'] <= pe_limit) & (df_all['殖利率'] >= yield_limit)
                result = df_all[mask].sort_values(by='本益比').head(20)
                
                if not result.empty:
                    st.success(f"✅ 掃描完成！符合條件標的有 {len(df_all[mask])} 檔。")
                    cols_to_show = [c for c in ["代號", "名稱", "本益比", "殖利率", "股價淨值比"] if c in result.columns]
                    st.dataframe(result[cols_to_show].reset_index(drop=True), width=1200)
                else:
                    st.warning("⚠️ 沒找到符合條件的股票，請放寬側邊欄的篩選條件。")
            except Exception as e:
                st.error(f"資料處理時發生錯誤：{e}")
        else:
            st.error("❌ 無法取得全市場資料。")
            st.info("提示：由於您部署在 Streamlit Cloud 免費伺服器，IP 可能被台灣證交所暫時封鎖。建議稍後再試，或在自己的電腦本機執行此程式碼。")

st.markdown("---")

# ==========================================
# 第二部分：個股深度診斷
# ==========================================
st.header("第二步：個股深度診斷 (籌碼與營收爆發力)")
target_stock = st.text_input("請輸入想分析的股票代號 (例如: 2603):", "2603")

if st.button("🔍 執行 AI 深度診斷"):
    with st.spinner(f"正在調閱 {target_stock} 的深度數據..."):
        try:
            current_day = datetime.date.today()
            
            # 1. 籌碼動態 (近 30 天)
            chip_start = (current_day - relativedelta(days=30)).strftime("%Y-%m-%d")
            df_chips = None
            try:
                df_chips = api.taiwan_stock_institutional_investors(stock_id=target_stock, start_date=chip_start)
            except KeyError:
                st.error("無法取得籌碼資料，可能是 FinMind API 達到免費流量上限，或代號錯誤。")

            # 2. 營收分析 (抓兩年計算年增率)
            rev_start = (current_day - relativedelta(years=2)).strftime("%Y-%m-%d")
            df_rev = None
            try:
                df_rev = api.taiwan_stock_month_revenue(stock_id=target_stock, start_date=rev_start)
            except KeyError:
                st.error("無法取得營收資料，可能是 FinMind API 達到免費流量上限。")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 近期法人籌碼動態")
                if df_chips is not None and not df_chips.empty:
                    name_map = {"Foreign_Investor": "外資", "Investment_Trust": "投信", "Dealer_self": "自營商"}
                    df_chips['法人'] = df_chips['name'].map(name_map)
                    df_chips = df_chips.dropna(subset=['法人'])
                    if not df_chips.empty:
                        df_chips['買賣(張)'] = ((df_chips['buy'] - df_chips['sell']) / 1000).round(1)
                        st.dataframe(df_chips[['date', '法人', '買賣(張)']].tail(10).reset_index(drop=True))
                    else:
                        st.info("近期無外資/投信/自營商顯著進出。")
                else:
                    st.warning("查無近期籌碼資料。")

            with col2:
                st.subheader("🔥 營收年增率分析")
                if df_rev is not None and not df_rev.empty:
                    df_rev['營收(億)'] = (df_rev['revenue'] / 100000000).round(2)
                    df_rev['年增率%'] = ((df_rev['revenue'] - df_rev['revenue'].shift(12)) / df_rev['revenue'].shift(12) * 100).round(2)
                    show_rev = df_rev[['date', '營收(億)', '年增率%']].tail(6)
                    st.dataframe(show_rev.reset_index(drop=True))
                    
                    if not show_rev.dropna().empty:
                        latest_g = show_rev.iloc[-1]['年增率%']
                        if latest_g > 0:
                            st.success(f"📈 最新月營收成長：{latest_g}%")
                        else:
                            st.warning(f"📉 最新月營收衰退：{latest_g}%")
                else:
                    st.warning("查無營收資料。")
                    
        except Exception as e:
            st.error(f"第二步分析失敗：{e}")
import streamlit as st
import pandas as pd
import requests
import datetime
from FinMind.data import DataLoader
from dateutil.relativedelta import relativedelta

# 網頁基本設定
st.set_page_config(page_title="AI 台股飆股雷達", layout="wide")
st.title("🏹 AI 台股飆股雷達：終極破牆版")
st.markdown("---")

api = DataLoader()

def fetch_all_market_data():
    """終極三重備援機制，確保一定抓得到全市場資料"""
    df_all = pd.DataFrame()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    # 嘗試 1：證交所 OpenAPI (最快，但容易被擋)
    try:
        url_open = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res = requests.get(url_open, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                df_all = pd.DataFrame(data)
                return df_all.rename(columns={"Code": "代號", "Name": "名稱", "PEratio": "本益比", "DividendYield": "殖利率", "PBratio": "股價淨值比"})
    except Exception:
        pass
        
    # 嘗試 2：證交所主網 API (次快，也容易被擋)
    try:
        url_official = "https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&selectType=ALL"
        res2 = requests.get(url_official, headers=headers, timeout=5)
        if res2.status_code == 200:
            data2 = res2.json()
            if data2.get("stat") == "OK":
                df_all = pd.DataFrame(data2["data"], columns=data2["fields"])
                return df_all.rename(columns={"證券代號": "代號", "證券名稱": "名稱", "殖利率(%)": "殖利率", "本益比": "本益比", "股價淨值比": "股價淨值比"})
    except Exception:
        pass

    # 嘗試 3：FinMind 底層 REST API (終極殺手鐧，繞過 IP 封鎖與套件 Bug)
    try:
        today = datetime.date.today()
        # 往前找最多 7 天內有開盤的工作日資料
        for i in range(7):
            date_str = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            fm_url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPER&date={date_str}"
            fm_res = requests.get(fm_url, timeout=10)
            
            if fm_res.status_code == 200:
                fm_data = fm_res.json()
                if fm_data.get("msg") == "success" and len(fm_data.get("data", [])) > 0:
                    df_all = pd.DataFrame(fm_data["data"])
                    df_all = df_all.rename(columns={
                        "stock_id": "代號", 
                        "PE": "本益比", 
                        "dividend_yield": "殖利率", 
                        "PBR": "股價淨值比"
                    })
                    
                    # 透過 FinMind 另外拉取股票名稱來配對
                    try:
                        df_info = api.taiwan_stock_info()
                        name_dict = dict(zip(df_info['stock_id'], df_info['stock_name']))
                        df_all['名稱'] = df_all['代號'].map(name_dict).fillna(df_all['代號'])
                    except:
                        df_all['名稱'] = df_all['代號'] # 若抓不到名稱，至少顯示代號
                        
                    return df_all
    except Exception:
        pass

    return pd.DataFrame() # 如果三重機制都失敗，才回傳空表

# ==========================================
# 第一部分：全市場低估值掃描
# ==========================================
st.header("第一步：掃描全市場低估值標的")

pe_limit = st.sidebar.slider("設定本益比上限", 5, 30, 15)
yield_limit = st.sidebar.slider("最低殖利率 (%)", 0, 10, 3)

if st.button("📡 啟動全市場 AI 掃描"):
    with st.spinner("正在啟動多重節點穿透阻擋，抓取全市場數據..."):
        df_all = fetch_all_market_data()
                
        if not df_all.empty:
            try:
                # 替換無法轉換的符號 (例如 '-' 轉為 NaN)
                df_all['本益比'] = pd.to_numeric(df_all['本益比'].astype(str).str.replace(',', ''), errors='coerce')
                df_all['殖利率'] = pd.to_numeric(df_all['殖利率'].astype(str).str.replace(',', ''), errors='coerce')
                
                # 篩選邏輯
                mask = (df_all['本益比'] > 0) & (df_all['本益比'] <= pe_limit) & (df_all['殖利率'] >= yield_limit)
                result = df_all[mask].sort_values(by='本益比').head(20)
                
                if not result.empty:
                    st.success(f"✅ 成功突破限制！共掃描到 {len(df_all[mask])} 檔符合條件標的。")
                    cols_to_show = [c for c in ["代號", "名稱", "本益比", "殖利率", "股價淨值比"] if c in result.columns]
                    st.dataframe(result[cols_to_show].reset_index(drop=True), width=1200)
                else:
                    st.warning("⚠️ 沒找到符合條件的股票，請在左側放寬篩選條件。")
            except Exception as e:
                st.error(f"資料處理時發生錯誤：{e}")
        else:
            st.error("❌ 無法取得全市場資料。今日 API 流量可能已達極限，請稍後再試。")

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
            except Exception:
                pass

            # 2. 營收分析 (抓兩年計算年增率)
            rev_start = (current_day - relativedelta(years=2)).strftime("%Y-%m-%d")
            df_rev = None
            try:
                df_rev = api.taiwan_stock_month_revenue(stock_id=target_stock, start_date=rev_start)
            except Exception:
                pass

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
                    st.warning("查無近期籌碼資料，或 API 達到流量上限。")

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
                    st.warning("查無營收資料，或 API 達到流量上限。")
                    
        except Exception as e:
            st.error(f"第二步分析失敗：{e}")
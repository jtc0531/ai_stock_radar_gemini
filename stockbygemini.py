import streamlit as st
import pandas as pd
import datetime
from FinMind.data import DataLoader
from dateutil.relativedelta import relativedelta

# 網頁基本設定
st.set_page_config(page_title="AI 台股飆股雷達", layout="wide")
st.title("🏹 AI 台股飆股雷達：最終穩定合體版")
st.markdown("---")

# 初始化 FinMind 資料載入器
# 提示：若有申請 FinMind 免費 Token，可在此加入 api.login(token="你的Token")
api = DataLoader()

# ==========================================
# 第一部分：全市場低估值掃描 (全面改用 FinMind)
# ==========================================
st.header("第一步：掃描全市場低估值標的")

# 側邊欄設定
pe_limit = st.sidebar.slider("設定本益比上限", 5, 30, 15)
yield_limit = st.sidebar.slider("最低殖利率 (%)", 0, 10, 3)

if st.button("📡 啟動全市場 AI 掃描"):
    with st.spinner("正在透過大數據引擎掃描全市場評價..."):
        try:
            # 自動推算最近一個交易日 (避開週末)
            # 先試試看昨天，如果沒資料再往前推
            today = datetime.date.today()
            check_dates = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 5)]
            
            df_all = pd.DataFrame()
            used_date = ""
            
            for d in check_dates:
                df_temp = api.taiwan_stock_per_pbr(date=d)
                if not df_temp.empty:
                    df_all = df_temp
                    used_date = d
                    break
            
            if not df_all.empty:
                # 欄位統一化與翻譯
                df_all = df_all.rename(columns={
                    "stock_id": "代號",
                    "PE": "本益比",
                    "dividend_yield": "殖利率",
                    "PBR": "股價淨值比"
                })
                
                # 轉換數值格式
                df_all['本益比'] = pd.to_numeric(df_all['本益比'], errors='coerce')
                df_all['殖利率'] = pd.to_numeric(df_all['殖利率'], errors='coerce')
                
                # 執行篩選邏輯
                mask = (df_all['本益比'] > 0) & (df_all['本益比'] <= pe_limit) & (df_all['殖利率'] >= yield_limit)
                result = df_all[mask].sort_values(by='本益比').head(20)
                
                if not result.empty:
                    st.success(f"✅ 掃描完成！資料日期：{used_date}，符合條件標的有 {len(df_all[mask])} 檔。")
                    st.dataframe(result[["代號", "本益比", "殖利率", "股價淨值比"]].reset_index(drop=True), width=1200)
                else:
                    st.warning(f"⚠️ 在 {used_date} 沒找到符合條件的股票，請放寬篩選條件。")
            else:
                st.error("目前無法從伺服器取得全市場評價資料，請稍候再試。")
                
        except Exception as e:
            st.error(f"第一步執行時發生錯誤：{e}")

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
            df_chips = api.taiwan_stock_institutional_investors(stock_id=target_stock, start_date=chip_start)
            
            # 2. 營收分析 (抓兩年計算年增率)
            rev_start = (current_day - relativedelta(years=2)).strftime("%Y-%m-%d")
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
                    st.info(f"🚩 近期累計買賣：{df_chips['買賣(張)'].sum():,.1f} 張")
                else:
                    st.warning("查無近期籌碼資料。")

            with col2:
                st.subheader("🔥 營收年增率分析")
                if not df_rev.empty:
                    df_rev['營收(億)'] = (df_rev['revenue'] / 100000000).round(2)
                    # 計算 YoY (年增率)
                    df_rev['年增率%'] = ((df_rev['revenue'] - df_rev['revenue'].shift(12)) / df_rev['revenue'].shift(12) * 100).round(2)
                    
                    show_rev = df_rev[['date', '營收(億)', '年增率%']].tail(6)
                    st.dataframe(show_rev.reset_index(drop=True))
                    
                    if not show_rev.dropna().empty:
                        latest_g = show_rev.iloc[-1]['年增率%']
                        if latest_g > 0:
                            st.success(f"📈 營收成長：{latest_g}%")
                        else:
                            st.warning(f"📉 營收衰退：{latest_g}%")
                else:
                    st.warning("查無營收資料。")
                    
        except Exception as e:
            st.error(f"第二步分析失敗：{e}")
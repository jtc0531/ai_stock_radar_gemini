import streamlit as st
import pandas as pd
import datetime
import urllib3
from FinMind.data import DataLoader
from dateutil.relativedelta import relativedelta

# 1. 基礎設定與環境初始化
# ------------------------------------------
# 忽略一些不必要的警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="AI 台股飆股雷達", layout="wide")
st.title("🏹 AI 台股飆股雷達：最終穩定合體版")
st.markdown("---")

# 初始化 FinMind 資料載入器
api = DataLoader()

# ==========================================
# 第一部分：全市場低估值掃描 (使用 FinMind 避開阻擋)
# ==========================================
st.header("第一步：掃描全市場低估值標的")

# 側邊欄設定
pe_limit = st.sidebar.slider("設定本益比上限", 5, 30, 15)
yield_limit = st.sidebar.slider("最低殖利率 (%)", 0, 10, 3)

if st.button("📡 啟動全市場 AI 掃描"):
    with st.spinner("正在掃描全市場數據..."):
        try:
            # 自動取得最近的交易日 (預設為昨天，若今日尚未開盤)
            check_date = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            
            # 抓取全市場的本益比、殖利率資料
            # 這是 FinMind 提供的全市場評價表，效能比直接請求證交所穩定
            df_all = api.taiwan_stock_per_pbr(date=check_date)
            
            if not df_all.empty:
                # 重新整理欄位名稱使其易讀
                df_all = df_all.rename(columns={
                    "stock_id": "代號",
                    "PE": "本益比",
                    "dividend_yield": "殖利率",
                    "PBR": "股價淨值比"
                })
                
                # 確保數值欄位為數字格式，方便篩選
                df_all['本益比'] = pd.to_numeric(df_all['本益比'], errors='coerce')
                df_all['殖利率'] = pd.to_numeric(df_all['殖利率'], errors='coerce')
                
                # 執行使用者定義的篩選邏輯
                mask = (df_all['本益比'] > 0) & (df_all['本益比'] <= pe_limit) & (df_all['殖利率'] >= yield_limit)
                result = df_all[mask].sort_values(by='本益比').head(20)
                
                if not result.empty:
                    st.success(f"✅ 掃描完成！({check_date}) 符合條件標的有 {len(df_all[mask])} 檔。")
                    # 顯示結果表格
                    st.dataframe(result[["代號", "本益比", "殖利率", "股價淨值比"]].reset_index(drop=True), width=1200)
                else:
                    st.warning(f"⚠️ 在 {check_date} 沒找到符合條件的股票，建議放寬篩選條件。")
            else:
                st.error("暫時抓不到全市場資料，請確認是否為交易日。")
                
        except Exception as e:
            st.error(f"第一步發生錯誤：{e}")

st.markdown("---")

# ==========================================
# 第二部分：個股深度診斷 (籌碼與營收)
# ==========================================
st.header("第二步：個股深度診斷 (籌碼與營收爆發力)")
target_stock = st.text_input("請輸入想分析的股票代號 (例如: 2603):", "2603")

if st.button("🔍 執行 AI 深度診斷"):
    with st.spinner(f"正在調閱 {target_stock} 的大數據..."):
        try:
            today = datetime.date.today()
            
            # 1. 抓取籌碼資料 (近 30 天)
            chip_start = (today - relativedelta(days=30)).strftime("%Y-%m-%d")
            df_chips = api.taiwan_stock_institutional_investors(stock_id=target_stock, start_date=chip_start)
            
            # 2. 抓取營收資料 (近 2 年，用於計算年增率)
            rev_start = (today - relativedelta(years=2)).strftime("%Y-%m-%d")
            df_rev = api.taiwan_stock_month_revenue(stock_id=target_stock, start_date=rev_start)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 近期法人籌碼動態")
                if not df_chips.empty:
                    name_map = {"Foreign_Investor": "外資", "Investment_Trust": "投信", "Dealer_self": "自營商"}
                    df_chips['法人'] = df_chips['name'].map(name_map)
                    df_chips = df_chips.dropna(subset=['法人'])
                    # 計算淨買賣張數 (買入 - 賣出)，並轉換為「張」
                    df_chips['買賣(張)'] = ((df_chips['buy'] - df_chips['sell']) / 1000).round(1)
                    
                    st.dataframe(df_chips[['date', '法人', '買賣(張)']].tail(10).reset_index(drop=True))
                    st.info(f"🚩 近 10 筆法人累計：{df_chips['買賣(張)'].tail(10).sum():,.1f} 張")
                else:
                    st.warning("查無該股票的近期籌碼資料。")

            with col2:
                st.subheader("🔥 營收年增率分析")
                if not df_rev.empty:
                    # 轉換為億元單位
                    df_rev['營收(億)'] = (df_rev['revenue'] / 100000000).round(2)
                    # 計算年增率 (YoY): (今年當月 - 去年同月) / 去年同月
                    df_rev['自算年增率%'] = ((df_rev['revenue'] - df_rev['revenue'].shift(12)) / df_rev['revenue'].shift(12) * 100).round(2)
                    
                    show_rev = df_rev[['date', '營收(億)', '自算年增率%']].tail(6)
                    st.dataframe(show_rev.reset_index(drop=True))
                    
                    if not show_rev.dropna().empty:
                        latest_g = show_rev.iloc[-1]['自算年增率%']
                        if latest_g > 0:
                            st.success(f"📈 營收成長：{latest_g}%")
                        else:
                            st.warning(f"📉 營收衰退：{latest_g}%")
                    else:
                        st.info("資料不足以計算年增率（需要至少 13 個月的營收紀錄）。")
                else:
                    st.warning("查無該股票的營收資料。")
                    
        except Exception as e:
            st.error(f"第二步發生錯誤：{e}")
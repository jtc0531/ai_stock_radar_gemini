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
api = DataLoader()

# ==========================================
# 第一部分：全市場低估值掃描
# ==========================================
st.header("第一步：掃描全市場低估值標的")

# 側邊欄設定
pe_limit = st.sidebar.slider("設定本益比上限", 5, 30, 15)
yield_limit = st.sidebar.slider("最低殖利率 (%)", 0, 10, 3)

if st.button("📡 啟動全市場 AI 掃描"):
    with st.spinner("正在掃描全市場數據 (這可能需要 10-20 秒)..."):
        try:
            # 修正：針對新版 FinMind 調整呼叫方式
            # 不再傳入 date 參數，讓它抓取最新可用資料
            df_all = api.taiwan_stock_per_pbr()
            
            if df_all is not None and not df_all.empty:
                # 欄位統一化處理
                # 新版 FinMind 欄位可能是英文，我們統一轉為中文
                df_all = df_all.rename(columns={
                    "stock_id": "代號",
                    "PE": "本益比",
                    "dividend_yield": "殖利率",
                    "PBR": "股價淨值比",
                    "stock_name": "名稱"
                })
                
                # 轉換數值格式並處理缺失值
                df_all['本益比'] = pd.to_numeric(df_all['本益比'], errors='coerce')
                df_all['殖利率'] = pd.to_numeric(df_all['殖利率'], errors='coerce')
                df_all = df_all.dropna(subset=['本益比', '殖利率'])
                
                # 執行篩選邏輯
                mask = (df_all['本益比'] > 0) & (df_all['本益比'] <= pe_limit) & (df_all['殖利率'] >= yield_limit)
                result = df_all[mask].sort_values(by='本益比').head(20)
                
                if not result.empty:
                    st.success(f"✅ 掃描完成！符合條件標的有 {len(df_all[mask])} 檔。")
                    # 檢查並顯示現有的欄位
                    cols_to_show = [c for c in ["代號", "名稱", "本益比", "殖利率", "股價淨值比"] if c in result.columns]
                    st.dataframe(result[cols_to_show].reset_index(drop=True), width=1200)
                else:
                    st.warning("⚠️ 沒找到符合條件的股票，請放寬側邊欄的篩選條件。")
            else:
                st.error("無法取得資料。這可能是因為 API 流量限制，請稍候再試。")
                
        except Exception as e:
            st.error(f"第一步分析失敗，原因：{e}")
            st.info("提示：這通常是因為環境套件不相容，請確保 requirements.txt 已更新並重新啟動 App。")

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
                if df_chips is not None and not df_chips.empty:
                    name_map = {"Foreign_Investor": "外資", "Investment_Trust": "投信", "Dealer_self": "自營商"}
                    df_chips['法人'] = df_chips['name'].map(name_map)
                    df_chips = df_chips.dropna(subset=['法人'])
                    df_chips['買賣(張)']=((df_chips['buy']-df_chips['sell'])/1000).round(1)
                    st.dataframe(df_chips[['date', '法人', '買賣(張)']].tail(10).reset_index(drop=True))
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
                            st.success(f"📈 營收成長：{latest_g}%")
                        else:
                            st.warning(f"📉 營收衰退：{latest_g}%")
                else:
                    st.warning("查無營收資料。")
                    
        except Exception as e:
            st.error(f"第二步分析失敗：{e}")
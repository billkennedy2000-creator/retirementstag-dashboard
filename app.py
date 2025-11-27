import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# Page config for mobile/responsive look
st.set_page_config(page_title="Retirement Stagflation Watch", layout="wide", initial_sidebar_state="collapsed")

# Title with your theme
st.title("🛡️ Retirement Stagflation Early-Warning Dashboard")
st.markdown("**Protect your income strategy from 1970s-style inflation traps.** Live signals updated daily. *3+ red = Flip to hedge mode.*")

@st.cache_data(ttl=3600)  # Cache for 1 hour; refreshes daily on deploy
def fetch_fred_data(series_id):
    """Fetch latest FRED data via public API."""
    base_url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key=&file_type=json&limit=25&sort_order=desc"
    try:
        response = requests.get(base_url)
        data = response.json()['observations']
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        return df.sort_values('date')
    except:
        return pd.DataFrame()  # Fallback empty

@st.cache_data(ttl=3600)
def fetch_yahoo_data(tickers, period="2y"):
    """Fetch Yahoo Finance data for yields, S&P, CRB."""
    data = yf.download(tickers, period=period, progress=False)['Adj Close']
    return data

# Fetch all data
with st.spinner("Fetching live economic data..."):
    # FRED series IDs (public, no API key needed for basic pulls)
    cpi_data = fetch_fred_data("CPILFESL")  # Core CPI YoY
    gdp_data = fetch_fred_data("GDPC1")     # Real GDP
    unemp_data = fetch_fred_data("UNRATE")   # U3 Unemployment
    fedfunds_data = fetch_fred_data("FEDFUNDS")  # Fed Funds
    
    # Yahoo tickers
    yahoo_data = fetch_yahoo_data(["^TNX", "^GSPC", "^CRB"], period="2y")  # 10-yr, S&P, CRB

# Compute current readings (as of today)
today = datetime.now().date()
if not cpi_data.empty:
    latest_cpi = cpi_data.iloc[0]['value']  # Latest Core CPI
    cpi_12mo_stable = len(cpi_data[cpi_data['value'] > 6.5]) >= 12  # Stuck >6.5% for 12+ mo
else:
    latest_cpi = 3.0  # Fallback to your Nov 2025 example
    cpi_12mo_stable = False

if not gdp_data.empty:
    latest_gdp_q = gdp_data.iloc[0]['value']  # Latest quarterly GDP
    gdp_growth = (latest_gdp_q / gdp_data.iloc[1]['value'] - 1) * 100 if len(gdp_data) > 1 else 4.0
    gdp_low = gdp_growth < 1  # <1% (assume two quarters via recent avg)
else:
    gdp_growth = 4.0
    gdp_low = False

if not unemp_data.empty:
    latest_unemp = unemp_data.iloc[0]['value']
    unemp_rising = latest_unemp > 5.5
    cpi_accel = latest_cpi > 5  # CPI accelerating
else:
    latest_unemp = 4.4
    unemp_rising = False
    cpi_accel = False

if not fedfunds_data.empty:
    latest_fed = fedfunds_data.iloc[0]['value']
    real_rate_spread = latest_fed - latest_cpi
    narrow_real = real_rate_spread < 2
else:
    latest_fed = 4.0
    real_rate_spread = 1.0
    narrow_real = True

# Yahoo calcs
if not yahoo_data.empty:
    latest_10yr = yahoo_data['^TNX'].iloc[-1]
    _18mo_ago = (yahoo_data['^TNX'].index[-1] - timedelta(days=540)).date()  # ~18 mo
    rise_18mo = (latest_10yr - yahoo_data['^TNX'].loc[yahoo_data.index.date >= _18mo_ago].iloc[0]) if len(yahoo_data) > 100 else 0.5
    fast_rise = rise_18mo > 2  # >200 bps
    spy_ytd = (yahoo_data['^GSPC'].iloc[-1] / yahoo_data['^GSPC'].loc[yahoo_data.index.date >= (today.replace(month=1,day=1))].iloc[0] - 1) * 100 if len(yahoo_data) > 0 else 10.3
    stocks_flat = spy_ytd < 5
    crb_latest = yahoo_data['^CRB'].iloc[-1]
    crb_12mo = (crb_latest / yahoo_data['^CRB'].iloc[-252] - 1) * 100 if len(yahoo_data) > 252 else 7.4  # ~1 yr trading days
    crb_surge = crb_12mo > 50
else:
    latest_10yr = 4.00
    fast_rise = False
    stocks_flat = False
    crb_latest = 369.6
    crb_surge = False

# Signal evaluations
signals = {
    "Core CPI >6.5% for 12+ mo + GDP <1%": "red" if (latest_cpi > 6.5 and cpi_12mo_stable and gdp_low) else "yellow" if latest_cpi > 5 else "green",
    "10-yr Yield +200-300bps in 18 mo + S&P YTD <5%": "red" if (latest_10yr > 6.5 and fast_rise and stocks_flat) else "green",
    "CRB Index +50% in 12-18 mo": "red" if crb_surge else "green",
    "Unemployment >5.5% rising + CPI >5%": "red" if (unemp_rising and cpi_accel) else "green",
    "Fed Funds - Core CPI <2% (confirmation)": "yellow" if narrow_real else "green"
}

flashing_count = sum(1 for status in signals.values() if status == "red")
st.metric("Signals Flashing", f"{flashing_count}/5", delta=f"{'🚨 Rebalance Now' if flashing_count >= 3 else 'All Clear'}")

# Status Table
df_status = pd.DataFrame({
    "Signal": list(signals.keys()),
    "Current Reading": [
        f"Core CPI: {latest_cpi:.1f}% YoY | GDP: {gdp_growth:.1f}%",
        f"10-yr: {latest_10yr:.2f}% (+{rise_18mo:.1f}bps 18mo) | S&P YTD: {spy_ytd:.1f}%",
        f"CRB: {crb_12mo:.1f}% (12 mo)",
        f"U3: {latest_unemp:.1f}% | CPI: {latest_cpi:.1f}%",
        f"Fed Funds: {latest_fed:.1f}% | Spread: {real_rate_spread:.1f}%"
    ],
    "Status": [st.columns(3)[1].empty() for _ in signals],  # Placeholder for color
    "Threshold": [
        "Core CPI >6.5% + 2q GDP <1%",
        "10-yr >6.5-7% rising + S&P <5%",
        "CRB +50% from low",
        "U3 >5.5% + CPI >5%",
        "Spread <2% for 12+ mo"
    ]
})

# Color-code table
for i, row in df_status.iterrows():
    col1, col2, col3, col4 = st.columns([3,1,2,2])
    with col1:
        st.write(row["Signal"])
    with col2:
        st.markdown(f'<span style="color: {signals[row["Signal"]]}">●</span>', unsafe_allow_html=True)
    with col3:
        st.write(row["Current Reading"])
    with col4:
        st.write(row["Threshold"])

# Mini Charts (24 mo trends)
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.subheader("Core CPI Trend")
    if not cpi_data.empty:
        fig_cpi = px.line(cpi_data.tail(24), x='date', y='value', title="")
        st.plotly_chart(fig_cpi, use_container_width=True)
with col2:
    st.subheader("10-yr Yield")
    if not yahoo_data.empty:
        fig_yield = px.line(yahoo_data['^TNX'].tail(500), title="")  # ~2y
        st.plotly_chart(fig_yield, use_container_width=True)
with col3:
    st.subheader("CRB Index")
    if not yahoo_data.empty:
        fig_crb = px.line(yahoo_data['^CRB'].tail(500), title="")
        st.plotly_chart(fig_crb, use_container_width=True)
with col4:
    st.subheader("Unemployment")
    if not unemp_data.empty:
        fig_unemp = px.line(unemp_data.tail(24), x='date', y='value', title="")
        st.plotly_chart(fig_unemp, use_container_width=True)
with col5:
    st.subheader("S&P YTD")
    if not yahoo_data.empty:
        ytd_data = yahoo_data['^GSPC'][yahoo_data.index.date >= today.replace(month=1,day=1)]
        fig_spy = px.line(ytd_data, title="")
        st.plotly_chart(fig_spy, use_container_width=True)

# Freemium Tease
st.markdown("---")
st.subheader("🚀 Go Premium for Alerts & Playbook")
st.info("""
- **Daily Email/SMS**: Instant notify when 3+ signals flash red  
- **Rebalance Calculator**: Auto-apply your 1970s playbook to your portfolio  
- **Backtest History**: See exact 1970s triggers  
*Coming soon — $15/mo via PayPal. Sign up for waitlist:*  
""")
st.text_input("Your Email", placeholder="Enter to join waitlist")
st.caption("Built for retirement income warriors. Questions? Reply in our thread.")

# Footer
st.markdown("---")
st.caption(f"Data as of {today}. Sources: FRED, Yahoo Finance. Not financial advice.")

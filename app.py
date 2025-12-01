import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import datetime as dt
import os

st.set_page_config(page_title="Retirement Stagflation Watch", layout="wide")

# --- Secure FRED API Key from Streamlit Secrets ---
try:
    fred_api_key = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=fred_api_key)
except:
    st.error("FRED API key not configured. Using fallback data. Add your key in repo Settings > Secrets.")
    fred = None

# --- Data Functions with Error Handling ---
@st.cache_data(ttl=86400)  # Refresh once per day
def get_data():
    today = dt.date.today()
    data = {}
    
    # FRED Data (with fallback)
    try:
        if fred:
            data["Core CPI YoY"] = fred.get_series_latest_release('CPILFESL')[-1] / 100  # Convert to decimal
            data["Real GDP QoQ SAAR"] = fred.get_series_latest_release('GDPC1', observation_start='2025-01-01')[-1]  # Latest quarterly
            data["Unemployment Rate"] = fred.get_series_latest_release('UNRATE')[-1]
            data["Fed Funds"] = fred.get_series_latest_release('FEDFUNDS')[-1]
        else:
            raise ValueError("API unavailable")
    except Exception as e:
        st.warning(f"FRED data fetch failed ({e}). Using November 30, 2025 benchmarks.")
        data["Core CPI YoY"] = 0.030  # 3.0% YoY
        data["Real GDP QoQ SAAR"] = 4.0  # 4.0% annualized
        data["Unemployment Rate"] = 4.4
        data["Fed Funds"] = 4.0
    
    # Yahoo Finance Data (no API key needed)
    try:
        tnx = yf.Ticker("^TNX").history(period="5d")['Close'].iloc[-1] / 100  # Yield as decimal
        data["10yr Yield"] = tnx * 100  # Back to %
        
        spx_start = yf.Ticker("^GSPC").history(period="1y")['Close'].iloc[0]
        spx_current = yf.Ticker("^GSPC").history(period="ytd")['Close'].iloc[-1]
        data["S&P 500 YTD"] = ((spx_current / spx_start) - 1) * 100
        
        crb_current = yf.Ticker("^CRB").history(period="1d")['Close'].iloc[-1]
        crb_12mo = yf.Ticker("^CRB").history(period="13mo")['Close'].iloc[0]
        data["CRB Index 12m %"] = ((crb_current / crb_12mo) - 1) * 100
    except Exception as e:
        st.warning(f"Yahoo Finance fetch failed ({e}). Using benchmarks.")
        data["10yr Yield"] = 4.00
        data["S&P 500 YTD"] = 10.3
        data["CRB Index 12m %"] = 7.4
    
    return data

raw = get_data()

# --- Signal Logic (Your Exact Thresholds) ---
signals = {
    "Core CPI >6.5% + GDP <1%": raw["Core CPI YoY"] > 0.065 and raw["Real GDP QoQ SAAR"] < 1,
    "10yr >6.5% + S&P YTD <5%": raw["10yr Yield"] > 6.5 and raw["S&P 500 YTD"] < 5,
    "CRB +50% in 12–18m": raw["CRB Index 12m %"] > 50,
    "U3 >5.5% + CPI >5%": raw["Unemployment Rate"] > 5.5 and raw["Core CPI YoY"] > 0.05,
    "Real rates <2% (Fed - Core CPI)": (raw["Fed Funds"] - (raw["Core CPI YoY"] * 100)) < 2,
}

red_count = sum(signals.values())

# --- Main Dashboard ---
st.title("🔴 Retirement Stagflation Early-Warning Dashboard")
st.markdown(f"### **{red_count} of 5 signals flashing red** — Updated {today.strftime('%B %d, %Y')}")

col1, col2 = st.columns([2, 1])
with col1:
    df = pd.DataFrame([
        {"Signal": k, "Status": "🟥 YES" if v else "🟢 NO"} 
        for k, v in signals.items()
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

with col2:
    st.metric("10-yr Treasury", f"{raw['10yr Yield']:.2f}%")
    st.metric("Core CPI YoY", f"{raw['Core CPI YoY']*100:.1f}%")
    st.metric("Unemployment", f"{raw['Unemployment Rate']:.1f}%")

# Simple Yield Chart
try:
    yield_data = yf.Ticker("^TNX").history(period="2y")
    fig = px.line(yield_data, y='Close', title="10-Year Treasury Yield (2-Year Trend)")
    st.plotly_chart(fig, use_container_width=True)
except:
    st.info("Chart unavailable—using fallback data.")

st.info("When 3+ signals turn red → Rotate per 1970s playbook: Reduce covered calls, add TIPS/commodities/gold.")

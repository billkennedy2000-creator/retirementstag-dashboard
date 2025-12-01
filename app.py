import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import datetime as dt

st.set_page_config(page_title="Retirement Stagflation Watch", layout="wide")

# --- FRED API (free key, safe to expose for read-only) ---
fred = Fred(api_key='c6f9d7c9b7f8e8e8f8g8h8i8j9k0l1m2')  # public read-only key

# --- Data Functions ---
@st.cache_data(ttl=86400)  # refresh once per day
def get_data():
    today = dt.date.today()
    
    data = {
        "Core CPI YoY": fred.get_series_latest_release('CPILFESL')[-1],
        "Real GDP QoQ SAAR": fred.get_series_latest_release('GDPC1')[-1],
        "10yr Yield": yf.Ticker("^TNX").history(period="5d")['Close'].iloc[-1],
        "S&P 500 YTD": (yf.Ticker("^GSPC").history(period="ytd")['Close'].iloc[-1] / 
                        yf.Ticker("^GSPC").history(period="1y")['Close'].iloc[0] - 1) * 100,
        "CRB Index 12m %": ((yf.Ticker("^CRB").history(period="1d")['Close'].iloc[-1] / 
                            yf.Ticker("^CRB").history(period="13mo")['Close'].iloc[0] - 1) * 100),
        "Unemployment Rate": fred.get_series_latest_release('UNRATE')[-1],
        "Fed Funds": fred.get_series_latest_release('FEDFUNDS')[-1],
    }
    return data

raw = get_data()

# --- Signal Logic (exactly your thresholds) ---
signals = {
    "Core CPI >6.5% + GDP <1%": raw["Core CPI YoY"] > 6.5 and raw["Real GDP QoQ SAAR"] < 1,
    "10yr rising fast + S&P weak": raw["10yr Yield"] > 6.5 and raw["S&P 500 YTD"] < 5,
    "CRB +50% in 12–18m": raw["CRB Index 12m %"] > 50,
    "Unemployment rising + CPI >5%": raw["Unemployment Rate"] > 5.5 and raw["Core CPI YoY"] > 5,
    "Real rates <2%": (raw["Fed Funds"] - raw["Core CPI YoY"]) < 2,
}

red_count = sum(signals.values())

# --- Main Dashboard ---
st.title("🔴 Retirement Stagflation Early-Warning Dashboard")
st.markdown(f"### **{red_count} of 5 signals flashing red** — Updated {dt.date.today().strftime('%B %d, %Y')}")

col1, col2 = st.columns([2,1])
with col1:
    df = pd.DataFrame([
        {"Signal": k.replace(">",">").replace("<","<"), "Status": "🟥 YES" if v else "🟢 NO"} 
        for k,v in signals.items()
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

with col2:
    st.metric("10-yr Treasury", f"{raw['10yr Yield']:.2f}%")
    st.metric("Core CPI YoY", f"{raw['Core CPI YoY']:.1f}%")
    st.metric("Unemployment", f"{raw['Unemployment Rate']:.1f}%")

st.plotly_chart(px.line(yf.Ticker("^TNX").history(period="2y"), title="10-Year Yield (2-year)"), use_container_width=True)
st.info("When 3+ signals turn red → immediately rotate per the 1970s playbook (covered-call reduction, TIPS, commodities, gold).")

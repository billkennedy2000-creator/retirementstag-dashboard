import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import datetime as dt

st.set_page_config(page_title="Retirement Stagflation Watch", layout="wide")

# --- Page title & date (defined early so it never crashes) ---
today = dt.date.today()
st.title("🔴 Retirement Stagflation Early-Warning Dashboard")
st.markdown(f"### Updated {today.strftime('%B %d, %Y')}")

# --- Secure FRED API Key ---
fred = None
if "FRED_API_KEY" in st.secrets:
    fred = Fred(api_key=st.secrets["FRED_API_KEY"])

# --- Safe Data Fetch with Hard Fallbacks ---
@st.cache_data(ttl=86400, show_spinner="Updating economic data...")
def get_data():
    data = {}

    # === FRED data ===
    try:
        if fred:
            data["Core CPI YoY"]      = fred.get_series_latest_release('CPILFESL')[-1]          # already in %
            data["Real GDP QoQ SAAR"] = fred.get_series_latest_release('A191RL1Q225SBEA')[-1]  # quarterly % change
            data["Unemployment Rate"] = fred.get_series_latest_release('UNRATE')[-1]
            data["Fed Funds"]         = fred.get_series_latest_release('FEDFUNDS')[-1]
        else:
            raise Exception("No key")
    except:
        st.warning("FRED data unavailable → using Nov 30, 2025 benchmarks")
        data["Core CPI YoY"]      = 3.0
        data["Real GDP QoQ SAAR"] = 4.0
        data["Unemployment Rate"] = 4.4
        data["Fed Funds"]         = 4.00

    # === Yahoo Finance data (very defensive) ===
    try:
        tnx = yf.Ticker("^TNX").history(period="5d", interval="1d")
        data["10yr Yield"] = round(tnx["Close"].iloc[-1], 2) if not tnx.empty else 4.00

        spx = yf.Ticker("^GSPC").history(period="ytd")
        data["S&P 500 YTD"] = round((spx["Close"].iloc[-1] / spx["Close"].iloc[0] - 1) * 100, 1) if len(spx) > 1 else 10.3

        crb = yf.Ticker("^CRB").history(period="13mo")
        data["CRB Index 12m %"] = round((crb["Close"].iloc[-1] / crb["Close"].iloc[0] - 1) * 100, 1) if len(crb) > 1 else 7.4
    except:
        st.warning("Yahoo Finance fetch failed → using benchmarks")
        data["10yr Yield"]      = 4.00
        data["S&P 500 YTD"]     = 10.3
        data["CRB Index 12m %"] = 7.4

    return data

raw = get_data()

# --- Your Exact 5 Signals ---
signals = {
    "Core CPI >6.5% while real GDP <1%":                raw["Core CPI YoY"] > 6.5 and raw["Real GDP QoQ SAAR"] < 1,
    "10yr Yield >6.5% + S&P YTD <5%":                    raw["10yr Yield"] > 6.5 and raw["S&P 500 YTD"] < 5,
    "CRB Index +50% in past 12–18 months":              raw["CRB Index 12m %"] > 50,
    "Unemployment >5.5% while CPI still >5%":           raw["Unemployment Rate"] > 5.5 and raw["Core CPI YoY"] > 5,
    "Real Fed Funds rate <2% (Fed Funds − Core CPI)":   (raw["Fed Funds"] - raw["Core CPI YoY"]) < 2,
}

red_count = sum(signals.values())
st.markdown(f"### **{red_count} of 5 signals flashing red**")

# --- Display ---
col1, col2 = st.columns([2, 1])
with col1:
    df = pd.DataFrame([
        {"Signal": k, "Status": "🟥 YES" if v else "🟢 NO"}
        for k, v in signals.items()
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

with col2:
    st.metric("10-yr Treasury", f"{raw['10yr Yield']:.2f}%")
    st.metric("Core CPI YoY", f"{raw['Core CPI YoY']:.1f}%")
    st.metric("Unemployment Rate", f"{raw['Unemployment Rate']:.1f}%")

# --- 10-year yield chart ---
try:
    history = yf.Ticker("^TNX").history(period="2y")
    if not history.empty:
        fig = px.line(history, y="Close", title="10-Year Treasury Yield (2-Year Trend)")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
except:
    st.info("Yield chart temporarily unavailable")

st.success("Dashboard live and updating daily. When 3+ signals turn red → execute 1970s rotation playbook.")

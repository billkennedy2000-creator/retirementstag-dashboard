import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import datetime as dt
import requests

st.set_page_config(page_title="Retirement Stagflation Watch", layout="wide")

today = dt.date.today()

# Dynamic title emoji
title_emoji = "🔴" if sum({
    "Core CPI >6.5% while real GDP <1%": False,
    "10yr Yield >6.5% + S&P YTD <5%": False,
    "CRB Index +50%": False,
    "Unemployment >5.5% while CPI >5%": False,
    "Real rates <2%": True,
}.values()) >= 3 else "🟢"

st.title(f"{title_emoji} Retirement Stagflation Early-Warning Dashboard")
st.markdown(f"### Updated {today.strftime('%B %d, %Y')}")

# === FRED (live if key exists) ===
fred = None
if "FRED_API_KEY" in st.secrets:
    fred = Fred(api_key=st.secrets["FRED_API_KEY"])

@st.cache_data(ttl=86400, show_spinner="Updating data...")
def get_data():
    data = {}
    try:
        if fred:
            data["Core CPI YoY"]      = fred.get_series_latest_release('CPILFESL')[-1]
            data["Real GDP QoQ SAAR"] = fred.get_series_latest_release('A191RL1Q225SBEA')[-1]
            data["Unemployment Rate"] = fred.get_series_latest_release('UNRATE')[-1]
            data["Fed Funds"]         = fred.get_series_latest_release('FEDFUNDS')[-1]
        else:
            raise Exception()
    except:
        st.warning("FRED live data unavailable — using latest benchmarks")
        data["Core CPI YoY"], data["Real GDP QoQ SAAR"] = 3.0, 4.0
        data["Unemployment Rate"], data["Fed Funds"] = 4.4, 4.00

    # Yahoo Finance (defensive)
    try:
        data["10yr Yield"] = round(yf.Ticker("^TNX").history(period="5d")["Close"].iloc[-1], 2)
        spx = yf.Ticker("^GSPC").history(period="ytd")
        data["S&P 500 YTD"] = round((spx["Close"].iloc[-1]/spx["Close"].iloc[0]-1)*100, 1)
        crb = yf.Ticker("^CRB").history(period="13mo")
        data["CRB Index 12m %"] = round((crb["Close"].iloc[-1]/crb["Close"].iloc[0]-1)*100, 1)
    except:
        data["10yr Yield"], data["S&P 500 YTD"], data["CRB Index 12m %"] = 4.02, 10.3, 7.4

    return data

raw = get_data()

# === Your 5 signals ===
signals = {
    "Core CPI >6.5% while real GDP <1%":                raw["Core CPI YoY"] > 6.5 and raw["Real GDP QoQ SAAR"] < 1,
    "10yr Yield >6.5% + S&P YTD <5%":                    raw["10yr Yield"] > 6.5 and raw["S&P 500 YTD"] < 5,
    "CRB Index +50% in past 12–18 months":              raw["CRB Index 12m %"] > 50,
    "Unemployment >5.5% while CPI still >5%":           raw["Unemployment Rate"] > 5.5 and raw["Core CPI YoY"] > 5,
    "Real Fed Funds rate <2%":                          (raw["Fed Funds"] - raw["Core CPI YoY"]) < 2,
}
red_count = sum(signals.values())
color = "red" if red_count >= 3 else "gray"
st.markdown(f"### **<span style='color:{color}'>{red_count} of 5 signals flashing red</span>**", unsafe_allow_html=True)

# Display
col1, col2 = st.columns([2,1])
with col1:
    df = pd.DataFrame([{"Signal": k, "Status": "🟥 YES" if v else "🟢 NO"} for k, v in signals.items()])
    st.dataframe(df, use_container_width=True, hide_index=True)
with col2:
    st.metric("10-yr Treasury", f"{raw['10yr Yield']:.2f}%")
    st.metric("Core CPI YoY", f"{raw['Core CPI YoY']:.1f}%")
    st.metric("Unemployment", f"{raw['Unemployment Rate']:.1f}%")

# Chart
try:
    fig = px.line(yf.Ticker("^TNX").history(period="2y"), y="Close", title="10-Year Treasury Yield (2-Year)")
    st.plotly_chart(fig, use_container_width=True)
except:
    pass

st.success("When 3+ signals turn red → immediately rotate per 1970s playbook.")

# === Mailchimp Email Capture ===
st.markdown("---")
st.subheader("🔔 Get notified the moment 3+ signals turn red")
with st.form(key="email_form"):
    email = st.text_input("Your email address", placeholder="you@example.com")
    submit = st.form_submit_button("Send me the alert (free)")

    if submit:
        if not email or "@" not in email:
            st.error("Please enter a valid email")
        else:
            dc = st.secrets["MAILCHIMP_DC"]
            audience_id = st.secrets["MAILCHIMP_AUDIENCE_ID"]
            url = f"https://{dc}.api.mailchimp.com/3.0/lists/{audience_id}/members/"
            data = {"email_address": email, "status": "subscribed"}
            try:
                response = requests.post(url, auth=("anystring", st.secrets.get("MAILCHIMP_API_KEY", "")), json=data)
                if response.status_code in [200, 201]:
                    st.success("✅ You’re in! You’ll get the alert the moment 3+ signals flash red.")
                else:
                    st.error("Temporary glitch — try again in a minute.")
            except:
                st.error("Connection issue — try again soon.")

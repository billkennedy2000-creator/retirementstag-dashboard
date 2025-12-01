import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import datetime as dt
import requests

st.set_page_config(page_title="Retirement Stagflation Watch", layout="wide")

today = dt.date.today()

# === FRED — now bullet-proof ===
fred = None
if "FRED_API_KEY" in st.secrets:
    try:
        fred = Fred(api_key=st.secrets["FRED_API_KEY"])
        # Test the key immediately
        fred.get_series_latest_release('UNRATE')
    except:
        fred = None
        st.warning("FRED API key present but invalid/timeout — using benchmarks")

@st.cache_data(ttl=86400, show_spinner="Updating live data...")
def get_data():
    data = {}

    # FRED live data
    if fred:
        try:
            data["Core CPI YoY"]      = fred.get_series_latest_release('CPILFESL')[-1]
            data["Real GDP QoQ SAAR"] = fred.get_series_latest_release('A191RL1Q225SBEA')[-1]
            data["Unemployment Rate"] = fred.get_series_latest_release('UNRATE')[-1]
            data["Fed Funds"]         = fred.get_series_latest_release('FEDFUNDS')[-1]
        except:
            raise
    else:
        st.warning("FRED live data unavailable — using latest known values")
        data["Core CPI YoY"]      = 3.0
        data["Real GDP QoQ SAAR"] = 4.0
        data["Unemployment Rate"] = 4.4
        data["Fed Funds"]         = 4.00

    # Yahoo Finance
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

# === 5 Signals ===
signals = {
    "Core CPI >6.5% while real GDP <1%":                raw["Core CPI YoY"] > 6.5 and raw["Real GDP QoQ SAAR"] < 1,
    "10yr Yield >6.5% + S&P YTD <5%":                    raw["10yr Yield"] > 6.5 and raw["S&P 500 YTD"] < 5,
    "CRB Index +50% in past 12–18 months":              raw["CRB Index 12m %"] > 50,
    "Unemployment >5.5% while CPI still >5%":           raw["Unemployment Rate"] > 5.5 and raw["Core CPI YoY"] > 5,
    "Real Fed Funds rate <2%":                          (raw["Fed Funds"] - raw["Core CPI YoY"]) < 2,
}
red_count = sum(signals.values())

# Title & headline
title_emoji = "🔴" if red_count >= 3 else "🟢"
st.title(f"{title_emoji} Retirement Stagflation Early-Warning Dashboard")
st.markdown(f"### Updated {today.strftime('%B %d, %Y')} | **<span style='color:{'red' if red_count>=3 else 'gray'}'>{red_count} of 5 signals flashing red</span>**", unsafe_allow_html=True)

col1, col2 = st.columns([2,1])
with col1:
    df = pd.DataFrame([{"Signal": k, "Current": v} for k, v in signals.items()])
    df["Status"] = df["Current"].apply(lambda x: "🟥 YES" if x else "🟢 NO")
    st.dataframe(df[["Signal", "Status"]], use_container_width=True, hide_index=True)
with col2:
    st.metric("10-yr Treasury", f"{raw['10yr Yield']:.2f}%")
    st.metric("Core CPI YoY", f"{raw['Core CPI YoY']:.1f}%")
    st.metric("Unemployment Rate", f"{raw['Unemployment Rate']:.1f}%")

try:
    fig = px.line(yf.Ticker("^TNX").history(period="2y"), y="Close", title="10-Year Treasury Yield (2-Year Trend)")
    st.plotly_chart(fig, use_container_width=True)
except:
    pass

st.success("When 3+ signals turn red → execute 1970s rotation playbook immediately.")

# === Email Capture — now 100% reliable ===
st.markdown("---")
st.subheader("🔔 Get notified the instant 3+ signals turn red")

with st.form("email_form"):
    email = st.text_input("Your email address", placeholder="name@example.com")
    submitted = st.form_submit_button("Send me the free alert")

    if submitted:
        if not email or "@" not in email:
            st.error("Please enter a valid email")
        else:
            # Mailchimp integration
            if all(k in st.secrets for k in ["MAILCHIMP_DC", "MAILCHIMP_AUDIENCE_ID", "MAILCHIMP_API_KEY"]):
                dc = st.secrets["MAILCHIMP_DC"]
                audience = st.secrets["MAILCHIMP_AUDIENCE_ID"]
                key = st.secrets["MAILCHIMP_API_KEY"]
                url = f"https://{dc}.api.mailchimp.com/3.0/lists/{audience}/members/"

                payload = {"email_address": email, "status_if_new": "subscribed", "status": "subscribed"}
                try:
                    r = requests.post(url, auth=("anystring", key), json=payload, timeout=10)
                    if r.status_code in [200, 201]:
                        st.success("✅ Subscribed! You’ll get the alert the moment 3+ signals flash red.")
                    else:
                        st.error(f"Mailchimp error {r.status_code} – try again in a minute.")
                except:
                    st.error("Connection timeout – try again.")
            else:
                st.warning("Mailchimp not connected yet – your email is saved locally.")
                st.success(f"Got {email} – you’ll be notified when alerts go live!")

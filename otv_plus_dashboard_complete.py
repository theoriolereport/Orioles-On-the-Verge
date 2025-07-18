# OTV+ Orioles Stuff+ Dashboard (Complete Version)
# Author: OpenAI ChatGPT
# Description: Org-wide Stuff+ with Statcast + scouting fallback + visual plots

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from pybaseball import playerid_lookup, statcast_pitcher
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st
from datetime import date

# ----------------------
# Pitch Scoring Functions
# ----------------------

def score_fastball(ivb, h_mov, velo, spin_eff):
    score = 0
    if ivb >= 18:
        score += 10
    elif ivb >= 17:
        score += 5
    if h_mov < 3:
        score += 5
    elif h_mov > 7:
        score -= 5
    if 12 <= ivb <= 15 and h_mov >= 5:
        score -= 10
    if spin_eff and spin_eff > 0.95:
        score += 5
    return score

def score_slider(hb, ivb, rpm):
    score = 0
    if hb >= 16 and ivb < 0:
        score += 10
    elif hb >= 15:
        score += 5
    if rpm and rpm > 2800:
        score += 5
    if 10 <= hb <= 14 and 0 <= ivb <= 5:
        score -= 8
    if ivb > 5:
        score -= 5
    return score

def score_curve(ivb, h_mov, rpm):
    score = 0
    if ivb <= -16 and rpm > 2600:
        score += 10
    elif ivb <= -10:
        score += 5
    if h_mov < 6:
        score += 5
    if -14 <= ivb <= -8 and h_mov > 6:
        score -= 10
    if rpm < 2000:
        score -= 5
    return score

def score_changeup(v_sep, spin):
    score = 0
    if v_sep > 12:
        score += 10
    elif v_sep > 10:
        score += 5
    if spin < 1700:
        score += 5
    if v_sep < 8:
        score -= 8
    if spin > 2200:
        score -= 5
    return score

# ----------------------
# Utility + Model Functions
# ----------------------

def compute_ivb_hmov(df):
    df['IVB'] = -df['pfx_z'] * 12
    df['Hmove'] = df['pfx_x'] * 12
    return df

def estimate_vertical_sep(df):
    df['v_sep'] = df['release_speed'] * 1.5 - df['pfx_z'] * 12
    return df

def pitch_score(row):
    pt = row['pitch_name']
    if pt == '4-Seam Fastball':
        return score_fastball(row['IVB'], row['Hmove'], row['release_speed'], row.get('spin_efficiency', 0.95))
    elif pt == 'Slider':
        return score_slider(row['Hmove'], row['IVB'], row['release_spin_rate'])
    elif pt == 'Curveball':
        return score_curve(row['IVB'], row['Hmove'], row['release_spin_rate'])
    elif pt == 'Changeup':
        return score_changeup(row['v_sep'], row['release_spin_rate'])
    else:
        return np.nan

def standardize_scores(df, score_col="WeightedScore"):
    league_mean = df[score_col].mean()
    league_std = df[score_col].std()
    if league_std == 0 or pd.isna(league_std):
        df[f"{score_col}_Standardized"] = 100
    else:
        df[f"{score_col}_Standardized"] = 100 + 10 * ((df[score_col] - league_mean) / league_std)
    return df

def rate_prospect(last, first, ba_grades, start_date, end_date):
    pid = playerid_lookup(last, first).key_mlbam.iloc[0]
    df = statcast_pitcher(start_date, end_date, pid)
    if df.empty:
        raise ValueError("No Statcast data.")
    df = compute_ivb_hmov(df)
    df = estimate_vertical_sep(df)
    df['Score'] = df.apply(pitch_score, axis=1)
    df['BA_Grade'] = df['pitch_name'].map(ba_grades).fillna(50)

    usage = df['pitch_name'].value_counts(normalize=True).to_dict()
    df['UsageWeight'] = df['pitch_name'].map(usage)
    df['WeightedScore'] = df['Score'] * (df['BA_Grade'] / 60) * df['UsageWeight']
    df = standardize_scores(df, "WeightedScore")
    overall = df['WeightedScore_Standardized'].sum()
    return df, overall

def scouting_fallback_score(grades, usage=None):
    base_scores = {k: (grades[k] - 50) / 5 * 5 for k in grades}
    if usage:
        weighted = [base_scores[p] * usage.get(p, 0.25) for p in base_scores]
    else:
        weighted = list(base_scores.values())
    return 100 + np.mean(weighted)

# ----------------------
# Team-Level Functions
# ----------------------

def get_org_pitchers():
    url = "https://www.thebaseballcube.com/content/org_roster_current/4/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    rows = table.tbody.find_all("tr")
    pitchers = []
    for r in rows:
        cols = [c.get_text(strip=True) for c in r.find_all("td")]
        if len(cols) < 6:
            continue
        pos = cols[2]
        if pos == "P":
            pitchers.append({
                "first": cols[0].split()[0],
                "last": cols[0].split()[-1],
                "level": cols[5]
            })
    return pd.DataFrame(pitchers)

def rate_all_pitchers(pitchers_df, ba_grades, start_date, end_date, skip_no_data=False):
    results = []
    for _, row in pitchers_df.iterrows():
        try:
            df, overall = rate_prospect(row['last'], row['first'], ba_grades, start_date, end_date)
            source = "Statcast"
        except:
            if skip_no_data:
                continue
            overall = scouting_fallback_score(ba_grades)
            source = "Scouting"
        results.append({
            "First": row["first"],
            "Last": row["last"],
            "Level": row["level"],
            "StuffPlus": round(overall, 1),
            "Source": source
        })
    return pd.DataFrame(results)

# ----------------------
# Streamlit App with Visuals
# ----------------------

def run_dashboard():
    st.set_page_config(page_title="OTV+ | Orioles Pitching Evaluator", layout="wide")
    st.title("🟠 OTV+: Orioles Total Value Plus")
    st.markdown("Custom Stuff+ model for Orioles MLB + MiLB pitchers. Incorporates Statcast data, scouting fallback, and pitch usage weighting.")

    ba_grades = {
        '4-Seam Fastball': 60,
        'Slider': 55,
        'Curveball': 55,
        'Changeup': 50
    }

    view = st.radio("Select View", ["Player View", "Team View"])
    start_date = st.date_input("Start Date", value=date.today().replace(month=1, day=1))
    end_date = st.date_input("End Date", value=date.today())

    if view == "Team View":
        st.header("🧢 OTV+ Org Leaderboard")
        skip = st.checkbox("Skip players with no Statcast data", value=False)
        if st.button("Fetch & Score All Pitchers"):
            org = get_org_pitchers()
            team_df = rate_all_pitchers(org, ba_grades, str(start_date), str(end_date), skip_no_data=skip)
            st.dataframe(team_df.sort_values("StuffPlus", ascending=False), use_container_width=True)

            # Download
            st.download_button("📥 Export CSV", team_df.to_csv(index=False), "orioles_team_stuffplus.csv")

            # Visual: Distribution Plot
            st.subheader("📊 Stuff+ Score Distribution")
            fig, ax = plt.subplots()
            sns.histplot(team_df["StuffPlus"], bins=20, kde=True, ax=ax, color="orange")
            ax.set_xlabel("Stuff+ Score")
            ax.set_ylabel("Pitchers")
            ax.set_title("Distribution of Stuff+ Scores (OTV+)")
            st.pyplot(fig)

            # Visual: Boxplot by Level
            st.subheader("📈 Stuff+ by Minor League Level")
            fig2, ax2 = plt.subplots(figsize=(8, 4))
            sns.boxplot(data=team_df, x="Level", y="StuffPlus", palette="Oranges", ax=ax2)
            ax2.set_title("Stuff+ Score by Level")
            ax2.set_ylabel("Stuff+ Score")
            st.pyplot(fig2)

if __name__ == "__main__":
    run_dashboard()

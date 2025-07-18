# Orioles-Specific Stuff+ Evaluator with Streamlit Dashboard
# Author: OpenAI ChatGPT
# Description: Evaluate and visualize Orioles-style pitch profiles using Statcast + BA grades

import pandas as pd
import numpy as np
from pybaseball import playerid_lookup, statcast_pitcher
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

# ----------------------
# Scoring Functions
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
# Processing Functions
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
    df[f"{score_col}_Standardized"] = 100 + 10 * ((df[score_col] - league_mean) / league_std)
    return df

def rate_prospect(last, first, ba_grades, start_date, end_date):
    pid = playerid_lookup(last, first).key_mlbam.iloc[0]
    df = statcast_pitcher(start_date, end_date, pid)
    df = compute_ivb_hmov(df)
    df = estimate_vertical_sep(df)
    df['Score'] = df.apply(pitch_score, axis=1)
    df['BA_Grade'] = df['pitch_name'].map(ba_grades).fillna(50)
    df['WeightedScore'] = df['Score'] * (df['BA_Grade'] / 60)
    df = standardize_scores(df, "WeightedScore")
    return df

# ----------------------
# Visualization Functions
# ----------------------

def plot_pitch_score_dist(df):
    fig, ax = plt.subplots()
    sns.violinplot(data=df, x='pitch_name', y='WeightedScore_Standardized', ax=ax)
    ax.set_title("Standardized Stuff+ Scores by Pitch Type (Orioles Model)")
    ax.set_xlabel("Pitch Type")
    ax.set_ylabel("Stuff+ Score")
    return fig

def plot_weighted_score_trend(df):
    df['game_date'] = pd.to_datetime(df['game_date'])
    daily = df.groupby('game_date')['WeightedScore_Standardized'].mean()
    fig, ax = plt.subplots(figsize=(10, 4))
    daily.plot(ax=ax, title="Daily Standardized Stuff+ Score")
    ax.set_ylabel("Stuff+ Score")
    return fig

def compare_players(df1, df2, name1, name2):
    mean_scores1 = df1.groupby('pitch_name')['WeightedScore_Standardized'].mean()
    mean_scores2 = df2.groupby('pitch_name')['WeightedScore_Standardized'].mean()
    combined = pd.DataFrame({name1: mean_scores1, name2: mean_scores2})
    fig, ax = plt.subplots()
    combined.plot(kind='bar', ax=ax)
    ax.set_title("Player Comparison by Pitch Type (Standardized Score)")
    ax.set_ylabel("Stuff+ Score")
    return fig

# ----------------------
# Streamlit UI
# ----------------------

def run_dashboard():
    st.set_page_config(page_title="Orioles Stuff+ Dashboard", layout="wide")
    st.title("⚾ Orioles Pitching Prospect Stuff+ Evaluator (Standardized)")
    st.markdown("Statcast-based pitch modeling with league-normalized scoring (avg = 100, SD = 10)")

    known_pitchers = {
        "Kyle Bradish": ("Kyle", "Bradish"),
        "Grayson Rodriguez": ("Grayson", "Rodriguez"),
        "DL Hall": ("DL", "Hall"),
        "Cade Povich": ("Cade", "Povich"),
        "Chayce McDermott": ("Chayce", "McDermott"),
        "Custom Input": ("", "")
    }

    ba_grades = {
        '4-Seam Fastball': 60,
        'Slider': 55,
        'Curveball': 55,
        'Changeup': 50
    }

    with st.form("player_form"):
        col1, col2 = st.columns(2)
        with col1:
            p1_name = st.selectbox("Select First Player", list(known_pitchers.keys()))
            first_name1, last_name1 = known_pitchers[p1_name]
            if p1_name == "Custom Input":
                first_name1 = st.text_input("First Player First Name")
                last_name1 = st.text_input("First Player Last Name")

        with col2:
            p2_name = st.selectbox("Select Second Player (Optional)", ["None"] + list(known_pitchers.keys()))
            if p2_name != "None":
                first_name2, last_name2 = known_pitchers[p2_name]
                if p2_name == "Custom Input":
                    first_name2 = st.text_input("Second Player First Name")
                    last_name2 = st.text_input("Second Player Last Name")
            else:
                first_name2 = last_name2 = ""

        start_date = st.date_input("Start Date", value=pd.to_datetime("2024-04-01"))
        end_date = st.date_input("End Date", value=pd.to_datetime("2024-07-01"))
        submitted = st.form_submit_button("Run Model")

    if submitted and first_name1 and last_name1:
        df1 = rate_prospect(last_name1, first_name1, ba_grades, str(start_date), str(end_date))
        st.subheader(f"🎯 {first_name1} {last_name1} Standardized Stuff+ Scores")
        st.pyplot(plot_pitch_score_dist(df1))
        st.pyplot(plot_weighted_score_trend(df1))
        st.download_button("📥 Download CSV", df1.to_csv(index=False), file_name=f"{first_name1}_{last_name1}_standardized_scores.csv")

        if first_name2 and last_name2:
            df2 = rate_prospect(last_name2, first_name2, ba_grades, str(start_date), str(end_date))
            st.subheader(f"🎯 {first_name2} {last_name2} Standardized Stuff+ Scores")
            st.pyplot(plot_pitch_score_dist(df2))
            st.pyplot(plot_weighted_score_trend(df2))
            st.subheader("🔍 Player Comparison")
            st.pyplot(compare_players(df1, df2, f"{first_name1} {last_name1}", f"{first_name2} {last_name2}"))

if __name__ == "__main__":
    run_dashboard()

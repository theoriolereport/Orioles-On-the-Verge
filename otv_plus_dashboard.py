# OTV+ Orioles Stuff+ Dashboard
# Author: OpenAI ChatGPT
# Description: Stuff+ dashboard for Baltimore Orioles organization (MLB + MiLB)

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from pybaseball import playerid_lookup, statcast_pitcher
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st
from datetime import date

# [Functions are identical to previous version up to team_df]

# Streamlit App with Visuals
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

"""CareerAI entry point, authentication, shared layout, and page navigation."""

import base64
from html import escape
from pathlib import Path

import streamlit as st

import api_client
from api_client import CareerAPIError
from student_pages import (
    render_career_guide_panel,
    render_chat_page,
    render_home_page,
    render_jobs_page,
    render_learning_page,
    render_profile_page,
    render_recommendations_page,
    render_skill_gaps_page,
)

st.set_page_config(
    page_title="CareerAI | Student career guidance",
    page_icon=":material/auto_awesome:",
    layout="wide",
    initial_sidebar_state="expanded",
)

auth_background_style = ""
if not st.session_state.get("account"):
    student_career_photo = base64.b64encode(
        (Path(__file__).with_name("assets") / "student-career.jpg").read_bytes()
    ).decode("ascii")
    auth_background_style = """
        [data-testid="stAppViewContainer"] {
            background-image:
                linear-gradient(
                    125deg,
                    rgba(243, 247, 255, 0.74) 0%,
                    rgba(248, 249, 253, 0.78) 52%,
                    rgba(241, 250, 247, 0.74) 100%
                ),
                url("data:image/jpeg;base64,__STUDENT_CAREER_PHOTO__"),
                linear-gradient(135deg, #f3f7ff 0%, #f8f9fd 52%, #f1faf7 100%);
            background-position: center, center, center;
            background-repeat: no-repeat;
            background-size: cover, cover, cover;
            background-attachment: fixed;
        }
    """.replace("__STUDENT_CAREER_PHOTO__", student_career_photo)

st.html(
    """
    <style>
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(135deg, #f3f7ff 0%, #f8f9fd 52%, #f1faf7 100%);
        }
        __AUTH_BACKGROUND_STYLE__
        .block-container {
            padding-top: 2.25rem;
            padding-bottom: 3.5rem;
            max-width: 1360px;
        }
        h1, h2, h3, h4 {
            letter-spacing: -0.035em;
        }
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3,
        [data-testid="stMarkdownContainer"] h4 {
            color: #244da8;
        }
        [data-testid="stCaptionContainer"] p {
            color: #606980;
        }
        [class*="st-key-metric-"] {
            min-height: 132px;
            padding: 1.15rem 1.2rem;
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(27, 37, 68, 0.055);
        }
        .st-key-metric-skills {
            background: linear-gradient(140deg, #e5edff 0%, #f3f6ff 100%);
            border-color: #cbd9ff;
            border-left: 4px solid #4778ed;
        }
        .st-key-metric-interests {
            background: linear-gradient(140deg, #e1f6ed 0%, #f2fbf6 100%);
            border-color: #c6ead8;
            border-left: 4px solid #35a87b;
        }
        .st-key-metric-experience {
            background: linear-gradient(140deg, #fff0d9 0%, #fff9ed 100%);
            border-color: #f3dfb9;
            border-left: 4px solid #e59a2f;
        }
        .st-key-metric-match {
            background: linear-gradient(140deg, #eee8ff 0%, #f8f5ff 100%);
            border-color: #d9ceff;
            border-left: 4px solid #8664df;
        }
        [data-testid="stMetricValue"] {
            color: #20263a;
            font-weight: 700;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(165deg, #101a32 0%, #172747 55%, #111b33 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.07);
        }
        [data-testid="stSidebarNavLink"] {
            border-radius: 12px;
            transition: background 160ms ease, box-shadow 160ms ease, transform 160ms ease;
        }
        [data-testid="stSidebarNavLink"]:hover {
            background: rgba(110, 151, 235, 0.16);
            transform: translateX(2px);
        }
        [data-testid="stSidebarNavLink"][aria-current="page"] {
           
            background: linear-gradient(105deg, #2d63cf 0%, #377ee8 62%, #258d9a 100%);
            box-shadow: 0 5px 16px rgba(28, 89, 186, 0.28);
        }
        [data-testid="stSidebarNavLink"][aria-current="page"] span {
            color: #fff !important;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: #c4cada;
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a {
            border-radius: 12px;
        }
        [data-testid="stBaseButton-primary"] {
            border: 0;
            background: linear-gradient(105deg, #2563eb 0%, #397ff4 58%, #5175ee 100%);
            color: #fff;
            box-shadow: 0 6px 16px rgba(37, 99, 235, 0.24);
        }
        [data-testid="stBaseButton-primary"]:hover {
            border: 0;
            background: linear-gradient(105deg, #1d4ed8 0%, #2563eb 58%, #455fe0 100%);
            color: #fff;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.34);
            transform: translateY(-1px);
        }
        [data-testid="stLinkButton"] a {
            border: 0;
            background: linear-gradient(105deg, #2563eb 0%, #397ff4 58%, #5175ee 100%);
            color: #fff !important;
            box-shadow: 0 5px 14px rgba(37, 99, 235, 0.2);
            transition: box-shadow 160ms ease, transform 160ms ease;
        }
        [data-testid="stLinkButton"] a:hover {
            background: linear-gradient(105deg, #1d4ed8 0%, #2563eb 58%, #455fe0 100%);
            color: #fff !important;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.3);
            transform: translateY(-1px);
        }
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stTextArea"] textarea {
            border-radius: 12px;
            transition: border-color 150ms ease, box-shadow 150ms ease;
        }
        [data-testid="stTextInput"] input:focus,
        [data-testid="stNumberInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus,
        [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within,
        [data-testid="stMultiSelect"] [data-baseweb="select"]:focus-within {
            border-color: #4f82e8;
            box-shadow: 0 0 0 3px rgba(57, 121, 237, 0.14);
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            border: 1px solid #cad9fb;
            border-radius: 999px;
            background: linear-gradient(120deg, #e8efff, #edf5ff);
            color: #2856ad;
            font-weight: 600;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 18px;
            border-color: #dfe6f1;
            box-shadow: 0 7px 24px rgba(27, 37, 68, 0.045);
            transition: box-shadow 160ms ease, border-color 160ms ease, transform 160ms ease;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:hover {
            border-color: #c6d5ef;
            box-shadow: 0 12px 30px rgba(27, 37, 68, 0.08);
            transform: translateY(-2px);
        }
        [data-testid="stProgressBarTrack"] {
            border-radius: 999px;
            background: #e8edf6;
            overflow: hidden;
        }
        [data-testid="stProgressBarTrack"] > div {
            border-radius: inherit;
            background: linear-gradient(90deg, #3979ed 0%, #5d7bea 58%, #35a87b 100%);
        }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
            color: #245bc1;
        }
        [data-testid="stAlert"] {
            border-radius: 14px;
            box-shadow: 0 4px 14px rgba(27, 37, 68, 0.045);
        }
        [data-testid="stPageLink"] a {
            border-radius: 12px;
            font-weight: 600;
            border: 0;
            background: linear-gradient(105deg, #2563eb 0%, #397ff4 58%, #5175ee 100%);
            color: #fff !important;
            box-shadow: 0 5px 14px rgba(37, 99, 235, 0.2);
            transition: box-shadow 160ms ease, transform 160ms ease;
        }
        [data-testid="stPageLink"] a:hover {
            background: linear-gradient(105deg, #1d4ed8 0%, #2563eb 58%, #455fe0 100%);
            color: #fff !important;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.3);
            transform: translateY(-1px);
        }
        [data-testid="stLinkButton"] a {
            border-radius: 12px;
            font-weight: 650;
        }
        .st-key-career-guide-shortcut {
            position: fixed !important;
            right: clamp(16px, 2.5vw, 36px);
            bottom: clamp(16px, 2.5vw, 30px);
            z-index: 1000;
            width: min(390px, calc(100vw - 32px));
            pointer-events: none;
        }
        .st-key-career-guide-shortcut > div {
            pointer-events: auto;
        }
        .st-key-career-guide-panel {
            margin-bottom: 0.75rem;
            padding: 0.8rem;
            border: 1px solid #dbe3f1;
            border-radius: 14px;
            background: #fff;
            box-shadow: 0 12px 36px rgba(25, 43, 78, 0.2);
        }
        .st-key-career-guide-close [data-testid="stBaseButton-secondary"] {
            width: 36px;
            height: 36px;
            padding: 0;
            border-radius: 50%;
            font-size: 1.05rem;
            font-weight: 700;
        }
        .st-key-career-guide-toggle [data-testid="stBaseButton-primary"] {
            display: flex;
            width: 68px;
            height: 68px;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.1rem;
            padding: 0.35rem;
            border-radius: 50%;
            background: linear-gradient(110deg, #1745b5 0%, #3477ef 60%, #168f9a 100%);
            box-shadow: 0 8px 24px rgba(30, 75, 172, 0.3);
            font-size: 0.72rem;
            font-weight: 700;
            line-height: 1;
            transition: box-shadow 160ms ease, transform 160ms ease;
        }
        .st-key-career-guide-toggle {
            align-self: flex-end;
        }
        .st-key-career-guide-toggle [data-testid="stBaseButton-primary"]:hover {
            background: linear-gradient(110deg, #123b9e 0%, #2866d4 60%, #117b85 100%);
            box-shadow: 0 11px 28px rgba(30, 75, 172, 0.38);
            transform: translateY(-2px);
        }
        [data-testid="stTabs"] [role="tab"] {
            font-weight: 600;
        }
        .workspace-hero {
            position: relative;
            overflow: hidden;
            margin: 0 0 1.6rem;
            padding: 1.7rem 2rem;
            border: 1px solid #e4e8f7;
            border-radius: 23px;
            background:
                radial-gradient(ellipse at 90% 0%, rgba(184, 195, 255, 0.43), transparent 33%),
                linear-gradient(115deg, #f0f3ff 0%, #f8f8ff 55%, #eef8f5 100%);
            box-shadow: 0 12px 32px rgba(35, 48, 87, 0.055);
        }
        .workspace-hero::after {
            position: absolute;
            top: -84px;
            right: 3%;
            width: 180px;
            height: 180px;
            border: 1px solid rgba(85, 117, 247, 0.11);
            border-radius: 50%;
            content: "";
            box-shadow: 0 0 0 24px rgba(85, 117, 247, 0.035), 0 0 0 48px rgba(85, 117, 247, 0.025);
            pointer-events: none;
        }
        .workspace-eyebrow {
            position: relative;
            z-index: 1;
            margin-bottom: 0.5rem;
            color: #5a6bc0;
            font-size: 0.7rem;
            font-weight: 750;
            letter-spacing: 0.12em;
        }
        .workspace-hero h1 {
            position: relative;
            z-index: 1;
            margin: 0;
            color: #485fc7;
            background-image: linear-gradient(100deg, #1745b5 0%, #3477ef 58%, #12998f 100%);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: clamp(1.9rem, 3.2vw, 2.65rem);
            font-weight: 730;
            line-height: 1.15;
            letter-spacing: -0.055em;
        }
        .workspace-hero p {
            position: relative;
            z-index: 1;
            max-width: 690px;
            margin: 0.55rem 0 0;
            color: #626b80;
            font-size: 0.98rem;
            line-height: 1.6;
        }
        [class*="st-key-metric-"] [data-testid="stMetricLabel"] {
            color: #606980;
            font-weight: 600;
        }
        [class*="st-key-metric-"] [data-testid="stMetricValue"] {
            font-size: 1.85rem;
            letter-spacing: -0.045em;
        }
        .st-key-metric-career-matches {
            position: relative;
            background: linear-gradient(140deg, #e5efff 0%, #f5f8ff 100%);
            border-color: #cbdcff;
            border-left: 4px solid #3979ed;
            cursor: pointer;
            transition: box-shadow 160ms ease, border-color 160ms ease;
        }
        .st-key-metric-career-matches:hover {
            border-color: #a9c5fa;
            box-shadow: 0 10px 26px rgba(37, 99, 235, 0.16);
        }
        .st-key-metric-career-matches [data-testid="stButton"] {
            position: absolute;
            inset: 0;
            z-index: 2;
        }
        .st-key-metric-career-matches [data-testid="stButton"] button {
            width: 100%;
            height: 100%;
            padding: 0;
            border: 0;
            background: transparent;
            color: transparent;
            box-shadow: none;
            cursor: pointer;
        }
        .st-key-metric-career-matches [data-testid="stButton"] button:hover {
            border: 0;
            background: transparent;
            color: transparent;
            box-shadow: none;
        }
        .st-key-metric-career-matches [data-testid="stButton"] button:focus-visible {
            outline: 3px solid #3979ed;
            outline-offset: -4px;
        }
        .st-key-metric-career-matches [data-testid="stMetricValue"] {
            color: #245bc1;
        }
        .st-key-metric-profile-skills {
            background: linear-gradient(140deg, #e1f6ed 0%, #f4fbf6 100%);
            border-color: #c6ead8;
            border-left: 4px solid #35a87b;
        }
        .st-key-metric-profile-skills [data-testid="stMetricValue"] {
            color: #20845d;
        }
        .st-key-metric-learning-topics {
            background: linear-gradient(140deg, #eee8ff 0%, #f8f5ff 100%);
            border-color: #d9ceff;
            border-left: 4px solid #8664df;
        }
        .st-key-metric-learning-topics [data-testid="stMetricValue"] {
            color: #6948bd;
        }
        .st-key-metric-skill-gaps {
            background: linear-gradient(140deg, #fff0d9 0%, #fff9ed 100%);
            border-color: #f3dfb9;
            border-left: 4px solid #e59a2f;
        }
        .st-key-metric-skill-gaps [data-testid="stMetricValue"] {
            color: #a96013;
        }
        [class*="st-key-skill-gap-role-tone-0-"] {
            --role-accent: #3979ed;
            --role-tint: #edf4ff;
            --skill-tint: #f7faff;
        }
        [class*="st-key-skill-gap-role-tone-1-"] {
            --role-accent: #35a87b;
            --role-tint: #eaf8f0;
            --skill-tint: #f6fcf8;
        }
        [class*="st-key-skill-gap-role-tone-2-"] {
            --role-accent: #d88b25;
            --role-tint: #fff5e3;
            --skill-tint: #fffbf2;
        }
        [class*="st-key-skill-gap-role-tone-3-"] {
            --role-accent: #d96062;
            --role-tint: #fff0f0;
            --skill-tint: #fff8f8;
        }
        [class*="st-key-skill-gap-role-tone-4-"] {
            --role-accent: #168f9a;
            --role-tint: #e8f7f7;
            --skill-tint: #f5fbfb;
        }
        [class*="st-key-skill-gap-role-tone-5-"] {
            --role-accent: #8664df;
            --role-tint: #f1edff;
            --skill-tint: #faf8ff;
        }
        [class*="st-key-skill-gap-role-tone-"] [data-testid="stExpander"] details > summary {
            border-left: 4px solid var(--role-accent);
            border-radius: 8px;
            background: var(--role-tint);
        }
        [class*="st-key-skill-gap-role-tone-"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: color-mix(in srgb, var(--role-accent) 34%, white);
            border-left: 3px solid var(--role-accent);
            background: var(--skill-tint);
        }
        [class*="st-key-skill-flow-learn-"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #cbdcff;
            border-top: 4px solid #4778ed;
            background: linear-gradient(155deg, #edf4ff 0%, #ffffff 100%);
        }
        [class*="st-key-skill-flow-practice-"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #c6ead8;
            border-top: 4px solid #35a87b;
            background: linear-gradient(155deg, #eaf8f0 0%, #ffffff 100%);
        }
        [class*="st-key-skill-flow-show-"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #d9ceff;
            border-top: 4px solid #8664df;
            background: linear-gradient(155deg, #f1edff 0%, #ffffff 100%);
        }
        [class*="st-key-skill-flow-learn-"] [data-testid="stVerticalBlockBorderWrapper"],
        [class*="st-key-skill-flow-practice-"] [data-testid="stVerticalBlockBorderWrapper"],
        [class*="st-key-skill-flow-show-"] [data-testid="stVerticalBlockBorderWrapper"] {
            min-height: 14rem;
        }
        .st-key-metric-skills [data-testid="stMetricValue"] {
            color: #315fc5;
        }
        .st-key-metric-interests [data-testid="stMetricValue"] {
            color: #20845d;
        }
        .st-key-metric-experience [data-testid="stMetricValue"] {
            color: #a96013;
        }
        .st-key-metric-match [data-testid="stMetricValue"] {
            color: #6948bd;
        }
        [class*="st-key-recommendations-summary-"] {
            min-height: 112px;
            border-color: #d8e4f5;
            background: linear-gradient(145deg, #ffffff 0%, #f1f6ff 100%);
        }
        .st-key-recommendations-summary-top-match {
            border-left: 4px solid #4778ed;
        }
        .st-key-recommendations-summary-skills {
            border-left: 4px solid #35a87b;
        }
        [class*="st-key-recommendation-card-"] {
            border-color: #d8e3f2;
            background: linear-gradient(145deg, #ffffff 0%, #f8faff 100%);
            box-shadow: 0 8px 24px rgba(27, 37, 68, 0.045);
            transition: border-color 160ms ease, box-shadow 160ms ease;
        }
        [class*="st-key-recommendation-card-"]:hover {
            border-color: #b6c9ec;
            box-shadow: 0 12px 28px rgba(37, 75, 138, 0.09);
        }
        .st-key-recommendation-card-1 {
            border-top: 4px solid #4778ed;
        }
        .st-key-recommendation-card-2 {
            border-top: 4px solid #35a87b;
        }
        .st-key-recommendation-card-3 {
            border-top: 4px solid #8664df;
        }
        [class*="st-key-job-search-summary-"] {
            min-height: 112px;
            border-color: #d8e4f5;
            background: linear-gradient(145deg, #ffffff 0%, #f1f6ff 100%);
        }
        .st-key-job-search-summary-top-fit {
            border-left: 4px solid #4778ed;
        }
        .st-key-job-search-summary-location {
            border-left: 4px solid #35a87b;
        }
        [class*="st-key-job-opportunity-"] {
            border-color: #d8e3f2;
            background: linear-gradient(145deg, #ffffff 0%, #f8faff 100%);
            box-shadow: 0 8px 24px rgba(27, 37, 68, 0.045);
            transition: border-color 160ms ease, box-shadow 160ms ease;
        }
        [class*="st-key-job-opportunity-"]:hover {
            border-color: #b6c9ec;
            box-shadow: 0 12px 28px rgba(37, 75, 138, 0.09);
        }
        .st-key-job-opportunity-0 {
            border-top: 4px solid #4778ed;
        }
        .st-key-job-opportunity-1 {
            border-top: 4px solid #35a87b;
        }
        .st-key-job-opportunity-2 {
            border-top: 4px solid #8664df;
        }
        [class*="st-key-recommendation-next-"] {
            height: 100%;
            border-color: #d9e4f3;
            background: linear-gradient(150deg, #f4f8ff 0%, #ffffff 82%);
        }
        [class*="st-key-recommendation-next-"] [data-testid="stMarkdownContainer"] h4 {
            color: #244da8;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stProgress"]) {
            border-color: #dce7fa;
            background: linear-gradient(145deg, #ffffff 0%, #f5f8ff 100%);
        }
        .st-key-dashboard-roadmap {
            border-color: #d4e4fa;
            background: linear-gradient(150deg, #f0f7ff 0%, #ffffff 78%);
        }
        [class*="st-key-learning-track"] {
            border-color: #d5e1f2;
            background: linear-gradient(155deg, #f7faff 0%, #ffffff 55%, #f4fbf8 100%);
        }
        [class*="st-key-roadmap-step-0"] {
            border-color: #cbdcff;
            border-top: 4px solid #4778ed;
            background: linear-gradient(155deg, #edf4ff 0%, #ffffff 100%);
        }
        [class*="st-key-roadmap-step-1"] {
            border-color: #c6ead8;
            border-top: 4px solid #35a87b;
            background: linear-gradient(155deg, #eaf8f0 0%, #ffffff 100%);
        }
        [class*="st-key-roadmap-step-2"] {
            border-color: #d9ceff;
            border-top: 4px solid #8664df;
            background: linear-gradient(155deg, #f1edff 0%, #ffffff 100%);
        }
        [class*="st-key-roadmap-step-0"] [data-testid="stMarkdownContainer"] a {
            color: #245bc1;
            font-weight: 700;
        }
        [class*="st-key-roadmap-step-1"] [data-testid="stMarkdownContainer"] a {
            color: #20845d;
            font-weight: 700;
        }
        [class*="st-key-roadmap-step-2"] [data-testid="stMarkdownContainer"] a {
            color: #6948bd;
            font-weight: 700;
        }
        [class*="st-key-roadmap-arrow"] {
            color: #73819b;
            text-align: center;
        }
        .st-key-dashboard-assistant {
            border-color: #d8e5ff;
            background: linear-gradient(145deg, #edf4ff 0%, #f8f5ff 100%);
        }
        [data-testid="stBaseButton-header"],
        [data-testid="stMainMenu"],
        [data-testid="stStatusWidget"] {
            display: none;
        }
        [data-testid="stHeader"],
        [data-testid="stHeader"] * {
            pointer-events: none !important;
        }
        [data-testid="stExpandSidebarButton"] {
            position: fixed;
            top: 0.5rem;
            left: 0.5rem;
            z-index: 1000001;
            width: 2.75rem;
            height: 2.75rem;
            opacity: 0;
            cursor: pointer;
            pointer-events: auto !important;
        }
        [data-testid="stExpandSidebarButton"]:focus-visible {
            opacity: 1;
        }
        .st-key-account-topbar {
            position: fixed !important;
            top: 0.35rem;
            right: 1rem;
            z-index: 1000000;
            display: flex;
            width: max-content !important;
            height: auto !important;
            min-width: max-content;
            margin: 0;
            padding: 0;
            border: 0;
            background: transparent;
            box-shadow: none;
            overflow: visible !important;
        }
        .st-key-account-topbar > div {
            width: max-content !important;
        }
        .st-key-account-topbar [data-testid="stPopover"] button {
            width: max-content;
            min-width: max-content;
            flex: 0 0 auto;
            gap: 0.45rem;
            min-height: 2.25rem;
            padding: 0.1rem 0.55rem 0.1rem 0.2rem;
            border: 1px solid #2d63cf;
            border-radius: 999px;
            background: linear-gradient(105deg, #2d63cf 0%, #377ee8 62%, #258d9a 100%);
            color: #fff;
            font-weight: 600;
            white-space: nowrap;
            box-shadow: 0 4px 12px rgba(37, 99, 190, 0.24);
            transition: background 150ms ease, border-color 150ms ease, box-shadow 150ms ease;
        }
        .st-key-account-topbar [data-testid="stPopover"] button:hover {
            border-color: #204fae;
            background: linear-gradient(105deg, #2456bb 0%, #2e6dd4 62%, #1d7d89 100%);
            color: #fff;
            box-shadow: 0 6px 16px rgba(37, 99, 190, 0.32);
        }
        .st-key-account-topbar [data-testid="stPopover"] button:focus-visible {
            outline: 3px solid rgba(37, 99, 235, 0.28);
            outline-offset: 2px;
        }
        .st-key-account-topbar [data-testid="stPopover"] {
            position: relative;
            width: max-content !important;
            min-width: max-content;
            flex: 0 0 auto;
        }
        .st-key-account-topbar [data-testid="stPopover"] button [data-testid="stIconMaterial"] {
            display: inline-flex;
            width: 28px;
            height: 28px;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.2);
            color: #fff;
        }
        @media (max-width: 640px) {
            .st-key-account-topbar {
                top: 0.25rem;
                right: 0.5rem;
            }
        }
        .st-key-dashboard-profile {
            border-color: #dbe5f5;
            background: linear-gradient(120deg, #f4f8ff 0%, #fff 58%, #f2faf7 100%);
        }
        .st-key-profile-completion {
            border-color: #cbdcff;
            background: linear-gradient(110deg, #edf4ff 0%, #fff 72%, #f0f8ff 100%);
        }
        .st-key-profile-completion [data-testid="stMarkdownContainer"] h4 {
            color: #245bc1;
        }
        .dashboard-welcome {
            position: relative;
            display: flex;
            min-height: 132px;
            align-items: center;
            justify-content: space-between;
            overflow: hidden;
            margin: 0 0 1.2rem;
            padding: 1.15rem 1.5rem;
            border: 1px solid #dbe9fb;
            border-radius: 20px;
            background:
                radial-gradient(ellipse at 82% 20%, rgba(113, 181, 242, 0.19), transparent 34%),
                linear-gradient(110deg, #eaf4ff 0%, #e8f8ff 55%, #e7f8f4 100%);
            box-shadow: 0 9px 26px rgba(44, 91, 150, 0.065);
        }
        .dashboard-welcome-copy {
            position: relative;
            z-index: 1;
        }
        .dashboard-kicker {
            margin-bottom: 0.35rem;
            color: #3975c7;
            font-size: 0.66rem;
            font-weight: 750;
            letter-spacing: 0.13em;
        }
        .dashboard-welcome h1 {
            margin: 0;
            color: #17375f;
            font-size: clamp(1.65rem, 2.8vw, 2.15rem);
            font-weight: 750;
            line-height: 1.18;
            letter-spacing: -0.05em;
        }
        .dashboard-welcome p {
            max-width: 660px;
            margin: 0.45rem 0 0;
            color: #526985;
            font-size: 0.9rem;
            line-height: 1.5;
        }
        .welcome-wave {
            color: #e5a63b;
        }
        .dashboard-welcome-art {
            width: min(28%, 230px);
            min-width: 140px;
            align-self: stretch;
        }
        .dashboard-profile-label {
            color: #65738a;
            font-size: 0.78rem;
        }
        .st-key-home-purpose-discover {
            border-color: #cbd9ff;
            border-top: 3px solid #4778ed;
            background: linear-gradient(155deg, #edf3ff 0%, #fff 82%);
        }
        .st-key-home-purpose-discover [data-testid="stMarkdownContainer"] h4 {
            color: #315fc5;
        }
        .st-key-home-purpose-grow {
            border-color: #c6ead8;
            border-top: 3px solid #35a87b;
            background: linear-gradient(155deg, #eaf8f0 0%, #fff 82%);
        }
        .st-key-home-purpose-grow [data-testid="stMarkdownContainer"] h4 {
            color: #20845d;
        }
        .st-key-home-purpose-act {
            border-color: #d9ceff;
            border-top: 3px solid #8664df;
            background: linear-gradient(155deg, #f1edff 0%, #fff 82%);
        }
        .st-key-home-purpose-act [data-testid="stMarkdownContainer"] h4 {
            color: #6948bd;
        }
        .career-hero {
            position: relative;
            overflow: hidden;
            min-height: 390px;
            padding: 2.25rem;
            border: 1px solid rgba(255, 255, 255, 0.72);
            border-radius: 26px;
            background:
                radial-gradient(ellipse at 83% 16%, rgba(175, 192, 255, 0.48), transparent 34%),
                linear-gradient(145deg, #f0f3ff 0%, #f8f6ff 54%, #eff8f7 100%);
            box-shadow: 0 18px 46px rgba(35, 48, 87, 0.09);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .career-hero::after {
            position: absolute;
            right: -70px;
            bottom: -116px;
            width: 280px;
            height: 280px;
            border: 1px solid rgba(85, 117, 247, 0.12);
            border-radius: 50%;
            content: "";
            box-shadow: 0 0 0 34px rgba(85, 117, 247, 0.035), 0 0 0 68px rgba(85, 117, 247, 0.025);
            pointer-events: none;
        }
        .hero-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            margin-bottom: 1.25rem;
            color: #4f64c9;
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.11em;
        }
        .hero-eyebrow span {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #6c83f7;
            box-shadow: 0 0 0 4px rgba(108, 131, 247, 0.13);
        }
        .career-hero h1 {
            max-width: 600px;
            margin: 0;
            color: #3449a7;
            background-image: linear-gradient(105deg, #173caa 0%, #326fec 55%, #178aa9 100%);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: clamp(2.5rem, 4.2vw, 4.3rem);
            font-weight: 760;
            line-height: 1.04;
            letter-spacing: -0.065em;
        }
        .career-hero h1 span {
            background-image: linear-gradient(95deg, #4278ef 0%, #7755df 52%, #d34f94 100%);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 4px 12px rgba(105, 100, 213, 0.15));
        }
        .career-hero-copy {
            max-width: 440px;
            margin: 1.2rem 0 0;
            color: #5f687e;
            font-size: 1.04rem;
            line-height: 1.75;
        }
        .st-key-auth-card {
            padding: 1.4rem;
            border: 1px solid #e7eaf2;
            border-radius: 18px;
            background: #fff;
            box-shadow: 0 14px 36px rgba(27, 37, 68, 0.075);
        }
        .st-key-auth-welcome {
            margin: 0.8rem 0 1.15rem;
        }
        .st-key-auth-welcome h1 {
            margin: 0;
            color: #17375f;
            font-size: 2.8rem;
            font-weight: 740;
            line-height: 1.08;
            letter-spacing: 0;
        }
        .auth-welcome-kicker {
            margin: 0 0 0.35rem;
            color: #3975c7;
            font-size: 0.68rem;
            font-weight: 750;
            letter-spacing: 0.1em;
        }
        .st-key-auth-welcome [data-testid="stCaptionContainer"] p {
            color: #65738a;
            font-size: 0.9rem;
            line-height: 1.5;
            letter-spacing: 0;
        }
        .hero-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1.5rem;
        }
        .hero-tags span {
            padding: 0.46rem 0.72rem;
            border: 1px solid rgba(93, 111, 191, 0.13);
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.72);
            color: #535e7b;
            font-size: 0.78rem;
            font-weight: 600;
        }
        @media (max-width: 700px) {
            .block-container {
                padding-top: 1rem;
            }
            .workspace-hero {
                padding: 1.35rem;
            }
            .dashboard-welcome {
                min-height: 118px;
                padding: 1rem;
            }
            .dashboard-welcome-art {
                width: 30%;
                min-width: 95px;
                opacity: 0.68;
            }
            .career-hero {
                min-height: 0;
                padding: 1.65rem;
            }
            .career-hero h1 {
                font-size: 2.65rem;
            }
        }
    </style>
    """.replace("__AUTH_BACKGROUND_STYLE__", auth_background_style)
)

st.session_state.setdefault("account", None)
st.session_state.setdefault("auth_mode", "Create account")


def render_auth_page() -> None:
    """Render the existing registration and sign-in experience."""
    intro, auth_column = st.columns([1.15, 0.85], gap="large")
    with intro:
        st.html(
            """
            <section class="career-hero" aria-label="Personalized career guidance">
                <div class="hero-eyebrow"><span></span> YOUR NEXT CHAPTER STARTS HERE</div>
                <h1>Make your next move <span>your best one.</span></h1>
                <p class="career-hero-copy">
                    Find career paths that connect what you can do with what you love
                    and where you want to go.
                </p>
                <div class="hero-tags" aria-label="Career guidance features">
                    <span>Personalized paths</span>
                    <span>Practical learning</span>
                    <span>Built around you</span>
                </div>
            </section>
            """
        )

    with auth_column:
        with st.container(border=True, key="auth-card"):
            st.caption("YOUR CAREER WORKSPACE")
            st.segmented_control(
                "Account access",
                ["Create account", "Sign in"],
                key="auth_mode",
                label_visibility="collapsed",
                width="stretch",
            )

            if st.session_state.auth_mode == "Sign in":
                with st.container(key="auth-welcome"):
                    st.html('<p class="auth-welcome-kicker">GOOD TO SEE YOU AGAIN</p>')
                    st.title("Welcome")
                    st.caption("Sign in to continue to your career workspace.")
            else:
                st.subheader("Start with your strengths")
                st.caption("Create your account or sign in to pick up where you left off.")

            if st.session_state.auth_mode == "Create account":
                with st.form("register_form", clear_on_submit=False):
                    full_name = st.text_input("Full name", placeholder="e.g. Alex Morgan")
                    email = st.text_input("Email address", placeholder="you@example.com")
                    password = st.text_input(
                        "Password",
                        type="password",
                        placeholder="At least 8 characters",
                    )
                    confirm_password = st.text_input(
                        "Confirm password",
                        type="password",
                    )
                    registration_submitted = st.form_submit_button(
                        "Create account",
                        type="primary",
                        width="stretch",
                    )

                if registration_submitted:
                    try:
                        api_client.register_account(
                            full_name,
                            email,
                            password,
                            confirm_password,
                        )
                    except CareerAPIError as error:
                        st.error(str(error))
                    else:
                        st.success("Account created. You can now sign in.")

            else:
                with st.form("login_form", clear_on_submit=False, border=False):
                    login_email = st.text_input(
                        "Registered email address",
                        placeholder="you@example.com",
                    )
                    login_password = st.text_input("Password", type="password")
                    login_submitted = st.form_submit_button(
                        "Sign in",
                        type="primary",
                        width="stretch",
                    )

                if login_submitted:
                    try:
                        account = api_client.authenticate(login_email, login_password)
                    except CareerAPIError as error:
                        st.error(str(error))
                    else:
                        if account:
                            st.session_state.account = account
                            st.rerun()
                        st.error("Email or password is incorrect.")

            st.caption("Your password is securely stored as a salted cryptographic hash.")


def signed_in_account() -> dict[str, str]:
    """Return the authenticated account for the currently selected page."""
    account = st.session_state.get("account")
    if not account:
        st.error("Your session has ended. Please sign in again.")
        st.stop()
    return account


def render_logout_page() -> None:
    """End the current session and return to the sign-in page."""
    try:
        api_client.logout()
    except CareerAPIError:
        api_client.clear_session()
    st.session_state.account = None
    st.session_state.pop("career_chat_history", None)
    st.session_state.pop("career_page_links", None)
    st.rerun()


logo_path = Path(__file__).with_name("assets") / "careerai-logo.svg"
st.logo(str(logo_path), size="large", icon_image=str(logo_path))

if st.session_state.account:
    account = signed_in_account()
    with st.sidebar:
        st.caption(f"Signed in as\n{account['email']}")

    pages = [
        st.Page(
            lambda: render_home_page(signed_in_account()),
            title="Home",
            icon=":material/home:",
            default=True,
        ),
        st.Page(
            lambda: render_profile_page(signed_in_account()),
            title="Profile",
            icon=":material/person:",
            url_path="profile",
        ),
        st.Page(
            lambda: render_recommendations_page(signed_in_account()),
            title="Recommendations",
            icon=":material/auto_awesome:",
            url_path="recommendations",
        ),
        st.Page(
            lambda: render_learning_page(signed_in_account()),
            title="Learning roadmap",
            icon=":material/route:",
            url_path="learning-roadmap",
        ),
        st.Page(
            lambda: render_skill_gaps_page(signed_in_account()),
            title="Skill gap analysis",
            icon=":material/analytics:",
            url_path="skill-gap-analysis",
        ),
        st.Page(
            lambda: render_jobs_page(signed_in_account()),
            title="Job opportunities",
            icon=":material/work:",
            url_path="job-opportunities",
        ),
        st.Page(
            lambda: render_chat_page(signed_in_account()),
            title="AI Career Guide",
            icon=":material/support_agent:",
            url_path="ai-career-guide",
        ),
        st.Page(
            render_logout_page,
            title="Logout",
            icon=":material/logout:",
            url_path="logout",
        ),
    ]
    st.session_state["career_page_links"] = {
        page.title: page for page in pages
    }
    selected_page = st.navigation(pages, position="sidebar", expanded=True)
else:
    selected_page = st.navigation(
        [st.Page(render_auth_page, title="Sign in", icon=":material/login:")],
        position="hidden",
    )

selected_page.run()

with st.container(key="account-topbar"):
    if st.session_state.account:
        account = signed_in_account()
        with st.popover(
            account["full_name"].split()[0],
            icon=":material/person:",
            help="Account options",
            width="content",
        ):
            st.caption(account["email"])
            st.page_link(
                st.session_state["career_page_links"]["Profile"],
                label="Edit profile",
                icon=":material/edit:",
            )
            st.page_link(
                st.session_state["career_page_links"]["Logout"],
                label="Sign out",
                icon=":material/logout:",
            )

if st.session_state.account and selected_page.title != "AI Career Guide":
    with st.container(key="career-guide-shortcut"):
        if st.session_state.get("career_guide_open", False):
            render_career_guide_panel(signed_in_account())
        if st.button(
            "Chat",
            key="career-guide-toggle",
            type="primary",
            help="Open AI Career Guide",
            width=68,
        ):
            st.session_state["career_guide_open"] = not st.session_state.get(
                "career_guide_open", False
            )
            st.rerun()

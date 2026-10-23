"""Signed-in dashboard, profile, recommendations, learning, jobs, and chat pages."""

from __future__ import annotations

import json
import hashlib
import os
import re
from html import escape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Mapping

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

import api_client
from api_client import (
    CareerAPIError,
    answer_question,
    assistant_status,
    get_student_profile,
    save_student_profile,
)
from recommendations import (
    CAREER_PATHS,
    CareerMatch,
    SkillDevelopmentRecommendation,
    indeed_job_search_url,
    job_search_url,
    learning_resource_url,
    recommend_careers,
    recommend_skill_development,
)

EDUCATION_LEVELS = [
    "Diploma",
    "Undergraduate",
    "Postgraduate",
    "Other",
]
SKILL_OPTIONS = [
    "Python",
    "Java",
    "JavaScript",
    "SQL",
    "Data analysis",
    "Machine learning",
    "Web development",
    "Communication",
    "Problem solving",
    "Project management",
    "UI/UX design",
    "Cloud computing",
    "Cybersecurity",
    "Research",
]
SKILL_OPTIONS = sorted(
    set(SKILL_OPTIONS).union(
        skill for career in CAREER_PATHS for skill in career.skills
    )
)
INTERESTED_ROLE_OPTIONS = [career.title for career in CAREER_PATHS]
INTEREST_OPTIONS = [
    "Artificial intelligence",
    "Data and analytics",
    "Software development",
    "Design and creativity",
    "Business and entrepreneurship",
    "Healthcare",
    "Education",
    "Finance",
    "Science and research",
    "Social impact",
    "Cybersecurity",
    "Cloud technology",
]

FOLLOW_UP_PATTERNS = (
    r"^why\??$",
    r"^why is that\??$",
    r"^explain more\.?$",
    r"^tell me more\.?$",
    r"^what should i learn first\??$",
    r"^which one should i learn first\??$",
    r"^can you explain that\??$",
    r"^give me an example\.?$",
)
GREETING_PATTERN = re.compile(
    r"^(hi|hi there|hello|hello there|hey|good morning|good afternoon|good evening|"
    r"how are you|howdy)[!.?\s]*$",
    re.IGNORECASE,
)
COMPARISON_PATTERN = re.compile(
    r"\b(compare|comparison|difference|differences|versus|vs\.?)\b",
    re.IGNORECASE,
)
CAREER_QUESTION_PATTERN = re.compile(
    r"\b(career|careers|role|roles|job path|which path)\b", re.IGNORECASE
)
SKILL_QUESTION_PATTERN = re.compile(
    r"\b(skills?|learn|learning|improve|improvement|gap|roadmap|course)\b",
    re.IGNORECASE,
)
JOB_QUESTION_PATTERN = re.compile(
    r"\b(get a job|find a job|job|jobs|hired|hiring|interview|resume|"
    r"cv\b|apply|application|opportunit)\b",
    re.IGNORECASE,
)
PROJECT_QUESTION_PATTERN = re.compile(
    r"\b(project|projects|portfolio|build)\b", re.IGNORECASE
)
SQL_QUESTION_PATTERN = re.compile(
    r"\b(what is|explain|define|meaning of)\b.*\bsql\b|\bsql\b.*\?",
    re.IGNORECASE,
)
FOLLOW_UP_LOOKUP = tuple(re.compile(pattern, re.IGNORECASE) for pattern in FOLLOW_UP_PATTERNS)


def is_profile_complete(profile: Mapping[str, object] | None) -> bool:
    """Check that the required saved profile fields are present and usable."""
    if not profile:
        return False

    required_text = ("education_level", "field_of_study", "career_goal")
    if any(not str(profile.get(field, "")).strip() for field in required_text):
        return False
    if not isinstance(profile.get("skills"), list) or not profile["skills"]:
        return False
    return True


def profile_completion(profile: Mapping[str, object] | None) -> tuple[int, list[str]]:
    """Return completion percentage and required details still missing."""
    required_fields = (
        ("education_level", "Education level"),
        ("field_of_study", "Field of study"),
        ("skills", "Skills"),
        ("career_goal", "Career goal"),
    )
    missing = []
    for field, label in required_fields:
        value = profile.get(field) if profile else None
        if isinstance(value, (list, tuple, set)):
            populated = bool(value)
        else:
            populated = bool(str(value or "").strip())
        if not populated:
            missing.append(label)
    percentage = round(
        100 * (len(required_fields) - len(missing)) / len(required_fields)
    )
    return percentage, missing


def account_profile(account: Mapping[str, str]) -> dict[str, object] | None:
    """Load the signed-in student's profile from the existing SQLite database."""
    return get_student_profile(account["id"])


def page_link_target(title: str):
    """Read a page target from the current student's navigation session."""
    page_links = st.session_state["career_page_links"]
    if title in page_links:
        return page_links[title]

    legacy_title = {
        "AI Career Guide": "Chat assistant",
        "Chat assistant": "AI Career Guide",
    }.get(title)
    if legacy_title and legacy_title in page_links:
        return page_links[legacy_title]

    raise KeyError(title)


def page_header(title: str, subtitle: str) -> None:
    st.html(
        f"""
        <header class="workspace-hero">
            <div class="workspace-eyebrow">CAREERAI &nbsp; / &nbsp; STUDENT WORKSPACE</div>
            <h1>{escape(title)}</h1>
            <p>{escape(subtitle)}</p>
        </header>
        """
    )


def profile_incomplete_notice(profile_page) -> None:
    st.info(
        "Complete your student profile to get career suggestions based on your "
        "skills, education, and goals."
    )
    st.page_link(
        profile_page,
        label="Complete your profile",
        icon=":material/person_edit:",
    )


def render_metric(
    label: str,
    value: str,
    key: str,
    help_text: str,
    destination: str | None = None,
) -> None:
    with st.container(border=True, key=f"metric-{key}"):
        st.metric(label, value, help=help_text)
        if destination and st.button(
            f"Open {label.lower()}",
            key=f"open-{key}",
            help=f"Open {label.lower()}",
            width="stretch",
        ):
            st.switch_page(page_link_target(destination))


def render_profile_completion(profile: Mapping[str, object] | None) -> None:
    percentage, missing = profile_completion(profile)
    with st.container(border=True, key="profile-completion"):
        st.markdown("#### Profile completion")
        st.progress(percentage / 100, text=f"{percentage}% complete")
        if missing:
            st.caption(
                "Next, add: "
                + ", ".join(missing)
                + ". Role preferences are optional."
            )
            st.page_link(
                page_link_target("Profile"),
                label="Complete your profile",
                icon=":material/person_edit:",
            )
        else:
            st.caption(
                "Your essential profile details are ready to personalize career "
                "matches. Role preferences are optional."
            )


def render_match_explanation(match: CareerMatch) -> None:
    with st.expander("Why this match?"):
        if match.matched_skills:
            st.markdown("**Skills in your profile**")
            st.write(", ".join(match.matched_skills))
        if match.matched_interests:
            st.markdown("**Interests in your profile**")
            st.write(", ".join(match.matched_interests))
        if match.matched_roles:
            st.markdown("**Role preferences**")
            st.write(", ".join(match.matched_roles))
        if match.matched_context:
            st.markdown("**Related terms in your field or career goal**")
            st.write(", ".join(match.matched_context))
        if not (
            match.matched_skills
            or match.matched_interests
            or match.matched_roles
            or match.matched_context
        ):
            st.write(
                "No direct profile signals matched this role, so treat it as a "
                "general option to explore."
            )
        st.caption(
            "The percentage compares profile signals with this app's career catalog. "
            "It is not a prediction of job success or career suitability."
        )


def render_match_card(
    match: CareerMatch,
    *,
    compact: bool = False,
    rank: int | None = None,
) -> None:
    container_options = {"border": True}
    if not compact and rank is not None:
        container_options["key"] = f"recommendation-card-{rank}"

    with st.container(**container_options):
        if compact:
            title_column, score_column = st.columns([0.76, 0.24], gap="small")
            with title_column:
                st.markdown(f"#### {match.career.title}")
            with score_column:
                st.markdown(
                    f":blue-badge[:material/auto_awesome: {match.fit_score}% match]"
                )
            st.caption(match.career.description)
            matched = [
                *(f"Skill: {skill}" for skill in match.matched_skills),
                *(f"Interest: {interest}" for interest in match.matched_interests),
                *(f"Interested role: {role}" for role in match.matched_roles),
            ]
            if matched:
                st.caption(" · ".join(matched[:3]))
            st.progress(match.fit_score / 100)
            render_match_explanation(match)
            return

        title_column, score_column = st.columns([0.74, 0.26], gap="small")
        with title_column:
            if isinstance(rank, int):
                st.caption(f"CAREER PATH {rank:02d}")
            st.markdown(f"### {match.career.title}")
        with score_column:
            st.markdown(
                f":blue-badge[:material/auto_awesome: {match.fit_score}% profile match]"
            )
        st.progress(match.fit_score / 100, text=f"{match.fit_score}% profile signal match")
        st.write(match.career.description)
        if (
            match.matched_skills
            or match.matched_interests
            or match.matched_roles
            or match.matched_context
        ):
            matched = [
                *(f"Skill: {skill}" for skill in match.matched_skills),
                *(f"Interest: {interest}" for interest in match.matched_interests),
                *(f"Interested role: {role}" for role in match.matched_roles),
                *(f"Goal/field: {term}" for term in match.matched_context),
            ]
            st.markdown("**Your matching profile signals**")
            st.markdown(" ".join(f":blue-badge[{escape(signal)}]" for signal in matched[:5]))
        else:
            st.caption(
                "General starting point: no direct profile signal was found in the "
                "current career catalog."
            )

        if match.missing_skills:
            st.markdown("**Skills you could build next**")
            st.markdown(
                " ".join(
                    f":gray-badge[{escape(skill)}]"
                    for skill in match.missing_skills[:5]
                )
            )
        else:
            st.success("Your profile already includes this path's core catalog skills.")

        action_columns = st.columns(2, gap="small")
        with action_columns[0]:
            st.page_link(
                page_link_target("Learning roadmap"),
                label="Explore learning roadmap",
                icon=":material/route:",
            )
        with action_columns[1]:
            st.page_link(
                page_link_target("Skill gap analysis"),
                label="View skill gaps",
                icon=":material/analytics:",
            )
        render_match_explanation(match)


def render_home_introduction() -> None:
    st.subheader("What you can do here")
    st.write(
        "CareerAI helps you turn your skills, interests, and goals into career "
        "directions to explore, with practical ideas for what to learn and do next."
    )
    cards = st.columns(3, gap="medium")
    steps = [
        (
            "home-purpose-discover",
            "01  ·  FIND YOUR DIRECTION",
            "Explore careers that fit",
            "See career suggestions based on the skills, interests, education, and "
            "goals you add to your profile.",
        ),
        (
            "home-purpose-grow",
            "02  ·  BUILD YOUR SKILLS",
            "Know what to learn next",
            "Review skills to develop, suggested learning topics, and project ideas "
            "to help you explore a role.",
        ),
        (
            "home-purpose-act",
            "03  ·  TAKE A NEXT STEP",
            "Move forward with a plan",
            "Explore job-search links and ask the career assistant questions as you "
            "consider your next step.",
        ),
    ]
    for column, (key, eyebrow, title, description) in zip(cards, steps):
        with column:
            with st.container(border=True, key=key):
                st.caption(eyebrow)
                st.markdown(f"#### {title}")
                st.write(description)
    st.caption(
        "Career suggestions are starting points based on this app's role catalog, "
        "not a prediction of job success or a list of verified vacancies."
    )


def _render_dashboard_assistant(
    profile: Mapping[str, object],
    matches: list[CareerMatch],
    top_match: CareerMatch | None,
) -> None:
    st.subheader("Career guidance assistant")
    history = st.session_state.setdefault("career_chat_history", [])
    with st.container(border=True, key="dashboard-assistant"):
        if history:
            with st.container(height=190, border=False):
                for message in history[-4:]:
                    with st.chat_message(message["role"]):
                        st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(
                    "Hi! Ask about your career matches, skills, or learning next steps."
                )

        role_title = top_match.career.title if top_match else "a career path"
        quick_prompts = (
            ("Career options", "What career options fit my profile?"),
            ("Learning plan", f"Suggest a learning plan for {role_title}."),
            ("Skill advice", "How can I improve my skills?"),
        )
        prompt_columns = st.columns(len(quick_prompts), gap="small")
        for index, (column, (label, question)) in enumerate(
            zip(prompt_columns, quick_prompts)
        ):
            with column:
                if st.button(
                    label,
                    key=f"dashboard-guide-prompt-{index}",
                    width="stretch",
                ):
                    _submit_career_question(question, profile, matches, history)
                    st.rerun()

        with st.form("dashboard-career-guide-form", clear_on_submit=True):
            question = st.text_input(
                "Ask the career guide",
                placeholder="Type your message...",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(
                "Send",
                type="primary",
                icon=":material/send:",
                width="stretch",
            )
        if submitted and question.strip():
            _submit_career_question(question.strip(), profile, matches, history)
            st.rerun()


def render_home_page(account: Mapping[str, str]) -> None:
    profile = account_profile(account)
    first_name = account["full_name"].split()[0]
    st.html(
        f"""
        <header class="dashboard-welcome">
            <div class="dashboard-welcome-copy">
                <div class="dashboard-kicker">
                    YOUR SKILLS + INTERESTS + GOALS &nbsp; → &nbsp; YOUR NEXT STEP
                </div>
                <h1><span class="welcome-wave">✦</span> Hello, {escape(first_name)}!</h1>
                <p>Explore career directions and discover a practical next step based on your profile.</p>
            </div>
            <svg class="dashboard-welcome-art" viewBox="0 0 250 130" fill="none" aria-hidden="true">
                <circle cx="191" cy="65" r="60" fill="#fff" fill-opacity=".46"/>
                <circle cx="191" cy="65" r="45" stroke="#659BEA" stroke-opacity=".22"/>
                <path d="M111 110c20-1 26-12 40-17 17-6 20-12 27-23 8-13 20-14 29-21 9-7 10-16 22-23" stroke="#4387E9" stroke-width="4" stroke-linecap="round"/>
                <circle cx="151" cy="93" r="6" fill="#55B99A" stroke="white" stroke-width="3"/>
                <circle cx="207" cy="49" r="7" fill="#6C72E8" stroke="white" stroke-width="3"/>
                <rect x="138" y="18" width="74" height="44" rx="12" fill="white" fill-opacity=".92" stroke="#DCE7F8"/>
                <rect x="149" y="29" width="24" height="23" rx="7" fill="#E7F0FF"/>
                <path d="M154 46v-5l4-4 4 3 6-7" stroke="#3477EF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <rect x="180" y="31" width="21" height="4" rx="2" fill="#5680D8"/>
                <rect x="180" y="40" width="16" height="4" rx="2" fill="#B5C5E2"/>
                <path d="m225 17 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.5 2.9 1.1-6.1-4.5-4.3 6.2-.9L225 17Z" fill="#EDA94A"/>
                <circle cx="110" cy="36" r="4" fill="#4DB79A"/>
            </svg>
        </header>
        """
    )

    profile_ready = is_profile_complete(profile)
    profile_data = profile or {}
    matches = api_client.recommend_careers(profile, limit=5) if profile_ready else []
    top_match = matches[0] if matches else None
    experience_years = int(profile_data.get("experience_years", 0))
    learning_topic_count = len(
        {
            topic
            for match in matches
            for topic in match.career.learning_topics
        }
    )
    columns = st.columns(4, gap="small")
    metric_values = [
        (
            "Career matches",
            str(len(matches)) if profile_ready else "—",
            "career-matches",
            "Career suggestions ranked from the skills and interests in your profile.",
        ),
        (
            "Profile skills",
            str(len(profile_data.get("skills", []))),
            "profile-skills",
            "Skills you have added to your profile.",
        ),
        (
            "Learning topics",
            str(learning_topic_count) if profile_ready else "—",
            "learning-topics",
            "Distinct learning topics listed across the career suggestions shown below.",
        ),
        (
            "Skills to explore",
            str(len(top_match.missing_skills)) if top_match else "—",
            "skill-gaps",
            "Catalog skills not yet in your profile for the top career match.",
        ),
    ]
    for column, (label, value, key, help_text) in zip(columns, metric_values):
        with column:
            render_metric(
                label,
                value,
                key,
                help_text,
                destination="Recommendations" if key == "career-matches" else None,
            )

    left_column, right_column = st.columns([1.25, 0.95], gap="large")
    with left_column:
        section_title, section_action = st.columns(
            [0.72, 0.28],
            vertical_alignment="center",
        )
        with section_title:
            st.subheader("Top career recommendations")
        with section_action:
            st.page_link(
                page_link_target("Recommendations"),
                label="View all",
                icon=":material/arrow_forward:",
            )
        st.caption(
            "Explore role ideas ranked from your profile. These are suggestions, "
            "not hiring predictions."
        )
        if matches:
            for match in matches:
                render_match_card(match, compact=True)
        else:
            with st.container(border=True, key="dashboard-career-empty"):
                st.markdown("**Your career matches will appear here**")
                st.caption(
                    "Add your education, skills, and career goal to get suggestions "
                    "based on your profile."
                )
                st.page_link(
                    page_link_target("Profile"),
                    label="Complete your profile",
                    icon=":material/person_edit:",
                )

    with right_column:
        st.subheader("Your learning roadmap")
        if top_match:
            with st.container(border=True, key="dashboard-roadmap"):
                st.caption(f"STARTING WITH YOUR TOP MATCH · {top_match.fit_score}% PROFILE MATCH")
                st.markdown(f"#### {top_match.career.title}")
                for step, topic in enumerate(top_match.career.learning_topics, start=1):
                    step_column, topic_column = st.columns([0.12, 0.88], gap="small")
                    with step_column:
                        st.markdown(f"**{step:02d}**")
                    with topic_column:
                        st.markdown(f"[{topic}]({learning_resource_url(topic)})")
                st.markdown("**Try a portfolio project**")
                st.write(top_match.career.projects[0])
                st.caption(
                    "Learning links open course-catalog searches; review details "
                    "before enrolling."
                )
        else:
            with st.container(border=True, key="dashboard-roadmap"):
                st.markdown("**Your personalized roadmap will appear here**")
                st.caption("Complete your profile to get relevant learning steps.")
        st.page_link(
            page_link_target("Learning roadmap"),
            label="Explore learning roadmaps",
            icon=":material/route:",
        )

        _render_dashboard_assistant(profile, matches, top_match)
        st.page_link(
            page_link_target("AI Career Guide"),
            label="Open full AI Career Guide",
            icon=":material/support_agent:",
        )

    st.subheader("Your profile snapshot")
    with st.container(border=True, key="dashboard-profile"):
        profile_heading, profile_action = st.columns(
            [0.8, 0.2],
            vertical_alignment="center",
        )
        with profile_heading:
            field_of_study = profile_data.get("field_of_study", "")
            education_level = profile_data.get("education_level", "")
            profile_title = " · ".join(
                value for value in (str(field_of_study), str(education_level)) if value
            ) or "Your profile details"
            st.markdown(f"#### {profile_title}")
        with profile_action:
            st.page_link(
                page_link_target("Profile"),
                label="Edit profile",
                icon=":material/edit:",
            )
        experience_label = (
            "Fresher"
            if experience_years == 0
            else f"{experience_years} years of experience"
        )
        st.caption(
            f"{experience_label} · {profile_data.get('preferred_location', 'Remote')} "
            f"· Goal: {profile_data.get('career_goal') or 'Add a career goal'}"
        )
        skill_column, interest_column = st.columns(2, gap="large")
        with skill_column:
            st.markdown("**Your skills**")
            st.markdown(
                " · ".join(profile_data.get("skills", [])) or "Add skills to your profile"
            )
        with interest_column:
            st.markdown("**Your interests**")
            st.markdown(
                " · ".join(profile_data.get("interests", []))
                or "Add interests to your profile"
            )
        if profile_data.get("interested_roles"):
            st.markdown("**Roles you’re interested in**")
            st.markdown(" · ".join(profile_data["interested_roles"]))
    st.caption(
        "Career matches come from this app's role catalog. Job links are live searches, "
        "not verified vacancies; check listings before sharing personal information."
    )


def render_profile_summary(profile: Mapping[str, object]) -> None:
    experience = int(profile.get("experience_years", 0))
    st.write(f"**Education:** {profile['education_level']}")
    st.write(f"**Field:** {profile['field_of_study']}")
    st.write(
        "**Experience:** "
        + ("Fresher" if experience == 0 else f"{experience} years")
    )
    st.write(f"**Location:** {profile.get('preferred_location', 'Remote')}")
    st.write("**Skills:** " + ", ".join(profile["skills"]))
    interested_roles = profile.get("interested_roles", [])
    if interested_roles:
        st.write("**Interested roles:** " + ", ".join(interested_roles))
    st.write(f"**Career goal:** {profile['career_goal']}")


def render_profile_page(account: Mapping[str, str]) -> None:
    profile = account_profile(account)
    current = profile or {}
    page_header(
        "Your profile",
        "Keep your education, skills, and goals up to date for relevant guidance.",
    )
    render_profile_completion(current)

    with st.form("student_profile_form"):
        education_level = st.selectbox(
            "Education level",
            EDUCATION_LEVELS,
            index=(
                EDUCATION_LEVELS.index(current["education_level"])
                if current.get("education_level") in EDUCATION_LEVELS
                else 0
            ),
        )
        field_of_study = st.text_input(
            "Field of study",
            value=str(current.get("field_of_study", "")),
            placeholder="e.g. Computer science",
        )
        skills = st.multiselect(
            "Skills",
            SKILL_OPTIONS,
            default=[
                skill for skill in current.get("skills", []) if skill in SKILL_OPTIONS
            ],
            help="Choose your current skills. Options include skills used across CareerAI's career catalog.",
        )
        interested_roles = st.multiselect(
            "Interested roles",
            INTERESTED_ROLE_OPTIONS,
            default=[
                role
                for role in current.get("interested_roles", [])
                if role in INTERESTED_ROLE_OPTIONS
            ],
            help="Choose roles you want CareerAI to prioritize in your recommendations.",
        )
        current_experience = int(current.get("experience_years", 0))
        experience_level = st.selectbox(
            "Experience",
            ["Fresher", "Experienced"],
            index=0 if current_experience == 0 else 1,
        )
        experience_years = 0
        if experience_level == "Experienced":
            experience_years = st.slider(
                "Years of experience",
                min_value=1,
                max_value=40,
                value=min(max(current_experience, 1), 40),
            )
        career_goal = st.text_area(
            "Career goal",
            value=str(current.get("career_goal", "")),
            placeholder="What kind of role or impact are you working toward?",
        )
        preferred_location = st.text_input(
            "Preferred job location",
            value=str(current.get("preferred_location", "Remote")),
            placeholder="e.g. Bengaluru, India or Remote",
        )
        submitted = st.form_submit_button(
            "Save profile",
            type="primary",
            width="stretch",
        )

    if submitted:
        if not field_of_study.strip():
            st.error("Enter your field of study.")
        elif not skills:
            st.error("Choose at least one skill.")
        elif not career_goal.strip():
            st.error("Describe your career goal.")
        else:
            saved_interests = current.get("interests", [])
            if not isinstance(saved_interests, list):
                saved_interests = []
            save_student_profile(
                account["id"],
                education_level,
                field_of_study,
                skills,
                saved_interests,
                experience_years,
                career_goal,
                preferred_location,
                interested_roles,
            )
            profile = account_profile(account)
            if is_profile_complete(profile):
                st.switch_page(page_link_target("Home"))
            st.success("Your student profile has been saved.")

    if profile:
        st.subheader("Profile overview")
        with st.container(border=True):
            render_profile_summary(profile)


def render_recommendations_page(account: Mapping[str, str]) -> None:
    profile = account_profile(account)
    page_header(
        "Career recommendations",
        "Explore role suggestions and the profile signals behind each match.",
    )
    if not is_profile_complete(profile):
        profile_incomplete_notice(page_link_target("Profile"))
        return

    matches = api_client.recommend_careers(profile)
    top_match = matches[0]
    skills_to_build = {
        skill for match in matches for skill in match.missing_skills
    }
    summary_columns = st.columns(3, gap="medium")
    with summary_columns[0]:
        with st.container(border=True, key="recommendations-summary-paths"):
            st.metric("Career paths to explore", len(matches))
            st.caption("Ranked using the profile details you provided.")
    with summary_columns[1]:
        with st.container(border=True, key="recommendations-summary-top-match"):
            st.metric("Top profile match", f"{top_match.fit_score}%")
            st.caption(top_match.career.title)
    with summary_columns[2]:
        with st.container(border=True, key="recommendations-summary-skills"):
            st.metric("Skills to build", len(skills_to_build))
            st.caption("Across the recommended career paths.")

    st.subheader("Career paths picked for you")
    st.caption(
        "Start with the strongest profile match, then compare the skills and interests "
        "behind each suggestion."
    )
    st.caption(
        "Fit scores are a weighted match against this app's role catalog. They are "
        "not predictions of job success or independently validated assessments."
    )
    if not any(match.fit_score for match in matches):
        st.info(
            "No direct catalog match was found for the selected profile signals. "
            "The roles below are general starting points, not personalized matches."
        )
    for rank, match in enumerate(matches, start=1):
        render_match_card(match, rank=rank)

    st.subheader("Make your next move")
    next_step_columns = st.columns(3, gap="medium")
    next_steps = (
        (
            "recommendation-next-skills",
            ":material/analytics:",
            "Close a skill gap",
            "See practical ways to build the skills needed for your recommended roles.",
            "Skill gap analysis",
            "View skill gaps",
        ),
        (
            "recommendation-next-learning",
            ":material/route:",
            "Plan your learning",
            "Follow a learning sequence and explore portfolio project ideas.",
            "Learning roadmap",
            "Open learning roadmap",
        ),
        (
            "recommendation-next-jobs",
            ":material/work:",
            "Explore opportunities",
            "Search for current role-related job listings based on your location.",
            "Job opportunities",
            "Explore job searches",
        ),
    )
    for column, (key, icon, title, description, destination, label) in zip(
        next_step_columns, next_steps
    ):
        with column:
            with st.container(border=True, key=key):
                st.markdown(f"#### {icon} {title}")
                st.write(description)
                st.page_link(
                    page_link_target(destination),
                    label=label,
                    icon=":material/arrow_forward:",
                )


def roadmap_stage(index: int, total: int) -> tuple[str, str]:
    if total == 1:
        return "LEARN", "Explore this topic"
    if index == 0:
        return "START", "Build your foundation"
    if index == total - 1:
        return "APPLY", "Put your learning into practice"
    return "BUILD", "Practice the key skills"


def render_roadmap_diagram(
    match: CareerMatch,
    roadmap: Mapping[str, object] | None = None,
) -> None:
    roadmap = roadmap or api_client.curated_roadmap(match)
    steps = roadmap["steps"]
    track_id = re.sub(r"[^a-z0-9]+", "-", match.career.title.lower()).strip("-")
    st.markdown("**Your step-by-step roadmap**")
    st.caption(
        "Personalized with AI from your profile."
        if roadmap["generated"]
        else "Follow the curated path from learning the basics to applying your skills."
    )

    with st.container(border=True, key=f"learning-track-{track_id}"):
        column_sizes = [
            1 if index % 2 == 0 else 0.16
            for index in range(max(len(steps) * 2 - 1, 1))
        ]
        columns = st.columns(
            column_sizes,
            vertical_alignment="center",
            gap="small",
        )
        for index, step in enumerate(steps):
            stage, _ = roadmap_stage(index, len(steps))
            topic = step["topic"]
            with columns[index * 2]:
                with st.container(
                    border=True,
                    key=f"roadmap-step-{index % 3}-{track_id}-{index}",
                ):
                    st.caption(f"STEP {index + 1:02d} · {stage}")
                    st.markdown(f"[{topic}]({learning_resource_url(topic)})")
                    st.caption(step["objective"])
            if index < len(steps) - 1:
                with columns[index * 2 + 1]:
                    with st.container(key=f"roadmap-arrow-{track_id}-{index}"):
                        st.markdown(":material/arrow_forward:")


def render_learning_page(account: Mapping[str, str]) -> None:
    profile = account_profile(account)
    page_header(
        "Learning roadmap",
        "A suggested learning sequence and project ideas for your profile-based role paths.",
    )
    if not is_profile_complete(profile):
        profile_incomplete_notice(page_link_target("Profile"))
        return

    profile_fingerprint = hashlib.sha256(
        json.dumps(profile, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    roadmap_cache = st.session_state.setdefault("learning_roadmap_cache", {})
    for match in api_client.recommend_careers(profile):
        track_id = re.sub(
            r"[^a-z0-9]+",
            "-",
            match.career.title.lower(),
        ).strip("-")
        cache_key = (account["id"], profile_fingerprint, match.career.title)
        if cache_key not in roadmap_cache:
            try:
                roadmap_cache[cache_key] = api_client.generate_roadmap(
                    match.career.title
                )
            except CareerAPIError as error:
                roadmap_cache[cache_key] = api_client.curated_roadmap(
                    match,
                    str(error),
                )
        roadmap = roadmap_cache[cache_key]
        with st.container(border=True, key=f"learning-career-{track_id}"):
            st.subheader(match.career.title)
            st.progress(
                match.fit_score / 100,
                text=f"{match.fit_score}% profile signal match",
            )
            render_roadmap_diagram(match, roadmap)
            if roadmap.get("api_error"):
                st.caption("AI roadmap unavailable; showing the curated roadmap instead.")
            st.markdown("**Portfolio projects**")
            for project in roadmap["projects"]:
                st.write(f"- {project}")
            st.caption(
                "Course links open catalog searches. Review course details, "
                "availability, and price before enrolling."
            )


def render_skill_improvement_flow(
    recommendation: SkillDevelopmentRecommendation,
    *,
    role_index: int,
    skill_index: int,
) -> None:
    skill_key = re.sub(
        r"[^a-z0-9]+",
        "-",
        recommendation.skill.lower(),
    ).strip("-")
    flow_key = f"{role_index}-{skill_index}-{skill_key}"
    steps = st.columns(3, vertical_alignment="top", gap="small")

    with steps[0]:
        with st.container(border=True, key=f"skill-flow-learn-{flow_key}"):
            st.caption("STEP 01 · LEARN →")
            st.markdown(f"**Build your foundation in {recommendation.skill}**")
            st.write(recommendation.role_relevance)
            st.link_button(
                "Explore learning resources",
                learning_resource_url(recommendation.learning_topic),
                width="stretch",
            )
    with steps[1]:
        with st.container(border=True, key=f"skill-flow-practice-{flow_key}"):
            st.caption("STEP 02 · PRACTICE →")
            st.markdown("**Try it in a small task**")
            st.write(recommendation.practice)
    with steps[2]:
        with st.container(border=True, key=f"skill-flow-show-{flow_key}"):
            st.caption("STEP 03 · SHOW YOUR PROGRESS")
            st.markdown("**Keep evidence of what you learned**")
            st.write(
                "Save your work in a portfolio and add a short note about your "
                "approach, result, and what you would improve next."
            )


def render_skill_gaps_page(account: Mapping[str, str]) -> None:
    profile = account_profile(account)
    page_header(
        "Skill gap analysis",
        "See which core role skills are not yet listed in your profile and how to practice them.",
    )
    if not is_profile_complete(profile):
        profile_incomplete_notice(page_link_target("Profile"))
        return

    st.info(
        "For each skill, follow the visual path: learn the fundamentals, practice "
        "with a focused task, then save evidence of your progress."
    )
    for role_index, match in enumerate(api_client.recommend_careers(profile)):
        color_index = role_index % 6
        with st.container(key=f"skill-gap-role-tone-{color_index}-{role_index}"):
            with st.expander(match.career.title, expanded=role_index == 0):
                st.caption(
                    f"{match.fit_score}% profile match | "
                    f"{len(match.missing_skills)} skills to build"
                )
                st.progress(
                    match.fit_score / 100,
                    text=f"{match.fit_score}% profile match",
                )
                if not match.missing_skills:
                    st.success(
                        "All catalog core skills for this role are in your profile."
                    )
                    continue
                for skill_index, recommendation in enumerate(
                    api_client.recommend_skill_development(match),
                    start=1,
                ):
                    render_skill_improvement_flow(
                        recommendation,
                        role_index=role_index,
                        skill_index=skill_index,
                    )


def render_jobs_page(account: Mapping[str, str]) -> None:
    profile = account_profile(account)
    page_header(
        "Job opportunities",
        "Search for roles related to your profile-based career suggestions.",
    )
    if not is_profile_complete(profile):
        profile_incomplete_notice(page_link_target("Profile"))
        return

    location = str(profile.get("preferred_location", "Remote")).strip() or "Remote"
    is_fresher = int(profile.get("experience_years", 0)) == 0
    st.info(
        "These links open live job searches, not a verified list of individual "
        "vacancies. Confirm the employer, listing, and application website before "
        "sharing personal information."
    )
    matches = api_client.recommend_careers(profile, limit=len(CAREER_PATHS))
    summary_columns = st.columns(3, gap="medium")
    with summary_columns[0]:
        with st.container(border=True, key="job-search-summary-roles"):
            st.metric("Career paths", len(matches))
            st.caption("Browse every role in the CareerAI catalog.")
    with summary_columns[1]:
        with st.container(border=True, key="job-search-summary-top-fit"):
            st.metric("Top profile match", f"{matches[0].fit_score}%")
            st.caption(matches[0].career.title)
    with summary_columns[2]:
        with st.container(border=True, key="job-search-summary-location"):
            st.metric("Search location", location)
            st.caption("Applied to each job search.")

    st.subheader("Explore jobs for your career paths")
    st.caption(
        "Roles are ordered by profile signals. Explore any path that interests you, "
        "including roles where you have skills to build."
    )
    for role_index, match in enumerate(matches):
        with st.container(
            border=True,
            key=f"job-opportunity-{role_index}",
        ):
            title_column, fit_column = st.columns(
                [0.72, 0.28],
                vertical_alignment="center",
            )
            with title_column:
                st.markdown(f"### {match.career.title}")
            with fit_column:
                st.markdown(f":blue-badge[{match.fit_score}% profile match]")
            st.write(match.career.description)
            st.progress(
                match.fit_score / 100,
                text="Profile signal match",
            )
            matched_signals = [
                *(f"Skill: {skill}" for skill in match.matched_skills),
                *(f"Interest: {interest}" for interest in match.matched_interests),
                *(f"Role: {role}" for role in match.matched_roles),
            ]
            if matched_signals:
                st.markdown("**Why it may fit**")
                st.markdown(
                    " ".join(
                        f":green-badge[{escape(signal)}]"
                        for signal in matched_signals[:4]
                    )
                )
            else:
                st.caption(
                    "This is an additional catalog path to explore; no direct "
                    "profile signals matched yet."
                )
            if match.missing_skills:
                st.caption(
                    "Skills to build: " + ", ".join(match.missing_skills[:5])
                )
            search_columns = st.columns(2, gap="small")
            with search_columns[0]:
                st.link_button(
                    "Search on LinkedIn",
                    job_search_url(match.career.title, location, is_fresher),
                    type="primary",
                    width="stretch",
                )
            with search_columns[1]:
                st.link_button(
                    "Search on Indeed",
                    indeed_job_search_url(match.career.title, location, is_fresher),
                    width="stretch",
                )


def career_assistant_answer(
    question: str,
    profile: Mapping[str, object] | None,
    matches: list[CareerMatch],
    history: list[Mapping[str, str]] | None = None,
) -> str:
    """Answer a question by intent, using conversation context where relevant."""
    history = history or []
    question = question.strip()
    if not question:
        return "Ask a career question and I’ll help with a relevant next step."

    if GREETING_PATTERN.fullmatch(question):
        first_name = _profile_value(profile, "full_name")
        greeting = f"Hi{', ' + first_name if first_name else ''}! "
        return (
            greeting
            + "I can help you explore careers, prioritize skills, plan a job search, "
            "understand concepts, or choose a project. What would you like to work on?"
        )

    follow_up_intent = _follow_up_intent(question)
    prior_question = _last_user_question(history)
    prior_context = " ".join(
        [prior_question, *(str(item.get("content", "")) for item in history[-4:])]
    )
    if follow_up_intent:
        if not prior_question:
            return (
                "I need a little context for that follow-up. Which career, skill, "
                "or project are you asking about?"
            )
        effective_question = prior_question
        if follow_up_intent == "skills":
            contextual_role = (
                _named_career(prior_question, matches)
                or _last_named_career_in_history(history, matches)
                or (matches[0].career.title if matches else None)
            )
            effective_question = "Which skills should I learn first for " + (
                contextual_role
                or "my recommended career"
            ) + "?"
        elif follow_up_intent == "why":
            prior_intent = _intent_for_question(prior_question)
            if prior_intent == "career":
                role = _named_career(prior_question, matches) or (
                    matches[0].career.title if matches else None
                )
                if role:
                    match = _match_by_title(role, matches)
                    return _career_detail(match)
                return _career_reasons(prior_question, profile, matches)
            if prior_intent == "compare":
                return _comparison_detail(prior_question, matches)
            if prior_intent == "project":
                role = _named_career(prior_question, matches) or _named_career(
                    prior_context,
                    matches,
                )
                if role:
                    match = _match_by_title(role, matches)
                    return (
                        f"A {role} project is useful because it gives you practice "
                        f"with the role's work and evidence to discuss in interviews. "
                        f"For example: {match.career.projects[0]}"
                    )
            if prior_intent == "skills":
                target_role = (
                    _named_career(prior_question, matches)
                    or _last_named_career_in_history(history, matches)
                )
                return _first_skill_improvement(
                    f"Which skills should I learn for {target_role}?"
                    if target_role
                    else prior_question,
                    profile,
                    matches,
                )
            previous_skill = _named_skill(prior_question)
            if previous_skill:
                careers_using_skill = [
                    career.title
                    for career in CAREER_PATHS
                    if previous_skill in career.skills
                ]
                relevance = (
                    f" In this app's catalog it is a core skill for "
                    f"{', '.join(careers_using_skill)}."
                    if careers_using_skill
                    else ""
                )
                return (
                    f"{previous_skill} is useful because it helps you "
                    f"{_skill_purpose(previous_skill)}.{relevance}"
                )
            if prior_intent == "job":
                return (
                    "The preparation steps build on each other: projects provide "
                    "evidence for your resume, practice helps you explain that work, "
                    "and checking listings carefully helps focus your applications."
                )
            subject = _named_career(prior_context, matches)
            if subject:
                match = _match_by_title(subject, matches)
                return (
                    f"{subject} fits the catalog signals "
                    f"{_match_signals(match)}. Those are the profile details this "
                    "suggestion uses; it is not a guarantee of career suitability."
                )
            return (
                "I based my previous reply on the details in your last question. "
                "Tell me which part you want me to explain and I’ll focus on it."
            )
        elif follow_up_intent == "explain":
            prior_intent = _intent_for_question(prior_question)
            if prior_intent == "career":
                role = _named_career(prior_question, matches) or (
                    matches[0].career.title if matches else None
                )
                if role:
                    return _career_detail(_match_by_title(role, matches))
                return _career_reasons(prior_question, profile, matches)
            if prior_intent == "compare":
                return _comparison_detail(prior_question, matches)
            if prior_intent == "skills":
                target_role = (
                    _named_career(prior_question, matches)
                    or _last_named_career_in_history(history, matches)
                )
                return _first_skill_improvement(
                    f"Which skills should I learn for {target_role}?"
                    if target_role
                    else prior_question,
                    profile,
                    matches,
                )
            if prior_intent == "project":
                return _expand_project_idea(prior_question, profile, matches)
            if prior_intent == "job":
                return (
                    "To make the job search manageable, complete one step at a time: "
                    "first choose a target role, then collect project evidence for "
                    "your resume, and finally prepare applications and interviews."
                )
            subject = _named_skill(prior_question) or _named_skill(prior_context)
            if subject:
                return _expand_skill_explanation(subject)
            role = _named_career(prior_question, matches) or _named_career(
                prior_context,
                matches,
            )
            if role:
                match = _match_by_title(role, matches)
                return _expand_role_explanation(match)
            return (
                "Which part should I explain more: a career option, a skill, "
                "or a project idea?"
            )
        question = effective_question

    if SQL_QUESTION_PATTERN.search(question):
        return _explain_skill("SQL")

    intent = _intent_for_question(question)
    if intent == "compare":
        return _compare_careers(question, matches, profile)

    if intent == "job":
        return _job_preparation_plan(profile)

    if intent == "project":
        return _project_ideas(question, profile, matches)

    if intent == "skills":
        return _prioritized_skill_plan(question, profile, matches)

    if intent == "career":
        return _career_reasons(question, profile, matches)

    skill = _named_skill(question)
    if skill:
        return _explain_skill(skill)

    career = _named_career(question, matches)
    if career:
        return _expand_role_explanation(_match_by_title(career, matches))

    if not is_profile_complete(profile):
        return (
            "I can explain general career concepts, but I need a completed student "
            "profile before I can tailor career guidance. Add your field of study, "
            "skills, interests, and career goal on the Profile page."
        )
    if not matches:
        return (
            "There are no role suggestions available right now. Review your profile "
            "or ask me a general career question."
        )

    return (
        "I can help with career choices, skill priorities, job preparation, projects, "
        "or simple explanations. Try asking about one of those, or name a specific "
        "career or skill."
    )


def _profile_value(
    profile: Mapping[str, object] | None,
    field: str,
) -> str:
    value = profile.get(field, "") if profile else ""
    return str(value).strip()


def _follow_up_intent(question: str) -> str | None:
    normalized = question.strip().casefold()
    if any(pattern.fullmatch(normalized) for pattern in FOLLOW_UP_LOOKUP):
        if "learn first" in normalized:
            return "skills"
        if normalized.startswith("why"):
            return "why"
        return "explain"
    return None


def _last_user_question(history: list[Mapping[str, str]]) -> str:
    return next(
        (
            str(message.get("content", ""))
            for message in reversed(history)
            if message.get("role") == "user"
        ),
        "",
    )


def _last_named_career_in_history(
    history: list[Mapping[str, str]],
    matches: list[CareerMatch],
) -> str | None:
    return next(
        (
            role
            for message in reversed(history)
            if message.get("role") == "user"
            if (role := _named_career(str(message.get("content", "")), matches))
        ),
        None,
    )


def _intent_for_question(question: str) -> str:
    if COMPARISON_PATTERN.search(question):
        return "compare"
    if JOB_QUESTION_PATTERN.search(question):
        return "job"
    if PROJECT_QUESTION_PATTERN.search(question):
        return "project"
    if SKILL_QUESTION_PATTERN.search(question):
        return "skills"
    if CAREER_QUESTION_PATTERN.search(question):
        return "career"
    return "general"


def _named_career(question: str, matches: list[CareerMatch]) -> str | None:
    normalized = question.casefold()
    return next(
        (
            match.career.title
            for match in sorted(matches, key=lambda item: len(item.career.title), reverse=True)
            if match.career.title.casefold() in normalized
        ),
        None,
    )


def _match_by_title(title: str, matches: list[CareerMatch]) -> CareerMatch:
    return next(match for match in matches if match.career.title == title)


def _named_skill(question: str) -> str | None:
    return next(iter(_named_skills(question)), None)


def _named_skills(question: str) -> list[str]:
    normalized = question.casefold()
    known_skills = sorted(
        {skill for career in CAREER_PATHS for skill in career.skills}
        | set(SKILL_OPTIONS),
        key=len,
        reverse=True,
    )
    return [
        skill
        for skill in known_skills
        if re.search(rf"(?<!\w){re.escape(skill.casefold())}(?!\w)", normalized)
    ]


def _compare_skills(question: str, skills: list[str], profile) -> str:
    first, second = skills[:2]
    saved_skills = {
        str(skill).casefold()
        for skill in profile.get("skills", [])
    } if profile and isinstance(profile.get("skills"), list) else set()
    first_roles = [
        career.title for career in CAREER_PATHS if first in career.skills
    ]
    second_roles = [
        career.title for career in CAREER_PATHS if second in career.skills
    ]
    first_status = "already in your profile" if first.casefold() in saved_skills else "not yet listed in your profile"
    second_status = "already in your profile" if second.casefold() in saved_skills else "not yet listed in your profile"
    return (
        f"**{first}** and **{second}** are different skills. "
        f"{_explain_skill(first)} Your profile has {first} {first_status}. "
        f"{_explain_skill(second)} Your profile has {second} {second_status}. "
        f"In this app's role catalog, {first} is used for "
        f"{', '.join(first_roles) if first_roles else 'no listed role'}; {second} is "
        f"used for {', '.join(second_roles) if second_roles else 'no listed role'}. "
        "Choose based on the kind of work you want to practice."
    )


def _match_signals(match: CareerMatch) -> str:
    signals = [
        *(f"your {skill} skill" for skill in match.matched_skills),
        *(f"your interest in {interest}" for interest in match.matched_interests),
        *(f"your interest in the {role} role" for role in match.matched_roles),
    ]
    if signals:
        return ", ".join(signals)
    return "no direct skill or interest match, so treat it as a general option"


def _career_reasons(
    question: str,
    profile: Mapping[str, object] | None,
    matches: list[CareerMatch],
) -> str:
    if not is_profile_complete(profile):
        return (
            "To suggest careers that fit you, complete your profile with your field "
            "of study, skills, interests, and career goal. I can still explain any "
            "specific role or skill in general."
        )
    if not matches:
        return "I don't have any role matches to compare right now. Review your profile and try again."

    requested_role = _named_career(question, matches)
    if requested_role:
        match = _match_by_title(requested_role, matches)
        signals = _match_signals(match)
        return (
            f"{requested_role} is a "
            f"{'stronger' if match.fit_score else 'general'} option in the current "
            f"catalog ({match.fit_score}% profile signal match). The reason is {signals}. "
            f"One way to explore it is {match.career.learning_topics[0]}. "
            "The score is only a profile-to-catalog comparison, not a prediction."
        )

    ranked = sorted(matches, key=lambda match: match.fit_score, reverse=True)
    if not any(match.fit_score for match in ranked):
        return (
            "Your profile does not directly match the core skills or interests in "
            "the current career catalog, so I can't claim a best-fit recommendation. "
            "As general options to explore: "
            + "; ".join(
                f"{match.career.title} — {match.career.description}"
                for match in ranked[:3]
            )
            + ". Add more profile detail to make these suggestions more relevant."
        )

    explanations = [
        f"{match.career.title} ({match.fit_score}%): {_match_signals(match)}"
        for match in ranked
        if match.fit_score > 0
    ]
    return (
        "Based on the profile information you saved, these career options have the "
        "strongest catalog matches: "
        + "; ".join(explanations[:3])
        + ". These scores compare profile signals with this app's role catalog; they "
        "are not guarantees. Explore the top option with a small project before deciding."
    )


def _prioritized_skill_plan(
    question: str,
    profile: Mapping[str, object] | None,
    matches: list[CareerMatch],
) -> str:
    if not is_profile_complete(profile):
        return (
            "Complete your profile first so I can separate skills you already have "
            "from skills to build. Add your current skills, interests, and a target "
            "career goal on the Profile page."
        )
    if not matches:
        return "There are no career paths to base a skill plan on yet. Review your profile and try again."

    target = _named_career(question, matches)
    ranked_matches = (
        [_match_by_title(target, matches)]
        if target
        else sorted(matches, key=lambda item: item.fit_score, reverse=True)
    )
    ranked_guidance: list[tuple[int, str, str, str]] = []
    skill_roles: dict[str, list[str]] = {}
    seen_skills = set()
    for match in ranked_matches:
        for item in recommend_skill_development(match):
            skill_roles.setdefault(item.skill, []).append(match.career.title)
            if item.skill not in seen_skills:
                ranked_guidance.append(
                    (
                        len(ranked_guidance),
                        item.skill,
                        item.practice,
                        match.career.title,
                    )
                )
                seen_skills.add(item.skill)

    if not ranked_guidance:
        role = ranked_matches[0].career.title
        return (
            f"Your profile already lists the catalog's core skills for {role}. "
            f"Build evidence with a project: {ranked_matches[0].career.projects[0]}"
        )

    intro_role = f" for {target}" if target else " for your strongest profile matches"
    steps = [
        f"{index}. **{skill}** (first relevant to {first_role}"
        f"{', also useful for ' + ', '.join(skill_roles[skill][1:]) if len(skill_roles[skill]) > 1 else ''}): "
        f"{practice}"
        for index, (_, skill, practice, first_role) in enumerate(
            ranked_guidance[:5],
            start=1,
        )
    ]
    return (
        f"Based on the skills in your profile, start with these missing skills{intro_role}:\n\n"
        + "\n\n".join(steps)
        + "\n\nBuild one skill at a time and add a small project to show what you can do."
    )


def _job_preparation_plan(profile: Mapping[str, object] | None) -> str:
    if not is_profile_complete(profile):
        return (
            "Start by completing your profile and choosing a target role. Then use "
            "this practical plan: learn the role's core skills, build two small "
            "projects, prepare a concise resume, practice explaining your work, and "
            "apply to suitable entry-level or internship roles."
        )
    matches = recommend_careers(profile)
    if not matches:
        return "Review your profile and choose a target role before starting a focused job search."
    role = matches[0].career.title
    known_skills = ", ".join(profile["skills"])
    years = int(profile.get("experience_years", 0))
    level = "fresher/entry-level" if years == 0 else f"with {years} years of experience"
    return (
        f"For a {role} search as a {level}, try this plan:\n\n"
        f"1. **Choose a target:** begin with {role}, the strongest catalog match in "
        "your profile (not a hiring prediction).\n"
        f"2. **Strengthen evidence:** your profile lists {known_skills}. Compare these "
        "with entry-level job descriptions and close the most common gaps.\n"
        "3. **Build proof:** complete two small projects and write down the problem, "
        "your contribution, and what you learned.\n"
        "4. **Prepare materials:** tailor a one-page resume to each role and include "
        "links to projects you can explain.\n"
        "5. **Practice interviews:** rehearse explaining a project, solving a basic "
        "role-related problem, and asking the employer questions.\n"
        "6. **Apply carefully:** use the Job Opportunities page to search, verify "
        "each employer and listing, and track applications and follow-ups."
    )


def _project_ideas(
    question: str,
    profile: Mapping[str, object] | None,
    matches: list[CareerMatch],
) -> str:
    target = _named_career(question, matches)
    if not target and is_profile_complete(profile) and matches:
        target = matches[0].career.title
    if not target:
        return (
            "Complete your profile or name a target role so I can tailor a project. "
            "For any beginner project, choose a small problem, make a working first "
            "version, and write a README describing what you learned."
        )
    match = _match_by_title(target, matches)
    return (
        f"For a beginner {target} portfolio, try these projects:\n\n"
        + "\n".join(
            f"{index}. {project}"
            for index, project in enumerate(match.career.projects, start=1)
        )
        + "\n\nStart with the first idea, keep the scope small, and explain your "
        "decisions in a README."
    )


def _expand_project_idea(
    question: str,
    profile: Mapping[str, object] | None,
    matches: list[CareerMatch],
) -> str:
    role = _named_career(question, matches)
    if not role and is_profile_complete(profile) and matches:
        role = matches[0].career.title
    if not role:
        return _project_ideas(question, profile, matches)
    match = _match_by_title(role, matches)
    project = match.career.projects[0]
    return (
        f"For the {role} idea “{project}”, keep your first version small:\n\n"
        "1. Choose one question or user problem to solve.\n"
        "2. Build the simplest working version with tools you already know.\n"
        "3. Test it, note one improvement, and explain your decisions in a README.\n\n"
        "This gives you a clear project to discuss without making the scope too large."
    )


def _compare_careers(
    question: str,
    matches: list[CareerMatch],
    profile: Mapping[str, object] | None,
) -> str:
    skills = _named_skills(question)
    if len(skills) >= 2:
        return _compare_skills(question, skills, profile)

    named = []
    normalized = question.casefold()
    for match in matches:
        if match.career.title.casefold() in normalized and match not in named:
            named.append(match)
    if len(named) < 2:
        return (
            "Which two careers or skills would you like me to compare? For example, "
            "“Compare Data Analyst and Software Developer” or “Python vs SQL.”"
        )
    first, second = named[:2]
    first_signals = _match_signals(first)
    second_signals = _match_signals(second)
    stronger = (
        first.career.title
        if first.fit_score > second.fit_score
        else second.career.title
        if second.fit_score > first.fit_score
        else None
    )
    fit_comparison = (
        f" Your current profile has a higher catalog signal for {stronger} "
        f"({max(first.fit_score, second.fit_score)}% versus "
        f"{min(first.fit_score, second.fit_score)}%)."
        if stronger
        else " Your profile has equal catalog signal scores for these two roles."
    )
    return (
        f"**{first.career.title}:** {first.career.description} Core skills include "
        f"{', '.join(first.career.skills)}. Your profile signals: {first_signals}.\n\n"
        f"**{second.career.title}:** {second.career.description} Core skills include "
        f"{', '.join(second.career.skills)}. Your profile signals: {second_signals}."
        f"{fit_comparison} Try a small project from each path to compare the day-to-day "
        "work. Catalog scores are not predictions."
    )


def _comparison_detail(question: str, matches: list[CareerMatch]) -> str:
    named = [
        match
        for match in matches
        if match.career.title.casefold() in question.casefold()
    ]
    if len(named) >= 2:
        first, second = named[:2]
        return (
            f"The profile fit difference comes from which listed skills and interests "
            f"overlap: {first.career.title} matches {_match_signals(first)}, while "
            f"{second.career.title} matches {_match_signals(second)}. To decide, try "
            f"a small task from each path: {first.career.projects[0]} Then compare "
            "which kind of work you enjoyed more."
        )
    skills = _named_skills(question)
    if len(skills) >= 2:
        first, second = skills[:2]
        return (
            f"Choose between {first} and {second} based on the task you want to do: "
            f"{first} helps you {_skill_purpose(first)}, while {second} helps you "
            f"{_skill_purpose(second)}. Your next step is to try one short exercise "
            "in each and compare which felt more useful."
        )
    return "Which two careers or skills in that comparison would you like me to explain?"


def _first_skill_improvement(
    question: str,
    profile: Mapping[str, object] | None,
    matches: list[CareerMatch],
) -> str:
    if not is_profile_complete(profile) or not matches:
        return _prioritized_skill_plan(question, profile, matches)
    role = _named_career(question, matches)
    match = _match_by_title(role, matches) if role else matches[0]
    guidance = recommend_skill_development(match)
    if not guidance:
        return (
            f"Your profile already lists the catalog's core skills for "
            f"{match.career.title}. Build stronger evidence with this project: "
            f"{match.career.projects[0]}"
        )
    first = guidance[0]
    return (
        f"Start with **{first.skill}** for {match.career.title}. It is missing from "
        f"the skills in your profile and is a core role skill. {first.practice}"
    )


def _expand_skill_explanation(skill: str) -> str:
    expanded_examples = {
        "SQL": (
            "For example, `SELECT department, COUNT(*) FROM employees GROUP BY "
            "department;` groups employee rows by department and counts the rows in "
            "each group. SQL is useful when a role needs answers from stored data, "
            "such as finding how many orders each product received."
        ),
        "Python": (
            "For example, a loop can process several values: "
            "`for score in [70, 85]: print(score)`. Python is useful when you need "
            "repeatable steps, such as cleaning a list of data values."
        ),
    }
    return expanded_examples.get(
        skill,
        f"In practice, {skill} is useful when you need to "
        f"{_skill_purpose(skill)}. Try one small exercise, check the result, and "
        "write down what you learned.",
    )


def _explain_skill(skill: str) -> str:
    explanations = {
        "SQL": (
            "SQL stands for Structured Query Language. It is used to ask questions "
            "of data stored in tables. For example, `SELECT name FROM students WHERE "
            "grade = 'A';` asks a database to return the names of students whose "
            "grade is A. The table is `students`, and `WHERE` filters the rows."
        ),
        "Python": (
            "Python is a programming language often used for automation, web apps, "
            "and data work. For example, `print(2 + 3)` asks Python to calculate and "
            "display `5`."
        ),
        "Java": (
            "Java is a programming language used to build applications and services. "
            "For example, a Java program can validate form input before saving it."
        ),
        "JavaScript": (
            "JavaScript is a programming language commonly used to make web pages "
            "interactive. For example, it can respond when someone clicks a button."
        ),
        "Data analysis": (
            "Data analysis means checking and organizing information to answer a "
            "question. For example, you could compare monthly sales to find which "
            "products sold more often."
        ),
        "Machine learning": (
            "Machine learning is a way to train a computer model to find patterns "
            "in examples and make predictions. For instance, a model can learn from "
            "past house sales to estimate a price; its estimate still needs testing."
        ),
        "Web development": (
            "Web development is the work of creating and maintaining websites or "
            "web applications. HTML structures a page, CSS styles it, and JavaScript "
            "can add interactive behavior."
        ),
        "Communication": (
            "Communication is sharing information clearly and listening to others. "
            "A practical example is explaining a project result in a short summary "
            "that a non-specialist can understand."
        ),
        "Problem solving": (
            "Problem solving means defining a problem, breaking it into smaller "
            "parts, trying an approach, and checking whether it worked."
        ),
        "Project management": (
            "Project management is planning and coordinating work toward a goal. "
            "For example, a simple project plan lists tasks, dates, owners, and risks."
        ),
        "UI/UX design": (
            "UI/UX design focuses on how a digital product looks and how people use "
            "it. A designer might test a sign-up flow with users and simplify steps "
            "that cause confusion."
        ),
        "Cloud computing": (
            "Cloud computing means using computing services over the internet "
            "instead of managing all the hardware yourself. A web app might use a "
            "cloud server to store and serve its data."
        ),
        "Cybersecurity": (
            "Cybersecurity is protecting computers, accounts, networks, and data "
            "from misuse or attack. A simple example is using multi-factor "
            "authentication to make account access harder to steal."
        ),
        "Research": (
            "Research is a structured way to find and check evidence before drawing "
            "a conclusion. It includes asking a clear question and checking whether "
            "sources are reliable."
        ),
    }
    return explanations.get(
        skill,
        f"{skill} is a skill used in several roles. To understand it in practice, "
        "start with a beginner lesson and try a small project that uses it.",
    )


def _skill_purpose(skill: str) -> str:
    purposes = {
        "SQL": "retrieve and organize information in a database",
        "Python": "automate tasks and build practical tools",
        "Java": "build structured applications and services",
        "JavaScript": "make web applications interactive",
        "Data analysis": "find and communicate useful patterns in information",
        "Machine learning": "build and evaluate models that learn patterns from examples",
        "Web development": "create and maintain websites and web applications",
        "Communication": "explain ideas and coordinate work clearly",
        "Problem solving": "break challenges into steps and test possible solutions",
        "Project management": "plan work and coordinate people, tasks, and deadlines",
        "UI/UX design": "make digital products understandable and usable",
        "Cloud computing": "deploy and operate applications using online infrastructure",
        "Cybersecurity": "identify risks and protect systems and information",
        "Research": "find and evaluate evidence before making decisions",
    }
    return purposes.get(skill, "complete practical tasks in your chosen field")


def _expand_role_explanation(match: CareerMatch) -> str:
    return (
        f"{match.career.title}: {match.career.description} Common core skills include "
        f"{', '.join(match.career.skills)}. A beginner-friendly way to explore it is "
        f"{match.career.projects[0]}"
    )


def _career_detail(match: CareerMatch) -> str:
    return (
        f"{match.career.title} ranked well because of {_match_signals(match)}. "
        f"Its first suggested learning topic is {match.career.learning_topics[0]}. "
        "The match reflects only the profile details saved in this app."
    )


def generate_llm_answer(
    question: str,
    profile: Mapping[str, object] | None,
    history: list[Mapping[str, str]],
    matches: list[CareerMatch],
) -> str | None:
    """Use an OpenAI-compatible chat API only when an API key is configured."""
    api_key, model, endpoint = _llm_configuration()
    if not api_key:
        return None

    if not endpoint.rstrip("/").endswith("/chat/completions"):
        endpoint = f"{endpoint.rstrip('/')}/chat/completions"
    profile_context = {
        field: profile.get(field)
        for field in (
            "education_level",
            "field_of_study",
            "skills",
            "interests",
            "interested_roles",
            "experience_years",
            "career_goal",
            "preferred_location",
        )
    } if profile else {}
    system_prompt = (
        "You are a friendly career guidance assistant. Use simple English, practical "
        "examples, and answer the user's actual question directly. Use only the "
        "student details and career information provided; never invent profile facts, "
        "job listings, course credentials, or certainty. For follow-ups, use the "
        "conversation. If details are missing, say so and ask one useful question. "
        "Treat profile-match scores as catalog comparisons, not predictions."
    )
    career_context = [
        {
            "role": match.career.title,
            "description": match.career.description,
            "core_skills": match.career.skills,
            "matched_skills": match.matched_skills,
            "missing_skills": match.missing_skills,
            "matched_interests": match.matched_interests,
            "matched_roles": match.matched_roles,
            "profile_signal_score": match.fit_score,
            "beginner_projects": match.career.projects,
            "learning_topics": match.career.learning_topics,
        }
        for match in matches
    ]
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": "Saved student profile (may be empty): "
            + json.dumps(profile_context, ensure_ascii=True),
        },
        {
            "role": "system",
            "content": "Career catalog matches (may be empty): "
            + json.dumps(career_context, ensure_ascii=True),
        },
        *[
            {
                "role": str(item["role"]),
                "content": str(item["content"]),
            }
            for item in history[-10:]
            if item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
        ],
        {"role": "user", "content": question},
    ]
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.4},
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(
            f"The configured career assistant API returned HTTP {error.code}."
        ) from error
    except URLError as error:
        raise RuntimeError(
            "The configured career assistant API could not be reached."
        ) from error
    except OSError as error:
        raise RuntimeError(
            "The configured career assistant API could not be reached."
        ) from error
    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError(
            "The configured career assistant API did not return a valid response."
        ) from error

    try:
        answer = result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError, TypeError) as error:
        raise RuntimeError(
            "The configured career assistant API response had an unexpected format."
        ) from error
    if not answer:
        raise RuntimeError("The configured career assistant API returned an empty answer.")
    return answer


def _submit_career_question(
    question: str,
    profile: Mapping[str, object] | None,
    matches: list[CareerMatch],
    history: list[dict[str, str]],
) -> None:
    history.append({"role": "user", "content": question})
    try:
        result = answer_question(question, history[:-1])
        answer = result["answer"]
        if result["api_error"]:
            st.session_state["career_chat_error"] = result["api_error"]
    except CareerAPIError as error:
        st.session_state["career_chat_error"] = str(error)
        answer = career_assistant_answer(question, profile, matches, history[:-1])
    history.append({"role": "assistant", "content": answer})


def _llm_configuration() -> tuple[str, str, str]:
    """Prefer Groq settings, with optional OpenAI-compatible settings as fallback."""
    try:
        secrets = dict(st.secrets)
    except StreamlitSecretNotFoundError:
        secrets = {}

    groq_api_key = os.environ.get("GROQ_API_KEY") or str(
        secrets.get("GROQ_API_KEY", "")
    )
    if groq_api_key:
        model = os.environ.get("GROQ_MODEL") or str(
            secrets.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        )
        endpoint = os.environ.get("GROQ_BASE_URL") or str(
            secrets.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        )
        return groq_api_key.strip(), model.strip(), endpoint.strip()

    api_key = os.environ.get("OPENAI_API_KEY") or str(secrets.get("OPENAI_API_KEY", ""))
    model = os.environ.get("OPENAI_MODEL") or str(
        secrets.get("OPENAI_MODEL", "gpt-4o-mini")
    )
    endpoint = os.environ.get(
        "OPENAI_BASE_URL",
    ) or str(secrets.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    return api_key.strip(), model.strip(), endpoint.strip()


def render_career_guide_panel(account: Mapping[str, str]) -> None:
    profile = account_profile(account)
    matches = (
        api_client.recommend_careers(profile, limit=len(CAREER_PATHS))
        if is_profile_complete(profile)
        else []
    )
    history = st.session_state.setdefault("career_chat_history", [])
    api_error = st.session_state.pop("career_chat_error", None)

    with st.container(key="career-guide-panel"):
        header, close = st.columns([0.82, 0.18])
        with header:
            st.markdown("**AI Career Guide**")
        with close:
            if st.button(
                "X",
                key="career-guide-close",
                help="Close AI Career Guide",
                width=36,
            ):
                st.session_state["career_guide_open"] = False
                st.rerun()

        if api_error:
            st.warning(f"{api_error} I answered using local career guidance.")
        if not history:
            st.caption("Ask about career matches, skills, or next steps.")
        with st.container(height=300, border=False):
            for message in history:
                with st.chat_message(message["role"]):
                    st.write(message["content"])

        with st.form("career-guide-panel-form", clear_on_submit=True):
            question = st.text_input(
                "Message the AI Career Guide",
                key="career-guide-panel-input",
                placeholder="Ask a career question...",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(
                "Send",
                type="primary",
                icon=":material/send:",
                width="stretch",
            )
        if submitted and question.strip():
            _submit_career_question(question.strip(), profile, matches, history)
            st.rerun()


def render_chat_page(account: Mapping[str, str]) -> None:
    profile = account_profile(account)
    page_header(
        "AI Career Guide",
        "Ask about role suggestions, skill gaps, project ideas, or job-search next steps.",
    )
    llm_configured = assistant_status()
    st.caption(
        "Groq is used when GROQ_API_KEY is set in the environment or "
        ".streamlit/secrets.toml. Otherwise, an OpenAI-compatible API is used "
        "when OPENAI_API_KEY is configured; without either key, intent-based "
        "local guidance uses the career catalog. When configured, the relevant "
        "profile and conversation are sent to that API."
    )
    if not is_profile_complete(profile):
        st.info(
            "You can ask general questions now. Complete your profile for "
            "personalized career and skill suggestions."
        )
        st.page_link(
            page_link_target("Profile"),
            label="Complete your profile",
            icon=":material/person_edit:",
        )

    matches = (
        api_client.recommend_careers(profile, limit=len(CAREER_PATHS))
        if is_profile_complete(profile)
        else []
    )
    history = st.session_state.setdefault("career_chat_history", [])
    api_error = st.session_state.pop("career_chat_error", None)
    if api_error:
        st.warning(f"{api_error} I answered using the local career guidance instead.")
    if st.button("Clear conversation", icon=":material/delete_outline:"):
        st.session_state.career_chat_history = []
        st.session_state.pop("career_chat_error", None)
        st.rerun()

    for message in history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    question = st.chat_input("Ask about your career suggestions")
    if question:
        _submit_career_question(question, profile, matches, history)
        st.rerun()

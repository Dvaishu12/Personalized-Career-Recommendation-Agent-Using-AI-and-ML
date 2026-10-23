"""HTTP client used by the Streamlit frontend to call the FastAPI backend."""

from __future__ import annotations

import json
import os
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

from recommendations import CAREER_PATHS, CareerMatch, SkillDevelopmentRecommendation

API_BASE_URL = os.environ.get("CAREERAI_API_URL", "http://127.0.0.1:8000").rstrip("/")


class CareerAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _request(
    path: str,
    *,
    method: str = "GET",
    payload: Mapping[str, object] | None = None,
    authenticated: bool = True,
) -> object:
    headers = {"Content-Type": "application/json"}
    token = st.session_state.get("api_access_token")
    if authenticated and token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{API_BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            response_body = json.loads(error.read().decode("utf-8"))
            message = response_body.get("detail", "The backend request failed.")
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = "The backend request failed."
        raise CareerAPIError(str(message), error.code) from error
    except (URLError, TimeoutError, OSError) as error:
        raise CareerAPIError(
            "CareerAI backend is unavailable. Start it with `python -m uvicorn api:app --reload`."
        ) from error


def register_account(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
) -> None:
    _request(
        "/auth/register",
        method="POST",
        authenticated=False,
        payload={
            "full_name": full_name,
            "email": email,
            "password": password,
            "confirm_password": confirm_password,
        },
    )


def authenticate(email: str, password: str) -> dict[str, str] | None:
    try:
        result = _request(
            "/auth/login",
            method="POST",
            authenticated=False,
            payload={"email": email, "password": password},
        )
    except CareerAPIError as error:
        if error.status_code == 401:
            return None
        raise
    st.session_state["api_access_token"] = result["access_token"]
    return result["account"]


def clear_session() -> None:
    st.session_state.pop("api_access_token", None)


def logout() -> None:
    try:
        _request("/auth/logout", method="POST")
    finally:
        clear_session()


def get_student_profile(account_id: str) -> dict[str, object] | None:
    del account_id
    return _request("/profile")


def save_student_profile(
    account_id: str,
    education_level: str,
    field_of_study: str,
    skills: list[str],
    interests: list[str],
    experience_years: int,
    career_goal: str,
    preferred_location: str = "Remote",
    interested_roles: list[str] | None = None,
) -> None:
    del account_id
    _request(
        "/profile",
        method="PUT",
        payload={
            "education_level": education_level,
            "field_of_study": field_of_study,
            "skills": skills,
            "interests": interests,
            "experience_years": experience_years,
            "career_goal": career_goal,
            "preferred_location": preferred_location,
            "interested_roles": interested_roles or [],
        },
    )


def recommend_careers(
    profile: Mapping[str, object],
    limit: int = 3,
) -> list[CareerMatch]:
    del profile
    results = _request("/recommendations", method="POST", payload={"limit": limit})
    career_by_title = {career.title: career for career in CAREER_PATHS}
    matches = []
    for item in results:
        career = career_by_title.get(item["career"]["title"])
        if career is None:
            raise CareerAPIError("The backend returned an unknown career role.")
        matches.append(
            CareerMatch(
                career=career,
                fit_score=item["fit_score"],
                matched_skills=tuple(item["matched_skills"]),
                missing_skills=tuple(item["missing_skills"]),
                matched_interests=tuple(item["matched_interests"]),
                matched_roles=tuple(item["matched_roles"]),
                matched_context=tuple(item["matched_context"]),
            )
        )
    return matches


def recommend_skill_development(
    match: CareerMatch,
) -> list[SkillDevelopmentRecommendation]:
    results = _request(
        "/skill-development",
        method="POST",
        payload={"role": match.career.title},
    )
    return [SkillDevelopmentRecommendation(**item) for item in results]


def generate_roadmap(role: str) -> dict[str, object]:
    return _request("/roadmap", method="POST", payload={"role": role})


def curated_roadmap(
    match: CareerMatch,
    api_error: str | None = None,
) -> dict[str, object]:
    return {
        "generated": False,
        "steps": [
            {
                "topic": topic,
                "objective": f"Build a practical foundation in {topic}.",
            }
            for topic in match.career.learning_topics
        ],
        "projects": list(match.career.projects),
        "api_error": api_error,
    }


def assistant_status() -> bool:
    result = _request("/assistant/status")
    return bool(result["llm_configured"])


def answer_question(
    question: str,
    history: list[Mapping[str, str]],
) -> dict[str, str | None]:
    return _request(
        "/assistant",
        method="POST",
        payload={"question": question, "history": history[-10:]},
    )
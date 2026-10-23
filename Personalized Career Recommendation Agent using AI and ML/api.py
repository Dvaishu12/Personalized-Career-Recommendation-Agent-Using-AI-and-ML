"""FastAPI backend for CareerAI accounts, profiles, and career guidance."""

from __future__ import annotations

import secrets
import json
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from auth import (
    authenticate,
    create_account,
    get_student_profile,
    initialize_database,
    save_student_profile,
    validate_registration,
)
from recommendations import (
    CAREER_PATHS,
    recommend_careers,
    recommend_skill_development,
)
from student_pages import (
    _llm_configuration,
    career_assistant_answer,
    generate_llm_answer,
)

SESSION_TTL_SECONDS = 8 * 60 * 60
sessions: dict[str, tuple[dict[str, str], float]] = {}
bearer_scheme = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="CareerAI API",
    version="1.0.0",
    lifespan=lifespan,
)


class RegistrationRequest(BaseModel):
    full_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileRequest(BaseModel):
    education_level: str
    field_of_study: str
    skills: list[str]
    interests: list[str] = Field(default_factory=list)
    experience_years: int = Field(ge=0)
    career_goal: str
    preferred_location: str = "Remote"
    interested_roles: list[str] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    limit: int = Field(default=3, ge=1, le=20)


class SkillDevelopmentRequest(BaseModel):
    role: str


class RoadmapRequest(BaseModel):
    role: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistantRequest(BaseModel):
    question: str
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)


def _require_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")

    session = sessions.get(credentials.credentials)
    if session is None or session[1] <= time.time():
        sessions.pop(credentials.credentials, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Sign in again.")
    return session[0]


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(request: RegistrationRequest) -> dict[str, bool]:
    error = validate_registration(
        request.full_name,
        request.email,
        request.password,
        request.confirm_password,
    )
    if error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)
    if not create_account(request.full_name, request.email, request.password):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    return {"created": True}


@app.post("/auth/login")
def login(request: LoginRequest) -> dict[str, object]:
    account = authenticate(request.email, request.password)
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect.")

    token = secrets.token_urlsafe(32)
    sessions[token] = (account, time.time() + SESSION_TTL_SECONDS)
    return {"access_token": token, "account": account}


@app.post("/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, bool]:
    if credentials is not None:
        sessions.pop(credentials.credentials, None)
    return {"logged_out": True}


@app.get("/profile")
def read_profile(account: dict[str, str] = Depends(_require_account)):
    return get_student_profile(account["id"])


@app.put("/profile")
def write_profile(
    profile: ProfileRequest,
    account: dict[str, str] = Depends(_require_account),
) -> dict[str, bool]:
    save_student_profile(
        account["id"],
        profile.education_level,
        profile.field_of_study,
        profile.skills,
        profile.interests,
        profile.experience_years,
        profile.career_goal,
        profile.preferred_location,
        profile.interested_roles,
    )
    return {"saved": True}


@app.post("/recommendations")
def career_recommendations(
    request: RecommendationRequest,
    account: dict[str, str] = Depends(_require_account),
) -> list[dict[str, object]]:
    profile = get_student_profile(account["id"])
    if profile is None:
        return []
    return [asdict(match) for match in recommend_careers(profile, request.limit)]


@app.post("/skill-development")
def skill_development(
    request: SkillDevelopmentRequest,
    account: dict[str, str] = Depends(_require_account),
) -> list[dict[str, str]]:
    profile = get_student_profile(account["id"])
    if profile is None:
        return []
    match = next(
        (
            item
            for item in recommend_careers(profile, limit=len(CAREER_PATHS))
            if item.career.title == request.role
        ),
        None,
    )
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career role not found.")
    return [asdict(item) for item in recommend_skill_development(match)]


@app.post("/roadmap")
def generate_roadmap(
    request: RoadmapRequest,
    account: dict[str, str] = Depends(_require_account),
) -> dict[str, object]:
    profile = get_student_profile(account["id"])
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complete your profile first.")

    match = next(
        (
            item
            for item in recommend_careers(profile, limit=len(CAREER_PATHS))
            if item.career.title == request.role
        ),
        None,
    )
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career role not found.")

    def curated_response(error: str | None = None) -> dict[str, object]:
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
            "api_error": error,
        }

    if not _llm_configuration()[0]:
        return curated_response()

    prompt = (
        f"Create a personalized learning roadmap for {match.career.title}. "
        "Use the supplied student profile, matched and missing skills, and career "
        "catalog. Return only a JSON object with exactly two keys: steps and projects. "
        "steps must contain 3 to 6 objects, each with a concise topic and an "
        "actionable objective. Order steps from foundational to applied. projects "
        "must contain 2 to 4 realistic beginner-friendly project strings. Do not "
        "include markdown fences, URLs, unsupported certifications, or claims about "
        "guaranteed employment."
    )
    try:
        response = generate_llm_answer(prompt, profile, [], [match])
        roadmap = json.loads(response)
        steps = roadmap.get("steps") if isinstance(roadmap, dict) else None
        projects = roadmap.get("projects") if isinstance(roadmap, dict) else None
        if not isinstance(steps, list) or not 3 <= len(steps) <= 6:
            raise ValueError("The generated roadmap must contain 3 to 6 steps.")
        if not isinstance(projects, list) or not 2 <= len(projects) <= 4:
            raise ValueError("The generated roadmap must contain 2 to 4 projects.")

        validated_steps = []
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("A generated roadmap step had an invalid format.")
            topic = step.get("topic")
            objective = step.get("objective")
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError("A generated roadmap step is missing its topic.")
            if not isinstance(objective, str) or not objective.strip():
                raise ValueError("A generated roadmap step is missing its objective.")
            validated_steps.append(
                {"topic": topic.strip()[:120], "objective": objective.strip()[:400]}
            )

        validated_projects = [
            project.strip()[:400]
            for project in projects
            if isinstance(project, str) and project.strip()
        ]
        if len(validated_projects) < 2:
            raise ValueError("The generated roadmap is missing project suggestions.")
        return {
            "generated": True,
            "steps": validated_steps,
            "projects": validated_projects[:4],
            "api_error": None,
        }
    except (RuntimeError, ValueError, TypeError, json.JSONDecodeError) as error:
        return curated_response(str(error))


@app.get("/assistant/status")
def assistant_status(
    _: dict[str, str] = Depends(_require_account),
) -> dict[str, bool]:
    return {"llm_configured": bool(_llm_configuration()[0])}


@app.post("/assistant")
def answer_question(
    request: AssistantRequest,
    account: dict[str, str] = Depends(_require_account),
) -> dict[str, str | None]:
    profile = get_student_profile(account["id"])
    matches = (
        recommend_careers(profile, limit=len(CAREER_PATHS))
        if profile
        else []
    )
    history = [message.model_dump() for message in request.history]
    answer = None
    api_error = None
    if _llm_configuration()[0]:
        try:
            answer = generate_llm_answer(request.question, profile, history, matches)
        except RuntimeError as error:
            api_error = str(error)
    if answer is None:
        answer = career_assistant_answer(
            request.question,
            profile,
            matches,
            history,
        )
    return {"answer": answer, "api_error": api_error}
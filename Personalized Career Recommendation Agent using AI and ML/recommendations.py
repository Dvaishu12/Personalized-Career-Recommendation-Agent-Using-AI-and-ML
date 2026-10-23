"""Profile-based career matches, skill gaps, roadmaps, and job-search links."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlencode

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class CareerPath:
    title: str
    description: str
    skills: tuple[str, ...]
    interests: tuple[str, ...]
    keywords: tuple[str, ...]
    learning_topics: tuple[str, ...]
    projects: tuple[str, ...]


@dataclass(frozen=True)
class CareerMatch:
    career: CareerPath
    fit_score: int
    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]
    matched_interests: tuple[str, ...]
    matched_roles: tuple[str, ...] = ()
    matched_context: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillDevelopmentRecommendation:
    skill: str
    learning_topic: str
    role_relevance: str
    practice: str


CAREER_PATHS = (
    CareerPath(
        title="Data Analyst",
        description="Turn data into clear insights that support better decisions.",
        skills=("SQL", "Data analysis", "Python", "Communication"),
        interests=("Data and analytics", "Finance", "Business and entrepreneurship", "Science and research"),
        keywords=("data", "analytics", "analyst", "statistics", "finance", "research"),
        learning_topics=("SQL for data analysis", "Python data analysis", "Data visualization"),
        projects=("Analyze a public dataset and explain three findings.", "Build a dashboard that tracks a metric you care about."),
    ),
    CareerPath(
        title="Software Developer",
        description="Design, build, test, and maintain applications used by people and teams.",
        skills=("Python", "Java", "JavaScript", "Web development", "Problem solving"),
        interests=("Software development", "Education", "Cloud technology", "Artificial intelligence"),
        keywords=("software", "developer", "programming", "web", "application", "coding"),
        learning_topics=("Programming fundamentals", "Data structures and algorithms", "Building web applications"),
        projects=("Build a responsive portfolio website.", "Create a small application that solves a problem in your field of study."),
    ),
    CareerPath(
        title="Machine Learning Engineer",
        description="Build and evaluate data-driven models that help automate predictions and decisions.",
        skills=("Python", "Machine learning", "Data analysis", "SQL", "Cloud computing"),
        interests=("Artificial intelligence", "Data and analytics", "Science and research"),
        keywords=("machine learning", "artificial intelligence", "ai", "model", "prediction", "data science"),
        learning_topics=("Python for machine learning", "Model evaluation and feature engineering", "Deploying machine-learning models"),
        projects=("Train and compare models on a public dataset.", "Deploy a small prediction API and document its limitations."),
    ),
    CareerPath(
        title="UI/UX Designer",
        description="Research user needs and create accessible, intuitive digital experiences.",
        skills=("UI/UX design", "Communication", "Research", "Web development", "Problem solving"),
        interests=("Design and creativity", "Social impact", "Education"),
        keywords=("design", "ux", "ui", "user experience", "creative", "product"),
        learning_topics=("User research and usability testing", "Interaction design and prototyping", "Accessibility fundamentals"),
        projects=("Redesign a confusing screen and explain your design decisions.", "Run a small usability test and summarize the findings."),
    ),
    CareerPath(
        title="Cybersecurity Analyst",
        description="Help organizations identify security risks, monitor systems, and respond to threats.",
        skills=("Cybersecurity", "Python", "Cloud computing", "Research", "Problem solving"),
        interests=("Cybersecurity", "Cloud technology", "Science and research"),
        keywords=("security", "cybersecurity", "network", "risk", "cloud", "threat"),
        learning_topics=("Networking and security fundamentals", "Threat analysis and incident response", "Cloud security basics"),
        projects=("Complete a legal beginner security lab and write a responsible findings report.", "Create a checklist for securing a sample cloud application."),
    ),
    CareerPath(
        title="Product Manager",
        description="Connect customer needs, business goals, and engineering work to guide a product.",
        skills=("Communication", "Project management", "Problem solving", "Data analysis", "Research"),
        interests=("Business and entrepreneurship", "Social impact", "Education", "Healthcare"),
        keywords=("product", "business", "management", "entrepreneur", "strategy", "healthcare"),
        learning_topics=("Product discovery and user interviews", "Prioritization and product metrics", "Agile planning and communication"),
        projects=("Write a one-page product brief for a problem you know.", "Create a simple roadmap and success metrics for a student-focused feature."),
    ),
)

_CAREER_VECTORIZER = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
_CAREER_DOCUMENTS = [
    " ".join(
        (
            career.title,
            career.description,
            *career.skills,
            *career.interests,
            *career.keywords,
        )
    )
    for career in CAREER_PATHS
]
_CAREER_TFIDF_MATRIX = _CAREER_VECTORIZER.fit_transform(_CAREER_DOCUMENTS)

SKILL_DEVELOPMENT_GUIDANCE = {
    "Python": (
        "Python programming",
        "Use Python to automate tasks and build practical tools for this role.",
        "Write a small script for a real task in this career and publish it with a clear README.",
    ),
    "Java": (
        "Java programming and object-oriented design",
        "Java helps build and maintain structured applications and services.",
        "Build a small Java application with tests and document how its main components work together.",
    ),
    "JavaScript": (
        "JavaScript for interactive web applications",
        "JavaScript adds interactive behavior to web products and user interfaces.",
        "Create an accessible interactive page and test it in a browser at desktop and mobile sizes.",
    ),
    "SQL": (
        "SQL for querying relational databases",
        "SQL helps retrieve and organize the data used to answer role-specific questions.",
        "Use joins, aggregations, and filtering on a sample database, then explain the result.",
    ),
    "Data analysis": (
        "Data analysis and visualization",
        "Analyzing evidence helps this role make and communicate better decisions.",
        "Explore a public dataset, check its quality, and present a chart with a concise finding.",
    ),
    "Machine learning": (
        "Machine learning fundamentals",
        "Machine-learning knowledge supports building and evaluating data-driven solutions.",
        "Train a baseline model on a public dataset, compare metrics, and explain its limitations.",
    ),
    "Web development": (
        "Web development fundamentals",
        "Web development helps create and understand the digital products used in this role.",
        "Build a small responsive web app and include basic accessibility and usability checks.",
    ),
    "Communication": (
        "Workplace communication and presentation",
        "Clear communication helps explain decisions, findings, and next steps to other people.",
        "Turn one project into a one-page summary for a non-specialist and present it in three minutes.",
    ),
    "Problem solving": (
        "Structured problem solving",
        "A repeatable approach helps break role-specific challenges into testable steps.",
        "Write down a problem, constraints, possible approaches, and how you would test the best option.",
    ),
    "Project management": (
        "Project planning and delivery",
        "Planning helps coordinate work, deadlines, dependencies, and stakeholder expectations.",
        "Plan a small project with milestones, owners, risks, and a short retrospective after completion.",
    ),
    "UI/UX design": (
        "User experience research and interface design",
        "User-centered design helps make products easier and more accessible to use.",
        "Prototype a key user flow, test it with a few people, and record the improvements you made.",
    ),
    "Cloud computing": (
        "Cloud computing fundamentals",
        "Cloud concepts help understand how modern applications and services are deployed.",
        "Deploy a small demo app using a free learning tier and document its architecture and costs.",
    ),
    "Cybersecurity": (
        "Cybersecurity fundamentals",
        "Security knowledge helps identify risks and protect systems, users, and data.",
        "Complete a beginner security lab in an authorized environment and write a defensive findings report.",
    ),
    "Research": (
        "Research methods and evidence evaluation",
        "Research helps validate assumptions and make recommendations based on trustworthy evidence.",
        "Compare several credible sources on a role-related question and summarize the evidence and uncertainty.",
    ),
}


def recommend_careers(profile: Mapping[str, object], limit: int = 3) -> list[CareerMatch]:
    """Rank paths with explicit profile signals and TF-IDF cosine similarity."""
    raw_skills = profile.get("skills", [])
    raw_interests = profile.get("interests", [])
    raw_interested_roles = profile.get("interested_roles", [])
    skills = (
        {str(item).casefold() for item in raw_skills}
        if isinstance(raw_skills, (list, tuple, set))
        else set()
    )
    interests = (
        {str(item).casefold() for item in raw_interests}
        if isinstance(raw_interests, (list, tuple, set))
        else set()
    )
    interested_roles = (
        {str(item).casefold() for item in raw_interested_roles}
        if isinstance(raw_interested_roles, (list, tuple, set))
        else set()
    )
    context = " ".join(
        str(profile.get(field, ""))
        for field in ("field_of_study", "career_goal")
    ).casefold()
    profile_terms = [context]
    profile_terms.extend(str(item) for item in skills)
    profile_terms.extend(str(item) for item in interests)
    profile_terms.extend(str(item) for item in interested_roles)
    profile_vector = _CAREER_VECTORIZER.transform([" ".join(profile_terms)])
    text_similarity = cosine_similarity(
        profile_vector,
        _CAREER_TFIDF_MATRIX,
    )[0]

    matches: list[CareerMatch] = []
    for career_index, career in enumerate(CAREER_PATHS):
        matched_skills = tuple(skill for skill in career.skills if skill.casefold() in skills)
        matched_interests = tuple(
            interest for interest in career.interests if interest.casefold() in interests
        )
        matched_roles = (
            (career.title,)
            if career.title.casefold() in interested_roles
            else ()
        )
        matched_context = tuple(
            keyword for keyword in career.keywords if keyword in context
        )
        keyword_match = bool(matched_context)
        if interested_roles:
            signal_score = (
                34 * len(matched_skills) / len(career.skills)
                + 42 * len(matched_interests) / len(career.interests)
                + 9 * keyword_match
                + 15 * bool(matched_roles)
            )
        else:
            signal_score = (
                40 * len(matched_skills) / len(career.skills)
                + 50 * len(matched_interests) / len(career.interests)
                + 10 * keyword_match
            )
        score = round(
            0.8 * signal_score + 20 * float(text_similarity[career_index])
        )
        matches.append(
            CareerMatch(
                career=career,
                fit_score=score,
                matched_skills=matched_skills,
                missing_skills=tuple(
                    skill for skill in career.skills if skill.casefold() not in skills
                ),
                matched_interests=matched_interests,
                matched_roles=matched_roles,
                matched_context=matched_context,
            )
        )

    return sorted(matches, key=lambda match: (-match.fit_score, match.career.title))[:limit]


def recommend_skill_development(
    match: CareerMatch,
) -> list[SkillDevelopmentRecommendation]:
    """Explain how to improve each missing core skill for a career path."""
    recommendations = []
    for skill in match.missing_skills:
        learning_topic, role_relevance, practice = SKILL_DEVELOPMENT_GUIDANCE[skill]
        recommendations.append(
            SkillDevelopmentRecommendation(
                skill=skill,
                learning_topic=learning_topic,
                role_relevance=(
                    f"{role_relevance} It is a core skill for {match.career.title}."
                ),
                practice=practice,
            )
        )
    return recommendations


def learning_resource_url(topic: str) -> str:
    """Build a Coursera catalog search link for a learning topic."""
    return f"https://www.coursera.org/search?{urlencode({'query': topic})}"


def job_search_url(title: str, location: str, is_fresher: bool) -> str:
    """Build a LinkedIn Jobs search link without claiming a listing is live."""
    keywords = title if not is_fresher else f"{title} entry level"
    query = urlencode({"keywords": keywords, "location": location or "Remote"})
    return f"https://www.linkedin.com/jobs/search/?{query}"


def indeed_job_search_url(title: str, location: str, is_fresher: bool) -> str:
    """Build an Indeed job search link without claiming a listing is live."""
    keywords = title if not is_fresher else f"{title} entry level"
    query = urlencode({"q": keywords, "l": location or "Remote"})
    return f"https://www.indeed.com/jobs?{query}"

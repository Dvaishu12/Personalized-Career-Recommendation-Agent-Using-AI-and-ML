import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import auth
import student_pages
from student_pages import (
    INTERESTED_ROLE_OPTIONS,
    SKILL_OPTIONS,
    career_assistant_answer,
    generate_llm_answer,
    is_profile_complete,
    page_link_target,
    profile_completion,
    render_match_card,
    render_roadmap_diagram,
    render_skill_improvement_flow,
)
from recommendations import (
    CAREER_PATHS,
    indeed_job_search_url,
    job_search_url,
    learning_resource_url,
    recommend_careers,
    recommend_skill_development,
)

CHAT_PROFILE = {
    "education_level": "Undergraduate",
    "field_of_study": "Commerce",
    "skills": ["SQL", "Data analysis", "Python"],
    "interests": ["Data and analytics", "Finance"],
    "experience_years": 0,
    "career_goal": "Become a data analyst",
    "preferred_location": "Remote",
}


class RecommendationTests(unittest.TestCase):
    def test_profile_options_cover_catalog_skills_and_all_roles(self):
        catalog_skills = {
            skill for career in CAREER_PATHS for skill in career.skills
        }
        catalog_roles = {career.title for career in CAREER_PATHS}

        self.assertTrue(catalog_skills.issubset(SKILL_OPTIONS))
        self.assertEqual(set(INTERESTED_ROLE_OPTIONS), catalog_roles)

    def test_incomplete_profile_is_not_ready_for_personalized_results(self):
        self.assertFalse(is_profile_complete(None))
        self.assertFalse(
            is_profile_complete(
                {
                    "education_level": "Undergraduate",
                    "field_of_study": "",
                    "skills": ["Python"],
                    "interests": ["Artificial intelligence"],
                    "career_goal": "Become a developer",
                }
            )
        )

    def test_complete_profile_requires_skills_but_not_interests(self):
        self.assertTrue(
            is_profile_complete(
                {
                    "education_level": "Undergraduate",
                    "field_of_study": "Computer science",
                    "skills": ["Python"],
                    "career_goal": "Become a developer",
                }
            )
        )

    def test_profile_completion_counts_required_fields_and_names_gaps(self):
        self.assertEqual(
            profile_completion(None),
            (
                0,
                [
                    "Education level",
                    "Field of study",
                    "Skills",
                    "Career goal",
                ],
            ),
        )
        percentage, missing = profile_completion(CHAT_PROFILE)
        self.assertEqual(percentage, 100)
        self.assertEqual(missing, [])

        percentage, missing = profile_completion(
            {"education_level": "Undergraduate", "skills": ["Python"]}
        )
        self.assertEqual(percentage, 50)
        self.assertEqual(
            missing,
            ["Field of study", "Career goal"],
        )

    def test_ai_career_guide_resolves_legacy_navigation_title(self):
        guide_page = object()
        with patch.object(
            student_pages.st,
            "session_state",
            {"career_page_links": {"Chat assistant": guide_page}},
        ):
            self.assertIs(page_link_target("AI Career Guide"), guide_page)

    def test_roadmap_diagram_shows_ordered_learning_steps_and_links(self):
        match = recommend_careers(CHAT_PROFILE)[0]
        columns = [MagicMock() for _ in range(5)]
        markdown_calls = []
        caption_calls = []

        with (
            patch.object(student_pages.st, "columns", return_value=columns),
            patch.object(
                student_pages.st,
                "container",
                side_effect=lambda **kwargs: MagicMock(),
            ) as container,
            patch.object(
                student_pages.st,
                "markdown",
                side_effect=markdown_calls.append,
            ),
            patch.object(
                student_pages.st,
                "caption",
                side_effect=caption_calls.append,
            ),
        ):
            render_roadmap_diagram(match)

        for topic in match.career.learning_topics:
            self.assertTrue(
                any(f"[{topic}](" in str(call) for call in markdown_calls)
            )
        self.assertTrue(any("STEP 01 · START" in call for call in caption_calls))
        self.assertTrue(any("STEP 03 · APPLY" in call for call in caption_calls))
        self.assertEqual(
            sum(":material/arrow_forward:" in str(call) for call in markdown_calls),
            2,
        )
        keys = [call.kwargs["key"] for call in container.call_args_list]
        self.assertEqual(len(keys), len(set(keys)))

    def test_recommendation_card_shows_ranked_signals_and_next_step_links(self):
        match = recommend_careers(CHAT_PROFILE)[0]
        markdown_calls = []
        captions = []
        columns = [MagicMock(), MagicMock()]

        with (
            patch.object(
                student_pages.st,
                "container",
                side_effect=lambda **kwargs: MagicMock(),
            ) as container,
            patch.object(student_pages.st, "columns", return_value=columns),
            patch.object(
                student_pages.st,
                "markdown",
                side_effect=markdown_calls.append,
            ),
            patch.object(
                student_pages.st,
                "caption",
                side_effect=captions.append,
            ),
            patch.object(student_pages.st, "progress"),
            patch.object(student_pages.st, "write"),
            patch.object(student_pages.st, "page_link") as page_link,
            patch.object(student_pages, "page_link_target", return_value=object()),
            patch.object(student_pages, "render_match_explanation"),
        ):
            render_match_card(match, rank=1)

        self.assertEqual(
            container.call_args.kwargs,
            {"border": True, "key": "recommendation-card-1"},
        )
        self.assertIn("CAREER PATH 01", captions)
        self.assertTrue(
            any("Your matching profile signals" in call for call in markdown_calls)
        )
        self.assertEqual(page_link.call_count, 2)

    def test_assistant_answers_using_saved_profile_role_match(self):
        profile = {
            "education_level": "Undergraduate",
            "field_of_study": "Computer science",
            "skills": ["Python"],
            "interests": ["Software development"],
            "career_goal": "Become a developer",
        }
        match = recommend_careers(profile)[0]

        answer = career_assistant_answer("How can I improve my skills?", profile, [match])

        self.assertIn(match.career.title, answer)
        self.assertIn("missing skills", answer)

    def test_assistant_does_not_claim_to_personalize_without_profile(self):
        answer = career_assistant_answer("What career is right for me?", None, [])

        self.assertIn("complete your profile", answer)

    def test_chatbot_answers_eight_distinct_intents_relevantly(self):
        matches = recommend_careers(CHAT_PROFILE, limit=20)
        questions_and_expected = [
            ("Hi", ("Hi!", "What would you like")),
            ("Which career is good for me?", ("Data Analyst", "Data and analytics")),
            ("Which skills should I learn?", ("missing skills", "Communication")),
            ("How can I get a job?", ("resume", "projects")),
            ("What is SQL?", ("Structured Query Language", "SELECT name")),
            ("Which project should I build?", ("Data Analyst", "Analyze a public dataset")),
            (
                "Compare Data Analyst and Software Developer",
                ("Data Analyst:", "Software Developer:", "profile"),
            ),
            ("Compare Python vs SQL", ("Python", "SQL", "different skills")),
        ]

        answers = []
        for question, expected_fragments in questions_and_expected:
            with self.subTest(question=question):
                answer = career_assistant_answer(question, CHAT_PROFILE, matches)
                answers.append(answer)
                for fragment in expected_fragments:
                    self.assertIn(fragment.casefold(), answer.casefold())

        self.assertGreater(len(set(answers)), 6)

    def test_follow_up_why_uses_the_previous_career_question(self):
        matches = recommend_careers(CHAT_PROFILE, limit=20)
        history = [
            {"role": "user", "content": "Which career is good for me?"},
            {
                "role": "assistant",
                "content": career_assistant_answer(
                    "Which career is good for me?",
                    CHAT_PROFILE,
                    matches,
                ),
            },
        ]

        answer = career_assistant_answer("Why?", CHAT_PROFILE, matches, history)

        self.assertIn("Data Analyst", answer)
        self.assertIn("profile", answer)
        self.assertNotEqual(answer, history[-1]["content"])

    def test_follow_up_learn_first_uses_previous_career_context(self):
        matches = recommend_careers(CHAT_PROFILE, limit=20)
        history = [
            {"role": "user", "content": "Tell me about Software Developer"},
            {
                "role": "assistant",
                "content": "Software Developer uses Java and Web development.",
            },
        ]

        answer = career_assistant_answer(
            "What should I learn first?",
            CHAT_PROFILE,
            matches,
            history,
        )

        self.assertIn("Software Developer", answer)
        self.assertIn("1.", answer)
        self.assertIn("missing skills", answer)

    def test_follow_up_explain_more_expands_career_question(self):
        matches = recommend_careers(CHAT_PROFILE, limit=20)
        history = [
            {"role": "user", "content": "Which career is good for me?"},
            {
                "role": "assistant",
                "content": "Data Analyst is one catalog match based on SQL.",
            },
        ]

        answer = career_assistant_answer(
            "Explain more",
            CHAT_PROFILE,
            matches,
            history,
        )

        self.assertIn("Data Analyst", answer)
        self.assertIn("profile", answer)

    def test_follow_up_why_explains_the_previous_skill(self):
        matches = recommend_careers(CHAT_PROFILE, limit=20)
        history = [
            {"role": "user", "content": "What is SQL?"},
            {
                "role": "assistant",
                "content": career_assistant_answer(
                    "What is SQL?",
                    CHAT_PROFILE,
                    matches,
                ),
            },
        ]

        answer = career_assistant_answer("Why?", CHAT_PROFILE, matches, history)

        self.assertIn("SQL is useful", answer)
        self.assertIn("Data Analyst", answer)

    def test_follow_up_project_explanation_adds_steps_instead_of_repeating(self):
        matches = recommend_careers(CHAT_PROFILE, limit=20)
        history = [
            {"role": "user", "content": "Which project should I build?"},
            {
                "role": "assistant",
                "content": career_assistant_answer(
                    "Which project should I build?",
                    CHAT_PROFILE,
                    matches,
                ),
            },
        ]

        answer = career_assistant_answer(
            "Explain more",
            CHAT_PROFILE,
            matches,
            history,
        )

        self.assertIn("3.", answer)
        self.assertIn("README", answer)
        self.assertNotEqual(answer, history[-1]["content"])

    def test_groq_api_uses_profile_catalog_and_bearer_authentication(self):
        api_response = io.BytesIO(
            json.dumps(
                {"choices": [{"message": {"content": "A Groq career answer."}}]}
            ).encode("utf-8")
        )
        matches = recommend_careers(CHAT_PROFILE, limit=20)

        with (
            patch.dict(
                "os.environ",
                {"GROQ_API_KEY": "groq-test-key", "OPENAI_API_KEY": "openai-test-key"},
            ),
            patch.object(student_pages.st, "secrets", {}),
            patch("student_pages.urlopen", return_value=api_response) as mocked_urlopen,
        ):
            answer = generate_llm_answer("Which role fits me?", CHAT_PROFILE, [], matches)

        self.assertEqual(answer, "A Groq career answer.")
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "llama-3.3-70b-versatile")
        self.assertEqual(
            request.full_url,
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer groq-test-key")

    def test_openai_api_uses_profile_catalog_and_previous_turns(self):
        matches = recommend_careers(CHAT_PROFILE, limit=20)
        api_response = io.BytesIO(
            json.dumps(
                {"choices": [{"message": {"content": "A context-aware answer."}}]}
            ).encode("utf-8")
        )
        history = [{"role": "user", "content": "Which career is good for me?"}]

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch.object(student_pages.st, "secrets", {}),
            patch("student_pages.urlopen", return_value=api_response) as mocked_urlopen,
        ):
            answer = generate_llm_answer(
                "Why?",
                CHAT_PROFILE,
                history,
                matches,
            )

        self.assertEqual(answer, "A context-aware answer.")
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["messages"][3]["content"], history[0]["content"])
        self.assertIn("Data Analyst", payload["messages"][2]["content"])
        self.assertEqual(payload["messages"][4]["content"], "Why?")
        self.assertEqual(
            mocked_urlopen.call_args.args[0].get_header("Authorization"),
            "Bearer test-key",
        )
        self.assertTrue(
            mocked_urlopen.call_args.args[0].full_url.endswith(
                "/v1/chat/completions"
            )
        )

    def test_profile_signals_rank_relevant_path_and_find_skill_gap(self):
        profile = {
            "skills": ["SQL", "Data analysis", "Python"],
            "interests": ["Data and analytics", "Finance"],
            "field_of_study": "Commerce",
            "career_goal": "Become a data analyst",
        }

        matches = recommend_careers(profile)

        self.assertEqual(matches[0].career.title, "Data Analyst")
        self.assertEqual(matches[0].missing_skills, ("Communication",))
        self.assertGreater(matches[0].fit_score, matches[1].fit_score)
        self.assertEqual(matches[0].matched_context, ("data", "analyst"))

    def test_text_similarity_ranks_a_career_from_descriptive_goal_text(self):
        matches = recommend_careers(
            {"career_goal": "monitor systems and respond to incidents"}
        )

        self.assertEqual(matches[0].career.title, "Cybersecurity Analyst")
        self.assertGreater(matches[0].fit_score, 0)


    def test_interested_role_is_saved_as_a_recommendation_signal(self):
        matches = recommend_careers(
            {
                "interested_roles": ["UI/UX Designer"],
            }
        )

        self.assertEqual(matches[0].career.title, "UI/UX Designer")
        self.assertEqual(matches[0].matched_roles, ("UI/UX Designer",))
        self.assertGreater(matches[0].fit_score, matches[1].fit_score)

    def test_missing_skills_have_role_specific_improvement_guidance(self):
        match = recommend_careers(
            {
                "skills": ["SQL", "Data analysis", "Python"],
                "interests": ["Data and analytics", "Finance"],
            }
        )[0]

        guidance = recommend_skill_development(match)

        self.assertEqual([item.skill for item in guidance], ["Communication"])
        self.assertIn("Data Analyst", guidance[0].role_relevance)
        self.assertTrue(guidance[0].learning_topic)
        self.assertTrue(guidance[0].practice)

    def test_every_recommended_role_skill_has_improvement_guidance(self):
        for match in recommend_careers({}):
            with self.subTest(role=match.career.title):
                guidance = recommend_skill_development(match)

                self.assertEqual(
                    [item.skill for item in guidance],
                    list(match.missing_skills),
                )
                self.assertTrue(all(item.practice for item in guidance))

    def test_skill_improvement_flow_shows_learning_practice_and_evidence_steps(self):
        match = recommend_careers(CHAT_PROFILE)[0]
        recommendation = recommend_skill_development(match)[0]
        columns = [MagicMock() for _ in range(3)]
        captions = []
        markdown_calls = []

        with (
            patch.object(
                student_pages.st,
                "columns",
                return_value=columns,
            ) as columns_mock,
            patch.object(
                student_pages.st,
                "container",
                side_effect=lambda **kwargs: MagicMock(),
            ) as container,
            patch.object(
                student_pages.st,
                "caption",
                side_effect=captions.append,
            ),
            patch.object(
                student_pages.st,
                "markdown",
                side_effect=markdown_calls.append,
            ),
            patch.object(student_pages.st, "write") as write,
            patch.object(student_pages.st, "link_button") as link_button,
        ):
            render_skill_improvement_flow(
                recommendation,
                role_index=0,
                skill_index=1,
            )

        self.assertEqual(
            captions,
            [
                "STEP 01 · LEARN →",
                "STEP 02 · PRACTICE →",
                "STEP 03 · SHOW YOUR PROGRESS",
            ],
        )
        self.assertEqual(
            [call.kwargs["key"] for call in container.call_args_list],
            [
                f"skill-flow-learn-0-1-{recommendation.skill.lower()}",
                f"skill-flow-practice-0-1-{recommendation.skill.lower()}",
                f"skill-flow-show-0-1-{recommendation.skill.lower()}",
            ],
        )
        self.assertTrue(
            any(
                f"Build your foundation in {recommendation.skill}" in str(call)
                for call in markdown_calls
            )
        )
        self.assertTrue(
            any("Try it in a small task" in str(call) for call in markdown_calls)
        )
        self.assertTrue(
            any(
                "Keep evidence of what you learned" in str(call)
                for call in markdown_calls
            )
        )
        columns_mock.assert_called_once_with(
            3,
            vertical_alignment="top",
            gap="small",
        )
        link_button.assert_called_once()
        self.assertEqual(write.call_count, 3)

    def test_empty_profile_returns_bounded_starting_points(self):
        matches = recommend_careers({}, limit=2)

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].fit_score, 0)

    def test_learning_resource_link_encodes_topic(self):
        query = parse_qs(urlparse(learning_resource_url("Python data analysis")).query)

        self.assertEqual(query["query"], ["Python data analysis"])

    def test_fresher_job_link_uses_role_and_location(self):
        query = parse_qs(
            urlparse(job_search_url("Data Analyst", "Pune, India", True)).query
        )

        self.assertEqual(query["keywords"], ["Data Analyst entry level"])
        self.assertEqual(query["location"], ["Pune, India"])

    def test_indeed_job_link_uses_role_and_location(self):
        query = parse_qs(
            urlparse(indeed_job_search_url("Data Analyst", "Pune, India", True)).query
        )

        self.assertEqual(query["q"], ["Data Analyst entry level"])
        self.assertEqual(query["l"], ["Pune, India"])

    def test_job_page_shows_every_career_on_two_job_boards(self):
        account = {"id": "student-1"}
        matches = recommend_careers(CHAT_PROFILE, limit=len(CAREER_PATHS))
        link_buttons = []

        def make_columns(count, **kwargs):
            number_of_columns = count if isinstance(count, int) else len(count)
            return [MagicMock() for _ in range(number_of_columns)]

        with (
            patch.object(student_pages, "account_profile", return_value=CHAT_PROFILE),
            patch.object(student_pages, "page_header"),
            patch.object(
                student_pages.api_client,
                "recommend_careers",
                return_value=matches,
            ) as recommend,
            patch.object(student_pages.st, "info"),
            patch.object(student_pages.st, "caption"),
            patch.object(student_pages.st, "subheader"),
            patch.object(student_pages.st, "columns", side_effect=make_columns),
            patch.object(
                student_pages.st,
                "container",
                side_effect=lambda **kwargs: MagicMock(),
            ),
            patch.object(student_pages.st, "metric"),
            patch.object(student_pages.st, "markdown"),
            patch.object(student_pages.st, "write"),
            patch.object(student_pages.st, "progress"),
            patch.object(
                student_pages.st,
                "link_button",
                side_effect=lambda label, url, **kwargs: link_buttons.append(
                    (label, url)
                ),
            ),
        ):
            student_pages.render_jobs_page(account)

        recommend.assert_called_once_with(CHAT_PROFILE, limit=len(CAREER_PATHS))
        self.assertEqual(len(link_buttons), len(CAREER_PATHS) * 2)
        self.assertEqual(
            [label for label, _ in link_buttons].count("Search on LinkedIn"),
            len(CAREER_PATHS),
        )
        self.assertEqual(
            [label for label, _ in link_buttons].count("Search on Indeed"),
            len(CAREER_PATHS),
        )


class ProfileMigrationTests(unittest.TestCase):
    def test_initialize_database_adds_profile_fields_and_persists_role_choices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "career_agent.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        full_name TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                        password_hash TEXT NOT NULL,
                        password_salt TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE student_profiles (
                        account_id INTEGER PRIMARY KEY,
                        education_level TEXT NOT NULL,
                        field_of_study TEXT NOT NULL,
                        skills_json TEXT NOT NULL,
                        interests_json TEXT NOT NULL,
                        experience_years INTEGER NOT NULL,
                        career_goal TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                    );
                    INSERT INTO accounts
                        (full_name, email, password_hash, password_salt)
                    VALUES ('A Learner', 'learner@example.com', 'hash', 'salt');
                    INSERT INTO student_profiles
                        (account_id, education_level, field_of_study, skills_json,
                         interests_json, experience_years, career_goal)
                    VALUES (1, 'Undergraduate', 'Computer science', '["Python"]',
                            '["Artificial intelligence"]', 0, 'Become a developer');
                    """
                )

            with (
                patch.object(auth, "DB_PATH", database_path),
                patch.object(auth, "DATABASE_BACKEND", "sqlite"),
            ):
                auth.initialize_database()
                profile = auth.get_student_profile("1")

            self.assertEqual(profile["preferred_location"], "Remote")
            self.assertEqual(profile["experience_years"], 0)
            self.assertEqual(profile["interested_roles"], [])

            with (
                patch.object(auth, "DB_PATH", database_path),
                patch.object(auth, "DATABASE_BACKEND", "sqlite"),
            ):
                auth.save_student_profile(
                    "1",
                    "Undergraduate",
                    "Computer science",
                    ["Python"],
                    ["Artificial intelligence"],
                    0,
                    "Become a developer",
                    "Remote",
                    ["Software Developer"],
                )
                profile = auth.get_student_profile("1")

            self.assertEqual(profile["interested_roles"], ["Software Developer"])


if __name__ == "__main__":
    unittest.main()

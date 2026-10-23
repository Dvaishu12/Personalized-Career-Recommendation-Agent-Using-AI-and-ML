import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import auth
import api
from fastapi.testclient import TestClient


class FastAPIBackendTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerai-test.db"
        self.database_path_patch = patch.object(auth, "DB_PATH", self.database_path)
        self.database_backend_patch = patch.object(auth, "DATABASE_BACKEND", "sqlite")
        self.database_path_patch.start()
        self.database_backend_patch.start()
        api.sessions.clear()
        self.client = TestClient(api.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        api.sessions.clear()
        self.database_backend_patch.stop()
        self.database_path_patch.stop()
        self.temporary_directory.cleanup()

    def test_account_profile_recommendations_and_logout(self):
        registration = self.client.post(
            "/auth/register",
            json={
                "full_name": "Test Student",
                "email": "student@example.com",
                "password": "test-password-123",
                "confirm_password": "test-password-123",
            },
        )
        self.assertEqual(registration.status_code, 201)

        login = self.client.post(
            "/auth/login",
            json={"email": "student@example.com", "password": "test-password-123"},
        )
        self.assertEqual(login.status_code, 200)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        profile = {
            "education_level": "Undergraduate",
            "field_of_study": "Commerce",
            "skills": ["SQL", "Data analysis", "Python"],
            "interests": ["Data and analytics", "Finance"],
            "experience_years": 0,
            "career_goal": "Become a data analyst",
            "preferred_location": "Remote",
            "interested_roles": [],
        }
        saved = self.client.put("/profile", json=profile, headers=headers)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.client.get("/profile", headers=headers).json(), profile)

        recommendations = self.client.post(
            "/recommendations",
            json={"limit": 3},
            headers=headers,
        )
        self.assertEqual(recommendations.status_code, 200)
        self.assertEqual(recommendations.json()[0]["career"]["title"], "Data Analyst")

        generated_roadmap = {
            "steps": [
                {"topic": "SQL foundations", "objective": "Query a small dataset."},
                {"topic": "Python analysis", "objective": "Clean and inspect data."},
                {"topic": "Visualization", "objective": "Explain a useful finding."},
            ],
            "projects": ["Analyze a public dataset.", "Build a simple dashboard."],
        }
        with (
            patch.object(api, "_llm_configuration", return_value=("test-key", "test-model", "")),
            patch.object(
                api,
                "generate_llm_answer",
                return_value=json.dumps(generated_roadmap),
            ),
        ):
            roadmap = self.client.post(
                "/roadmap",
                json={"role": "Data Analyst"},
                headers=headers,
            )
        self.assertEqual(roadmap.status_code, 200)
        self.assertTrue(roadmap.json()["generated"])
        self.assertEqual(roadmap.json()["steps"][0]["topic"], "SQL foundations")

        with (
            patch.object(api, "_llm_configuration", return_value=("test-key", "test-model", "")),
            patch.object(api, "generate_llm_answer", return_value="not valid json"),
        ):
            fallback = self.client.post(
                "/roadmap",
                json={"role": "Data Analyst"},
                headers=headers,
            )
        self.assertEqual(fallback.status_code, 200)
        self.assertFalse(fallback.json()["generated"])
        self.assertEqual(len(fallback.json()["steps"]), 3)
        self.assertIsNotNone(fallback.json()["api_error"])

        logout = self.client.post("/auth/logout", headers=headers)
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/profile", headers=headers).status_code, 401)


if __name__ == "__main__":
    unittest.main()
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from unittest.mock import patch


@override_settings(DESKTOP_AUTO_AUTH=False)
class DesktopAccessTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(
        OWNER_ACCESS_TOKEN="", REQUIRE_OWNER_TOKEN=False,
        DESKTOP_MODE=True, DEMO_MODE=False,
    )
    def test_local_session_remains_private_with_demo_header(self):
        response = self.client.get("/api/session/", HTTP_X_DEMO_MODE="true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["mode"], "private")
        self.assertTrue(response.data["desktop"])
        self.assertFalse(response.data["demo_available"])

    @override_settings(OWNER_ACCESS_TOKEN="", REQUIRE_OWNER_TOKEN=False, DESKTOP_MODE=True, DEMO_MODE=False)
    def test_other_websites_cannot_trigger_local_actions(self):
        response = self.client.post(
            "/api/campaigns/", {"secteur": "restaurant", "ville": "Rennes", "rayon_km": 10},
            HTTP_ORIGIN="https://melui3.github.io",
        )
        self.assertEqual(response.status_code, 403)
        session = self.client.get("/api/session/", HTTP_ORIGIN="http://testserver")
        self.assertTrue(session.data["is_owner"])

    @override_settings(
        OWNER_ACCESS_TOKEN="local-test-token", REQUIRE_OWNER_TOKEN=True,
        DESKTOP_MODE=True, DEMO_MODE=False,
    )
    def test_configured_token_is_required_for_real_data(self):
        for headers in ({}, {"HTTP_X_OWNER_TOKEN": "wrong"}, {"HTTP_X_DEMO_MODE": "true"}):
            with self.subTest(headers=headers):
                response = self.client.get("/api/prospects/", **headers)
                self.assertEqual(response.status_code, 403)
        session = self.client.get("/api/session/", HTTP_X_OWNER_TOKEN="local-test-token")
        self.assertTrue(session.data["is_owner"])

    @override_settings(OWNER_ACCESS_TOKEN="", REQUIRE_OWNER_TOKEN=True, DEMO_MODE=False)
    def test_missing_required_token_fails_closed(self):
        response = self.client.get("/api/prospects/")
        self.assertEqual(response.status_code, 403)
        session = self.client.get("/api/session/")
        self.assertEqual(session.data["mode"], "locked")

    @override_settings(DESKTOP_MODE=True, DESKTOP_AUTO_AUTH=True, OWNER_ACCESS_TOKEN="", REQUIRE_OWNER_TOKEN=False, DEMO_MODE=False)
    @patch("prospection.private_config.desktop_access_token", return_value="test-windows-access")
    def test_automatic_desktop_key_is_required(self, token):
        self.assertEqual(self.client.get("/api/personal/contacts/").status_code, 403)
        session = self.client.get("/api/session/")
        self.assertTrue(session.data["auth_required"])
        self.assertFalse(session.data["is_owner"])
        session = self.client.get("/api/session/", HTTP_X_OWNER_TOKEN="test-windows-access")
        self.assertTrue(session.data["is_owner"])

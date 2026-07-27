import unittest
from unittest.mock import Mock, patch

from halo import HaloAPIError, HaloMemoryClient, MEMORY_RETRIEVE_FUNCTION_NAME


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text if text is not None else str(self._payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class HaloMemoryClientTest(unittest.TestCase):
    @patch("halo.client.requests.Session")
    def test_execute_retrieve_function_posts_expected_payload(self, session_class):
        session = Mock()
        session.post.return_value = FakeResponse(payload={"ok": True})
        session_class.return_value = session

        client = HaloMemoryClient(
            api_key="sk-test",
            project_key="project-a",
            halo_url="https://halo.test/",
            timeout=12,
        )
        result = client.execute_retrieve_function(
            end_user_key="end-user-1",
            session_data={"messages": [{"role": "user", "content": "hello"}]},
            limit=7,
            cursor="cursor-1",
            query="hello",
        )

        args, kwargs = session.post.call_args
        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            args[0],
            "https://halo.test/api/v1/memory/functions/halo_retrieve_end_user_memory",
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(kwargs["headers"]["x-halo-sdk"], "halo-python-sdk")
        self.assertEqual(kwargs["timeout"], 12)
        self.assertEqual(
            kwargs["json"],
            {
                "projectKey": "project-a",
                "endUserKey": "end-user-1",
                "arguments": {
                    "sessionData": {
                        "messages": [{"role": "user", "content": "hello"}]
                    },
                    "limit": 7,
                    "cursor": "cursor-1",
                    "query": "hello",
                },
            },
        )

    @patch("halo.client.requests.Session")
    def test_capture_posts_request_and_response_raw(self, session_class):
        session = Mock()
        session.post.return_value = FakeResponse(payload={"captured": True})
        session_class.return_value = session

        client = HaloMemoryClient(api_key="sk-test", project_key="project-a")
        result = client.capture(
            end_user_key="end-user-1",
            request_raw={"messages": [{"role": "user", "content": "remember this"}]},
            response_raw={"role": "assistant", "content": "saved"},
        )

        args, kwargs = session.post.call_args
        self.assertEqual(result, {"captured": True})
        self.assertEqual(args[0], "https://api.agihalo.com/api/v1/memory/capture")
        self.assertEqual(
            kwargs["json"],
            {
                "projectKey": "project-a",
                "endUserKey": "end-user-1",
                "requestRaw": {
                    "messages": [{"role": "user", "content": "remember this"}]
                },
                "responseRaw": {"role": "assistant", "content": "saved"},
            },
        )

    @patch("halo.client.requests.Session")
    def test_retrieve_posts_direct_inspection_payload(self, session_class):
        session = Mock()
        session.post.return_value = FakeResponse(payload={"rawEntries": []})
        session_class.return_value = session

        client = HaloMemoryClient(api_key="sk-test", project_key="project-a")
        result = client.retrieve(
            end_user_key="end-user-1",
            topics=("report_preferences", "profile"),
            query="weekly report",
            limit=3,
            cursor="cursor-2",
            include_raw=False,
            include_disabled_topics=True,
        )

        args, kwargs = session.post.call_args
        self.assertEqual(result, {"rawEntries": []})
        self.assertEqual(args[0], "https://api.agihalo.com/api/v1/memory/retrieve")
        self.assertEqual(
            kwargs["json"],
            {
                "projectKey": "project-a",
                "endUserKey": "end-user-1",
                "limit": 3,
                "includeRaw": False,
                "includeDisabledTopics": True,
                "topics": ["report_preferences", "profile"],
                "query": "weekly report",
                "cursor": "cursor-2",
            },
        )

    def test_validation_errors_are_explicit(self):
        with self.assertRaises(ValueError):
            HaloMemoryClient(api_key="", project_key="project-a")
        with self.assertRaises(ValueError):
            HaloMemoryClient(api_key="sk-test", project_key="sk-not-a-project")

        client = HaloMemoryClient(api_key="sk-test", project_key="project-a")
        with self.assertRaises(ValueError):
            client.execute_retrieve_function("end-user-1", None)
        with self.assertRaises(ValueError):
            client.capture("end-user-1")
        with self.assertRaises(ValueError):
            client.capture(
                "end-user-1",
                session_data={"messages": []},
            )
        with self.assertRaises(ValueError):
            client.retrieve("end-user-1", topics="profile")
        with self.assertRaises(ValueError):
            client.retrieve("end-user-1", topics=["profile", ""])

    @patch("halo.client.requests.Session")
    def test_non_success_response_raises_halo_api_error(self, session_class):
        session = Mock()
        session.post.return_value = FakeResponse(
            status_code=400,
            payload={"error": "sessionData is required"},
        )
        session_class.return_value = session

        client = HaloMemoryClient(api_key="sk-test", project_key="project-a")

        with self.assertRaises(HaloAPIError) as error:
            client.execute_retrieve_function("end-user-1", {"messages": []})

        self.assertEqual(str(error.exception), "sessionData is required")
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.response_body, {"error": "sessionData is required"})

    def test_function_declaration_exports_expected_shape(self):
        declaration = HaloMemoryClient.function_declaration()

        self.assertEqual(declaration["name"], MEMORY_RETRIEVE_FUNCTION_NAME)
        self.assertIn("sessionData", declaration["parameters"]["properties"])
        self.assertIn("sessionData", declaration["parameters"]["required"])

    @patch("halo.client.requests.Session")
    def test_delete_and_oauth_connection_helpers(self, session_class):
        session = Mock()
        session.post.return_value = FakeResponse(payload={"ok": True})
        session.put.return_value = FakeResponse(payload={"ok": True})
        session.get.return_value = FakeResponse(payload={"ok": True})
        session_class.return_value = session

        client = HaloMemoryClient(
            api_key="sk-test",
            project_key="oem project",
            halo_url="https://halo.test",
        )

        client.delete_topic(
            end_user_key="end-user-1",
            topic_key="profile",
            include_raw=False,
        )
        client.list_connectors()
        client.register_oauth_provider(
            provider_key="google",
            client_id="google-client",
            client_secret="google-secret",
            redirect_uri=(
                "https://connect.oem.test/"
                "api/v1/memory/oauth/callback/google"
            ),
        )
        client.register_oauth_return_uri(
            return_uri="oemapp://oauth/complete",
            completion_mode="mobile_deep_link",
        )
        client.start_oauth(
            scope_id="scope-1",
            connector_id="google.calendar",
            completion_mode="mobile_deep_link",
            return_uri="oemapp://oauth/complete",
        )
        client.refresh_connection("scope-1", "connection-1")

        post_args, post_kwargs = session.post.call_args_list[0]
        self.assertEqual(
            post_args[0],
            "https://halo.test/api/v1/memory/delete",
        )
        self.assertEqual(
            post_kwargs["json"],
            {
                "projectKey": "oem project",
                "target": "topic",
                "endUserKey": "end-user-1",
                "topicKey": "profile",
                "includeRaw": False,
            },
        )

        get_args, _ = session.get.call_args
        self.assertEqual(
            get_args[0],
            (
                "https://halo.test/api/v1/memory/projects/"
                "oem%20project/connectors"
            ),
        )

        put_args, put_kwargs = session.put.call_args
        self.assertEqual(
            put_args[0],
            (
                "https://halo.test/api/v1/memory/projects/"
                "oem%20project/oauth/providers/google"
            ),
        )
        self.assertEqual(
            put_kwargs["json"],
            {
                "clientId": "google-client",
                "clientSecret": "google-secret",
                "redirectUri": (
                    "https://connect.oem.test/"
                    "api/v1/memory/oauth/callback/google"
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()

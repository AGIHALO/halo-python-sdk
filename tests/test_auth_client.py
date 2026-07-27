import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock

from halo import HaloAPIError, HaloAuthClient, HaloOAuthClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text if text is not None else str(self._payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class HaloAuthClientTest(unittest.TestCase):
    def test_project_authentication_requests_and_provider_pkce(self):
        session = Mock()
        session.request.return_value = FakeResponse(
            payload={"access_token": "access-1"}
        )
        auth = HaloAuthClient(
            publishable_key="pk-project",
            halo_url="https://halo.test/",
            session=session,
        )

        auth.sign_up(
            email="user@example.com",
            password="Secret123!",
            display_name="Ada",
            redirect_to="https://app.example.com/auth/confirmed",
            data={"locale": "ko"},
        )
        auth.sign_in_with_password("user@example.com", "Secret123!")
        auth.refresh_session("refresh-1")
        auth.get_user("access-1")
        auth.logout("access-1")

        first_args, first_kwargs = session.request.call_args_list[0]
        self.assertEqual(first_args[0], "POST")
        self.assertEqual(
            first_args[1], "https://halo.test/api/v1/auth/signup"
        )
        self.assertEqual(first_kwargs["headers"]["apikey"], "pk-project")
        self.assertEqual(
            first_kwargs["headers"]["x-halo-sdk"], "halo-python-sdk"
        )
        self.assertEqual(
            first_kwargs["json"],
            {
                "email": "user@example.com",
                "password": "Secret123!",
                "display_name": "Ada",
                "redirect_to": "https://app.example.com/auth/confirmed",
                "data": {"locale": "ko"},
            },
        )

        provider_url = urlparse(
            auth.build_provider_authorize_url(
                provider="google",
                redirect_to="https://app.example.com/auth/callback",
                code_challenge="challenge-1",
                state="state-1",
            )
        )
        provider_query = parse_qs(provider_url.query)
        self.assertEqual(
            provider_url.path,
            "/api/v1/auth/providers/google/authorize",
        )
        self.assertEqual(provider_query["apikey"], ["pk-project"])
        self.assertEqual(
            provider_query["code_challenge_method"], ["S256"]
        )

    def test_service_oauth_requests(self):
        session = Mock()
        session.request.return_value = FakeResponse(payload={"ok": True})
        oauth = HaloOAuthClient(
            client_id="halo_client_1",
            client_secret="secret-1",
            halo_url="https://halo.test",
            session=session,
        )

        authorize_url = urlparse(
            oauth.build_authorize_url(
                redirect_uri="https://service.example.com/callback",
                scopes=["profile", "email"],
                state="state-1",
                code_challenge="challenge-1",
            )
        )
        self.assertEqual(
            parse_qs(authorize_url.query)["scope"],
            ["profile email"],
        )

        oauth.authorize(
            access_token="project-user-token",
            redirect_uri="https://service.example.com/callback",
            scopes=["profile", "email"],
            state="state-1",
            code_challenge="challenge-1",
        )
        oauth.exchange_code(
            code="halo-code",
            redirect_uri="https://service.example.com/callback",
            code_verifier="verifier-1",
        )
        oauth.refresh_token("oauth-refresh")
        oauth.get_user_info("oauth-access")

        authorize_args, authorize_kwargs = session.request.call_args_list[0]
        self.assertEqual(
            authorize_args[1],
            "https://halo.test/api/v1/auth/oauth/authorize",
        )
        self.assertEqual(
            authorize_kwargs["headers"]["Authorization"],
            "Bearer project-user-token",
        )

        _, exchange_kwargs = session.request.call_args_list[1]
        self.assertEqual(
            exchange_kwargs["json"],
            {
                "grant_type": "authorization_code",
                "client_id": "halo_client_1",
                "code": "halo-code",
                "redirect_uri": "https://service.example.com/callback",
                "client_secret": "secret-1",
                "code_verifier": "verifier-1",
            },
        )

    def test_authentication_error_code_is_retained(self):
        session = Mock()
        session.request.return_value = FakeResponse(
            status_code=429,
            payload={
                "error": "Too many authentication requests",
                "code": "AUTH_RATE_LIMIT_EXCEEDED",
            },
        )
        auth = HaloAuthClient(
            publishable_key="pk-project",
            session=session,
        )

        with self.assertRaises(HaloAPIError) as context:
            auth.sign_in_with_password("user@example.com", "secret")

        self.assertEqual(context.exception.status_code, 429)
        self.assertEqual(
            context.exception.code,
            "AUTH_RATE_LIMIT_EXCEEDED",
        )


if __name__ == "__main__":
    unittest.main()

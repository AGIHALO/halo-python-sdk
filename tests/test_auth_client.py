import base64
import hashlib
import json
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock

from halo import (
    HaloAPIError,
    HaloAuthClient,
    HaloOAuthClient,
    __version__,
    create_client,
    generate_oauth_state,
    generate_pkce_pair,
)


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
        auth.get_settings()
        auth.get_jwks()
        auth.request_password_recovery(
            "user@example.com",
            "https://app.example.com/auth/recovery",
        )
        auth.reset_password("recovery-token", "NewSecret123!")

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
            first_kwargs["headers"]["x-halo-sdk-version"], __version__
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

        pkce = generate_pkce_pair()
        state = generate_oauth_state()
        provider_url = urlparse(
            auth.build_provider_authorize_url(
                provider="google",
                redirect_to="https://app.example.com/auth/callback",
                code_challenge=pkce.challenge,
                state=state,
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
        self.assertEqual(provider_query["state"], [state])

        auth.exchange_provider_code(
            code="provider-code",
            code_verifier=pkce.verifier,
            redirect_to="https://app.example.com/auth/callback",
        )
        exchange_args, exchange_kwargs = session.request.call_args_list[-1]
        self.assertEqual(
            exchange_args[1],
            "https://halo.test/api/v1/auth/providers/token",
        )
        self.assertEqual(
            exchange_kwargs["json"],
            {
                "code": "provider-code",
                "code_verifier": pkce.verifier,
                "redirect_to": "https://app.example.com/auth/callback",
            },
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

        pkce = generate_pkce_pair()
        authorize_url = urlparse(
            oauth.build_authorize_url(
                redirect_uri="https://service.example.com/callback",
                scopes=["profile", "email"],
                state="state-1",
                code_challenge=pkce.challenge,
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
            code_challenge=pkce.challenge,
        )
        oauth.exchange_code(
            code="halo-code",
            redirect_uri="https://service.example.com/callback",
            code_verifier=pkce.verifier,
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
                "code_verifier": pkce.verifier,
            },
        )

    def test_pkce_and_oauth_state_helpers_match_production_contract(self):
        pkce = generate_pkce_pair()
        expected_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(pkce.verifier.encode("ascii")).digest()
            )
            .rstrip(b"=")
            .decode("ascii")
        )

        self.assertGreaterEqual(len(pkce.verifier), 43)
        self.assertLessEqual(len(pkce.verifier), 128)
        self.assertEqual(len(pkce.challenge), 43)
        self.assertEqual(pkce.challenge, expected_challenge)
        self.assertGreaterEqual(len(generate_oauth_state()), 22)

        auth = HaloAuthClient(publishable_key="pk-project")
        with self.assertRaisesRegex(ValueError, "43-character"):
            auth.build_provider_authorize_url(
                provider="google",
                redirect_to="https://app.example.com/auth/callback",
                code_challenge="not-a-valid-challenge",
            )
        with self.assertRaisesRegex(ValueError, "43-128"):
            auth.exchange_provider_code(
                code="provider-code",
                code_verifier="too-short",
                redirect_to="https://app.example.com/auth/callback",
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

    def test_create_client_manages_supabase_style_auth_session(self):
        user = {
            "id": "user-1",
            "projectId": "project-1",
            "email": "user@example.com",
        }

        def make_session(suffix):
            return {
                "access_token": f"access-{suffix}",
                "refresh_token": f"refresh-{suffix}",
                "token_type": "bearer",
                "expires_in": 3600,
                "expires_at": "2099-07-30T01:00:00.000Z",
                "user": user,
                "session": {
                    "id": f"session-{suffix}",
                    "projectId": "project-1",
                    "authUserId": "user-1",
                },
            }

        request_session = Mock()
        request_session.request.side_effect = [
            FakeResponse(payload=make_session("1")),
            FakeResponse(payload={"user": user}),
            FakeResponse(payload=make_session("2")),
            FakeResponse(payload={}),
        ]
        storage = {}
        halo = create_client(
            "https://halo.test/",
            "pk-project",
            {
                "session": request_session,
                "auth": {
                    "auto_refresh_token": False,
                    "persist_session": True,
                    "storage": storage,
                    "storage_key": "test-halo-session",
                },
            },
        )
        events = []
        subscription = halo.auth.on_auth_state_change(
            lambda event, _: events.append(event)
        )

        signed_in = halo.auth.sign_in_with_password(
            {
                "email": "user@example.com",
                "password": "Secret123!",
            }
        )
        self.assertEqual(signed_in["access_token"], "access-1")
        self.assertEqual(
            json.loads(storage["test-halo-session"])["refresh_token"],
            "refresh-1",
        )
        self.assertEqual(
            halo.auth.get_session()["access_token"],
            "access-1",
        )
        self.assertEqual(halo.auth.get_user()["user"]["id"], "user-1")
        refreshed = halo.auth.refresh_session()
        self.assertEqual(refreshed["refresh_token"], "refresh-2")
        halo.auth.sign_out()
        self.assertNotIn("test-halo-session", storage)
        self.assertEqual(
            events,
            [
                "INITIAL_SESSION",
                "SIGNED_IN",
                "TOKEN_REFRESHED",
                "SIGNED_OUT",
            ],
        )
        subscription.unsubscribe()

        get_user_call = request_session.request.call_args_list[1]
        self.assertEqual(
            get_user_call.kwargs["headers"]["apikey"],
            "pk-project",
        )
        self.assertEqual(
            get_user_call.kwargs["headers"]["Authorization"],
            "Bearer access-1",
        )
        logout_call = request_session.request.call_args_list[3]
        self.assertEqual(
            logout_call.kwargs["headers"]["apikey"],
            "pk-project",
        )
        self.assertEqual(
            logout_call.kwargs["headers"]["Authorization"],
            "Bearer access-2",
        )


if __name__ == "__main__":
    unittest.main()

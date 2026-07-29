import base64
import hashlib
import re
import secrets
from typing import NamedTuple
from urllib.parse import urlencode

import requests

from .client import DEFAULT_HALO_URL, HaloAPIError
from .version import __version__


HALO_SDK_NAME = "halo-python-sdk"
_PKCE_CHALLENGE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_PKCE_VERIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")


class HaloPkcePair(NamedTuple):
    """S256 PKCE values that must be kept together for one authorization flow."""

    verifier: str
    challenge: str


def generate_pkce_pair():
    """Generate an RFC 7636 verifier and its S256 base64url challenge."""

    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        )
        .rstrip(b"=")
        .decode("ascii")
    )
    return HaloPkcePair(verifier=verifier, challenge=challenge)


def generate_oauth_state(byte_length=32):
    """Generate opaque state for binding an OAuth callback to its request."""

    if (
        not isinstance(byte_length, int)
        or isinstance(byte_length, bool)
        or byte_length < 16
        or byte_length > 128
    ):
        raise ValueError("byte_length must be an integer between 16 and 128")
    return secrets.token_urlsafe(byte_length)


def _required_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def _optional_string(value):
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _optional_bounded_string(value, field_name, max_length):
    cleaned = _optional_string(value)
    if cleaned is not None and len(cleaned) > max_length:
        raise ValueError(
            f"{field_name} must be {max_length} characters or less"
        )
    return cleaned


def _required_pkce_challenge(value):
    challenge = _required_string(value, "code_challenge")
    if not _PKCE_CHALLENGE_PATTERN.fullmatch(challenge):
        raise ValueError(
            "code_challenge must be a 43-character S256 base64url value"
        )
    return challenge


def _required_pkce_verifier(value):
    verifier = _required_string(value, "code_verifier")
    if not _PKCE_VERIFIER_PATTERN.fullmatch(verifier):
        raise ValueError(
            "code_verifier must be 43-128 RFC 7636 unreserved characters"
        )
    return verifier


def _clean_scopes(scopes):
    if (
        not isinstance(scopes, (list, tuple))
        or not scopes
        or any(not _optional_string(scope) for scope in scopes)
    ):
        raise ValueError("scopes must be a non-empty list of non-empty strings")
    return [scope.strip() for scope in scopes]


class _HaloJsonClient:
    def __init__(self, halo_url=DEFAULT_HALO_URL, timeout=30, session=None):
        self.halo_url = _required_string(halo_url, "halo_url").rstrip("/")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self.timeout = timeout
        self.session = session or requests.Session()

    def _request(self, method, path, headers=None, payload=None):
        request_headers = {
            "Accept": "application/json",
            "x-halo-sdk": HALO_SDK_NAME,
            "x-halo-sdk-version": __version__,
        }
        request_headers.update(headers or {})
        if payload is not None:
            request_headers["Content-Type"] = "application/json"

        try:
            response = self.session.request(
                method,
                f"{self.halo_url}{path}",
                headers=request_headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise HaloAPIError(f"Halo API request failed: {exc}") from exc

        response_text = getattr(response, "text", "") or ""
        try:
            body = response.json()
        except ValueError:
            body = response_text
            if 200 <= response.status_code < 300 and response_text.strip():
                raise HaloAPIError(
                    "Halo API response was not valid JSON",
                    status_code=response.status_code,
                    response_body=body,
                )
            if 200 <= response.status_code < 300:
                return None

        if response.status_code < 200 or response.status_code >= 300:
            message = (
                str(body["error"])
                if isinstance(body, dict) and body.get("error") is not None
                else (
                    f"Halo API request failed with status "
                    f"{response.status_code}: {body}"
                    if body
                    else f"Halo API request failed with status {response.status_code}"
                )
            )
            error = HaloAPIError(
                message,
                status_code=response.status_code,
                response_body=body,
                code=body.get("code") if isinstance(body, dict) else None,
            )
            raise error

        return body


class HaloAuthClient(_HaloJsonClient):
    """Public Project Authentication client for OEM and application users."""

    def __init__(
        self,
        publishable_key,
        halo_url=DEFAULT_HALO_URL,
        timeout=30,
        session=None,
    ):
        super().__init__(halo_url=halo_url, timeout=timeout, session=session)
        self.publishable_key = _required_string(
            publishable_key, "publishable_key"
        )

    def get_settings(self):
        return self._auth_request("GET", "/api/v1/auth/settings")

    def get_jwks(self):
        return self._auth_request(
            "GET", "/api/v1/auth/.well-known/jwks.json"
        )

    def sign_up(
        self,
        email,
        password,
        display_name=None,
        redirect_to=None,
        data=None,
    ):
        payload = {
            "email": _required_string(email, "email"),
            "password": _required_string(password, "password"),
        }
        if _optional_string(display_name):
            payload["display_name"] = display_name.strip()
        if _optional_string(redirect_to):
            payload["redirect_to"] = redirect_to.strip()
        if data is not None:
            payload["data"] = data
        return self._auth_request("POST", "/api/v1/auth/signup", payload=payload)

    def sign_in_with_password(self, email, password):
        return self._auth_request(
            "POST",
            "/api/v1/auth/token?grant_type=password",
            payload={
                "email": _required_string(email, "email"),
                "password": _required_string(password, "password"),
            },
        )

    def refresh_session(self, refresh_token):
        return self._auth_request(
            "POST",
            "/api/v1/auth/token?grant_type=refresh_token",
            payload={
                "refresh_token": _required_string(
                    refresh_token, "refresh_token"
                )
            },
        )

    def get_user(self, access_token):
        return self._auth_request(
            "GET",
            "/api/v1/auth/user",
            access_token=access_token,
        )

    def logout(self, access_token):
        return self._auth_request(
            "POST",
            "/api/v1/auth/logout",
            payload={},
            access_token=access_token,
        )

    def request_password_recovery(self, email, redirect_to=None):
        payload = {"email": _required_string(email, "email")}
        if _optional_string(redirect_to):
            payload["redirect_to"] = redirect_to.strip()
        return self._auth_request(
            "POST", "/api/v1/auth/recover", payload=payload
        )

    def reset_password(self, token, password):
        return self._auth_request(
            "POST",
            "/api/v1/auth/password/reset",
            payload={
                "token": _required_string(token, "token"),
                "password": _required_string(password, "password"),
            },
        )

    def build_provider_authorize_url(
        self,
        provider,
        redirect_to,
        code_challenge,
        state=None,
    ):
        query = {
            "apikey": self.publishable_key,
            "redirect_to": _required_string(redirect_to, "redirect_to"),
            "code_challenge": _required_pkce_challenge(code_challenge),
            "code_challenge_method": "S256",
        }
        normalized_state = _optional_bounded_string(
            state, "state", 1024
        )
        if normalized_state:
            query["state"] = normalized_state
        provider_key = _required_string(provider, "provider")
        return (
            f"{self.halo_url}/api/v1/auth/providers/"
            f"{requests.utils.quote(provider_key, safe='')}/authorize?"
            f"{urlencode(query)}"
        )

    def exchange_provider_code(self, code, code_verifier, redirect_to):
        return self._auth_request(
            "POST",
            "/api/v1/auth/providers/token",
            payload={
                "code": _required_string(code, "code"),
                "code_verifier": _required_pkce_verifier(code_verifier),
                "redirect_to": _required_string(
                    redirect_to, "redirect_to"
                ),
            },
        )

    def _auth_request(
        self,
        method,
        path,
        payload=None,
        access_token=None,
    ):
        headers = {"apikey": self.publishable_key}
        if access_token is not None:
            headers["Authorization"] = (
                f"Bearer {_required_string(access_token, 'access_token')}"
            )
        return self._request(method, path, headers=headers, payload=payload)


class HaloOAuthClient(_HaloJsonClient):
    """OAuth client for Services registered in a HALO project."""

    def __init__(
        self,
        client_id,
        client_secret=None,
        halo_url=DEFAULT_HALO_URL,
        timeout=30,
        session=None,
    ):
        super().__init__(halo_url=halo_url, timeout=timeout, session=session)
        self.client_id = _required_string(client_id, "client_id")
        self.client_secret = _optional_string(client_secret)

    def build_authorize_url(
        self,
        redirect_uri,
        scopes,
        state=None,
        code_challenge=None,
    ):
        query = {
            "client_id": self.client_id,
            "redirect_uri": _required_string(redirect_uri, "redirect_uri"),
            "scope": " ".join(_clean_scopes(scopes)),
        }
        normalized_state = _optional_bounded_string(state, "state", 512)
        if normalized_state:
            query["state"] = normalized_state
        if _optional_string(code_challenge):
            query["code_challenge"] = _required_pkce_challenge(
                code_challenge
            )
            query["code_challenge_method"] = "S256"
        return f"{self.halo_url}/api/v1/auth/oauth/authorize?{urlencode(query)}"

    def get_authorization_details(self, redirect_uri, scopes):
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": _required_string(
                    redirect_uri, "redirect_uri"
                ),
                "scope": " ".join(_clean_scopes(scopes)),
            }
        )
        return self._request(
            "GET", f"/api/v1/auth/oauth/authorize?{query}"
        )

    def authorize(
        self,
        access_token,
        redirect_uri,
        scopes,
        state=None,
        code_challenge=None,
    ):
        payload = {
            "client_id": self.client_id,
            "redirect_uri": _required_string(redirect_uri, "redirect_uri"),
            "scopes": _clean_scopes(scopes),
        }
        normalized_state = _optional_bounded_string(state, "state", 512)
        if normalized_state:
            payload["state"] = normalized_state
        if _optional_string(code_challenge):
            payload["code_challenge"] = _required_pkce_challenge(
                code_challenge
            )
            payload["code_challenge_method"] = "S256"
        return self._request(
            "POST",
            "/api/v1/auth/oauth/authorize",
            headers={
                "Authorization": (
                    f"Bearer {_required_string(access_token, 'access_token')}"
                )
            },
            payload=payload,
        )

    def exchange_code(self, code, redirect_uri, code_verifier=None):
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": _required_string(code, "code"),
            "redirect_uri": _required_string(redirect_uri, "redirect_uri"),
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret
        if _optional_string(code_verifier):
            payload["code_verifier"] = _required_pkce_verifier(
                code_verifier
            )
        return self._request(
            "POST", "/api/v1/auth/oauth/token", payload=payload
        )

    def refresh_token(self, refresh_token):
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": _required_string(
                refresh_token, "refresh_token"
            ),
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret
        return self._request(
            "POST", "/api/v1/auth/oauth/token", payload=payload
        )

    def get_user_info(self, access_token):
        return self._request(
            "GET",
            "/api/v1/auth/oauth/userinfo",
            headers={
                "Authorization": (
                    f"Bearer {_required_string(access_token, 'access_token')}"
                )
            },
        )

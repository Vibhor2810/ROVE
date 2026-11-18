import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import settings
from app.main import app


class _FakeJWKS:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        class K:  # noqa
            pass
        k = K()
        k.key = self.key.public_key()
        return k


@pytest.fixture
def ec_key(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(security, "_jwks_client", lambda: _FakeJWKS(key))
    return key


def mint(key, alg="ES256", **over):
    claims = {"sub": "user-1", "email": "a@b.c", "aud": "authenticated", "exp": int(time.time()) + 300}
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg)


def test_valid_es256_token(ec_key):
    u = security.verify_token(mint(ec_key))
    assert u.id == "user-1"


def test_expired_rejected(ec_key):
    with pytest.raises(HTTPException) as e:
        security.verify_token(mint(ec_key, exp=int(time.time()) - 10))
    assert e.value.status_code == 401


def test_wrong_audience_rejected(ec_key):
    with pytest.raises(HTTPException) as e:
        security.verify_token(mint(ec_key, aud="anon"))
    assert e.value.status_code == 401


def test_missing_sub_rejected(ec_key):
    with pytest.raises(HTTPException) as e:
        security.verify_token(mint(ec_key, sub=None))
    assert e.value.status_code == 401


def test_wrong_signature_rejected(ec_key):
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(HTTPException) as e:
        security.verify_token(mint(other))
    assert e.value.status_code == 401


def test_alg_none_rejected(ec_key):
    tok = jwt.encode({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 99}, None, algorithm="none")
    with pytest.raises(HTTPException) as e:
        security.verify_token(tok)
    assert e.value.status_code == 401


def test_garbage_rejected(ec_key):
    with pytest.raises(HTTPException) as e:
        security.verify_token("not.a.jwt")
    assert e.value.status_code == 401


def test_hs256_requires_secret(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
    tok = jwt.encode({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 99}, "s" * 32, algorithm="HS256")
    with pytest.raises(HTTPException) as e:
        security.verify_token(tok)
    assert e.value.status_code == 503


def test_hs256_with_secret(monkeypatch):
    secret = "s" * 32
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", secret)
    tok = jwt.encode({"sub": "u9", "aud": "authenticated", "exp": int(time.time()) + 99}, secret, algorithm="HS256")
    assert security.verify_token(tok).id == "u9"


def test_hs256_wrong_secret(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "s" * 32)
    tok = jwt.encode({"sub": "u9", "aud": "authenticated", "exp": int(time.time()) + 99}, "x" * 32, algorithm="HS256")
    with pytest.raises(HTTPException) as e:
        security.verify_token(tok)
    assert e.value.status_code == 401


client = TestClient(app)


@pytest.mark.parametrize("path", ["/api/auth/me", "/api/music/search", "/api/library/sets", "/api/library/favorites"])
def test_protected_routes_need_token(path):
    assert client.get(path).status_code == 401


def test_bearer_with_junk_token_is_401_not_accepted():
    r = client.get("/api/library/sets", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 401


def test_valid_jwt_but_not_member_is_403(ec_key, monkeypatch):
    async def no(_user):
        return False
    monkeypatch.setattr("app.database.client.is_member", no)
    r = client.get("/api/library/sets", headers={"Authorization": f"Bearer {mint(ec_key)}"})
    assert r.status_code == 403


def test_member_passes_gate(ec_key, monkeypatch):
    async def yes(_user):
        return True
    async def fake_rest(*a, **k):
        return []
    monkeypatch.setattr("app.database.client.is_member", yes)
    monkeypatch.setattr("app.api.library.rest", fake_rest)
    r = client.get("/api/library/sets", headers={"Authorization": f"Bearer {mint(ec_key)}"})
    assert r.status_code == 200 and r.json() == {"sets": []}


def test_invite_validate_rejects_bad_format():
    assert client.post("/api/invitations/validate", json={"code": "a b;--"}).status_code == 422


def test_song_request_validation_and_store(ec_key, monkeypatch):
    async def yes(_u): return True
    saved = {}
    async def fake_rest(method, path, token, **k):
        saved.update(path=path, json=k.get("json")); return None
    monkeypatch.setattr("app.database.client.is_member", yes)
    monkeypatch.setattr("app.api.library.rest", fake_rest)
    h = {"Authorization": f"Bearer {mint(ec_key)}"}
    assert client.post("/api/library/requests", json={"text": "x"}, headers=h).status_code == 422
    r = client.post("/api/library/requests", json={"text": " Naacho Naacho ", "language": "Hindi"}, headers=h)
    assert r.status_code == 200 and saved["json"]["text"] == "Naacho Naacho" and saved["json"]["user_id"] == "user-1"
    assert client.post("/api/library/requests", json={"text": "hello"}).status_code == 401

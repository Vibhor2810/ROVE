"""LOCAL TEST STAND-INS for Supabase (auth + PostgREST + RPC) and Jamendo.
Not a real Supabase or Jamendo. Used only to exercise RØVE's real frontend and
backend end-to-end without external network access."""
import base64, json, time, uuid
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
KEY = ec.derive_private_key(0xC0FFEE1234567, ec.SECP256R1())  # fixed key so backend JWKS cache stays valid across resets
PUB = KEY.public_key().public_numbers()
b64 = lambda n: base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode()
USERS: dict[str, dict] = {}       # email -> {id, password}
INVITES = {"ROVE-FRIENDS-01": None, "ROVE-FRIENDS-02": None}  # code -> used_by
MEMBERS: set[str] = set()
T = {"rove_song_requests": [], "rove_sets": [], "rove_favorites": [], "rove_play_history": []}
HOST = "http://127.0.0.1:54321"


def session_for(uid: str, email: str):
    exp = int(time.time()) + 3600
    tok = jwt.encode({"sub": uid, "email": email, "aud": "authenticated", "role": "authenticated", "exp": exp},
                     KEY, algorithm="ES256", headers={"kid": "k1"})
    user = {"id": uid, "aud": "authenticated", "email": email, "app_metadata": {}, "user_metadata": {},
            "created_at": "2026-01-01T00:00:00Z"}
    return {"access_token": tok, "token_type": "bearer", "expires_in": 3600, "expires_at": exp,
            "refresh_token": f"r-{uid}", "user": user}


def uid_from(auth: str | None):
    if not auth or not auth.startswith("Bearer "):
        return None
    try:
        return jwt.decode(auth[7:], KEY.public_key(), algorithms=["ES256"], audience="authenticated")["sub"]
    except Exception:
        return None


@app.get("/auth/v1/.well-known/jwks.json")
def jwks():
    return {"keys": [{"kty": "EC", "crv": "P-256", "alg": "ES256", "use": "sig", "kid": "k1", "x": b64(PUB.x), "y": b64(PUB.y)}]}


@app.post("/auth/v1/signup")
async def signup(req: Request):
    b = await req.json()
    if b["email"] in USERS:
        raise HTTPException(422, "User already registered")
    uid = str(uuid.uuid4()); USERS[b["email"]] = {"id": uid, "password": b["password"]}
    return session_for(uid, b["email"])


@app.post("/auth/v1/token")
async def token(req: Request, grant_type: str):
    b = await req.json()
    if grant_type == "password":
        u = USERS.get(b.get("email"))
        if not u or u["password"] != b.get("password"):
            raise HTTPException(400, detail={"error": "invalid_grant", "error_description": "Invalid login credentials", "msg": "Invalid login credentials"})
        return session_for(u["id"], b["email"])
    rt = b.get("refresh_token", "")
    for email, u in USERS.items():
        if rt == f"r-{u['id']}":
            return session_for(u["id"], email)
    raise HTTPException(400, "bad refresh")


@app.get("/auth/v1/user")
def user(authorization: str | None = Header(None)):
    uid = uid_from(authorization)
    if not uid: raise HTTPException(401)
    email = next(e for e, u in USERS.items() if u["id"] == uid)
    return session_for(uid, email)["user"]


@app.post("/auth/v1/logout")
def logout():
    return Response(status_code=204)


@app.post("/rest/v1/rpc/rove_validate_invite")
async def validate(req: Request):
    code = (await req.json())["p_code"]
    return code in INVITES and INVITES[code] is None


@app.post("/rest/v1/rpc/rove_redeem_invite")
async def redeem(req: Request, authorization: str | None = Header(None)):
    uid = uid_from(authorization); code = (await req.json())["p_code"]
    if not uid or code not in INVITES or INVITES[code] is not None:
        return False
    INVITES[code] = uid; MEMBERS.add(uid); return True


def rows_for(table, uid, params):
    if table == "rove_members":
        return [{"user_id": uid}] if uid in MEMBERS and params.get("user_id") == f"eq.{uid}" else []
    if uid not in MEMBERS:  # RLS: owner AND member
        return None
    rows = [r for r in T[table] if r["user_id"] == uid]
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("eq.") and k not in ("user_id",):
            rows = [r for r in rows if str(r.get(k)) == v[3:]]
    return rows


@app.api_route("/rest/v1/{table}", methods=["GET", "POST", "PATCH", "DELETE"])
async def rest(table: str, req: Request, authorization: str | None = Header(None), prefer: str | None = Header(None)):
    uid = uid_from(authorization); params = dict(req.query_params)
    if not uid: raise HTTPException(401)
    if req.method == "GET":
        rows = rows_for(table, uid, params)
        if rows is None: return []
        if "order" in params:
            col, _, d = params["order"].partition(".")
            rows = sorted(rows, key=lambda r: str(r.get(col, "")), reverse=(d == "desc"))
        return rows[: int(params.get("limit", 1000))]
    if uid not in MEMBERS: raise HTTPException(403)
    if req.method == "POST":
        b = await req.json()
        assert b["user_id"] == uid, "RLS with-check violated"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if table == "rove_sets": b = {"id": str(uuid.uuid4()), "created_at": now, "updated_at": now, **b}
        if table == "rove_favorites":
            T[table][:] = [r for r in T[table] if not (r["user_id"] == uid and r["track_id"] == b["track_id"])]
            b["created_at"] = now
        if table == "rove_play_history": b = {"id": len(T[table]) + 1, "played_at": now, **b}
        T[table].append(b)
        return Response(json.dumps([b]), media_type="application/json", status_code=201) if prefer and "return=representation" in prefer else Response(status_code=201)
    rows = rows_for(table, uid, params) or []
    if req.method == "PATCH":
        b = await req.json()
        for r in rows: r.update(b)
        return rows
    for r in rows: T[table].remove(r)
    return Response(status_code=204)


# ---------- Jamendo stand-in ----------
def mk(i, name, artist, lang, speed, lic="by-nc-sa", audio=True, genres=("pop",)):
    return {"id": str(i), "name": name, "artist_name": artist, "duration": 100, "image": "",
            "audio": f"{HOST}/audio/t{i}.mp3" if audio else "",
            "license_ccurl": f"http://creativecommons.org/licenses/{lic}/3.0/",
            "musicinfo": {"lang": {"hi": "hi", "pa": "pa", "en": "en"}[lang], "speed": speed,
                          "tags": {"genres": list(genres), "vartags": ["energetic"]}}}


CATALOGUE = [
    mk(1, "Let's Nacho", "Nucleya", "hi", "high", genres=("dance",)),
    mk(2, "Dil Chori", "Honey Singh", "hi", "veryhigh", genres=("dance",)),
    mk(3, "Naacho Naacho", "Vishal Mishra", "hi", "veryhigh", genres=("dance",)),
    mk(4, "Slow Burn Hindi", "Arijit", "hi", "low", genres=("lounge",)),
    mk(5, "No Derivs Anthem", "ND Artist", "hi", "high", lic="by-nc-nd", genres=("dance",)),
    mk(6, "Punjabi Party", "Diljit", "pa", "veryhigh", genres=("dance",)),
    mk(7, "Lover", "Diljit Dosanjh", "pa", "high", genres=("dance",)),
    mk(8, "Sad Punjabi", "Singer", "pa", "low", genres=("lounge",)),
    mk(9, "English Pop One", "Pop Act", "en", "medium"),
    mk(10, "English Pop Two", "Pop Act", "en", "high"),
    mk(11, "Locked Preview", "No Audio", "en", "high", audio=False),
    mk(12, "English Rock", "Rock Act", "en", "veryhigh", genres=("rock",)),
]


@app.get("/v3.0/tracks/")
def tracks(search: str = "", lang: str = "", tags: str = "", limit: int = 20, id: str = ""):
    rows = CATALOGUE
    if id: rows = [r for r in rows if r["id"] == id]
    if lang: rows = [r for r in rows if r["musicinfo"]["lang"] == lang]
    if tags: rows = [r for r in rows if set(tags.split("+")) & set(r["musicinfo"]["tags"]["genres"])]
    if search: rows = [r for r in rows if search.lower() in (r["name"] + r["artist_name"]).lower()]
    return {"headers": {"code": 0}, "results": rows[:limit]}


app.mount("/audio", StaticFiles(directory=str(Path(__file__).parent / "audio")), name="audio")


# ---------- YouTube Data API stand-in ----------
def yv(i, title, embeddable=True, dur="PT3M30S"):
    return {"id": i, "snippet": {"title": title, "channelTitle": "Test Artist", "liveBroadcastContent": "none",
            "thumbnails": {"high": {"url": ""}}}, "contentDetails": {"duration": dur},
            "status": {"embeddable": embeddable, "privacyStatus": "public"}}

YT_VIDEOS = [yv("vid00000001", "Song One"), yv("vid00000002", "Song Two"), yv("vid00000003", "Song Three"),
             yv("vid00000004", "Song Four"), yv("blocked00001", "Blocked Video"), yv("dies0000001", "Dies Midway"),
             yv("noembed0001", "Not Embeddable", embeddable=False), yv("short0000001", "Too Short", dur="PT40S")]


@app.get("/youtube/v3/search")
def yt_search(q: str = "", key: str = ""):
    if key != "test-yt-key": raise HTTPException(403, detail={"error": {"errors": [{"reason": "keyInvalid"}]}})
    return {"items": [{"id": {"videoId": v["id"]}} for v in YT_VIDEOS]}


@app.get("/youtube/v3/videos")
def yt_videos(id: str = "", key: str = ""):
    ids = id.split(",")
    return {"items": [v for v in YT_VIDEOS if v["id"] in ids]}

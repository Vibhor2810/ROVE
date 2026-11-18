# RØVE

Private, invite-only smart music-set platform. You pick the room; RØVE builds the set and plays it as a live two-deck DJ experience. Frontend recreates the NAUX flow (only the name and accent colour changed: Electric Purple `#A855F7`).

```
frontend/frontend   React 19 + Vite + TypeScript + Tailwind v4 + Framer Motion
backend/backend     FastAPI + Pydantic, provider abstraction, librosa audio engine
backend/backend/migrations   versioned, additive SQL (001_rove_core.sql)
e2e/                local test harness (stand-in Supabase + Jamendo) and browser tests
backup_original/    your original frontend src and requirements.txt, untouched copies
```

## Run locally
**1. Database** – In the Supabase SQL editor run `migrations/001_rove_core.sql` then `migrations/002_song_requests.sql`. Both only *add* `rove_*` tables/functions. Then create invites:
`insert into rove_invitations(code) values ('PICK-A-LONG-RANDOM-CODE');` (≥ 8 chars; use long random codes, validation is a public endpoint).

**2. Backend**
```bash
cd backend/backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill SUPABASE_URL, SUPABASE_ANON_KEY, JAMENDO_CLIENT_ID
uvicorn app.main:app --port 8765 --reload
pytest                 # 59 tests
```
**3. Frontend**
```bash
cd frontend/frontend
cp .env.example .env.local   # VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY / VITE_API_URL
npm install && npm run dev   # http://localhost:5173
npm run build                # tsc -b && vite build
```
Fonts (Anton, Inter) are bundled via `@fontsource`, no CDN needed.

## How invite-only works
* Sign-up form validates the code (`rove_validate_invite`), creates the Supabase user, then calls `rove_redeem_invite`, an atomic SQL function that consumes the code and inserts the user into `rove_members`.
* Every data route on the API requires a **verified** Supabase JWT (signature via JWKS/ES256 or HS256 secret, `exp`, `aud=authenticated`, `sub`; `alg=none` rejected) **and** a `rove_members` row. All tables use RLS (`owner AND member`), and the backend queries PostgREST with the *caller's* JWT so RLS applies. No service-role key is used or shipped.
* Recommended in Supabase Dashboard: keep email sign-ups enabled (needed for the flow) and turn on email confirmation. Non-members can authenticate but cannot read or write anything.

## Music providers and rights
| Provider | State |
|---|---|
| **YouTube** | Official **YouTube Data API v3** for search/metadata + the official **IFrame Player** for playback (a visible 320×200 player tile on the Live screen; Premium removes ads). No stream extraction, no `yt-dlp`. Only embeddable, public, non-age-restricted videos of 90s–12min are used. Rights: full/seek/segment allowed; **crossfade, DJ transition, sharing, public performance denied** (hard cuts between YouTube tracks). **No waveform/BPM/key/highlight analysis** (audio isn't accessible) so YouTube tracks play full with a seekable progress bar. Needs `YOUTUBE_API_KEY`. Free quota ≈ 100 searches/day; results are cached 24h and language counts don't spend quota. When quota/key fails, the set falls back to Jamendo and the error is shown. Playing music in public venues is still a licensing question YouTube's embed does not answer for you. |
| **Jamendo** | Real adapter (search, track fetch, stream URLs). Rights derived per track from its Creative-Commons licence: full/seek playback allowed; `ND` licences deny crossfade/segment/DJ transition; public performance and sharing always denied. Needs `JAMENDO_CLIENT_ID`. |
| **MusicBrainz** | Real adapter, **metadata only**, never audio, all rights denied. |
| **VYBE** | **Structure only.** I could not verify a public partner API, so no calls are made and `configured()` is always false. Needs partner approval + docs. |
| Spotify / YouTube / mainstream | Not integrated. No scraping or stream extraction. Add a licensed adapter implementing `MusicProvider` later. |

Unknown permissions default to denied. The server decides playability from provider data (`/api/playback/authorize`), never from the client.

**Catalogue reality:** Jamendo is independent/CC music. It has little to no Bollywood/Punjabi chart music, so Hindi/Punjabi "songs ready" counts will be small or zero and those cards disable at zero. Mainstream parity with NAUX requires a licensed catalogue (label/aggregator agreement) – that is a business step, not code.

## DJ engine (what is real)
* Backend (`librosa`): BPM, Camelot key, **estimated** loudness-based highlight (always labelled `estimated`, never "most popular"), waveform; BPM/key compatibility; rights-aware transition planning (`cut`/`crossfade`/`beatmatch`). Analysis only fetches tracks the provider licenses for playback, from an allow-listed host (SSRF guard).
* Frontend: two `HTMLAudioElement` decks, volume-ramp crossfades, IN/OUT cue window with click-to-set-IN, Skip, Play Full, pause/resume (Space), Play Next search, Remove Next.
* Not implemented: EQ moves and true beat-matched tempo sync in the browser (needs a CORS-enabled Web Audio graph and time-stretching), looping, provider-supplied "most-listened" sections (no provider connected that supplies them). The plan is computed server-side but only crossfade/cut are applied client-side.

## Deployment
* Frontend → Cloudflare Pages (build `npm run build`, output `dist`; set the three `VITE_*` vars).
* Backend → any Python host (Fly.io, Render, Railway): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; set env from `.env.example`, `APP_ENV=production`, and `CORS_ORIGINS` to your Pages URL. ffmpeg recommended on the host for broader decoding.
* R2 is reserved for user-owned uploads (variables exist, upload path **not built**).

### Getting a YouTube API key
Google Cloud Console → create/select a project → *APIs & Services → Library* → enable **YouTube Data API v3** → *Credentials → Create credentials → API key* → paste into `backend/.env` as `YOUTUBE_API_KEY`. (Optional: restrict the key to that API.) Restart the backend.

## Still needed from you
1. Run the migration; create invite codes. 2. `JAMENDO_CLIENT_ID` (and confirm with Jamendo that a private invite-only app fits their non-commercial terms). 3. VYBE partner approval/docs, if wanted. 4. A licensed mainstream catalogue if you want Bollywood/Punjabi chart music. 5. R2 credentials + upload feature if you want user uploads.

# SearchHub

A knowledge-base search platform. The core of the project is a search engine written from scratch in Python (no search library): tokenizer, inverted index, BM25 ranking, Trie autocomplete, Levenshtein typo tolerance, filters and highlighting. Around it sit a PostgreSQL schema, a FastAPI backend and a React frontend.

## What is built

| Area | Status |
|---|---|
| PostgreSQL schema + SQL migration file (6 tables, foreign keys, indexes, JOIN + GROUP BY query) | Done |
| Search engine from scratch (all seven required parts) | Done |
| `GET /search`, `GET /search/suggest` | Done |
| Seed script (520 articles, 19 tags, near-duplicates, typos) | Done |
| Automated tests (76, including every required search case, the auth flow and the WebSocket channel) | Done |
| Frontend: Ctrl/Cmd+K palette, debounced autocomplete with keyboard navigation, result cards with highlighted snippets, tag filters, sort, pagination, skeletons, empty and error states, toasts, dark/light mode, responsive layout, stale-request cancellation | Done |
| Dashboard (searches per minute, trending searches, zero-result rate, top bookmarked tags) | Done, polls every 10 s |
| Document page (bookmark toggle, related articles) | Done |
| `docker-compose.yml` (PostgreSQL, API, web) | Written, not run on the author's machine (see Unfinished) |
| JWT authentication (register, login, 15-minute access token, 7-day rotating refresh token stored hashed, logout revocation, roles) | Done |
| Admin-only document create / edit / delete API | Done (API only, no admin UI) |
| Login and register pages, protected routes, silent token refresh | Done |
| WebSocket channel: JWT-authenticated, server heartbeat, live trending searches, live activity feed, bookmark-update notifications, client reconnect with backoff | Done (basic, single instance) |
| Redis, RabbitMQ, Kafka, live indexing status, admin panel UI, AI summary | Not built, see Unfinished |

## Setup

### With Docker (one command)

```
docker compose up --build
```

- Web UI: http://localhost:3000
- API docs: http://localhost:8000/docs

PostgreSQL applies the files in `backend/migrations/` (in order) the first time its data volume is created. The API container then seeds the database and starts the server. To re-run the migration from scratch, run `docker compose down -v` first. The search index is built from the database at startup, so seeding must happen before the API starts (compose does this).

### Without Docker

Requires Python 3.10+, Node 18+ and a running PostgreSQL database. Set `DATABASE_URL` in `backend/.env` (see `.env.example`).

```
cd backend
pip install -r requirements.txt
psql -U searchhub -d searchhub -f migrations/001_initial_schema.sql
psql -U searchhub -d searchhub -f migrations/002_refresh_tokens.sql
python -m scripts.seed
uvicorn app.main:app --reload

cd ../frontend
npm install
npm run dev
```

The UI runs on http://localhost:5173 and proxies `/api` to the backend on port 8000.

Seeded accounts: `admin@searchhub.dev` / `admin12345` (admin) and `user@searchhub.dev` / `user12345` (regular user). Set a strong `JWT_SECRET` in `backend/.env` for anything beyond local use.

### Tests

```
cd backend
python -m pytest
```

The tests need no database server: API tests run on in-memory SQLite and the search tests run on the seed corpus in memory.

## Search engine (`backend/app/search/`)

| File | Responsibility |
|---|---|
| `tokenizer.py` | Lowercase, remove apostrophes, split on anything that is not a letter or digit, drop stop words and single letters |
| `index.py` | Inverted index: term to `{docId: weighted term frequency}`, document records, corpus statistics |
| `engine.py` | Query parsing, BM25 scoring, typo fallback, filters, sorting, pagination, facets, related articles |
| `trie.py` | Prefix tree for autocomplete |
| `fuzzy.py` | Levenshtein distance with early exit, candidate lookup |
| `snippets.py` | Best-window snippet extraction and `<mark>` highlighting |
| `loader.py` | Builds the engine from the `documents` table at startup |

### How ranking works

1. Each document is tokenized as title and body. A term's stored frequency is `body_count + 3 * title_count`, so a title match counts three times a body match. Document length is weighted the same way.
2. BM25 (`k1 = 1.5`, `b = 0.75`) scores each query term against each candidate document. IDF is `ln(1 + (N - df + 0.5) / (df + 0.5))`, which never goes negative.
3. The sum of the term scores is multiplied by the fraction of query terms the document contains. This is why articles about "kafka consumer group" rank above articles that only contain the word "group" or mention consumer groups once.
4. Typos: a query term with no exact match is compared with the vocabulary. Words within the allowed edit distance become candidates, weighted `1 / (1 + distance)`. Allowed distance is 0 for words of 3 letters or fewer, 1 for 4 letters and 2 for 5 or more, so short words do not match half the vocabulary. 
5. Filters (tag, author, date range) are applied to the candidate set before scoring. Several tags mean a document must carry all of them.
6. Snippets are HTML-escaped first; the only tags that ever appear in a snippet are `<mark>`, so the frontend can safely render them.

### Complexity

Let N be the number of documents, V the vocabulary size, L the length of a document in tokens, q the number of query terms, p the average posting-list length and m the number of matching documents.

| Operation | Time | Space |
|---|---|---|
| Index one document | O(L) | O(unique terms in the doc) |
| Remove or replace one document | O(unique terms in the doc) | none extra |
| Whole index | O(total tokens) to build | O(total postings), plus stored text |
| Search (exact terms) | O(q·p) to score, O(m log m) to sort | O(m) |
| Typo fallback, per unmatched term | O(V · d · len) worst case; the early exit makes most words cost O(1) | O(V) |
| Autocomplete | O(prefix + nodes below the prefix) plus O(k log n) to rank | O(total characters in the vocabulary) |
| Snippet and highlight | O(body length) per returned hit only | O(1) |

Search runs in about 1 to 2 ms on the 520-article corpus.

### Scaling beyond 1 million documents

The current index is a single in-process Python structure. To go past a million documents I would change these things, roughly in this order:

1. **Top-k instead of full sort.** Use a heap for the top page rather than sorting every match, and use WAND or MaxScore pruning so low-scoring documents are skipped without being scored.
2. **Compressed, on-disk posting lists.** Store postings sorted by docId with delta and variable-byte (or bit-packed) encoding and skip pointers, in immutable segments that are memory-mapped, as Lucene does. New documents go into a small in-memory segment that is flushed and merged in the background, so writes never rebuild the whole index.
3. **Sharding.** Partition documents by hash of docId across nodes. Each search is sent to every shard (scatter), each returns its top k, and a coordinator merges them (gather). Shards share IDF statistics (or use a periodically refreshed global copy) so scores are comparable.
4. **Faster fuzzy matching.** Replace the linear vocabulary scan with a BK-tree, a symmetric-delete index or a Levenshtein automaton walked over the Trie.
5. **Autocomplete.** Store the top-k completions at each Trie node, or use a finite-state transducer, so a lookup costs O(prefix length).
6. **Snippets from stored fields.** Keep document text in the shard (or an object store) and fetch only the ten hits on the page, instead of holding every body in RAM.
7. **Caching and replicas.** Cache popular queries, add read replicas per shard, and keep PostgreSQL as the source of truth that rebuilds any shard.

## Authentication (JWT)

### The pipeline

```
Register / Login                     Every API call                       Access token expires (15 min)
----------------                     --------------                       ------------------------------
POST /auth/login                     Authorization: Bearer <access>       API answers 401
  check bcrypt hash                    verify signature + exp                 |
  create access token (JWT, 15 min)    load user, check role                  v
  create refresh token (random,        -> 200, or 401 / 403                POST /auth/refresh {refresh_token}
    7 days), store its SHA-256 hash                                           hash it, look it up
  return both                                                                 revoke the old row (rotation)
                                                                              issue a NEW access + refresh pair
Logout: POST /auth/logout -> refresh row marked revoked
```

- **Access token** is a signed JWT (HS256) holding `sub` (user id), `name`, `role`, `iat`, `exp`. The server keeps no record of it; it trusts the signature.
- **Refresh token** is a random 64-character string, not a JWT. Only its SHA-256 hash is stored (`refresh_tokens.token_hash`), so a leaked database cannot be used to log in.
- **Rotation:** every refresh revokes the used token and issues a new one.
- **Reuse detection:** presenting an already-revoked refresh token means it was probably stolen, so every active refresh token of that user is revoked and the user must log in again.
- **Same error for wrong email and wrong password** (`Invalid email or password.`). When the email does not exist the server still runs a bcrypt check against a dummy hash, so response time does not reveal which emails exist.
- **Roles:** `get_current_user` protects every route except `/auth/*` and `/health`; `require_admin` returns 403 unless `role == "admin"`. Only admins can `POST`, `PUT` and `DELETE /documents`. The role is read from the database, not trusted from the token.

### Code map

| File | Role |
|---|---|
| `backend/app/security.py` | bcrypt hashing, JWT creation and verification, refresh-token generation and hashing |
| `backend/app/deps.py` | `get_current_user` (Bearer token to user) and `require_admin` |
| `backend/app/routers/auth.py` | register, login, refresh, logout |
| `backend/migrations/002_refresh_tokens.sql` | `refresh_tokens` table |
| `frontend/src/api.js` | Attaches the token; on a 401 refreshes once (shared by all concurrent requests) and retries |
| `frontend/src/components/Auth.jsx` | Auth context, session restore on page load, protected-route wrapper |
| `frontend/src/pages/AuthPages.jsx` | Login and register forms with validation |

### Trade-offs

- **The access token is kept in memory and the refresh token in `localStorage`.** Memory cannot be read by other scripts but is lost on reload, which the silent refresh at startup solves. `localStorage` is readable by any script on the page, so an XSS bug would leak the refresh token. An `httpOnly` `SameSite` cookie is safer but needs CSRF protection and cookie handling; it was not done here.
- **An access token cannot be revoked before it expires.** Logout revokes the refresh token, but a stolen access token still works for up to 15 minutes. That is the standard trade-off for stateless tokens; the short lifetime limits the damage.
- **HS256 (shared secret)** is fine with one backend. With several independent services verifying tokens, RS256/ES256 (private key signs, public key verifies) would be better.
- **No rate limiting or lockout on `/auth/login`**, so passwords can be guessed by brute force.
- Registration reveals whether an email is taken (409). Login does not.

## Real-time channel (WebSocket)

`GET /ws?token=<access token>` (`backend/app/routers/ws.py`, `backend/app/realtime.py`).

| Message from server | When | Who receives it |
|---|---|---|
| `connected` | Right after the token is accepted | The connecting user |
| `trending` (top 10 queries, last hour) | After any search | Everyone connected |
| `activity` ("Someone bookmarked ...") | When a bookmark is newly added | Everyone connected |
| `notification` ("... was updated") | When an admin edits a document | Only users who bookmarked it (not the editor) |
| `ping` | Every 25 s | The connection; the client answers `pong` |

- **Authentication:** browsers cannot set headers on a WebSocket, so the access token goes in the query string. The server accepts the socket, validates the JWT and that the user still exists, and otherwise closes with code `4401`.
- **Heartbeat:** the server sends an application-level `ping` every 25 s. A connection that sends nothing for 60 s is closed (code `1001`), which also removes half-dead connections.
- **Token expiry:** the server closes the socket with `4401` when the access token expires. The client then refreshes its token and reconnects, so a socket never outlives its authentication.
- **Reconnect:** `frontend/src/components/Live.jsx` reconnects with exponential backoff (1 s, 2 s, 4 s ... capped at 30 s, plus jitter), resets the delay after a successful connection, and fetches a fresh token before each attempt.
- **How pushes are triggered:** the search and bookmark routes finish their normal work and hand the message to FastAPI's `BackgroundTasks`, which broadcasts after the HTTP response. Nothing is computed when nobody is connected.
- **Proxying:** the Vite dev proxy has `ws: true` and nginx sends the `Upgrade` headers, so `/api/ws` works in both modes.

Limits: connections are held in the memory of one API process. With several API instances a message would only reach clients connected to the instance that handled the request; the fix is Redis pub/sub (not built).

## Database

Tables: `users`, `documents`, `tags`, `document_tags`, `bookmarks`, `search_events`, with foreign keys everywhere. `documents.author_id` uses `RESTRICT`, join tables use `CASCADE`, and `search_events.user_id` uses `SET NULL` so analytics survive a deleted user. `role` and `status` are protected by `CHECK` constraints.

Two deliberate differences from the brief's column list: `bookmarks` has a `created_at` column (needed for "last 7 days"), and `search_events.user_id` is nullable (searches are logged before login exists).

### Index choices

| Index | Reason |
|---|---|
| `users.email` (unique) | Login lookup, and enforces one account per email |
| `documents.author_id` | The author filter, and foreign-key checks on delete |
| `documents.created_at` | Date-range filters and "newest first" listings |
| `documents.status` | The worker and admin views look up pending or failed documents |
| `document_tags (document_id, tag_id)` primary key | Tags of a document; prevents duplicate tagging |
| `document_tags.tag_id` | The reverse lookup, "all documents with this tag", and the JOIN in the top-tags query. The primary key cannot serve it because `tag_id` is its second column |
| `bookmarks (user_id, document_id)` primary key | A user's bookmarks and the "is this bookmarked" check; prevents duplicates |
| `bookmarks.document_id` | Counting bookmarks per document, and the join to `document_tags` |
| `bookmarks.created_at` | The 7-day window in the top-tags query |
| `search_events.created_at` | Every analytics query is a time-window scan |
| `search_events (user_id, created_at)` | A user's recent searches (per-user history and limits) |
| `search_events.query` | Grouping by query text for top and zero-result queries |

The JOIN + GROUP BY query is `top_tags_by_bookmarks` in `backend/app/queries.py`. It joins `bookmarks`, `document_tags` and `tags`, filters the last 7 days and groups by tag.

## Design decisions and trade-offs

- **Python with FastAPI.** Least boilerplate, automatic API docs, and a natural fit for writing the algorithms by hand.
- **The index is in memory and rebuilt from PostgreSQL at startup.** Simple and fast, and PostgreSQL stays the source of truth. The cost is a startup delay that grows with the corpus, and one process owns the index. Documents added after startup are not searchable until the API restarts.
- **Postings are dictionaries, not lists of tuples.** Semantically it is still term to `(docId, tf)`, but replacing or deleting one document is cheap, which is what makes indexing idempotent: indexing the same document twice leaves the index unchanged (tested).
- **OR semantics with a coverage multiplier** instead of strict AND. Partial matches still appear, but rank below documents that contain every term.
- **Trending and analytics come from the `search_events` table** with plain SQL. That is simple and correct, but every dashboard refresh runs aggregate queries. At higher volume these would be pre-aggregated.
- **No comments in the code, by request.** Names and structure are meant to carry the explanation; this README is where the reasoning lives.
- **Seed data mentions Redis, Kafka and other technologies** only as article topics, because those are the sample search queries in the brief. The application itself does not use them.

## Unfinished (honest list)

- **No admin panel UI.** Admins can create, edit and delete documents through the API (`/docs`), but there is no markdown editor, no live indexing-status table and no failed-jobs view. Because there is no worker, admin changes are indexed synchronously and `status` is set to `indexed` immediately.
- **Authentication gaps:** no login rate limiting, no email verification, no password reset, refresh token in `localStorage`, and an access token cannot be revoked before it expires (see Authentication trade-offs). The WebSocket connection is authenticated with the same JWT (see Real-time channel).
- **Redis is not used**: no search-result cache, no rate limiting (30 searches per minute with 429 and `Retry-After`), no trending sorted set.
- **RabbitMQ indexing worker, retries and dead-letter queue are not built**, and the document `status` column is always `indexed`.
- **Kafka event streaming and the analytics consumer are not built.**
- **WebSockets are basic.** Live trending, the activity feed, bookmark-update notifications, heartbeat and reconnect are done. **Live indexing status is not**, because indexing is synchronous and there is no RabbitMQ worker, so there is no `pending` state to show. Messages reach only clients connected to the same API instance (no Redis pub/sub). The dashboard charts still poll every 10 seconds. The nginx WebSocket proxy settings were written but not run in Docker; the Vite proxy path was tested end to end.
- **AI summary and suggested tags are not built.**
- **Related articles** are found by searching with the article's title, so a near-duplicate or a passing mention can appear near the top.
- **The dashboard chart is a hand-written SVG bar chart**, with no charting library and no time-range selector.
- **Docker is untested here.** The Docker daemon was not available on the development machine, so `docker-compose.yml` and the Dockerfiles were written but never run. The seed script, API and frontend were run locally against a SQLite database created from the same models; the SQL migration files themselves have never been executed against PostgreSQL.
- **Frontend has no automated tests.** The UI was built and exercised through its API proxy, but it was not clicked through in a browser during development.
- **Typo tolerance uses plain Levenshtein**, so a swapped pair of letters ("kafak") costs 2, not 1. Short words (3 letters or fewer) are never corrected.
- **Search is English-only**: the stop-word list is English and there is no stemming, so "index" and "indexing" are different terms.

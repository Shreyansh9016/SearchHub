# SearchHub

SearchHub is a website where people log in and search technical articles. The most important part is a **search engine written from scratch** in Python, with no search library. It handles ranking, typo fixing, autocomplete, filters and highlighted snippets.

**Built with:** Python (FastAPI), PostgreSQL, React, Docker.

## What works

- Search with ranking (title matches count 3 times more than body matches)
- Typo tolerance: searching `kafak` still finds Kafka articles
- Autocomplete suggestions (top 5) while typing, and a Ctrl+K search popup
- Filters by tag, author and date; sort by relevance, newest or oldest; pages
- Highlighted words in the result snippets
- Login and sign-up with secure tokens; only admins can add, edit or delete articles
- Bookmarks, related articles, and a dashboard with statistics
- Live trending searches on the dashboard, pushed over a WebSocket
- Dark and light mode, loading skeletons, error messages, works on mobile
- 75 automated tests

## How to run it

### The easy way (Docker)

```
docker compose up --build
```

Then open **http://localhost:3000**. Docker starts the database, the API and the website together and loads 520 sample articles.

To start again with a clean database (this deletes saved data):

```
docker compose down -v
docker compose up --build
```

### Without Docker

You need Python 3.10+, Node 18+ and a running PostgreSQL.

1. Create a database and user called `searchhub`.
2. Run the two files in `backend/migrations/` (they create the tables):
   ```
   psql -U searchhub -d searchhub -f backend/migrations/001_initial_schema.sql
   psql -U searchhub -d searchhub -f backend/migrations/002_refresh_tokens.sql
   ```
3. Copy `.env.example` to `backend/.env` and adjust it if your database uses a different port.
4. Start the backend:
   ```
   cd backend
   pip install -r requirements.txt
   python -m scripts.seed
   uvicorn app.main:app --reload
   ```
5. Start the website in a second terminal:
   ```
   cd frontend
   npm install
   npm run dev
   ```
   Open http://localhost:5173.

### Test accounts

| Who | Email | Password |
|---|---|---|
| Admin | `admin@searchhub.dev` | `admin12345` |
| Normal user | `user@searchhub.dev` | `user12345` |

Or create your own account on the sign-up page. These passwords are for local testing only.

### Run the tests

```
cd backend
python -m pytest
```

No database is needed for the tests.

### Where to look

- API list with a "Try it" screen: http://localhost:8000/docs
- Admins can add, edit and delete articles there. First run `POST /auth/login` with the admin account, copy the `access_token` from the answer, click **Authorize** at the top and paste it in.

## How it works (in simple words)

### Searching
1. **Clean the text.** Make everything lowercase, remove punctuation, and drop common words like "the" and "and".
2. **Build an index.** Like the index at the back of a book: for every word, a list of the articles that contain it and how many times.
3. **Rank the results.** We use a scoring method called BM25. A word in the title counts 3 times more than a word in the body. Articles that contain *all* the search words score higher.
4. **Fix typos.** If a word matches nothing, we look for known words that are 1 or 2 letters different. Very short words are never changed, to avoid silly matches.
5. **Autocomplete.** Words are stored in a tree, so all words starting with "kaf" can be found quickly. The most common ones are shown first.
6. **Highlight.** We pick the part of the article with the most matches and wrap the matched words in `<mark>`. The text is escaped first, so it is safe to show.

The index is kept in the API's memory and built from the database when the API starts.

### Logging in
- When you log in you get two tokens. The **access token** lasts 15 minutes and is sent with every request. The **refresh token** lasts 7 days and is only used to get a new access token.
- The website refreshes the access token automatically, so you are not logged out every 15 minutes.
- Every refresh gives you a brand new refresh token and cancels the old one. If someone reuses an old one, all sessions for that user are cancelled.
- Refresh tokens are stored in the database in scrambled (hashed) form, and passwords are hashed with bcrypt.
- A wrong email and a wrong password give the same error, so nobody can find out which emails have accounts.

### Live updates
The website opens one WebSocket connection after login (using the same login token). Whenever anyone searches, the server sends everyone the new list of trending searches, so the dashboard changes without a refresh. The server also sends a "ping" every 25 seconds to check the connection is alive, closes it if it goes quiet, and closes it when the login token expires. The website then gets a new token and reconnects by itself. If the connection drops, it retries after 1, 2, 4, 8 seconds and so on (up to 30 seconds).

Only trending searches are sent this way. Other live features (an activity feed, notifications, indexing status) are not built.

## The database

Seven tables: `users`, `documents`, `tags`, `document_tags` (links documents to tags), `bookmarks`, `search_events` (a log of every search) and `refresh_tokens` (login sessions). They are connected with foreign keys. The dashboard uses one query that joins three tables and groups the result: the top tags by bookmarks in the last 7 days (in `backend/app/queries.py`).

### Why these indexes

An index makes a lookup fast, like a book's index. We added them where we look things up often:

| Index | Why |
|---|---|
| `users.email` | Finding a user at login |
| `documents.author_id` | Filtering by author |
| `documents.created_at` | Date filters and sorting by newest |
| `documents.status` | Finding pending or failed documents |
| `document_tags.tag_id` | Finding all documents with a tag (the primary key only helps in the other direction) |
| `bookmarks.document_id` | Counting bookmarks for a document |
| `bookmarks.created_at` | The "last 7 days" filter |
| `search_events.created_at` | Every dashboard number looks at a time window |
| `search_events (user_id, created_at)` | A user's recent searches |
| `search_events.query` | Counting the same query many times |
| `refresh_tokens.token_hash` | Finding a session by its token |

## How fast is it, and how would it grow?

**Speed today.** Searching 520 articles takes about 1 to 2 milliseconds.

| Action | Roughly how long it takes | Memory |
|---|---|---|
| Add an article | Grows with the article's length | Grows with the number of different words in it |
| Search | Grows with how many articles contain the search words | Small |
| Typo check | Compares against every known word, so it grows with the vocabulary size | Small |
| Autocomplete | Grows with the prefix length and how many words start with it | Grows with the total letters in the vocabulary |

**Growing beyond 1 million articles.** One computer's memory would not be enough, so we would:
1. **Split the index across several servers** (each holds part of the articles). Every search asks all of them and merges the top results.
2. **Keep the index on disk** in compressed files instead of memory, and add new articles in small batches that are merged later.
3. **Only score the best candidates** instead of sorting every match.
4. **Use a faster typo lookup** (a special tree for edit distance) instead of comparing with every word.
5. **Remember popular searches** so they are not recalculated.
6. Keep PostgreSQL as the main copy of the data, so any server's index can be rebuilt from it.

## Design decisions

- **Python and FastAPI:** the least code to write, automatic API documentation at `/docs`, and easy to write the search algorithms in.
- **Search index in memory:** very fast and simple. PostgreSQL still holds the real data.
- **Plain SQL files for the database setup** (no migration tool): easy to read. Docker runs them automatically the first time.
- **Two kinds of tokens:** the short-lived one limits the damage if it is stolen, and the long-lived one keeps users logged in.
- **Search matches any word but ranks "all words" first:** you still get results for partly matching searches, but the best ones come first.
- **The dashboard reads from the `search_events` table:** simple and always correct, with no extra services.
- **Sample data is generated by a script** (`backend/scripts/seed_data.py`) with fixed randomness, so the tests get the same articles every time. The articles mention Redis and Kafka only because those are topics to search for; the app does not use them.
- **No comments in the code, by request.** File and function names are meant to explain it, and this README explains the reasoning.

## Trade-offs

- **In-memory index:** fast, but it is rebuilt at every start, and it belongs to one server only.
- **The dashboard recounts searches every time** instead of keeping running totals. It is simple, but it gets slower when there are millions of search records.
- **The refresh token is saved in the browser's `localStorage`.** It is easy, but a malicious script on the page could read it. A more secure cookie would need extra protection work.
- **An access token cannot be cancelled early.** After logout it still works until it expires (up to 15 minutes). That is the price of not checking the database on every request.
- **The WebSocket works on one server only.** Running several API servers would need something like Redis to share messages.
- **Typo fixing counts a swapped pair of letters as 2 mistakes** and never touches words of 3 letters or fewer.
- **Pagination instead of infinite scroll.** Simpler and easier to use with the keyboard.

## What is unfinished (honest list)

**Things the project brief asked for that are not built:**
- **Redis:** not used at all. There is no search cache, no rate limit (30 searches per minute), and trending searches come from the database instead of a Redis list.
- **RabbitMQ:** no background indexing worker, no retries and no failed-jobs queue. Articles are indexed instantly when saved, so an article's status is always `indexed`.
- **Kafka:** no event streaming and no analytics consumer. The dashboard reads the `search_events` table directly.
- **Live indexing status** (pending → indexed): not shown, because indexing is instant.
- **Admin panel in the website:** admins can add, edit and delete articles only through the API page (`/docs`). There is no markdown editor, no status table and no failed-jobs page.
- **AI summary and suggested tags:** not built, and no AI service is used.
- **Dashboard charts:** there is one hand-drawn bar chart (searches per minute). Top queries and the zero-result rate are a list and a number, not charts.
- **Infinite scroll:** not built (pagination is used instead).

**Smaller gaps:**
- No login attempt limit, so passwords could be guessed by brute force. No password reset and no email check.
- The only live feature is trending searches; there is no activity feed, no notifications and no live indexing status. It works on a single server only (see Trade-offs).
- Search is English only and does not understand word forms ("index" and "indexing" are different words).
- Related articles are found by searching with the article's title, so they can be a little rough (a copy of the article can show up first).
- If an article is added or changed, the index updates only in the API instance that handled the request. Restarting rebuilds it from the database.

**Not fully tested:**
- The Docker setup starts and serves the site, but the database setup file `001_initial_schema.sql` has never been run from a completely empty database on a real PostgreSQL. The refresh-token file (`002`) was applied to a real PostgreSQL successfully.
- The nginx settings for WebSockets in Docker were written but not run. WebSockets were tested end to end with the development server.
- The website has no automated tests, and it was tested through its API rather than clicked through in a browser.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import ResultCard from "../components/ResultCard";
import { EmptyState, ErrorState, ResultSkeletons } from "../components/States";
import { useFetch } from "../hooks/useFetch";

const PAGE_SIZE = 10;

function Pagination({ page, total, onChange }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (pages <= 1) return null;
  const numbers = [];
  for (let p = Math.max(1, page - 2); p <= Math.min(pages, page + 2); p++) numbers.push(p);
  return (
    <nav className="pagination" aria-label="Pagination">
      <button className="btn" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Previous
      </button>
      {numbers.map((p) => (
        <button
          key={p}
          className={p === page ? "btn btn-primary" : "btn"}
          aria-current={p === page ? "page" : undefined}
          onClick={() => onChange(p)}
        >
          {p}
        </button>
      ))}
      <button className="btn" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Next
      </button>
    </nav>
  );
}

function Landing() {
  return (
    <div className="landing">
      <h1>Find answers in technical articles</h1>
      <p className="muted">
        Press <kbd>Ctrl</kbd> <kbd>K</kbd> anywhere, or type above.
      </p>
    </div>
  );
}

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const tags = useMemo(() => params.getAll("tag"), [params]);
  const sort = params.get("sort") ?? "relevance";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [draft, setDraft] = useState(q);

  useEffect(() => setDraft(q), [q]);

  const tagKey = tags.join(",");
  const { data, error, loading, reload } = useFetch(
    (signal) => api.search({ q, tag: tags, sort, page, limit: PAGE_SIZE }, signal),
    [q, tagKey, sort, page],
    { enabled: q.trim().length > 0 }
  );

  const update = useCallback(
    (changes) => {
      const next = new URLSearchParams(params);
      Object.entries(changes).forEach(([key, value]) => {
        next.delete(key);
        if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
        else if (value !== null && value !== "") next.set(key, value);
      });
      setParams(next);
    },
    [params, setParams]
  );

  const toggleTag = useCallback(
    (tag) => update({ tag: tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag], page: null }),
    [tags, update]
  );

  const submit = (event) => {
    event.preventDefault();
    update({ q: draft.trim(), page: null });
  };

  const facets = data ? Object.entries(data.facets).slice(0, 12) : [];

  return (
    <>
      <form className="searchbar" onSubmit={submit} role="search">
        <input
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Search articles, e.g. kafka consumer group"
          aria-label="Search articles"
        />
        <button className="btn btn-primary" type="submit">
          Search
        </button>
      </form>

      {!q.trim() && <Landing />}

      {q.trim() && (
        <div className="layout-2col">
          <aside className="filters" aria-label="Filters">
            <h3>Sort by</h3>
            <select value={sort} onChange={(e) => update({ sort: e.target.value, page: null })} aria-label="Sort by">
              <option value="relevance">Relevance</option>
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
            </select>
            <h3>Tags</h3>
            <div className="chips">
              {tags.filter((t) => !facets.some(([name]) => name === t)).map((t) => (
                <button key={t} className="chip chip-active" onClick={() => toggleTag(t)} aria-pressed="true">
                  {t} ×
                </button>
              ))}
              {facets.map(([name, count]) => (
                <button
                  key={name}
                  className={tags.includes(name) ? "chip chip-active" : "chip"}
                  onClick={() => toggleTag(name)}
                  aria-pressed={tags.includes(name)}
                >
                  {name} <span className="muted">{count}</span>
                </button>
              ))}
            </div>
          </aside>

          <section aria-live="polite">
            {loading && <ResultSkeletons />}
            {!loading && error && <ErrorState error={error} onRetry={reload} />}
            {!loading && !error && data && (
              <>
                <p className="muted result-count">
                  {data.total} result{data.total === 1 ? "" : "s"}
                </p>
                {data.total === 0 && (
                  <EmptyState title="No results found">
                    Nothing matched “{q}”. Try different words{tags.length > 0 ? " or remove a tag filter" : ""}.
                  </EmptyState>
                )}
                {data.results.map((hit) => (
                  <ResultCard key={hit.id} hit={hit} activeTags={tags} onTagClick={toggleTag} />
                ))}
                <Pagination page={page} total={data.total} onChange={(p) => update({ page: p })} />
              </>
            )}
          </section>
        </div>
      )}
    </>
  );
}

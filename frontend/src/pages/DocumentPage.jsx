import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { ErrorState, Skeleton } from "../components/States";
import { useToast } from "../components/Toasts";
import { useFetch } from "../hooks/useFetch";

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "long" });

export default function DocumentPage() {
  const { id } = useParams();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch((signal) => api.document(id, signal), [id]);
  const [bookmarked, setBookmarked] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data) setBookmarked(data.bookmarked);
  }, [data]);

  const toggleBookmark = async () => {
    const next = !bookmarked;
    setBookmarked(next);
    setBusy(true);
    try {
      await (next ? api.bookmark(id) : api.unbookmark(id));
      toast.success(next ? "Added to bookmarks" : "Removed from bookmarks");
    } catch (err) {
      setBookmarked(!next);
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="card">
        <div className="skeleton" style={{ height: 32, width: "70%", marginBottom: 20 }} />
        <Skeleton lines={8} height={16} />
      </div>
    );
  }
  if (error && !data) {
    return <ErrorState error={error} onRetry={reload} />;
  }

  return (
    <div className="layout-2col reverse">
      <article className="card document">
        <div className="chips">
          {data.tags.map((tag) => (
            <Link key={tag} className="chip" to={`/search?q=${encodeURIComponent(tag)}&tag=${tag}`}>
              {tag}
            </Link>
          ))}
        </div>
        <h1>{data.title}</h1>
        <p className="muted">
          By {data.author} · Updated {dateFormat.format(new Date(data.updated_at))}
        </p>
        {data.body.split(/\n{2,}/).map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </article>

      <aside className="side">
        <button
          className={bookmarked ? "btn btn-primary btn-block" : "btn btn-block"}
          onClick={toggleBookmark}
          disabled={busy}
          aria-pressed={bookmarked}
        >
          {bookmarked ? "★ Bookmarked" : "☆ Bookmark"}
        </button>
        <div className="card">
          <h3>Related articles</h3>
          {data.related.length === 0 && <p className="muted">No related articles yet.</p>}
          <ul className="plain-list">
            {data.related.map((item) => (
              <li key={item.id}>
                <Link to={`/documents/${item.id}`}>{item.title}</Link>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

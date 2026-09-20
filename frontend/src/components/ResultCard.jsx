import { memo } from "react";
import { Link } from "react-router-dom";

const dateFormat = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" });

function ResultCard({ hit, activeTags, onTagClick }) {
  return (
    <article className="card result">
      <h2 className="result-title">
        <Link to={`/documents/${hit.id}`}>{hit.title}</Link>
      </h2>
      <p className="result-snippet" dangerouslySetInnerHTML={{ __html: hit.snippet }} />
      <div className="result-meta">
        <div className="chips">
          {hit.tags.map((tag) => (
            <button
              key={tag}
              className={activeTags.includes(tag) ? "chip chip-active" : "chip"}
              onClick={() => onTagClick(tag)}
              aria-pressed={activeTags.includes(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
        <span className="muted">{dateFormat.format(new Date(hit.created_at))}</span>
      </div>
    </article>
  );
}

export default memo(ResultCard);

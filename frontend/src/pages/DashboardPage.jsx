import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { useLive } from "../components/Live";
import { useFetch } from "../hooks/useFetch";

function Stat({ label, value }) {
  return (
    <div className="card stat">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function BarChart({ points }) {
  const max = Math.max(1, ...points.map((p) => p.count));
  const width = 600;
  const height = 160;
  const barWidth = width / points.length;
  return (
    <svg viewBox={`0 0 ${width} ${height + 20}`} className="chart" role="img" aria-label="Searches per minute">
      {points.map((point, index) => {
        const barHeight = (point.count / max) * height;
        const time = new Date(point.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        return (
          <g key={point.minute}>
            <title>{`${time}: ${point.count} searches`}</title>
            <rect
              x={index * barWidth + 2}
              y={height - barHeight}
              width={barWidth - 4}
              height={Math.max(barHeight, 1)}
              rx="2"
              className="bar"
            />
          </g>
        );
      })}
      <text x="0" y={height + 16} className="axis">
        {new Date(points[0].minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </text>
      <text x={width} y={height + 16} textAnchor="end" className="axis">
        now
      </text>
    </svg>
  );
}

const STATUS_LABEL = { live: "Live", connecting: "Connecting…", offline: "Offline" };

function LiveBadge({ status }) {
  return (
    <span className={`live-badge live-${status}`} role="status">
      <span className="live-dot" aria-hidden="true" />
      {STATUS_LABEL[status]}
    </span>
  );
}

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function ActivityFeed({ items }) {
  if (items.length === 0) return <p className="muted">Waiting for activity…</p>;
  return (
    <ul className="plain-list activity-list" aria-live="polite">
      {items.map((item, index) => (
        <li key={`${item.at}-${index}`}>
          <Link to={`/documents/${item.document_id}`}>{item.message}</Link>
          <span className="muted">{timeFormat.format(new Date(item.at))}</span>
        </li>
      ))}
    </ul>
  );
}

function QueryList({ items, empty }) {
  if (items.length === 0) return <p className="muted">{empty}</p>;
  return (
    <ol className="rank-list">
      {items.map((item) => (
        <li key={item.query}>
          <Link to={`/search?q=${encodeURIComponent(item.query)}`}>{item.query}</Link>
          <span className="muted">{item.count}</span>
        </li>
      ))}
    </ol>
  );
}

export default function DashboardPage() {
  const stats = useFetch((signal) => api.analytics(signal), [], { refreshMs: 10000 });
  const tags = useFetch((signal) => api.topBookmarkedTags(signal), [], { refreshMs: 30000 });
  const live = useLive();

  if (stats.error && !stats.data) return <ErrorState error={stats.error} onRetry={stats.reload} />;

  const data = stats.data;
  return (
    <>
      <div className="page-head">
        <h1>Dashboard</h1>
        <LiveBadge status={live.status} />
      </div>
      <p className="muted">Last 60 minutes · charts refresh every 10 seconds, trending and activity update live</p>

      {!data ? (
        <div className="grid-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card">
              <Skeleton lines={2} height={20} />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="grid-3">
            <Stat label="Zero-result rate" value={`${(data.zero_result_rate * 100).toFixed(1)}%`} />
          </div>

          <section className="card">
            <h3>Searches per minute</h3>
            {data.total_searches === 0 ? (
              <EmptyState title="No searches yet">Run a few searches and they will appear here.</EmptyState>
            ) : (
              <BarChart points={data.per_minute} />
            )}
          </section>

          <div className="grid-3">
            <section className="card">
              <h3>Trending searches</h3>
              <QueryList items={live.trending ?? data.top_queries} empty="Nothing yet." />
            </section>
            <section className="card">
              <h3>Live activity</h3>
              <ActivityFeed items={live.activity} />
            </section>
            <section className="card">
              <h3>Top bookmarked tags (7 days)</h3>
              {(tags.data ?? []).length === 0 ? (
                <p className="muted">No bookmarks yet.</p>
              ) : (
                <ol className="rank-list">
                  {tags.data.map((tag) => (
                    <li key={tag.name}>
                      <Link to={`/search?q=${encodeURIComponent(tag.name)}&tag=${tag.name}`}>{tag.name}</Link>
                      <span className="muted">{tag.bookmarks}</span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}

export function Skeleton({ lines = 3, height = 14 }) {
  return (
    <div className="skeleton-block" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton" style={{ height, width: i === lines - 1 ? "60%" : "100%" }} />
      ))}
    </div>
  );
}

export function ResultSkeletons({ count = 5 }) {
  return (
    <div role="status" aria-label="Loading results">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card">
          <div className="skeleton" style={{ height: 20, width: "55%", marginBottom: 12 }} />
          <Skeleton lines={3} />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="state">
      <div className="state-icon" aria-hidden="true">
        ◌
      </div>
      <h2>{title}</h2>
      {children && <p>{children}</p>}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <div className="state-icon" aria-hidden="true">
        !
      </div>
      <h2>Something went wrong</h2>
      <p>{error?.message || "Unknown error"}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

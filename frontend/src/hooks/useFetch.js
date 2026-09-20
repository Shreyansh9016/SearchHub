import { useCallback, useEffect, useState } from "react";

export function useFetch(fetcher, deps, { enabled = true, refreshMs = 0 } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, error: null, loading: false });
      return undefined;
    }
    const controller = new AbortController();
    setState((prev) => ({ data: prev.data, error: null, loading: true }));

    const run = () =>
      fetcher(controller.signal)
        .then((data) => setState({ data, error: null, loading: false }))
        .catch((error) => {
          if (error.name === "AbortError") return;
          setState((prev) => ({ data: prev.data, error, loading: false }));
        });

    run();
    const timer = refreshMs ? setInterval(run, refreshMs) : null;
    return () => {
      controller.abort();
      if (timer) clearInterval(timer);
    };
  }, [...deps, enabled, reloadKey, refreshMs]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  return { ...state, reload };
}

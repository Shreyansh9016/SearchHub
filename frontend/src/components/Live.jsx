import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getFreshAccessToken, refreshSession } from "../api";
import { useAuth } from "./Auth";

const LiveContext = createContext({ status: "offline", trending: null });

const MAX_DELAY_MS = 30000;
const AUTH_FAILED = 4401;

export function LiveProvider({ children }) {
  const { user } = useAuth();
  const [status, setStatus] = useState("offline");
  const [trending, setTrending] = useState(null);
  const userId = user?.id;

  useEffect(() => {
    if (!userId) {
      setStatus("offline");
      setTrending(null);
      return undefined;
    }

    let socket = null;
    let timer = null;
    let attempt = 0;
    let stopped = false;

    const scheduleReconnect = () => {
      const delay = Math.min(MAX_DELAY_MS, 1000 * 2 ** attempt) + Math.random() * 500;
      attempt += 1;
      timer = setTimeout(connect, delay);
    };

    async function connect() {
      if (stopped) return;
      setStatus("connecting");
      let token;
      try {
        token = await getFreshAccessToken();
      } catch (error) {
        scheduleReconnect();
        return;
      }
      if (stopped) return;

      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${scheme}://${window.location.host}/api/ws?token=${encodeURIComponent(token)}`);
      socket = ws;

      ws.onmessage = (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch (error) {
          return;
        }
        if (data.type === "ping") ws.send(JSON.stringify({ type: "pong" }));
        else if (data.type === "trending") setTrending(data.queries);
        else if (data.type === "connected") {
          attempt = 0;
          setStatus("live");
        }
      };

      ws.onclose = async (event) => {
        if (stopped) return;
        setStatus("offline");
        if (event.code === AUTH_FAILED) {
          try {
            await refreshSession();
          } catch (error) {
            return;
          }
        }
        scheduleReconnect();
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      if (socket) socket.close();
    };
  }, [userId]);

  const value = useMemo(() => ({ status, trending }), [status, trending]);
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive() {
  return useContext(LiveContext);
}

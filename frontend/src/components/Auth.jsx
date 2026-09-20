import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { api, clearSession, currentAccessToken, parseUser, refreshSession, setAuthLostHandler } from "../api";
import { Skeleton } from "./States";
import { useToast } from "./Toasts";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const toast = useToast();
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setAuthLostHandler(() => {
      setUser(null);
      toast.error("Your session expired. Please log in again.");
    });
  }, [toast]);

  useEffect(() => {
    let cancelled = false;
    async function restore() {
      if (api.hasSession()) {
        try {
          const data = await refreshSession();
          if (!cancelled) setUser(parseUser(data.access_token));
        } catch (error) {
          clearSession();
        }
      }
      if (!cancelled) setReady(true);
    }
    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api.login({ email, password });
    setUser(parseUser(data.access_token));
  }, []);

  const register = useCallback(async (name, email, password) => {
    const data = await api.register({ name, email, password });
    setUser(parseUser(data.access_token));
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, ready, login, register, logout }), [user, ready, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export function ProtectedRoute() {
  const { user, ready } = useAuth();
  const location = useLocation();

  if (!ready) {
    return (
      <div className="container">
        <Skeleton lines={4} height={18} />
      </div>
    );
  }
  if (!user || !currentAccessToken()) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <Outlet />;
}

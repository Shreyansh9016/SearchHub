import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "./Auth";
import CommandPalette from "./CommandPalette";

const isMac = typeof navigator !== "undefined" && /Mac/i.test(navigator.platform);

export default function Layout() {
  const { user, logout } = useAuth();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "light");

  useEffect(() => {
    const onKey = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const closePalette = useCallback(() => setPaletteOpen(false), []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch (error) {
      return;
    }
  };

  return (
    <>
      <header className="header">
        <div className="header-inner">
          <NavLink to="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              ⌕
            </span>
            SearchHub
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/dashboard">Dashboard</NavLink>
          </nav>
          <div className="header-actions">
            <button className="palette-trigger" onClick={() => setPaletteOpen(true)} aria-label="Open search">
              <span>Search…</span>
              <kbd>{isMac ? "⌘" : "Ctrl"} K</kbd>
            </button>
            <button
              className="icon-btn theme-btn"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? "☀" : "☾"}
            </button>
            <span className="user-name" title={user?.role}>
              {user?.name}
            </span>
            <button className="btn" onClick={logout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main id="main" className="container">
        <Outlet />
      </main>
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </>
  );
}

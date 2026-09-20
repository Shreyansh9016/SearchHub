import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useDebounce } from "../hooks/useDebounce";

export default function CommandPalette({ open, onClose }) {
  const [text, setText] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [active, setActive] = useState(-1);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const listId = useId();
  const debounced = useDebounce(text, 200);

  useEffect(() => {
    if (open) {
      setText("");
      setSuggestions([]);
      setActive(-1);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  useEffect(() => {
    const prefix = debounced.trim();
    if (!open || !prefix) {
      setSuggestions([]);
      return undefined;
    }
    const controller = new AbortController();
    api
      .suggest(prefix, controller.signal)
      .then((data) => {
        setSuggestions(data.suggestions);
        setActive(-1);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [debounced, open]);

  if (!open) return null;

  const go = (query) => {
    const trimmed = query.trim();
    if (!trimmed) return;
    onClose();
    navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  };

  const onKeyDown = (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (suggestions.length ? (i + 1) % suggestions.length : -1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (suggestions.length ? (i <= 0 ? suggestions.length - 1 : i - 1) : -1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      go(active >= 0 ? suggestions[active] : text);
    } else if (event.key === "Escape") {
      onClose();
    }
  };

  return (
    <div className="palette-backdrop" onMouseDown={onClose}>
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          className="palette-input"
          placeholder="Search articles…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded={suggestions.length > 0}
          aria-controls={listId}
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          aria-autocomplete="list"
        />
        <ul id={listId} role="listbox" className="palette-list">
          {suggestions.map((suggestion, index) => (
            <li
              key={suggestion}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              className={index === active ? "palette-item active" : "palette-item"}
              onMouseEnter={() => setActive(index)}
              onClick={() => go(suggestion)}
            >
              {suggestion}
            </li>
          ))}
          {text.trim() && suggestions.length === 0 && (
            <li className="palette-hint">Press Enter to search for “{text.trim()}”</li>
          )}
        </ul>
        <div className="palette-footer">
          <span>
            <kbd>↑</kbd> <kbd>↓</kbd> navigate
          </span>
          <span>
            <kbd>Enter</kbd> search
          </span>
          <span>
            <kbd>Esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}

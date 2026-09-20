export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const REFRESH_KEY = "refresh_token";

let accessToken = null;
let refreshPromise = null;
let onAuthLost = () => {};

function readRefreshToken() {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch (error) {
    return null;
  }
}

function writeRefreshToken(token) {
  try {
    if (token) localStorage.setItem(REFRESH_KEY, token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch (error) {
    return;
  }
}

function decodeClaims(token) {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(payload)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json);
  } catch (error) {
    return null;
  }
}

export function parseUser(token) {
  const claims = decodeClaims(token);
  return claims ? { id: Number(claims.sub), name: claims.name, role: claims.role } : null;
}

export function setAuthLostHandler(handler) {
  onAuthLost = handler;
}

function storeTokens(data) {
  accessToken = data.access_token;
  writeRefreshToken(data.refresh_token);
  return data;
}

export function clearSession() {
  accessToken = null;
  writeRefreshToken(null);
}

async function send(path, { method = "GET", params, body, signal, auth = true } = {}) {
  const url = new URL(`/api${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, v));
      else url.searchParams.set(key, value);
    });
  }

  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let response;
  try {
    response = await fetch(url, { method, headers, signal, body: body ? JSON.stringify(body) : undefined });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("Cannot reach the server. Is the API running?", 0);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = data.detail[0].msg;
    } catch (error) {
      message = `Request failed (${response.status})`;
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return null;
  return response.json();
}

export function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const token = readRefreshToken();
      if (!token) throw new ApiError("No session", 401);
      const data = await send("/auth/refresh", { method: "POST", body: { refresh_token: token }, auth: false });
      return storeTokens(data);
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function request(path, options = {}) {
  try {
    return await send(path, options);
  } catch (error) {
    if (error.status !== 401 || options.auth === false) throw error;
    try {
      await refreshSession();
    } catch (refreshError) {
      if (refreshError.name === "AbortError") throw refreshError;
      clearSession();
      onAuthLost();
      throw error;
    }
    return send(path, options);
  }
}

export const api = {
  register: (body) => request("/auth/register", { method: "POST", body, auth: false }).then(storeTokens),
  login: (body) => request("/auth/login", { method: "POST", body, auth: false }).then(storeTokens),
  logout: async () => {
    const token = readRefreshToken();
    clearSession();
    if (token) {
      try {
        await send("/auth/logout", { method: "POST", body: { refresh_token: token }, auth: false });
      } catch (error) {
        return;
      }
    }
  },
  hasSession: () => Boolean(readRefreshToken()),
  search: (params, signal) => request("/search", { params, signal }),
  suggest: (prefix, signal) => request("/search/suggest", { params: { prefix }, signal }),
  topBookmarkedTags: (signal) => request("/tags/top-bookmarked", { signal }),
  document: (id, signal) => request(`/documents/${id}`, { signal }),
  bookmark: (id) => request(`/documents/${id}/bookmark`, { method: "PUT" }),
  unbookmark: (id) => request(`/documents/${id}/bookmark`, { method: "DELETE" }),
  analytics: (signal) => request("/analytics/summary", { signal }),
};

export function currentAccessToken() {
  return accessToken;
}

export async function getFreshAccessToken() {
  const claims = accessToken ? decodeClaims(accessToken) : null;
  if (!claims || claims.exp * 1000 - Date.now() < 30000) await refreshSession();
  return accessToken;
}

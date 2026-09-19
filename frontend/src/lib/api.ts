import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("socmint_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// NOTE (dev-only tradeoff): storing tokens in localStorage is simple for
// this prototype but is not the Zero-Trust-ideal choice (XSS exposure).
// TODO: move to httpOnly, SameSite=strict cookies + CSRF token before any
// real deployment.

// Refresh-token handling. Without this, the backend's short-lived access
// tokens (spec: "minutes, not days") mean every session silently starts
// failing API calls once the token expires -- the refresh token was being
// stored at login and never used anywhere. Since POST /auth/refresh
// ROTATES the refresh token on every use (app/routers/auth.py), two
// concurrent 401s must not trigger two independent refresh calls: the
// second would present an already-rotated-out token and fail even though
// the session is genuinely still valid. refreshPromise below ensures only
// one refresh is ever in flight -- every other 401 that arrives while it's
// pending just awaits the same promise instead of starting its own.
let refreshPromise: Promise<string> | null = null;

function clearSessionAndRedirect() {
  localStorage.removeItem("socmint_access_token");
  localStorage.removeItem("socmint_refresh_token");
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

async function performRefresh(): Promise<string> {
  const refreshToken = localStorage.getItem("socmint_refresh_token");
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }
  // Deliberately a raw axios call, not `api.post` -- going through the
  // interceptor-wrapped instance here would recurse if this call itself
  // ever 401s (an expired/reused refresh token does exactly that).
  const { data } = await axios.post(
    `${api.defaults.baseURL}/auth/refresh`,
    { refresh_token: refreshToken }
  );
  localStorage.setItem("socmint_access_token", data.access_token);
  localStorage.setItem("socmint_refresh_token", data.refresh_token);
  return data.access_token;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const isAuthEndpoint = originalRequest?.url?.includes("/auth/login")
      || originalRequest?.url?.includes("/auth/refresh")
      || originalRequest?.url?.includes("/auth/mfa/verify");

    if (error.response?.status !== 401 || isAuthEndpoint || originalRequest._retried) {
      return Promise.reject(error);
    }
    originalRequest._retried = true;

    try {
      if (!refreshPromise) {
        refreshPromise = performRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const newAccessToken = await refreshPromise;
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      return api(originalRequest);
    } catch {
      clearSessionAndRedirect();
      return Promise.reject(error);
    }
  }
);

export default api;

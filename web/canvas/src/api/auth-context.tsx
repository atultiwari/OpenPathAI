import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { ApiClient, defaultBaseUrl } from "./client";

type AuthState = {
  client: ApiClient;
  baseUrl: string;
  token: string | null;
  setToken: (token: string | null) => void;
  setBaseUrl: (url: string) => void;
};

const AuthContext = createContext<AuthState | null>(null);

const TOKEN_KEY = "__openpathai_canvas_token__";

function readSessionToken(): string | null {
  // Bearer tokens never go to localStorage. sessionStorage is purged
  // when the tab closes and is not shared across tabs by default — a
  // small concession for usability so the user doesn't re-paste on
  // every reload.
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  return window.sessionStorage.getItem(TOKEN_KEY);
}

function writeSessionToken(value: string | null): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  if (value) {
    window.sessionStorage.setItem(TOKEN_KEY, value);
  } else {
    window.sessionStorage.removeItem(TOKEN_KEY);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [baseUrl, setBaseUrlState] = useState<string>(() => defaultBaseUrl());
  const [token, setTokenState] = useState<string | null>(() =>
    readSessionToken()
  );

  const setToken = useCallback((next: string | null) => {
    writeSessionToken(next);
    setTokenState(next);
  }, []);

  const setBaseUrl = useCallback((url: string) => {
    setBaseUrlState(url.trim() || defaultBaseUrl());
  }, []);

  const client = useMemo(
    () => new ApiClient(baseUrl, token),
    [baseUrl, token]
  );

  const value = useMemo<AuthState>(
    () => ({ client, baseUrl, token, setToken, setBaseUrl }),
    [client, baseUrl, token, setToken, setBaseUrl]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return value;
}

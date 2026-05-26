import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { apiCall, DEFAULT_BASE_URL, normalizeBaseUrl } from "../api";
import type { UserInfo } from "../types";

type AuthContextValue = {
  token: string;
  user: UserInfo | null;
  baseUrl: string;
  loading: boolean;
  setBaseUrl: (url: string) => void;
  login: (token: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const KEYS = {
  token: "ann.frontend.token",
  user: "ann.frontend.user",
  baseUrl: "ann.frontend.baseUrl",
} as const;

function readUser(): UserInfo | null {
  try {
    const v = localStorage.getItem(KEYS.user);
    return v ? (JSON.parse(v) as UserInfo) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(
    () => localStorage.getItem(KEYS.token) || "",
  );
  const [user, setUser] = useState<UserInfo | null>(readUser);
  const [baseUrl, setBaseUrlState] = useState(() =>
    normalizeBaseUrl(localStorage.getItem(KEYS.baseUrl) || DEFAULT_BASE_URL),
  );
  const [loading, setLoading] = useState(
    () => !!localStorage.getItem(KEYS.token),
  );
  const initDone = useRef(false);

  const setBaseUrl = useCallback((url: string) => {
    const normalized = normalizeBaseUrl(url);
    setBaseUrlState(normalized);
    localStorage.setItem(KEYS.baseUrl, normalized);
  }, []);

  const logout = useCallback(() => {
    setToken("");
    setUser(null);
    localStorage.removeItem(KEYS.token);
    localStorage.removeItem(KEYS.user);
  }, []);

  const fetchMe = useCallback(
    async (tok: string, base: string): Promise<UserInfo | null> => {
      try {
        const resp = await apiCall<UserInfo>({
          baseUrl: base,
          token: tok,
          path: "/auth/me",
        });
        return resp.data;
      } catch {
        return null;
      }
    },
    [],
  );

  const login = useCallback(
    async (tok: string) => {
      localStorage.setItem(KEYS.token, tok);
      setToken(tok);
      const me = await fetchMe(tok, baseUrl);
      if (me) {
        setUser(me);
        localStorage.setItem(KEYS.user, JSON.stringify(me));
      }
    },
    [fetchMe, baseUrl],
  );

  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;

    const savedToken = localStorage.getItem(KEYS.token);
    if (!savedToken) {
      setLoading(false);
      return;
    }

    void fetchMe(
      savedToken,
      normalizeBaseUrl(localStorage.getItem(KEYS.baseUrl) || DEFAULT_BASE_URL),
    ).then((me) => {
      if (me) {
        setUser(me);
        localStorage.setItem(KEYS.user, JSON.stringify(me));
      } else {
        logout();
      }
      setLoading(false);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const value = useMemo<AuthContextValue>(
    () => ({ token, user, baseUrl, loading, setBaseUrl, login, logout }),
    [token, user, baseUrl, loading, setBaseUrl, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}

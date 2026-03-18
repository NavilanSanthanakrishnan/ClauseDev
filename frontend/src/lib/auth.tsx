import { startTransition, useEffect, useMemo, useState } from 'react';

import { api, type AuthResponse } from './api';
import { AuthContext, type AuthContextValue, type AuthState } from './auth-context';

const STORAGE_KEY = 'clauseai.auth';

function readStoredAuth(): AuthState {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return { user: null, accessToken: null, refreshToken: null };
  }

  try {
    return JSON.parse(raw) as AuthState;
  } catch {
    return { user: null, accessToken: null, refreshToken: null };
  }
}

function persistAuth(payload: AuthState) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function normalizeAuth(response: AuthResponse): AuthState {
  return {
    user: response.user,
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(() => readStoredAuth());
  const [isRestoring, setIsRestoring] = useState(true);

  useEffect(() => {
    async function restore() {
      const stored = readStoredAuth();
      if (!stored.accessToken) {
        setIsRestoring(false);
        return;
      }

      try {
        const user = await api.me(stored.accessToken);
        startTransition(() => {
          const next = { ...stored, user };
          setState(next);
          persistAuth(next);
        });
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
        setState({ user: null, accessToken: null, refreshToken: null });
      } finally {
        setIsRestoring(false);
      }
    }

    void restore();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      isRestoring,
      login: async (email, password) => {
        const auth = normalizeAuth(await api.login({ email, password }));
        persistAuth(auth);
        setState(auth);
      },
      signup: async (email, password, displayName) => {
        const auth = normalizeAuth(await api.signup({ email, password, display_name: displayName }));
        persistAuth(auth);
        setState(auth);
      },
      logout: async () => {
        if (state.refreshToken) {
          await api.logout(state.refreshToken).catch(() => undefined);
        }
        window.localStorage.removeItem(STORAGE_KEY);
        setState({ user: null, accessToken: null, refreshToken: null });
      },
    }),
    [isRestoring, state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

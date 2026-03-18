import { createContext, useContext } from 'react';

import type { User } from './api';

export type AuthState = {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
};

export type AuthContextValue = AuthState & {
  isRestoring: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}

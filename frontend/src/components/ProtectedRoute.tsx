import type { PropsWithChildren } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../lib/auth-context';

export function ProtectedRoute({ children }: PropsWithChildren) {
  const location = useLocation();
  const { user, isRestoring } = useAuth();

  if (isRestoring) {
    return (
      <div className="public-shell">
        <div className="loading-shell">
          <div className="loading-pulse" />
          <strong>Restoring your workspace</strong>
          <p>Loading your saved session and protected pages.</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}

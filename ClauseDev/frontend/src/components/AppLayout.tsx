import type { PropsWithChildren } from 'react';

import { Sidebar } from './Sidebar';

export function AppLayout({ children }: PropsWithChildren) {
  return (
    <div className="workspace-app">
      <Sidebar />
      <div className="workspace-main">
        <div className="workspace-main-bg" />
        <main className="workspace-page">{children}</main>
      </div>
    </div>
  );
}

import { Navigate, Outlet, Route, Routes } from 'react-router-dom';

import { AppLayout } from './components/AppLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { BillsDatabasePage } from './pages/BillsDatabasePage';
import { BillsHomePage } from './pages/BillsHomePage';
import { ChatPage } from './pages/ChatPage';
import { EditorPage } from './pages/EditorPage';
import { HomePage } from './pages/HomePage';
import { LawsDatabasePage } from './pages/LawsDatabasePage';
import { LoginPage } from './pages/LoginPage';
import { ProjectStagePage } from './pages/ProjectStagePage';
import { SignupPage } from './pages/SignupPage';
import { SettingsPage } from './pages/SettingsPage';

function ProtectedShell() {
  return (
    <ProtectedRoute>
      <AppLayout>
        <Outlet />
      </AppLayout>
    </ProtectedRoute>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route element={<ProtectedShell />}>
        <Route path="/bills" element={<BillsHomePage />} />
        <Route path="/bills/database" element={<BillsDatabasePage />} />
        <Route path="/laws/database" element={<LawsDatabasePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/projects/:projectId/upload" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/extraction" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/metadata" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/similar-bills" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/similar-bills/report" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/similar-bills/fixes" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/legal" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/legal/report" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/legal/fixes" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/stakeholders" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/stakeholders/report" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/stakeholders/fixes" element={<ProjectStagePage />} />
        <Route path="/projects/:projectId/editor" element={<EditorPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;

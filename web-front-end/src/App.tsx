import { Routes, Route, Navigate } from 'react-router-dom';
import SystemAccessPage from './components/SystemAccessPage';

/**
 * Single-page access: only / renders SystemAccessPage.
 * All other paths redirect to / (client-side). Safe for direct URLs and manual navigation.
 * Deployment: serve index.html for all routes (SPA fallback) so client-side redirect works.
 */
function App() {
  return (
    <Routes>
      <Route path="/" element={<SystemAccessPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import MainLayout from './layouts/MainLayout';
import ImportPage from './pages/ImportPage';
import ItemsPage from './pages/ItemsPage';
import AssessmentPage from './pages/AssessmentPage';
import ReportPage from './pages/ReportPage';

export default function App() {
  return (
    <ConfigProvider theme={{
      token: {
        colorPrimary: '#1a1f3a',
        borderRadius: 8,
      },
    }}>
      <BrowserRouter>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/import" element={<ImportPage />} />
            <Route path="/items" element={<ItemsPage />} />
            <Route path="/assessment" element={<AssessmentPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/" element={<Navigate to="/assessment" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

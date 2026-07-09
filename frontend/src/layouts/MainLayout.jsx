import { useState, useEffect } from 'react';
import { Layout, Menu } from 'antd';
import {
  UploadOutlined, SettingOutlined, DashboardOutlined,
  FileTextOutlined, HistoryOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { fetchImportStatus, fetchHistory } from '../api';

const { Sider, Content } = Layout;

const menuItems = [
  { key: '/import', icon: <UploadOutlined />, label: '数据导入' },
  { key: '/items', icon: <SettingOutlined />, label: '评估指标' },
  { key: '/assessment', icon: <DashboardOutlined />, label: '执行评估' },
  { key: '/report', icon: <FileTextOutlined />, label: '报告生成' },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [hasData, setHasData] = useState(false);
  const [hasHistory, setHasHistory] = useState(false);
  const [reportDone, setReportDone] = useState(false);

  useEffect(() => {
    Promise.all([fetchImportStatus(), fetchHistory(1)]).then(([sr, hr]) => {
      const counts = sr.data?.counts || {};
      setHasData(Object.values(counts).some(c => c > 0));
      setHasHistory((hr.data?.history || []).length > 0);
    }).catch(() => {});
    setReportDone(localStorage.getItem('report_done') === '1');
  }, []);

  const canEnter = (key) => {
    if (key === '/import' || key === '/items') return true;
    if (key === '/assessment') return hasData;
    if (key === '/report') return hasHistory;
    return false;
  };

  // 简化为两步导航：评估和报告需要前置条件
  const getSelectedKey = () => {
    const path = location.pathname;
    if (path.startsWith('/import')) return '/import';
    if (path.startsWith('/items')) return '/items';
    if (path.startsWith('/assessment') || path.startsWith('/history')) return '/assessment';
    if (path.startsWith('/report')) return '/report';
    return '/assessment';
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header>
        <span style={{ color: '#fff', fontSize: '1.15rem', fontWeight: 600 }}>
          公司洗钱风险评估
        </span>
      </Layout.Header>
      <Layout>
        <Sider width={200} style={{ paddingTop: 16 }}>
          <Menu
            mode="inline"
            selectedKeys={[getSelectedKey()]}
            items={menuItems.map(m => ({
              ...m,
              disabled: !canEnter(m.key) && m.key !== getSelectedKey(),
            }))}
            onClick={({ key }) => canEnter(key) ? navigate(key) : null}
          />
        </Sider>
        <Content style={{ padding: 24, background: '#f0f2f5', minHeight: 'calc(100vh - 56px)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

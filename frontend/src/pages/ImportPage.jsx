import { useState, useEffect } from 'react';
import { Card, Button, Upload, Table, Tag, Space, Steps, Divider, message } from 'antd';
import { UploadOutlined, DownloadOutlined, ClearOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { uploadCsv, confirmImport, clearData, fetchImportStatus } from '../api';

const TABLES = [
  { key: 'customer', label: '客户表', icon: '👤' },
  { key: 'account', label: '账户表', icon: '💳' },
  { key: 'trans_record', label: '交易表', icon: '💸' },
  { key: 'product', label: '产品表', icon: '📦' },
];

export default function ImportPage() {
  const [previews, setPreviews] = useState({});
  const [importResult, setImportResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTable, setActiveTable] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    fetchImportStatus().then(r => {
      const counts = r.data?.counts || {};
      const has = Object.values(counts).some(c => c > 0);
      if (has) {
        const pre = {};
        Object.entries(counts).forEach(([k, v]) => {
          if (v > 0) pre[k] = { done: true, count: v };
        });
        setPreviews(pre);
        setCurrentStep(1);
      }
    }).catch(() => {});
  }, []);

  const handleUpload = async (table, file) => {
    try {
      const r = await uploadCsv(table, file);
      const pv = r.data?.preview || {};
      console.log('Upload response:', table, pv);
      setPreviews(prev => {
        const next = {
          ...prev,
          [table]: { done: true, count: pv.total_rows, warnings: pv.validation?.error_count || 0, preview: pv },
        };
        console.log('New previews:', next);
        return next;
      });
      setActiveTable(table);
      setCurrentStep(1);
      message.success(`${TABLES.find(t => t.key === table)?.label} 上传成功 (${pv.total_rows}条)`);
    } catch (e) {
      message.error(`上传失败: ${e.response?.data?.detail || e.message}`);
    }
  };

  // Auto-select first uploaded table
  useEffect(() => {
    if (!activeTable) {
      const first = TABLES.find(t => previews[t.key]?.done);
      if (first) setActiveTable(first.key);
    }
  }, [previews, activeTable]);

  const handleConfirm = async () => {
    setLoading(true);
    try {
      const r = await confirmImport();
      setImportResult(r.data);
      setCurrentStep(2);
      message.success(`成功导入 ${r.data?.imported || 0} 条记录`);
    } catch (e) {
      message.error('导入失败');
    }
    setLoading(false);
  };

  const handleClear = async () => {
    await clearData();
    setPreviews({});
    setImportResult(null);
    setActiveTable(null);
    setCurrentStep(0);
    localStorage.removeItem('report_done');
    message.success('数据已清空');
  };

  const activePreview = activeTable ? previews[activeTable]?.preview : null;
  const hasUploads = TABLES.some(t => previews[t.key]?.done);

  return (
    <div>
      <Steps current={currentStep} size="small" style={{ marginBottom: 24 }}
        items={[
          { title: '下载CSV模板', description: '按模板整理数据' },
          { title: '预览并调整数据', description: '上传并校验' },
          { title: '查看导入结果', description: '确认写入' },
        ]} />

      {/* Step 1: Templates */}
      <Card title="第一步：下载CSV模板" style={{ marginBottom: 16 }} size="small">
        <Space wrap>
          {TABLES.map(t => (
            <Button key={t.key} icon={<DownloadOutlined />}
              href={`/api/import/templates/${t.key}`}>
              {t.icon} {t.label}模板
            </Button>
          ))}
        </Space>
      </Card>

      {/* Step 2: Upload */}
      <Card title="第二步：预览并调整数据" style={{ marginBottom: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {TABLES.map(t => {
            const info = previews[t.key];
            const isDone = info?.done;
            const isWarn = isDone && info?.warnings > 0;
            const isActive = activeTable === t.key;
            return (
              <Card key={t.key} size="small"
                title={<span>{t.icon} {t.label}</span>}
                style={{
                  borderColor: isActive ? '#4a90d9' : isDone ? '#52c41a' : '#d9d9d9',
                  borderWidth: isActive ? 2 : 1,
                  cursor: isDone ? 'pointer' : 'default',
                  background: isDone ? '#f6ffed' : '#fff',
                }}
                onClick={() => isDone && setActiveTable(t.key)}
                extra={isDone ? (
                  <Tag color={isWarn ? 'orange' : 'green'}>
                    {isWarn ? `${info.count}条/${info.warnings}警告` : `${info.count}条 ✓`}
                  </Tag>
                ) : null}
              >
                <Upload beforeUpload={(file) => { handleUpload(t.key, file); return false; }}
                  showUploadList={false} accept=".csv">
                  <Button icon={<UploadOutlined />} block>上传 {t.label} CSV</Button>
                </Upload>
              </Card>
            );
          })}
        </div>

        <Divider />

        {/* Preview */}
        {activePreview ? (
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8, fontWeight: 600 }}>
              {TABLES.find(t => t.key === activeTable)?.label} — 预览
              ({activePreview.preview_rows?.length || 0}行 / 共{activePreview.total_rows}行)
              {activePreview.validation?.error_count > 0
                ? <Tag color="orange" style={{ marginLeft: 8 }}>⚠ {activePreview.validation.error_count} 个校验警告</Tag>
                : <Tag color="green" style={{ marginLeft: 8 }}>✓ 全部通过</Tag>}
            </div>
            {activePreview.validation?.errors?.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                {activePreview.validation.errors.slice(0, 10).map((e, i) => (
                  <div key={i} style={{ color: '#d48806', fontSize: 13 }}>
                    第{e.row}行: {e.errors?.join('; ')}
                  </div>
                ))}
              </div>
            )}
            <Table size="small" pagination={false} scroll={{ x: 800 }}
              dataSource={(activePreview.preview_rows || []).map((r, i) => ({ ...r, _key: i }))}
              columns={(activePreview.columns || []).map(c => ({ title: c, dataIndex: c, ellipsis: true, width: 130 }))}
              rowKey="_key" />
          </div>
        ) : null}

        <Space>
          <Button type="primary" onClick={handleConfirm} loading={loading}
            disabled={!hasUploads}>
            确认导入
          </Button>
          <Button danger icon={<ClearOutlined />} onClick={handleClear}>
            清空数据
          </Button>
        </Space>
      </Card>

      {/* Step 3: Results */}
      {importResult && (
        <Card title="第三步：查看导入结果" style={{ marginBottom: 16 }}>
          {Object.entries(importResult.tables || {}).map(([k, v]) => (
            <div key={k} style={{ padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
              <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
              <b>{v.label}</b>: 总计 {v.total_rows} 条全部写入 ✓
              {v.warnings > 0 && <Tag color="orange" style={{ marginLeft: 8 }}>{v.warnings} 条质量问题</Tag>}
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

import { useState, useEffect } from 'react';
import { Card, Table, Select, Tag, Button, message } from 'antd';
import { fetchItems, fetchPresets, toggleItem } from '../api';

const DIM_NAMES = { customer: '客户风险', product: '产品/业务风险', channel: '渠道风险', geography: '地域风险' };
const DIM_COLORS = { customer: 'blue', product: 'orange', channel: 'purple', geography: 'green' };

export default function ItemsPage() {
  const [items, setItems] = useState([]);
  const [preset, setPreset] = useState('preset_securities');
  const [presets, setPresets] = useState([]);

  useEffect(() => {
    fetchPresets().then(r => setPresets(r.data?.presets || [])).catch(() => {});
  }, []);

  useEffect(() => {
    fetchItems(preset).then(r => {
      const list = r.data?.items || [];
      const counters = {};
      const itemsWithCode = list.map(it => {
        const prefix = { customer: 'cust', product: 'prod', channel: 'chan', geography: 'geo' }[it.dimension] || 'oth';
        counters[prefix] = (counters[prefix] || 0) + 1;
        return { ...it, code: prefix + '-' + String(counters[prefix]).padStart(2, '0') };
      });
      setItems(itemsWithCode);
    }).catch(() => {});
  }, [preset]);

  const handleToggle = async (key, enabled) => {
    await toggleItem(key, enabled);
    setItems(prev => prev.map(it => it.item_key === key ? { ...it, enabled: enabled ? 0 : 1 } : it));
    message.success(enabled ? '已禁用' : '已启用');
  };

  const columns = [
    { title: '操作', width: 80, render: (_, r) => (
      <Button size="small" type={r.enabled ? 'default' : 'primary'} danger={r.enabled}
        onClick={() => handleToggle(r.item_key, r.enabled)}>
        {r.enabled ? '禁用' : '启用'}
      </Button>
    )},
    { title: '状态', width: 80, render: (_, r) => (
      <Tag color={r.enabled ? 'green' : 'default'}>{r.enabled ? '启用中' : '禁用中'}</Tag>
    )},
    { title: '编号', dataIndex: 'code', width: 90, render: v => <span style={{ fontFamily: 'monospace', color: '#888' }}>{v}</span> },
    { title: '维度', dataIndex: 'dimension', width: 100, render: v => <Tag color={DIM_COLORS[v]}>{DIM_NAMES[v]}</Tag> },
    { title: '指标名称', dataIndex: 'name', render: v => <b>{v}</b> },
    { title: '类型', dataIndex: 'category', width: 90, render: v => <Tag color={v === 'data_driven' ? 'processing' : 'warning'}>{v === 'data_driven' ? '数据驱动' : '框架评估'}</Tag> },
    { title: '说明', dataIndex: 'description', ellipsis: true },
  ];

  return (
    <Card title="评估指标管理" extra={
      <Select value={preset} onChange={setPreset} style={{ width: 160 }}>
        {presets.map(p => <Select.Option key={p.id} value={p.id}>{p.name}</Select.Option>)}
      </Select>
    }>
      <Table columns={columns} dataSource={items} rowKey="item_key" size="middle"
        rowClassName={r => r.enabled ? '' : 'ant-table-row-gray'}
        pagination={false} scroll={{ x: 900 }} />
    </Card>
  );
}

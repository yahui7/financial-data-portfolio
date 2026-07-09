import { useState, useEffect, useRef } from 'react';
import { Card, Button, Select, Row, Col, Table, Tag, Collapse, Descriptions, Space, message } from 'antd';
import { PlayCircleOutlined, HistoryOutlined } from '@ant-design/icons';
import * as echarts from 'echarts';
import { runAssessment, fetchPresets, fetchHistory, fetchHistoryDetail, fetchTrend, fetchCompare } from '../api';

const DIM_LABELS = ['客户风险', '产品/业务风险', '渠道风险', '地域风险'];
const DIM_KEYS = ['customer', 'product', 'channel', 'geography'];

export default function AssessmentPage() {
  const [preset, setPreset] = useState('preset_securities');
  const [presets, setPresets] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyList, setHistoryList] = useState([]);
  const [compareData, setCompareData] = useState(null);
  const [compareIds, setCompareIds] = useState({ a: null, b: null });
  const [trendData, setTrendData] = useState([]);
  const radarRef = useRef(null);
  const trendRef = useRef(null);

  useEffect(() => {
    fetchPresets().then(r => setPresets(r.data?.presets || [])).catch(() => {});
    // 自动加载最近评估
    fetchHistory(1).then(async r => {
      const list = r.data?.history || [];
      if (list.length > 0) {
        const dt = await fetchHistoryDetail(list[0].id);
        const rec = dt.data?.record;
        if (rec?.dimensions) {
          setResult({
            assessment_time: rec.assess_date,
            preset_id: rec.preset_id,
            overall_score: rec.overall_score,
            risk_level: rec.risk_level,
            risk_level_name: { '低': '低风险', '中': '中风险', '高': '高风险', '最高': '最高风险' }[rec.risk_level] || rec.risk_level,
            data_summary: rec.data_summary,
            dimensions: rec.dimensions,
            recommendations: rec.recommendations,
          });
          setPreset(rec.preset_id || 'preset_securities');
        }
      }
    }).catch(() => {});
  }, []);

  const handleAssess = async () => {
    setLoading(true);
    try {
      const r = await runAssessment(preset);
      if (r.data?.status === 'ok') setResult(r.data);
    } catch (e) { message.error('评估失败'); }
    setLoading(false);
  };

  const handleShowHistory = async () => {
    const newState = !showHistory;
    setShowHistory(newState);
    if (newState) {
      const hr = await fetchHistory(50);
      const list = hr.data?.history || [];
      setHistoryList(list);
      if (list.length >= 2) setCompareIds({ a: list[0].id, b: list[1].id });
      const tr = await fetchTrend(50);
      setTrendData(tr.data?.trend || []);
    }
  };

  const handleCompare = async () => {
    if (!compareIds.a || !compareIds.b) return;
    const r = await fetchCompare(compareIds.a, compareIds.b);
    setCompareData(r.data);
  };

  const radarOption = result ? {
    tooltip: {},
    radar: {
      indicator: DIM_KEYS.map((k, i) => ({ name: DIM_LABELS[i] + '\n' + result.dimensions[k].score + '分', max: 100 })),
    },
    series: [{
      type: 'radar', data: [{ value: DIM_KEYS.map(k => result.dimensions[k].score), name: '评估',
        areaStyle: { color: 'rgba(74,144,226,0.12)' }, lineStyle: { color: '#4a90e2', width: 2 } }],
    }],
  } : {};

  const trendOption = trendData.length > 0 ? {
    tooltip: { trigger: 'axis' },
    legend: { data: ['综合', '客户', '产品', '渠道', '地域'] },
    xAxis: { type: 'category', data: trendData.map(d => d.date?.slice(0, 10)) },
    yAxis: { type: 'value', min: 0, max: 100 },
    series: [
      { name: '综合', type: 'line', data: trendData.map(d => d.overall), lineStyle: { width: 3 } },
      { name: '客户', type: 'line', data: trendData.map(d => d.customer) },
      { name: '产品', type: 'line', data: trendData.map(d => d.product) },
      { name: '渠道', type: 'line', data: trendData.map(d => d.channel) },
      { name: '地域', type: 'line', data: trendData.map(d => d.geography) },
    ],
  } : {};

  const scoreColor = (s) => s <= 30 ? '#52c41a' : s <= 60 ? '#faad14' : '#e74c3c';
  const riskTag = (r) => r === '高' ? 'red' : r === '中' ? 'gold' : 'green';

  return (
    <div>
      {!showHistory ? (
        <>
          <Card style={{ marginBottom: 16 }}>
            <Space>
              <span style={{ fontWeight: 600 }}>选择模板</span>
              <Select value={preset} onChange={setPreset} style={{ width: 160 }}>
                {presets.map(p => <Select.Option key={p.id} value={p.id}>{p.name}</Select.Option>)}
              </Select>
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleAssess} loading={loading}>
                执行评估
              </Button>
              <Button icon={<HistoryOutlined />} onClick={handleShowHistory}>评估历史</Button>
            </Space>
          </Card>

          {!result && <Card><div style={{ textAlign: 'center', padding: 40, color: '#bbb' }}>选择模板，点击"执行评估"开始</div></Card>}

          {result && (
            <>
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={6}>
                  <Card style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 13, color: '#888', marginBottom: 8 }}>综合风险评分</div>
                    <div style={{ fontSize: 56, fontWeight: 700, color: scoreColor(result.overall_score) }}>
                      {result.overall_score}
                    </div>
                    <Tag color={riskTag(result.risk_level)} style={{ fontSize: 14, padding: '2px 16px' }}>
                      {result.risk_level_name}
                    </Tag>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="四维风险雷达"><div ref={el => { if (el && !radarRef.current) { radarRef.current = echarts.init(el); } if (radarRef.current && result) radarRef.current.setOption(radarOption, true); }} style={{ height: 300 }} /></Card>
                </Col>
                <Col span={6}>
                  <Card title="关键发现">
                    {(() => {
                      const all = DIM_KEYS.flatMap(k => result.dimensions[k].items);
                      const h = all.filter(i => i.risk === '高').length;
                      const m = all.filter(i => i.risk === '中').length;
                      const l = all.filter(i => i.risk === '低').length;
                      const top = all.find(i => i.risk === '高');
                      return <>
                        <div style={{ fontSize: 28, fontWeight: 700, color: '#e74c3c' }}>{h} <span style={{ fontSize: 14, color: '#888' }}>项高风险</span></div>
                        <div style={{ fontSize: 22, fontWeight: 700, color: '#faad14' }}>{m} <span style={{ fontSize: 13, color: '#888' }}>项中风险</span></div>
                        <div style={{ fontSize: 18, color: '#52c41a' }}>{l} <span style={{ fontSize: 13, color: '#888' }}>项低风险</span></div>
                        {top && <div style={{ marginTop: 12, padding: 8, background: '#fff2f0', borderRadius: 6, color: '#cf1322', fontSize: 13 }}>
                          ⚠ 最突出: <b>{top.name}</b><br/>{top.remark}
                        </div>}
                      </>;
                    })()}
                  </Card>
                </Col>
              </Row>

              <Card size="small" style={{ marginBottom: 16 }}>
                <Descriptions column={4} size="small">
                  <Descriptions.Item label="👤 客户">{result.data_summary.customers}人</Descriptions.Item>
                  <Descriptions.Item label="💳 账户">{result.data_summary.accounts}个</Descriptions.Item>
                  <Descriptions.Item label="💸 交易">{result.data_summary.transactions}笔</Descriptions.Item>
                  <Descriptions.Item label="📦 产品">{result.data_summary.products}只</Descriptions.Item>
                </Descriptions>
              </Card>

              <Collapse defaultActiveKey={DIM_KEYS} items={DIM_KEYS.map((k, i) => ({
                key: k, label: `${i + 1}. ${DIM_LABELS[i]} — ${result.dimensions[k].score} 分`,
                children: (
                  <>
                    <Table size="small" pagination={false} dataSource={result.dimensions[k].items}
                      columns={[
                        { title: '评估项', dataIndex: 'name', render: v => <b>{v}</b> },
                        { title: '风险', dataIndex: 'risk', width: 60, render: v => <Tag color={riskTag(v)}>{v}</Tag> },
                        { title: '数据详情', dataIndex: 'detail', render: v => <span style={{ fontSize: 13 }}>{v}</span> },
                        { title: '说明', dataIndex: 'remark', render: v => <span style={{ fontSize: 13, color: '#888' }}>{v}</span> },
                      ]} rowKey="name" />
                    {result.dimensions[k].recommendations?.length > 0 && (
                      <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                        {result.dimensions[k].recommendations.map((r, j) => <li key={j} style={{ fontSize: 13, color: '#666' }}>{r}</li>)}
                      </ul>
                    )}
                  </>
                ),
              }))} />
            </>
          )}
        </>
      ) : (
        <>
          <Card style={{ marginBottom: 16 }}>
            <Space>
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleShowHistory}>返回评估</Button>
            </Space>
          </Card>

          {/* 对比分析 */}
          <Card title="对比分析" style={{ marginBottom: 16 }}>
            <Space style={{ marginBottom: 16 }}>
              <Select placeholder="评估A" value={compareIds.a} onChange={v => setCompareIds(prev => ({ ...prev, a: v }))}
                style={{ width: 280 }} options={historyList.map(h => ({ label: `#${h.id} ${h.assess_date} (${h.overall_score}分)`, value: h.id }))} />
              <span style={{ fontWeight: 700, color: '#999' }}>VS</span>
              <Select placeholder="评估B" value={compareIds.b} onChange={v => setCompareIds(prev => ({ ...prev, b: v }))}
                style={{ width: 280 }} options={historyList.map(h => ({ label: `#${h.id} ${h.assess_date} (${h.overall_score}分)`, value: h.id }))} />
              <Button onClick={handleCompare}>对比</Button>
            </Space>
            {compareData && (
              <Row gutter={16}>
                <Col span={12}><Card size="small" style={{ textAlign: 'center' }}>
                  <div style={{ color: '#999' }}>{compareData.assessment_a.date}</div>
                  <div style={{ fontSize: 36, fontWeight: 700 }}>{compareData.assessment_a.overall_score}</div>
                  <Tag>{compareData.assessment_a.risk_level}</Tag>
                </Card></Col>
                <Col span={12}><Card size="small" style={{ textAlign: 'center' }}>
                  <div style={{ color: '#999' }}>{compareData.assessment_b.date}</div>
                  <div style={{ fontSize: 36, fontWeight: 700 }}>{compareData.assessment_b.overall_score}</div>
                  <Tag>{compareData.assessment_b.risk_level}</Tag>
                </Card></Col>
                <Col span={24} style={{ marginTop: 12 }}>
                  {Object.entries(compareData.comparison || {}).map(([k, v]) => (
                    <span key={k} style={{ marginRight: 24 }}>
                      <span style={{ color: '#888' }}>{k === 'overall' ? '综合' : DIM_LABELS[DIM_KEYS.indexOf(k)]}: </span>
                      <span style={{ color: v.direction === 'up' ? '#e74c3c' : v.direction === 'down' ? '#52c41a' : '#999', fontWeight: 700 }}>{v.label}</span>
                    </span>
                  ))}
                </Col>
              </Row>
            )}
          </Card>

          {/* 评估记录 */}
          <Card title="评估记录" style={{ marginBottom: 16 }}>
            <Table size="small" dataSource={historyList} rowKey="id" columns={[
              { title: '日期', dataIndex: 'assess_date' },
              { title: '模板', dataIndex: 'preset_id', render: v => ({ preset_securities: '基金', preset_bank: '银行', preset_insurance: '保险' }[v] || v) },
              { title: '评分', dataIndex: 'overall_score', render: v => <b>{v}</b> },
              { title: '等级', dataIndex: 'risk_level', render: v => <Tag color={riskTag(v)}>{v}</Tag> },
              { title: '客户', dataIndex: 'customer_count' },
              { title: '交易', dataIndex: 'trans_count' },
            ]} pagination={false} />
          </Card>

          {/* 趋势分析 */}
          <Card title="趋势分析">
            {trendData.length > 0 ? <div ref={el => { if (el && !trendRef.current) { trendRef.current = echarts.init(el); } if (trendRef.current) trendRef.current.setOption(trendOption, true); }} style={{ height: 400 }} /> : <div style={{ textAlign: 'center', color: '#bbb', padding: 40 }}>暂无数据</div>}
          </Card>
        </>
      )}
    </div>
  );
}

import { useState, useEffect, useRef } from 'react';
import {
  Card, Tabs, Table, Button, Input, Select, Space, Tag, Modal,
  Popconfirm, message, List, Divider, Steps, Upload,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, CopyOutlined,
  FileWordOutlined, EyeOutlined, DownloadOutlined, SaveOutlined,
  UploadOutlined, SwapOutlined,
} from '@ant-design/icons';
import {
  fetchTemplates, fetchTemplateDetail, saveTemplate, deleteTemplate,
  downloadCsvTemplate, uploadCsv, generateReport, exportWord,
  fetchReportHistory, fetchReportHistoryDetail, saveReportHistory,
  deleteReportHistory, exportHistoryWord, compareHistory,
} from '../api';

/* ═══════════════════════════════════════════════════════
   模板管理 Tab
   ═══════════════════════════════════════════════════════ */
function TemplateTab({ onSelect }) {
  const [templates, setTemplates] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [tplName, setTplName] = useState('');
  const [tplDesc, setTplDesc] = useState('');
  const [sections, setSections] = useState([]);

  useEffect(() => { load(); }, []);

  const load = () => fetchTemplates().then(r => setTemplates(r.data?.templates || []));

  const openNew = () => {
    setEditingId(null); setTplName(''); setTplDesc('');
    setSections([{ title: '', content: '' }]); setModalOpen(true);
  };

  const openEdit = async (tpl) => {
    if (tpl.preset) return message.warning('系统预设模板不可编辑，请先复制');
    const res = await fetchTemplateDetail(tpl.id);
    const full = res.data?.template || tpl;
    setEditingId(full.id); setTplName(full.name); setTplDesc(full.description || '');
    setSections((full.sections || []).map(s => ({ title: s.title, content: s.content || '' })));
    setModalOpen(true);
  };

  const copyTpl = async (tpl) => {
    const res = await fetchTemplateDetail(tpl.id);
    const full = res.data?.template || tpl;
    await saveTemplate({
      name: full.name + ' - 副本',
      description: full.description || '',
      sections: (full.sections || []).map(s => ({ title: s.title, content: s.content || '' })),
    });
    message.success('已复制'); load();
  };

  const del = async (id) => { await deleteTemplate(id); message.success('已删除'); load(); };

  const save = async () => {
    if (!tplName.trim()) return message.warning('请输入模板名称');
    const secs = sections.filter(s => s.title.trim());
    if (!secs.length) return message.warning('至少需要一个章节');
    await saveTemplate({
      id: editingId || undefined,
      name: tplName, description: tplDesc,
      sections: secs.map(s => ({ title: s.title, content: s.content })),
    });
    message.success('模板已保存'); setModalOpen(false); load();
  };

  const addSection = () => setSections([...sections, { title: '', content: '' }]);
  const removeSection = (i) => setSections(sections.filter((_, idx) => idx !== i));

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openNew}>新建模板</Button>
      </Space>
      <Table size="middle" dataSource={templates} rowKey="id" pagination={false}
        columns={[
          { title: '模板名称', dataIndex: 'name', render: (v, r) => <><b>{v}</b> {r.preset && <Tag color="blue">系统预设</Tag>}</> },
          { title: '描述', dataIndex: 'description', ellipsis: true },
          { title: '章节数', render: (_, r) => (r.sections || []).length },
          {
            title: '操作', width: 300,
            render: (_, r) => (
              <Space>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
                <Button size="small" icon={<CopyOutlined />} onClick={() => copyTpl(r)}>复制</Button>
                {!r.preset && (
                  <Popconfirm title="确定删除？" onConfirm={() => del(r.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                )}
                <Button size="small" onClick={() => onSelect?.(r)}>选用</Button>
              </Space>
            ),
          },
        ]} />

      <Modal title={editingId ? '编辑模板' : '新建模板'} open={modalOpen}
        onOk={save} onCancel={() => setModalOpen(false)} width={800}
        okText="保存" cancelText="取消">
        <Input placeholder="模板名称" value={tplName} onChange={e => setTplName(e.target.value)}
          style={{ marginBottom: 8, fontWeight: 600, fontSize: 15 }} />
        <Input placeholder="模板描述（可选）" value={tplDesc} onChange={e => setTplDesc(e.target.value)}
          style={{ marginBottom: 16 }} />
        <Divider style={{ margin: '8px 0' }} />
        <List dataSource={sections} renderItem={(s, i) => (
          <div key={i} style={{ marginBottom: 12, border: '1px solid #f0f0f0', borderRadius: 8, padding: 10 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
              <Input placeholder="章节标题" value={s.title}
                onChange={e => { const u = [...sections]; u[i].title = e.target.value; setSections(u); }}
                style={{ fontWeight: 600, flex: 1 }} />
              <Button size="small" danger onClick={() => removeSection(i)}>删除</Button>
            </div>
            <Input.TextArea placeholder="章节内容，使用 {{变量名}} 标记占位符" value={s.content}
              onChange={e => { const u = [...sections]; u[i].content = e.target.value; setSections(u); }}
              rows={6} />
          </div>
        )} />
        <Button onClick={addSection} icon={<PlusOutlined />} block>添加章节</Button>
      </Modal>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   生成报告 Tab — 三步向导
   ═══════════════════════════════════════════════════════ */
function GenerateTab({ selectedTpl }) {
  const [templates, setTemplates] = useState([]);
  const [tplId, setTplId] = useState(null);
  const [tplDetail, setTplDetail] = useState(null);
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState('form'); // 'form' | 'csv'
  const [formData, setFormData] = useState({});
  const [csvData, setCsvData] = useState(null);
  const [csvFile, setCsvFile] = useState(null);
  const [csvStatus, setCsvStatus] = useState('');
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [report, setReport] = useState(null);

  useEffect(() => {
    fetchTemplates().then(r => {
      const list = r.data?.templates || [];
      setTemplates(list);
      const id = selectedTpl?.id || list[0]?.id;
      if (id) { setTplId(id); loadTplDetail(id); }
    });
  }, []);

  const loadTplDetail = async (id) => {
    const res = await fetchTemplateDetail(id);
    if (res.data?.template) {
      setTplDetail(res.data.template);
      setTitle(res.data.template.name || '');
    }
  };

  const selectTpl = (id) => {
    setTplId(id); loadTplDetail(id);
  };

  const goStep2 = () => {
    if (!tplDetail) return message.error('请先选择模板');
    setStep(2); setMode('form'); setCsvData(null); setCsvFile(null); setCsvStatus('');
    setFormData({}); setAuthor('');
  };

  const handleCsvDownload = async () => {
    try {
      const r = await downloadCsvTemplate(tplId);
      const url = URL.createObjectURL(r.data);
      const a = document.createElement('a'); a.href = url;
      a.download = `${tplDetail?.name || 'template'}_填写模板.csv`; a.click();
      URL.revokeObjectURL(url);
    } catch { message.error('下载失败'); }
  };

  const handleCsvUpload = async (file) => {
    setCsvFile(file); setCsvStatus('解析中...');
    try {
      const r = await uploadCsv(tplId, file);
      setCsvData(r.data?.data || {}); setCsvStatus(`已加载 ${Object.keys(r.data?.data || {}).length} 个字段`);
    } catch { setCsvStatus('解析失败'); message.error('CSV 解析失败'); }
    return false; // prevent default upload
  };

  const doGenerate = async (src) => {
    const data = src === 'csv' ? csvData : formData;
    if (src === 'csv' && !csvData) return message.error('请先上传 CSV 文件');
    try {
      const r = await generateReport({
        template_id: tplId, title, author,
        date: new Date().toISOString().slice(0, 10), data,
      });
      setReport(r.data?.report); setStep(3);
    } catch { message.error('生成失败'); }
  };

  const doExport = async () => {
    if (!report) return;
    try {
      const sections = report.sections.map((s, i) => {
        const el = document.querySelector(`.preview-section-content[data-idx="${i}"]`);
        return { title: s.title, content: el ? el.value : s.content };
      });
      const r = await exportWord({ title: report.title, author: report.author, date: report.date, sections });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement('a'); a.href = url;
      a.download = `${report.date}_${report.title}.docx`; a.click();
      URL.revokeObjectURL(url);
      localStorage.setItem('report_done', '1');
      message.success('Word 已下载');
    } catch { message.error('导出失败'); }
  };

  const doSaveHistory = async () => {
    if (!report) return;
    const sections = report.sections.map((s, i) => {
      const el = document.querySelector(`.preview-section-content[data-idx="${i}"]`);
      return { title: s.title, content: el ? el.value : s.content };
    });
    try {
      await saveReportHistory({
        title: report.title, template_id: report.template_id,
        template_name: report.template_name, author: report.author,
        date: report.date, sections,
      });
      message.success('已保存到历史');
    } catch { message.error('保存失败'); }
  };

  const placeholders = tplDetail ? tplDetail.placeholders || extractPlaceholders(tplDetail) : [];
  const extractPlaceholders = (tpl) => {
    const set = new Set();
    (tpl.sections || []).forEach(s => {
      (s.content || '').replace(/\{\{(.+?)\}\}/g, (_, k) => set.add(k));
    });
    return [...set];
  };

  return (
    <div>
      {step === 1 && (
        <Card title="第一步：选择报告模板">
          <Space wrap>
            <Select value={tplId} onChange={selectTpl} style={{ width: 280 }}
              options={templates.map(t => ({ label: t.name, value: t.id }))} />
          </Space>
          {tplDetail && (
            <Card type="inner" style={{ marginTop: 16 }}>
              <p><Tag color="blue">{tplDetail.preset ? '系统预设' : '自定义'}</Tag>
                <b>{tplDetail.name}</b></p>
              <p style={{ color: '#888' }}>{tplDetail.description || ''}</p>
              <p>章节数：{tplDetail.sections?.length || 0} ｜ 占位符：{placeholders.length} 个</p>
            </Card>
          )}
          <Divider />
          <Button type="primary" size="large" icon={<EditOutlined />} onClick={goStep2} disabled={!tplId}>
            下一步：填写数据
          </Button>
        </Card>
      )}

      {step === 2 && (
        <Card title="第二步：填写报告数据"
          extra={<Button onClick={() => setStep(1)}>← 返回重选模板</Button>}>
          <Space style={{ marginBottom: 16 }}>
            <Button type={mode === 'form' ? 'primary' : 'default'} onClick={() => setMode('form')}>📝 在线填写</Button>
            <Button type={mode === 'csv' ? 'primary' : 'default'} onClick={() => setMode('csv')}>📄 CSV 导入</Button>
          </Space>

          {mode === 'form' && (
            <div>
              {placeholders.map(p => (
                <div key={p} style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{p}</div>
                  <Input.TextArea rows={2} placeholder={`请输入 ${p}`}
                    onChange={e => setFormData({ ...formData, [p]: e.target.value })} />
                </div>
              ))}
              <Input placeholder="报告标题" value={title} onChange={e => setTitle(e.target.value)}
                style={{ marginBottom: 8 }} />
              <Input placeholder="编制人" value={author} onChange={e => setAuthor(e.target.value)}
                style={{ marginBottom: 16 }} />
              <Button type="primary" size="large" onClick={() => doGenerate('form')}>🔍 生成预览</Button>
            </div>
          )}

          {mode === 'csv' && (
            <div>
              <Space style={{ marginBottom: 16 }}>
                <Button icon={<DownloadOutlined />} onClick={handleCsvDownload}>下载 CSV 模板</Button>
                <Upload beforeUpload={handleCsvUpload} showUploadList={false} maxCount={1}
                  accept=".csv">
                  <Button icon={<UploadOutlined />}>上传填好的 CSV</Button>
                </Upload>
                {csvStatus && <Tag color={csvStatus.includes('失败') ? 'red' : 'green'}>{csvStatus}</Tag>}
              </Space>
              <Input placeholder="报告标题" value={title} onChange={e => setTitle(e.target.value)}
                style={{ marginBottom: 8 }} />
              <Input placeholder="编制人" value={author} onChange={e => setAuthor(e.target.value)}
                style={{ marginBottom: 16 }} />
              <Button type="primary" size="large" onClick={() => doGenerate('csv')}>🔍 生成预览</Button>
            </div>
          )}
        </Card>
      )}

      {step === 3 && report && (
        <Card title="第三步：预览与调整"
          extra={<Button onClick={() => setStep(2)}>← 返回修改</Button>}>
          <div style={{ marginBottom: 16 }}>
            <h3>{report.title}</h3>
            <p style={{ color: '#aaa' }}>
              模板：{report.template_name} ｜ 编制人：{report.author || '-'} ｜ 日期：{report.date || '-'}
            </p>
          </div>
          {(report.sections || []).map((s, i) => (
            <Card key={i} type="inner" title={s.title} style={{ marginBottom: 12 }}>
              <Input.TextArea
                className="preview-section-content"
                data-idx={i}
                defaultValue={s.content}
                rows={Math.max(4, (s.content || '').split('\n').length)}
                style={{ fontFamily: 'inherit', lineHeight: 1.7 }} />
            </Card>
          ))}
          <Divider />
          <Space>
            <Button type="primary" icon={<DownloadOutlined />} onClick={doExport} size="large">📥 下载 Word</Button>
            <Button icon={<SaveOutlined />} onClick={doSaveHistory} size="large">💾 保存到历史</Button>
          </Space>
        </Card>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   历史报告 Tab
   ═══════════════════════════════════════════════════════ */
function HistoryTab() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [viewOpen, setViewOpen] = useState(false);
  const [viewRecord, setViewRecord] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareData, setCompareData] = useState(null);

  const load = () => {
    setLoading(true);
    fetchReportHistory().then(r => setData(r.data?.history || [])).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const viewReport = async (id) => {
    setViewOpen(true);
    const r = await fetchReportHistoryDetail(id);
    setViewRecord(r.data?.record);
  };

  const downloadWord = async (rec) => {
    try {
      const r = await exportHistoryWord(rec.id);
      const url = URL.createObjectURL(r.data);
      const a = document.createElement('a'); a.href = url;
      a.download = `${rec.date || 'report'}_${rec.title}.docx`; a.click();
      URL.revokeObjectURL(url);
    } catch { message.error('下载失败'); }
  };

  const del = async (id) => { await deleteReportHistory(id); message.success('已删除'); load(); };

  const toggleCompare = () => {
    setCompareMode(!compareMode); setSelectedIds([]);
  };

  const onCheck = (id, checked) => {
    if (checked) {
      if (selectedIds.length >= 2) return message.warning('最多选择 2 份报告');
      setSelectedIds([...selectedIds, id]);
    } else {
      setSelectedIds(selectedIds.filter(x => x !== id));
    }
  };

  const doCompare = async () => {
    if (selectedIds.length !== 2) return;
    const r = await compareHistory(selectedIds.join(','));
    setCompareData(r.data);
    setCompareOpen(true);
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<SwapOutlined />} type={compareMode ? 'primary' : 'default'}
          onClick={toggleCompare}>
          {compareMode ? '退出对比' : '对比模式'}
        </Button>
        {compareMode && (
          <>
            <span>已选 {selectedIds.length}/2</span>
            <Button type="primary" disabled={selectedIds.length !== 2} onClick={doCompare}>
              开始对比
            </Button>
          </>
        )}
      </Space>

      <Table size="middle" loading={loading} dataSource={data} rowKey="id" pagination={false}
        rowSelection={compareMode ? {
          selectedRowKeys: selectedIds,
          onSelect: (rec, checked) => onCheck(rec.id, checked),
        } : undefined}
        columns={[
          { title: '日期', dataIndex: 'date', width: 110 },
          { title: '报告标题', dataIndex: 'title' },
          { title: '模板', dataIndex: 'template_name', width: 120, render: v => <Tag>{v}</Tag> },
          { title: '编制人', dataIndex: 'author', width: 100 },
          { title: '保存时间', dataIndex: 'created_at', width: 170 },
          {
            title: '操作', width: 240,
            render: (_, r) => (
              <Space>
                <Button size="small" icon={<EyeOutlined />} onClick={() => viewReport(r.id)}>查看</Button>
                <Button size="small" icon={<DownloadOutlined />} onClick={() => downloadWord(r)}>下载</Button>
                <Popconfirm title="确定删除？" onConfirm={() => del(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]} />

      {/* 历史预览 */}
      <Modal title="报告详情" open={viewOpen} onCancel={() => setViewOpen(false)} width={750} footer={null}>
        {viewRecord && (
          <>
            <p style={{ color: '#888', marginBottom: 16 }}>
              模板：{viewRecord.template_name || '-'} ｜
              编制人：{viewRecord.content_json?.author || '-'} ｜
              日期：{viewRecord.content_json?.date || '-'}
            </p>
            {(viewRecord.content_json?.sections || viewRecord.sections || []).map((s, i) => (
              <Card key={i} type="inner" title={s.title} style={{ marginBottom: 8 }}>
                <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 14, lineHeight: 1.7, margin: 0 }}>{s.content}</pre>
              </Card>
            ))}
          </>
        )}
      </Modal>

      {/* 对比 */}
      <Modal title="报告对比" open={compareOpen} onCancel={() => setCompareOpen(false)} width={1000} footer={null}>
        {compareData && (
          <div style={{ display: 'flex', gap: 20 }}>
            <div style={{ flex: 1 }}>
              <h4>📄 {compareData.report_a?.title} ({compareData.report_a?.date})</h4>
              {compareData.diff?.map((sec, i) => (
                <div key={i} style={{
                  padding: 10, marginBottom: 8, borderRadius: 6,
                  background: sec.type === 'removed' ? '#fff1f0' : sec.type === 'same' ? '#f8f9fa' : '#fffbe6',
                  border: sec.type === 'removed' ? '1px solid #ffa39e' : sec.type === 'modified' ? '1px solid #ffe58f' : 'none',
                }}>
                  <strong>{sec.title}</strong>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 13, margin: '4px 0 0' }}>
                    {sec.content_a || '(无此章节)'}
                  </pre>
                </div>
              ))}
            </div>
            <div style={{ flex: 1 }}>
              <h4>📄 {compareData.report_b?.title} ({compareData.report_b?.date})</h4>
              {compareData.diff?.map((sec, i) => (
                <div key={i} style={{
                  padding: 10, marginBottom: 8, borderRadius: 6,
                  background: sec.type === 'added' ? '#f6ffed' : sec.type === 'same' ? '#f8f9fa' : '#fffbe6',
                  border: sec.type === 'added' ? '1px solid #b7eb8f' : sec.type === 'modified' ? '1px solid #ffe58f' : 'none',
                }}>
                  <strong>{sec.title}</strong>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 13, margin: '4px 0 0' }}>
                    {sec.content_b || '(无此章节)'}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   报告生成主页面
   ═══════════════════════════════════════════════════════ */
export default function ReportPage() {
  const [tab, setTab] = useState('generate');
  const [selectedTpl, setSelectedTpl] = useState(null);

  return (
    <Card>
      <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'templates', label: '模板管理',
          children: <TemplateTab onSelect={t => { setSelectedTpl(t); setTab('generate'); }} /> },
        { key: 'generate', label: '报告生成',
          children: <GenerateTab selectedTpl={selectedTpl} /> },
        { key: 'history', label: '历史报告',
          children: <HistoryTab /> },
      ]} />
    </Card>
  );
}

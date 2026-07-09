import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export const fetchPresets = () => api.get('/aml/presets');
export const fetchItems = (preset) => api.get('/aml/items', { params: { preset_id: preset } });
export const toggleItem = (key, enabled) => api.put(`/aml/items/${key}`, { enabled: enabled ? 0 : 1 });
export const runAssessment = (preset) => api.post('/aml/assess', null, { params: { preset_id: preset } });
export const fetchHistory = (limit = 50) => api.get('/aml/history', { params: { limit } });
export const fetchHistoryDetail = (id) => api.get(`/aml/history/${id}`);
export const fetchTrend = (limit = 12) => api.get('/aml/history/trend', { params: { limit } });
export const fetchCompare = (id1, id2) => api.get('/aml/compare', { params: { id1, id2 } });
export const fetchImportStatus = () => api.get('/import/status');
export const uploadCsv = (table, file) => {
  const fd = new FormData(); fd.append('file', file);
  return api.post('/import/upload', fd, { params: { table } });
};
export const confirmImport = (table) => api.post('/import/confirm', null, { params: { table } });
export const clearData = () => api.post('/import/clear');
// 报告生成
export const fetchTemplates = () => api.get('/report/templates');
export const fetchTemplateDetail = (id) => api.get(`/report/templates/${id}`);
export const saveTemplate = (data) => data.id
  ? api.put(`/report/templates/${data.id}`, data)
  : api.post('/report/templates', data);
export const deleteTemplate = (id) => api.delete(`/report/templates/${id}`);
export const downloadCsvTemplate = (templateId) =>
  api.post('/report/csv-template', { template_id: templateId }, { responseType: 'blob' });
export const uploadCsv = (templateId, file) => {
  const fd = new FormData(); fd.append('file', file);
  return api.post('/report/upload-csv', fd, { params: { template_id: templateId } });
};
export const generateReport = (data) => api.post('/report/generate', data);
export const exportWord = (data) => api.post('/report/export', data, { responseType: 'blob' });
export const fetchReportHistory = () => api.get('/report/history');
export const fetchReportHistoryDetail = (id) => api.get(`/report/history/${id}`);
export const saveReportHistory = (data) => api.post('/report/history', data);
export const deleteReportHistory = (id) => api.delete(`/report/history/${id}`);
export const exportHistoryWord = (id) =>
  api.get(`/report/history/${id}/export`, { responseType: 'blob' });
export const compareHistory = (ids) => api.get('/report/history/compare', { params: { ids } });

export default api;

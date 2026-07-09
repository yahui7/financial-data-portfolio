/**
 * API 封装
 */
const API = {
    base: '/api/report',

    async get(url) {
        const res = await fetch(this.base + url);
        return res.json();
    },

    async post(url, data) {
        const res = await fetch(this.base + url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const contentType = res.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            return res.json();
        }
        return res;
    },

    async put(url, data) {
        const res = await fetch(this.base + url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    async del(url) {
        const res = await fetch(this.base + url, { method: 'DELETE' });
        return res.json();
    },

    async uploadCsv(templateId, file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${this.base}/upload-csv?template_id=${encodeURIComponent(templateId)}`, {
            method: 'POST',
            body: formData,
        });
        return res.json();
    },

    downloadBlob(url, data, filename) {
        return fetch(this.base + url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        }).then(res => {
            if (!res.ok) throw new Error('下载失败');
            return res.blob();
        }).then(blob => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
            URL.revokeObjectURL(a.href);
        });
    },

    downloadHistoryWord(historyId, filename) {
        return fetch(`${this.base}/history/${historyId}/export`)
            .then(res => {
                if (!res.ok) throw new Error('下载失败');
                return res.blob();
            })
            .then(blob => {
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = filename;
                a.click();
                URL.revokeObjectURL(a.href);
            });
    },
};

// Toast 通知
function showToast(msg, type = '') {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.className = 'toast ' + type;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 2500);
}

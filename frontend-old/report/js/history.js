/**
 * 历史报告页面
 */
const HistoryPage = {
    compareMode: false,
    selectedIds: [],
    currentPreviewId: null,

    async load() {
        const res = await API.get('/history');
        if (res.status !== 'ok') { showToast('加载历史失败', 'error'); return; }
        this.render(res.history);
    },

    render(history) {
        const container = document.getElementById('history-list');
        if (!history.length) {
            container.innerHTML = '<p style="color:#999;text-align:center;padding:40px;">暂无历史报告</p>';
            return;
        }

        const showCheckbox = this.compareMode;
        container.innerHTML = `
            <table class="history-table">
                <thead>
                    <tr>
                        ${showCheckbox ? '<th style="width:40px;">选择</th>' : ''}
                        <th>报告标题</th>
                        <th>模板</th>
                        <th>编制人</th>
                        <th>日期</th>
                        <th>创建时间</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    ${history.map(h => `
                        <tr>
                            ${showCheckbox ? `<td><input type="checkbox" class="compare-check" data-id="${h.id}" ${this.selectedIds.includes(h.id) ? 'checked' : ''} /></td>` : ''}
                            <td><strong>${this.esc(h.title)}</strong></td>
                            <td>${this.esc(h.template_name || '-')}</td>
                            <td>${this.esc(h.author || '-')}</td>
                            <td>${this.esc(h.date || '-')}</td>
                            <td style="font-size:12px;color:#999;">${this.esc(h.created_at || '-')}</td>
                            <td class="td-actions">
                                <button class="btn btn-sm btn-outline" data-action="preview" data-id="${h.id}">预览</button>
                                <button class="btn btn-sm btn-outline" data-action="download" data-id="${h.id}">下载</button>
                                <button class="btn btn-sm btn-danger" data-action="delete" data-id="${h.id}">删除</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // 绑定事件
        container.querySelectorAll('[data-action="preview"]').forEach(btn => {
            btn.addEventListener('click', () => this.preview(parseInt(btn.dataset.id)));
        });
        container.querySelectorAll('[data-action="download"]').forEach(btn => {
            btn.addEventListener('click', () => this.download(parseInt(btn.dataset.id)));
        });
        container.querySelectorAll('[data-action="delete"]').forEach(btn => {
            btn.addEventListener('click', () => this.del(parseInt(btn.dataset.id)));
        });
        if (showCheckbox) {
            container.querySelectorAll('.compare-check').forEach(cb => {
                cb.addEventListener('change', () => {
                    const id = parseInt(cb.dataset.id);
                    if (cb.checked) {
                        if (this.selectedIds.length >= 2) {
                            cb.checked = false;
                            showToast('最多选择2份报告进行对比', 'error');
                            return;
                        }
                        this.selectedIds.push(id);
                    } else {
                        this.selectedIds = this.selectedIds.filter(x => x !== id);
                    }
                    this.updateCompareBar();
                });
            });
            this.updateCompareBar();
        }
    },

    // ── 预览 ──

    async preview(id) {
        const res = await API.get(`/history/${id}`);
        if (res.status !== 'ok') { showToast('加载失败', 'error'); return; }

        const record = res.record;
        const content = record.content_json;
        this.currentPreviewId = id;

        document.getElementById('preview-title').textContent = content.title || record.title;
        document.getElementById('preview-body').innerHTML = `
            <p style="color:#888;font-size:13px;margin-bottom:16px;">
                模板：${this.esc(record.template_name || '-')} &nbsp;|&nbsp;
                编制人：${this.esc(content.author || '-')} &nbsp;|&nbsp;
                日期：${this.esc(content.date || '-')}
            </p>
            ${(content.sections || []).map(s => `
                <div style="margin-bottom:20px;">
                    <h4 style="color:#1a1f3a;border-bottom:1px solid #f0f0f0;padding-bottom:6px;margin-bottom:10px;">
                        ${this.esc(s.title)}
                    </h4>
                    <pre style="white-space:pre-wrap;font-family:inherit;font-size:14px;line-height:1.8;color:#444;background:#fafafa;padding:14px;border-radius:6px;">${this.esc(s.content)}</pre>
                </div>
            `).join('')}
        `;

        document.getElementById('history-preview').classList.remove('hidden');
    },

    // ── 下载 ──

    async download(id) {
        const res = await API.get(`/history/${id}`);
        if (res.status !== 'ok') { showToast('加载失败', 'error'); return; }

        const content = res.record.content_json;
        const filename = `${content.date || 'report'}_${res.record.title}.docx`;

        try {
            await API.downloadHistoryWord(id, filename);
            showToast('Word 已下载', 'success');
        } catch (e) {
            showToast('下载失败', 'error');
        }
    },

    // ── 删除 ──

    async del(id) {
        if (!confirm('确定删除此报告？')) return;
        const res = await API.del(`/history/${id}`);
        if (res.status !== 'ok') { showToast(res.message, 'error'); return; }
        showToast('已删除', 'success');
        this.load();
    },

    // ── 对比 ──

    toggleCompareMode() {
        this.compareMode = !this.compareMode;
        this.selectedIds = [];
        document.getElementById('btn-compare-mode').textContent = this.compareMode ? '📋 退出对比' : '🔍 对比模式';
        if (this.compareMode) {
            document.getElementById('compare-bar').classList.remove('hidden');
        } else {
            document.getElementById('compare-bar').classList.add('hidden');
        }
        this.load();
    },

    updateCompareBar() {
        document.getElementById('compare-count').textContent = this.selectedIds.length;
        document.getElementById('btn-do-compare').disabled = this.selectedIds.length !== 2;
    },

    async doCompare() {
        if (this.selectedIds.length !== 2) { showToast('请选择2份报告', 'error'); return; }

        const res = await API.get(`/history/compare?ids=${this.selectedIds.join(',')}`);
        if (res.status !== 'ok') { showToast('对比失败: ' + (res.message || ''), 'error'); return; }

        this.renderCompare(res);
        document.getElementById('compare-preview').classList.remove('hidden');
    },

    renderCompare(data) {
        const body = document.getElementById('compare-body');

        let leftHTML = '';
        let rightHTML = '';

        data.diff.forEach(section => {
            if (section.type === 'same') {
                // 相同章节 — 两边都显示
                leftHTML += this._sectionHTML(section.title, 'same', section.content);
                rightHTML += this._sectionHTML(section.title, 'same', section.content);
            } else if (section.type === 'modified') {
                // 修改 — 左边原内容，右边新内容 + diff
                leftHTML += this._sectionHTML(section.title, 'modified', section.content_a);
                rightHTML += this._sectionHTML(section.title, 'modified', section.content_b, section.diff);
            } else if (section.type === 'removed') {
                // 仅A有 — 左边显示，右边空白
                leftHTML += this._sectionHTML(section.title, 'removed', section.content_a);
                rightHTML += this._sectionHTML(section.title, 'removed', '（无此章节）');
            } else if (section.type === 'added') {
                // 仅B有 — 左边空白，右边显示
                leftHTML += this._sectionHTML(section.title, 'added', '（无此章节）');
                rightHTML += this._sectionHTML(section.title, 'added', section.content_b);
            }
        });

        body.innerHTML = `
            <div class="compare-col">
                <h4>📄 ${this.esc(data.report_a.title)} (${this.esc(data.report_a.date)})</h4>
                ${leftHTML}
            </div>
            <div class="compare-col">
                <h4>📄 ${this.esc(data.report_b.title)} (${this.esc(data.report_b.date)})</h4>
                ${rightHTML}
            </div>
        `;
    },

    _sectionHTML(title, type, content, diffLines) {
        let inner;
        if (diffLines && diffLines.length) {
            inner = diffLines.map(d => {
                const cls = d.type; // 'same', 'added', 'removed'
                const prefix = d.type === 'added' ? '+ ' : (d.type === 'removed' ? '- ' : '  ');
                return `<div class="diff-line ${cls}">${prefix}${this.esc(d.text)}</div>`;
            }).join('');
        } else {
            inner = `<pre style="white-space:pre-wrap;font-family:inherit;font-size:13px;line-height:1.8;color:#555;">${this.esc(content)}</pre>`;
        }
        return `<div class="compare-section ${type}"><h5>${this.esc(title)}</h5>${inner}</div>`;
    },

    esc(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};

// ── 事件绑定 ──
document.getElementById('btn-compare-mode').addEventListener('click', () => HistoryPage.toggleCompareMode());
document.getElementById('btn-do-compare').addEventListener('click', () => HistoryPage.doCompare());
document.getElementById('btn-cancel-compare').addEventListener('click', () => HistoryPage.toggleCompareMode());
document.getElementById('btn-close-preview').addEventListener('click', () => {
    document.getElementById('history-preview').classList.add('hidden');
});
document.getElementById('btn-close-preview-bottom').addEventListener('click', () => {
    document.getElementById('history-preview').classList.add('hidden');
});
document.getElementById('btn-close-compare').addEventListener('click', () => {
    document.getElementById('compare-preview').classList.add('hidden');
});
document.getElementById('btn-preview-export').addEventListener('click', () => {
    if (HistoryPage.currentPreviewId) {
        HistoryPage.download(HistoryPage.currentPreviewId);
    }
});

// 点击遮罩关闭
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', () => {
        document.getElementById('history-preview').classList.add('hidden');
        document.getElementById('compare-preview').classList.add('hidden');
    });
});

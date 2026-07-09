/**
 * 报告生成页面
 */
const GeneratePage = {
    selectedTpl: null,
    csvData: null,
    currentStep: 1,

    async init() {
        // 加载模板列表供选择
        const res = await API.get('/templates');
        if (res.status !== 'ok') { showToast('加载模板失败', 'error'); return; }
        this.renderTemplateSelect(res.templates);

        // 回到第一步
        this.goToStep(1);

        // 绑定步骤指示器点击
        document.querySelectorAll('#generate-stepper .stepper-step').forEach(el => {
            el.addEventListener('click', () => {
                const step = parseInt(el.dataset.step);
                if (step < this.currentStep) {
                    this.goToStep(step);
                }
            });
        });

        // 绑定返回重选模板
        document.getElementById('btn-back-to-select').addEventListener('click', () => this.goToStep(1));

        // 绑定模式切换
        document.getElementById('btn-mode-form').addEventListener('click', () => this.switchMode('form'));
        document.getElementById('btn-mode-csv').addEventListener('click', () => this.switchMode('csv'));

        // 绑定按钮
        document.getElementById('btn-generate').addEventListener('click', () => this.generate('form'));
        document.getElementById('btn-generate-csv').addEventListener('click', () => this.generate('csv'));
        document.getElementById('btn-download-csv').addEventListener('click', () => this.downloadCsvTemplate());
        document.getElementById('csv-file-input').addEventListener('change', (e) => this.handleCsvUpload(e));
        document.getElementById('btn-back-edit').addEventListener('click', () => this.goToStep(2));
        document.getElementById('btn-export-word').addEventListener('click', () => this.exportWord());
        document.getElementById('btn-save-history').addEventListener('click', () => this.saveHistory());
    },

    // ── 步骤导航 ──

    goToStep(step) {
        this.currentStep = step;

        // 显示/隐藏步骤内容
        document.getElementById('step-select-tpl').classList.toggle('hidden', step !== 1);
        document.getElementById('step-fill-data').classList.toggle('hidden', step !== 2);
        document.getElementById('step-preview').classList.toggle('hidden', step !== 3);

        // 更新步骤指示器
        this.updateStepper(step);

        // 显示/隐藏步骤条
        const stepper = document.getElementById('generate-stepper');
        stepper.classList.toggle('hidden', step < 1);
    },

    updateStepper(step) {
        const steps = document.querySelectorAll('#generate-stepper .stepper-step');
        const lines = document.querySelectorAll('#generate-stepper .stepper-line');

        steps.forEach(el => {
            const s = parseInt(el.dataset.step);
            el.classList.remove('active', 'done', 'clickable');
            if (s < step) {
                el.classList.add('done', 'clickable');
            } else if (s === step) {
                el.classList.add('active');
            }
        });

        lines.forEach((line, i) => {
            if (i + 1 < step) {
                line.classList.add('done');
            } else {
                line.classList.remove('done');
            }
        });
    },

    // ── 模板选择 ──

    renderTemplateSelect(templates) {
        const container = document.getElementById('tpl-select-list');
        container.innerHTML = templates.map(t => {
            const badge = t.preset
                ? '<span class="card-badge">预设</span>'
                : '<span class="card-badge">自定义</span>';
            return `<div class="card ${t.preset ? 'preset' : 'custom'}" data-tpl-id="${t.id}">
                ${badge}
                <div class="card-name">${this.esc(t.name)}</div>
                <div class="card-desc">${this.esc(t.description || '')} · ${t.sections.length} 个章节</div>
            </div>`;
        }).join('');

        container.querySelectorAll('.card').forEach(card => {
            card.addEventListener('click', () => {
                container.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                const tplId = card.dataset.tplId;
                this.selectedTpl = templates.find(t => t.id === tplId);
                this.enterStep2();
            });
        });

        // 恢复之前选中的模板高亮
        if (this.selectedTpl) {
            const selectedCard = container.querySelector(`[data-tpl-id="${this.selectedTpl.id}"]`);
            if (selectedCard) selectedCard.classList.add('selected');
        }
    },

    async enterStep2() {
        if (!this.selectedTpl) { showToast('请先选择模板', 'error'); return; }

        // 获取模板详情（含占位符）
        const res = await API.get(`/templates/${this.selectedTpl.id}`);
        if (res.status !== 'ok') { showToast('模板加载失败', 'error'); return; }
        this.selectedTpl = res.template;

        // 渲染占位符表单
        this.renderPlaceholderForm(res.placeholders);

        // 重置 CSV 状态
        this.csvData = null;
        document.getElementById('csv-status').textContent = '';
        document.getElementById('csv-file-input').value = '';

        // 预填标题
        document.getElementById('report-title').value = this.selectedTpl.name;
        document.getElementById('report-title-csv').value = this.selectedTpl.name;
        document.getElementById('report-author').value = '';
        document.getElementById('report-author-csv').value = '';

        // 默认在线填写模式
        this.switchMode('form');

        this.goToStep(2);
    },

    renderPlaceholderForm(placeholders) {
        const container = document.getElementById('placeholder-form');
        if (!placeholders || !placeholders.length) {
            container.innerHTML = '<p style="color:#888">该模板没有占位符，可以直接生成。</p>';
            return;
        }
        container.innerHTML = placeholders.map(p => `
            <div class="form-group">
                <label>${this.esc(p)}</label>
                <textarea class="input placeholder-input" data-key="${this.esc(p)}" rows="3" placeholder="请输入 ${this.esc(p)} ..."></textarea>
            </div>
        `).join('');
    },

    switchMode(mode) {
        document.getElementById('btn-mode-form').classList.toggle('active', mode === 'form');
        document.getElementById('btn-mode-csv').classList.toggle('active', mode === 'csv');
        document.getElementById('mode-form').classList.toggle('hidden', mode !== 'form');
        document.getElementById('mode-csv').classList.toggle('hidden', mode !== 'csv');
    },

    // ── CSV 下载/上传 ──

    async downloadCsvTemplate() {
        if (!this.selectedTpl) { showToast('请先选择模板', 'error'); return; }
        try {
            const res = await fetch(`${API.base}/csv-template`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ template_id: this.selectedTpl.id }),
            });
            if (!res.ok) {
                const err = await res.json();
                showToast(err.message || '下载失败', 'error');
                return;
            }
            const blob = await res.blob();
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `${this.selectedTpl.name}_填写模板.csv`;
            a.click();
            URL.revokeObjectURL(a.href);
            showToast('CSV 模板已下载', 'success');
        } catch (e) {
            showToast('下载失败: ' + e.message, 'error');
        }
    },

    async handleCsvUpload(e) {
        const file = e.target.files[0];
        if (!file) return;
        const statusEl = document.getElementById('csv-status');
        statusEl.textContent = '解析中...';
        statusEl.style.color = '#e67e22';

        const res = await API.uploadCsv(this.selectedTpl.id, file);
        if (res.status !== 'ok') {
            statusEl.textContent = res.message || '解析失败';
            statusEl.style.color = '#e74c3c';
            showToast(res.message || 'CSV 解析失败', 'error');
            return;
        }
        this.csvData = res.data;
        statusEl.textContent = `已加载 ${Object.keys(res.data).length} 个字段`;
        statusEl.style.color = '#52c41a';
        showToast('CSV 数据已加载', 'success');
    },

    // ── 生成预览 ──

    async generate(mode) {
        if (!this.selectedTpl) { showToast('请先选择模板', 'error'); return; }

        let data = {};
        const titleId = mode === 'csv' ? 'report-title-csv' : 'report-title';
        const authorId = mode === 'csv' ? 'report-author-csv' : 'report-author';

        if (mode === 'csv') {
            if (!this.csvData) { showToast('请先上传 CSV 文件', 'error'); return; }
            data = this.csvData;
        } else {
            document.querySelectorAll('#placeholder-form .placeholder-input').forEach(input => {
                data[input.dataset.key] = input.value;
            });
        }

        const req = {
            template_id: this.selectedTpl.id,
            title: document.getElementById(titleId).value.trim() || this.selectedTpl.name,
            author: document.getElementById(authorId).value.trim(),
            date: new Date().toISOString().slice(0, 10),
            data,
        };

        const res = await API.post('/generate', req);
        if (res.status !== 'ok') { showToast(res.message || '生成失败', 'error'); return; }

        this.generatedReport = res.report;
        this.renderPreview(res.report);
        this.goToStep(3);
        document.getElementById('step-preview').scrollIntoView({ behavior: 'smooth' });
    },

    renderPreview(report) {
        const container = document.getElementById('preview-edit');
        container.innerHTML = `
            <div style="margin-bottom: 16px;">
                <h3 style="color:#1a1f3a;">${this.esc(report.title)}</h3>
                <p style="color:#aaa;font-size:13px;">
                    模板：${this.esc(report.template_name)} &nbsp;|&nbsp;
                    编制人：${this.esc(report.author || '-')} &nbsp;|&nbsp;
                    日期：${this.esc(report.date || '-')}
                </p>
            </div>
            ${(report.sections || []).map((s, i) => `
                <div class="preview-section">
                    <h4>${this.esc(s.title)}</h4>
                    <textarea class="input preview-section-content" data-idx="${i}" rows="8">${this.esc(s.content)}</textarea>
                </div>
            `).join('')}
        `;
    },

    // ── 导出 Word ──

    async exportWord() {
        const sections = [];
        const sectionEls = document.querySelectorAll('.preview-section-content');
        sectionEls.forEach((el, i) => {
            const title = this.generatedReport.sections[i]?.title || `章节${i + 1}`;
            sections.push({ title, content: el.value || el.textContent });
        });

        const data = {
            title: this.generatedReport.title,
            author: this.generatedReport.author,
            date: this.generatedReport.date,
            sections,
        };

        try {
            await API.downloadBlob('/export', data, `${this.generatedReport.date}_${this.generatedReport.title}.docx`);
            showToast('Word 已下载', 'success');
        } catch (e) {
            showToast('导出失败: ' + e.message, 'error');
        }
    },

    // ── 保存历史 ──

    async saveHistory() {
        const sections = [];
        const sectionEls = document.querySelectorAll('.preview-section-content');
        sectionEls.forEach((el, i) => {
            const title = this.generatedReport.sections[i]?.title || `章节${i + 1}`;
            sections.push({ title, content: el.value || el.textContent });
        });

        const data = {
            title: this.generatedReport.title,
            template_id: this.generatedReport.template_id,
            template_name: this.generatedReport.template_name,
            author: this.generatedReport.author,
            date: this.generatedReport.date,
            sections,
        };

        const res = await API.post('/history', data);
        if (res.status !== 'ok') { showToast(res.message || '保存失败', 'error'); return; }
        showToast('已保存到历史', 'success');
    },

    esc(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};

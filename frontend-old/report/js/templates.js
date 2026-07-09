/**
 * 模板管理页面
 */
const TemplatesPage = {
    currentTpl: null, // 正在编辑的模板
    editingId: null,  // 编辑中的模板ID（null=新建）

    async load() {
        const res = await API.get('/templates');
        if (res.status !== 'ok') { showToast('加载模板失败', 'error'); return; }
        this.render(res.templates);
    },

    render(templates) {
        const container = document.getElementById('templates-list');
        if (!templates.length) {
            container.innerHTML = '<p style="color:#999;text-align:center;padding:40px;">暂无模板，点击右上角"新建模板"开始</p>';
            return;
        }
        container.innerHTML = templates.map(t => {
            const badge = t.preset
                ? '<span class="card-badge">预设</span>'
                : '<span class="card-badge">自定义</span>';
            const actions = '<button class="btn btn-sm btn-outline" data-action="view" data-id="' + t.id + '">查看</button>'
                + '<button class="btn btn-sm btn-outline" data-action="copy" data-id="' + t.id + '">复制</button>'
                + (t.preset ? ''
                    : '<button class="btn btn-sm btn-outline" data-action="edit" data-id="' + t.id + '">编辑</button>'
                    + '<button class="btn btn-sm btn-danger" data-action="delete" data-id="' + t.id + '">删除</button>');
            return `<div class="card ${t.preset ? 'preset' : 'custom'}">
                ${badge}
                <div class="card-name">${this.esc(t.name)}</div>
                <div class="card-desc">${this.esc(t.description || '')} · ${t.sections.length} 个章节</div>
                <div class="card-actions">${actions}</div>
            </div>`;
        }).join('');

        // 事件委托
        container.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const action = btn.dataset.action;
                const id = btn.dataset.id;
                if (action === 'view') this.view(id);
                if (action === 'copy') this.copy(id);
                if (action === 'edit') this.edit(id);
                if (action === 'delete') this.del(id);
            });
        });
    },

    async view(id) {
        const res = await API.get(`/templates/${id}`);
        if (res.status !== 'ok') { showToast('模板不存在', 'error'); return; }
        this.editingId = id;
        this._openModal(res.template, true);
    },

    async copy(id) {
        const res = await API.get(`/templates/${id}`);
        if (res.status !== 'ok') { showToast('模板不存在', 'error'); return; }

        // 复制：清空 ID，模板名称加上"副本"后缀
        const tpl = JSON.parse(JSON.stringify(res.template));
        tpl.id = undefined;
        tpl.preset = false;
        tpl.name = (tpl.name || '') + ' - 副本';
        this.editingId = null;
        this._openModal(tpl, false);
    },

    async edit(id) {
        const res = await API.get(`/templates/${id}`);
        if (res.status !== 'ok') { showToast('模板不存在', 'error'); return; }

        this.editingId = id;
        this._openModal(res.template, false);
    },

    async del(id) {
        if (!confirm('确定删除此模板？此操作不可恢复。')) return;
        const res = await API.del(`/templates/${id}`);
        if (res.status !== 'ok') { showToast(res.message, 'error'); return; }
        showToast('删除成功', 'success');
        this.load();
    },

    // ── 模态框 ──

    _openModal(tpl, readonly) {
        this.currentTpl = tpl;
        const modal = document.getElementById('tpl-editor-modal');
        const titleEl = document.getElementById('tpl-editor-title');
        const bodyEl = document.getElementById('tpl-editor-body');
        const footerEl = document.getElementById('tpl-editor-footer');

        titleEl.textContent = readonly ? '查看模板' : (this.editingId ? '编辑模板' : '新建模板');

        let sectionsHTML = '';
        if (tpl.sections && tpl.sections.length > 0) {
            sectionsHTML = tpl.sections.map((s, i) => `
                <div class="tpl-section-block">
                    <div class="form-group">
                        <label>章节 ${i + 1} 标题</label>
                        <input type="text" class="input section-title" value="${this.esc(s.title)}" data-idx="${i}" ${readonly ? 'readonly' : ''} />
                    </div>
                    <div class="form-group">
                        <label>章节 ${i + 1} 内容 <span class="hint">（用 <code>$&#123;{字段名}}</code> 标记占位符）</span></label>
                        <textarea class="input section-content" data-idx="${i}" rows="12" ${readonly ? 'readonly' : ''}>${this.esc(s.content)}</textarea>
                    </div>
                </div>
            `).join('');
        }

        bodyEl.innerHTML = `
            <div class="form-row-inline">
                <label>模板名称：</label>
                <input type="text" class="input" id="edit-tpl-name" value="${this.esc(tpl.name || '')}" ${readonly ? 'readonly' : ''} style="flex:1;" />
            </div>
            <div class="form-row-inline">
                <label>模板描述：</label>
                <input type="text" class="input" id="edit-tpl-desc" value="${this.esc(tpl.description || '')}" ${readonly ? 'readonly' : ''} style="flex:1;" />
            </div>
            <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #f0f0f0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <strong style="color: #1a1f3a;">报告章节</strong>
                    ${!readonly ? '<button class="btn btn-sm btn-outline" id="btn-add-section">+ 添加章节</button>' : ''}
                </div>
                <div id="tpl-sections-container">${sectionsHTML || '<p style="color:#999;text-align:center;padding:20px;">暂无章节，点击"添加章节"开始</p>'}</div>
            </div>
        `;

        footerEl.innerHTML = readonly
            ? '<button class="btn btn-outline" id="btn-close-editor">关闭</button>'
            : `<button class="btn btn-outline" id="btn-add-section-bottom">+ 添加章节</button>
               <div style="flex:1;"></div>
               <button class="btn btn-outline" id="btn-close-editor">取消</button>
               <button class="btn btn-primary" id="btn-save-tpl">💾 保存模板</button>`;

        modal.classList.remove('hidden');

        // 事件绑定
        if (!readonly) {
            const addHandler = () => this._addSection();
            document.getElementById('btn-add-section')?.addEventListener('click', addHandler);
            document.getElementById('btn-add-section-bottom')?.addEventListener('click', addHandler);
            document.getElementById('btn-save-tpl').addEventListener('click', () => this._save());
        }
        document.getElementById('btn-close-editor').addEventListener('click', () => this._closeModal());
        document.getElementById('btn-close-tpl-editor').addEventListener('click', () => this._closeModal());
        document.querySelector('#tpl-editor-modal .modal-overlay').addEventListener('click', () => this._closeModal());

        // ESC 关闭
        this._escHandler = (e) => { if (e.key === 'Escape') this._closeModal(); };
        document.addEventListener('keydown', this._escHandler);
    },

    _addSection() {
        const container = document.getElementById('tpl-sections-container');
        // 移除空提示
        const empty = container.querySelector('p');
        if (empty) empty.remove();

        const idx = container.querySelectorAll('.section-title').length + 1;
        const div = document.createElement('div');
        div.className = 'tpl-section-block';
        div.innerHTML = `
            <div class="form-group">
                <label>章节 ${idx} 标题</label>
                <input type="text" class="input section-title" value="" placeholder="输入章节标题" />
            </div>
            <div class="form-group">
                <label>章节 ${idx} 内容 <span class="hint">（用 <code>$&#123;{字段名}}</code> 标记占位符）</span></label>
                <textarea class="input section-content" rows="12" placeholder="输入内容，用{{变量}}标记占位符"></textarea>
            </div>
        `;
        container.appendChild(div);

        // 滚动到底部
        div.scrollIntoView({ behavior: 'smooth', block: 'center' });
        div.querySelector('input').focus();
    },

    async _save() {
        const name = document.getElementById('edit-tpl-name').value.trim();
        const desc = document.getElementById('edit-tpl-desc').value.trim();
        if (!name) { showToast('请输入模板名称', 'error'); return; }

        const titles = document.querySelectorAll('#tpl-sections-container .section-title');
        const contents = document.querySelectorAll('#tpl-sections-container .section-content');
        const sections = [];
        for (let i = 0; i < titles.length; i++) {
            const title = titles[i].value.trim();
            const content = contents[i].value;
            if (!title) continue;
            sections.push({ title, content });
        }
        if (!sections.length) { showToast('至少需要一个章节', 'error'); return; }

        const isPresetEdit = this.currentTpl && this.currentTpl.preset && !this.editingId;
        const data = {
            id: this.editingId || undefined,
            name,
            description: desc,
            sections,
            preset: isPresetEdit ? false : (this.currentTpl ? this.currentTpl.preset : false),
        };

        let res;
        if (this.editingId) {
            res = await API.put(`/templates/${this.editingId}`, data);
        } else {
            delete data.id;
            res = await API.post('/templates', data);
        }

        if (res.status !== 'ok') { showToast(res.message || '保存失败', 'error'); return; }
        showToast('保存成功', 'success');
        this._closeModal();
        this.load();
    },

    _closeModal() {
        document.getElementById('tpl-editor-modal').classList.add('hidden');
        this.currentTpl = null;
        this.editingId = null;
        if (this._escHandler) {
            document.removeEventListener('keydown', this._escHandler);
            this._escHandler = null;
        }
    },

    esc(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};

// 绑定新建按钮（初始）
document.getElementById('btn-new-template').addEventListener('click', () => {
    TemplatesPage.editingId = null;
    TemplatesPage._openModal({ name: '', description: '', sections: [] }, false);
});

/**
 * 主入口 — Tab 切换
 */
(function () {
    const tabs = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.tab-panel');

    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            tabs.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            panels.forEach(p => {
                p.classList.toggle('active', p.id === `panel-${tab}`);
            });

            // 切换时刷新对应面板
            if (tab === 'templates') TemplatesPage.load();
            if (tab === 'generate') GeneratePage.init();
            if (tab === 'history') HistoryPage.load();
        });
    });

    // 初始加载
    TemplatesPage.load();
})();

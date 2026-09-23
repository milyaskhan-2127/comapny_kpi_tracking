// Productix KPI Tracking — Enterprise Backup & Restore Manager
// Defensive rewrite: every render/refresh path is guarded so an unexpected
// error can never leave the page blank ("white screen").

frappe.pages['backups'] = frappe.pages['backups'] || {};

frappe.pages['backups'].on_page_load = function(wrapper) {
    try {
        const page = wrapper.page || frappe.ui.make_app_page({
            parent: wrapper,
            title: __('Enterprise Backup & Restore Manager'),
            single_column: true
        });
        wrapper.page = page;
        if (page.main) page.main.addClass('kpi-tracking-app productix-backup-page');

        frappe.xcall('productix.kpi_tracking.api.dashboard.get_user_context').then((ctx) => {
            page._ctx = ctx || {};
            if (!ctx.is_admin) {
                frappe.show_alert({ message: __('Backup Manager is restricted to administrators.'), indicator: 'orange' });
                frappe.set_route('kpi-department-dashboard');
                return;
            }
            setup_backup_page_actions(page);
            render_backup_manager(page);
        }).catch(() => {
            // Never block the page on context lookup failure; render anyway.
            setup_backup_page_actions(page);
            render_backup_manager(page);
        });
    } catch (err) {
        console.error('Backup manager init error', err);
        try {
            if (wrapper && wrapper.page && wrapper.page.main) {
                wrapper.page.main.html(`
                    <div class="p-4" style="max-width: 760px; margin: 40px auto; text-align: center;">
                        <h4>Backup Manager could not initialize</h4>
                        <p class="text-muted">An unexpected error occurred while loading the page.</p>
                        <pre style="text-align: left; max-height: 200px; overflow: auto; font-size: 12px;">${frappe.utils.escape_html(err && err.stack ? err.stack : String(err))}</pre>
                        <button class="btn btn-primary btn-sm mt-2" onclick="window.location.reload()">Reload Page</button>
                    </div>
                `);
            }
        } catch (e) { /* give up silently */ }
    }
};

frappe.pages['backups'].refresh = function(wrapper) {
    try {
        const page = wrapper && wrapper.page;
        if (page && page._reload_backups) {
            page._reload_backups();
        } else if (page && page.main && page.main.length) {
            render_backup_manager(page);
        }
    } catch (err) {
        console.error('Backup manager refresh error', err);
    }
};

function setup_backup_page_actions(page) {
    if (!page) return;
    try {
        if (page.clear_inner_toolbar) page.clear_inner_toolbar();
        if (page.clear_menu) page.clear_menu();

        page.set_primary_action(__('⚡ Instant DB Backup'), function() {
            create_backup(page, 'db');
        }, 'fa fa-database');

        page.set_secondary_action(__('🚀 Full System Backup'), function() {
            create_backup(page, 'all');
        }, 'fa fa-archive');

        page.add_inner_button(__('🎯 Export KPI JSON'), function() {
            export_kpi_json_backup(page);
        });

        page.add_inner_button(__('📤 Upload Backup'), function() {
            toggle_upload_section(page);
        });

        page.add_inner_button(__('🔄 Refresh'), function() {
            load_backups(page, true);
        });

        page.add_menu_item(__('🏢 Company Performance Overview'), () => frappe.set_route('kpi-company-overview'));
        page.add_menu_item(__('✍️ Data Entry Sheet'), () => frappe.set_route('kpi-data-entry-page'));
        page.add_menu_item(__('🤖 AI Performance Assistant'), () => frappe.set_route('kpi-ai-assistant'));
        page.add_menu_item(__('⚙️ KPI Settings'), () => frappe.set_route('Form', 'KPI Settings'));
    } catch (err) {
        console.error('Backup manager action setup error', err);
    }
}

function render_backup_manager(page) {
    if (!page || !page.main || !page.main.length) {
        console.warn('Backup manager: page.main unavailable, skipping render');
        return;
    }
    try {
        page._backups = [];
        page._filter_type = 'all';
        page._search_query = '';

        const html = `
            <div class="productix-backup-container" style="padding: 20px 0; max-width: 1400px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                <!-- Header Banner -->
                <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px; padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                    <div>
                        <div class="d-flex align-items-center gap-2">
                            <span style="font-size: 26px;">💾</span>
                            <h2 style="font-weight: 700; color: var(--text-color, #0f172a); margin: 0; font-size: 22px;">
                                Enterprise Backup & Restore Manager
                            </h2>
                        </div>
                        <p style="color: var(--text-muted, #64748b); margin: 6px 0 0 0; font-size: 14px;">
                            Generate immediate database dumps, export dedicated KPI JSON backups, or restore archives with a preview + explicit confirmation step.
                        </p>
                    </div>
                    <div class="d-flex gap-2 flex-wrap align-items-center">
                        <button class="btn btn-default btn-sm btn-refresh-backups" style="display: flex; align-items: center; gap: 6px; font-weight: 500;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                            Refresh
                        </button>
                        <button class="btn btn-default btn-sm btn-toggle-upload" style="display: flex; align-items: center; gap: 6px; background: #f8fafc; border: 1px solid #cbd5e1; font-weight: 500;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                            Upload Backup File
                        </button>
                        <button class="btn btn-warning btn-sm btn-export-kpi-json" style="display: flex; align-items: center; gap: 6px; background: #7c3aed; border-color: #7c3aed; font-weight: 600; color: #fff;">
                            🎯 Export KPI JSON Backup
                        </button>
                        <button class="btn btn-primary btn-sm btn-backup-db" style="display: flex; align-items: center; gap: 6px; background: #2563eb; border-color: #2563eb; font-weight: 600;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                            ⚡ Instant DB Backup (.sql.gz)
                        </button>
                        <button class="btn btn-success btn-sm btn-backup-full" style="display: flex; align-items: center; gap: 6px; background: #059669; border-color: #059669; font-weight: 600; color: #fff;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                            🚀 Full System Backup (.tar)
                        </button>
                    </div>
                </div>

                <!-- KPI Metric Summary Cards -->
                <div class="row g-3 mb-4" id="backup-metrics-row">
                    <div class="col-md-3 col-sm-6">
                        <div class="backup-metric-card" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                            <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Total Backups</div>
                            <div id="metric-total-count" style="font-size: 28px; font-weight: 700; color: #0f172a; margin-top: 4px;">-</div>
                            <div style="font-size: 12px; color: #10b981; margin-top: 2px;">Stored on server</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-sm-6">
                        <div class="backup-metric-card" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                            <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Database Dumps</div>
                            <div id="metric-db-count" style="font-size: 28px; font-weight: 700; color: #2563eb; margin-top: 4px;">-</div>
                            <div style="font-size: 12px; color: #64748b; margin-top: 2px;">SQL compressed (.sql.gz)</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-sm-6">
                        <div class="backup-metric-card" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                            <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Total Storage Used</div>
                            <div id="metric-total-size" style="font-size: 28px; font-weight: 700; color: #0f172a; margin-top: 4px;">-</div>
                            <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Private backup directory</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-sm-6">
                        <div class="backup-metric-card" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                            <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Latest Backup</div>
                            <div id="metric-latest-time" style="font-size: 15px; font-weight: 600; color: #0f172a; margin-top: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">-</div>
                            <div style="font-size: 12px; color: #059669; margin-top: 4px;">Server timestamp</div>
                        </div>
                    </div>
                </div>

                <!-- Upload Section (Collapsible) -->
                <div id="backup-upload-section" class="mb-4" style="display: none;">
                    <div style="background: #f8fafc; border: 2px dashed #94a3b8; border-radius: 12px; padding: 24px; text-align: center;">
                        <h4 style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">Upload Backup File</h4>
                        <p style="color: #64748b; font-size: 13px; margin-bottom: 16px;">
                            Supported formats: <code>.sql.gz</code>, <code>.sql</code>, <code>.tar</code>, <code>.json</code>, <code>.zip</code>. The file will be placed in the site's private backup storage.
                        </p>
                        <div class="d-flex justify-content-center align-items-center gap-3 flex-wrap">
                            <input type="file" id="backup-file-input" style="max-width: 320px; font-size: 13px;" class="form-control" accept=".sql.gz,.sql,.tar,.gz,.json,.zip,.tar.gz" />
                            <button class="btn btn-primary btn-sm btn-submit-upload" style="display: flex; align-items: center; gap: 6px;">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                                Upload to Server
                            </button>
                            <button class="btn btn-default btn-sm btn-cancel-upload">Cancel</button>
                        </div>
                        <div id="upload-progress-container" class="mt-3" style="display: none; max-width: 400px; margin: 0 auto;">
                            <div class="progress" style="height: 8px; border-radius: 4px;">
                                <div class="progress-bar progress-bar-striped progress-bar-animated" style="width: 100%; background: #2563eb;"></div>
                            </div>
                            <small class="text-muted mt-1 d-block" id="upload-status-text">Uploading file to server...</small>
                        </div>
                    </div>
                </div>

                <!-- Table Card & Filters -->
                <div style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                    <div style="padding: 16px 20px; border-bottom: 1px solid var(--border-color, #e2e8f0); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                        <div class="d-flex gap-2 flex-wrap" id="backup-filter-tabs">
                            <button class="btn btn-sm btn-filter active btn-primary" data-type="all" style="font-weight: 600; border-radius: 6px;">All Files (<span id="count-all">0</span>)</button>
                            <button class="btn btn-sm btn-filter btn-default" data-type="kpi_json" style="border-radius: 6px;">🎯 KPI Backups (<span id="count-kpi">0</span>)</button>
                            <button class="btn btn-sm btn-filter btn-default" data-type="database" style="border-radius: 6px;">Database Dumps (<span id="count-db">0</span>)</button>
                            <button class="btn btn-sm btn-filter btn-default" data-type="files" style="border-radius: 6px;">Files Archives (<span id="count-files">0</span>)</button>
                            <button class="btn btn-sm btn-filter btn-default" data-type="config" style="border-radius: 6px;">Config (<span id="count-config">0</span>)</button>
                        </div>
                        <div style="position: relative; min-width: 260px;">
                            <input type="text" id="backup-search-input" class="form-control form-control-sm" placeholder="Filter backup files..." style="padding-left: 32px; border-radius: 6px;" />
                            <svg style="position: absolute; left: 10px; top: 9px; color: #94a3b8;" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        </div>
                    </div>

                    <!-- Table List -->
                    <div class="table-responsive">
                        <table class="table table-hover mb-0" style="font-size: 13px;">
                            <thead style="background: var(--table-bg, #f8fafc); border-bottom: 1px solid var(--border-color, #e2e8f0);">
                                <tr>
                                    <th style="padding: 14px 20px; font-weight: 600; color: #475569;">File Name</th>
                                    <th style="padding: 14px 16px; font-weight: 600; color: #475569; width: 180px;">Type</th>
                                    <th style="padding: 14px 16px; font-weight: 600; color: #475569; width: 130px;">Size</th>
                                    <th style="padding: 14px 16px; font-weight: 600; color: #475569; width: 190px;">Created Date</th>
                                    <th style="padding: 14px 20px; font-weight: 600; color: #475569; width: 250px; text-align: right;">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="backups-table-body">
                                <tr>
                                    <td colspan="5" style="text-align: center; padding: 40px; color: #94a3b8;">
                                        <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
                                        <span class="ms-2">Loading available backups from server...</span>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        page.main.html(html);
        bind_backup_events(page);
        load_backups(page);

        page._reload_backups = function() {
            load_backups(page);
        };
    } catch (err) {
        console.error('Backup manager render error', err);
        try {
            if (page.main) {
                page.main.html(`
                    <div class="p-4" style="max-width: 760px; margin: 40px auto; text-align: center;">
                        <h4>Backup Manager could not render</h4>
                        <p class="text-muted">An unexpected error occurred while building the page.</p>
                        <pre style="text-align: left; max-height: 200px; overflow: auto; font-size: 12px;">${frappe.utils.escape_html(err && err.stack ? err.stack : String(err))}</pre>
                    </div>
                `);
            }
        } catch (e) { /* give up silently */ }
    }
}

function bind_backup_events(page) {
    if (!page || !page.main || !page.main.length) return;
    const $wrap = page.main;

    $wrap.find('.btn-refresh-backups').on('click', () => load_backups(page, true));
    $wrap.find('.btn-toggle-upload').on('click', () => toggle_upload_section(page));
    $wrap.find('.btn-cancel-upload').on('click', () => {
        $wrap.find('#backup-upload-section').slideUp(200);
        $wrap.find('#backup-file-input').val('');
    });

    $wrap.find('.btn-export-kpi-json').on('click', () => export_kpi_json_backup(page));
    $wrap.find('.btn-backup-db').on('click', () => create_backup(page, 'db'));
    $wrap.find('.btn-backup-full').on('click', () => create_backup(page, 'all'));
    $wrap.find('.btn-submit-upload').on('click', () => handle_file_upload(page));

    $wrap.find('.btn-filter').on('click', function() {
        $wrap.find('.btn-filter').removeClass('active btn-primary').addClass('btn-default');
        $(this).addClass('active btn-primary').removeClass('btn-default');
        page._filter_type = $(this).data('type');
        render_backups_table(page);
    });

    $wrap.find('#backup-search-input').on('input', function() {
        page._search_query = $(this).val().toLowerCase().trim();
        render_backups_table(page);
    });
}

function toggle_upload_section(page) {
    if (!page || !page.main || !page.main.length) return;
    page.main.find('#backup-upload-section').slideToggle(200);
}

function load_backups(page, show_alert) {
    if (!page || !page.main || !page.main.length) return;
    frappe.call({
        method: 'productix.api.backup.get_backups_list',
        callback: function(r) {
            try {
                if (r.message && r.message.success) {
                    page._backups = r.message.backups || [];
                    update_metrics_cards(page, r.message);
                    render_backups_table(page);
                    if (show_alert) {
                        frappe.show_alert({ message: __('Backups list refreshed'), indicator: 'green' });
                    }
                } else {
                    page.main.find('#backups-table-body').html(`
                        <tr><td colspan="5" style="text-align: center; padding: 40px; color: #dc2626;">Failed to retrieve backups from server.</td></tr>
                    `);
                }
            } catch (err) {
                console.error('Backup list load error', err);
            }
        },
        error: function() {
            try {
                page.main.find('#backups-table-body').html(`
                    <tr><td colspan="5" style="text-align: center; padding: 40px; color: #dc2626;">Error connecting to backup service.</td></tr>
                `);
            } catch (err) { console.error(err); }
        }
    });
}

function update_metrics_cards(page, data) {
    if (!page || !page.main || !page.main.length) return;
    const $wrap = page.main;
    $wrap.find('#metric-total-count').text(data.total_count || 0);
    $wrap.find('#metric-db-count').text(data.db_count || 0);
    $wrap.find('#metric-total-size').text(data.total_size_formatted || '0 B');
    $wrap.find('#metric-latest-time').text(data.latest_backup || 'None');

    const backups = page._backups || [];
    const db_count = backups.filter(b => b.is_db).length;
    const kpi_count = backups.filter(b => b.type === 'kpi_json' || (b.filename && b.filename.toLowerCase().includes('kpi'))).length;
    const files_count = backups.filter(b => b.type === 'public_files' || b.type === 'private_files' || b.type === 'archive').length;
    const config_count = backups.filter(b => b.type === 'config').length;

    $wrap.find('#count-all').text(backups.length);
    $wrap.find('#count-kpi').text(kpi_count);
    $wrap.find('#count-db').text(db_count);
    $wrap.find('#count-files').text(files_count);
    $wrap.find('#count-config').text(config_count);
}

function render_backups_table(page) {
    if (!page || !page.main || !page.main.length) return;
    try {
        let filtered = page._backups || [];

        if (page._filter_type === 'database') {
            filtered = filtered.filter(b => b.is_db);
        } else if (page._filter_type === 'kpi_json') {
            filtered = filtered.filter(b => b.type === 'kpi_json' || (b.filename && b.filename.toLowerCase().includes('kpi')));
        } else if (page._filter_type === 'files') {
            filtered = filtered.filter(b => b.type === 'public_files' || b.type === 'private_files' || b.type === 'archive');
        } else if (page._filter_type === 'config') {
            filtered = filtered.filter(b => b.type === 'config');
        }

        if (page._search_query) {
            filtered = filtered.filter(b => b.filename && b.filename.toLowerCase().includes(page._search_query));
        }

        const tbody = page.main.find('#backups-table-body');
        tbody.empty();

        if (filtered.length === 0) {
            tbody.html(`
                <tr>
                    <td colspan="5" style="text-align: center; padding: 40px; color: #64748b;">
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" style="margin-bottom: 8px;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        <div style="font-weight: 500;">No backup files found matching criteria</div>
                        <small class="text-muted">Click "🎯 Export KPI JSON Backup" or "⚡ Instant DB Backup" above to generate a new backup.</small>
                    </td>
                </tr>
            `);
            return;
        }

        const badgeColors = {
            'blue': { bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' },
            'green': { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0' },
            'purple': { bg: '#faf5ff', color: '#7e22ce', border: '#e9d5ff' },
            'orange': { bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' },
            'grey': { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' }
        };

        filtered.forEach(function(b) {
            const style = badgeColors[b.badge_color] || badgeColors['grey'];
            const fname = String(b.filename || '');
            const can_restore = b.can_restore || fname.endsWith('.sql') || fname.endsWith('.sql.gz') || fname.endsWith('.json');

            const tr = $(`
                <tr style="vertical-align: middle;">
                    <td style="padding: 12px 20px; font-weight: 500; color: #1e293b; font-family: monospace; font-size: 13px;">
                        <span style="margin-right: 6px;">📄</span> ${frappe.utils.escape_html(fname)}
                    </td>
                    <td style="padding: 12px 16px;">
                        <span style="background: ${style.bg}; color: ${style.color}; border: 1px solid ${style.border}; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap;">
                            ${b.type_label || 'Backup File'}
                        </span>
                    </td>
                    <td style="padding: 12px 16px; font-weight: 600; color: #475569;">
                        ${b.size_formatted}
                    </td>
                    <td style="padding: 12px 16px; color: #64748b; font-size: 12px;">
                        ${b.created_at}
                    </td>
                    <td style="padding: 12px 20px; text-align: right;">
                        <div class="d-flex justify-content-end gap-2">
                            <a href="${b.download_url}" target="_blank" download="${frappe.utils.escape_html(fname)}" class="btn btn-default btn-xs" style="display: inline-flex; align-items: center; gap: 4px; color: #2563eb; font-weight: 600; border-color: #bfdbfe; background: #eff6ff;" title="Direct Download to PC">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                                Download
                            </a>
                            ${can_restore ? `
                            <button class="btn btn-default btn-xs btn-restore-file" data-filename="${frappe.utils.escape_html(fname)}" style="display: inline-flex; align-items: center; gap: 4px; color: #059669; font-weight: 600; border-color: #bbf7d0; background: #f0fdf4;" title="Preview, then restore records into database">
                                🔄 Preview & Restore
                            </button>
                            ` : ''}
                            <button class="btn btn-default btn-xs btn-delete-file" data-filename="${frappe.utils.escape_html(fname)}" style="display: inline-flex; align-items: center; gap: 4px; color: #dc2626; border-color: #fecaca; background: #fef2f2;" title="Delete from server">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                                Delete
                            </button>
                        </div>
                    </td>
                </tr>
            `);

            tr.find('.btn-restore-file').on('click', function(e) {
                e.preventDefault();
                const fn = $(this).data('filename');
                preview_restore_backup(page, fn);
            });

            tr.find('.btn-delete-file').on('click', function(e) {
                e.preventDefault();
                const fn = $(this).data('filename');
                confirm_delete_backup(page, fn);
            });

            tbody.append(tr);
        });
    } catch (err) {
        console.error('Backup table render error', err);
    }
}

function export_kpi_json_backup(page) {
    frappe.show_alert({ message: __('Exporting KPI Tracking JSON backup... Please wait'), indicator: 'blue' });

    frappe.call({
        method: 'productix.api.backup.export_kpi_json_backup',
        freeze: true,
        freeze_message: __('Generating dedicated KPI JSON export...'),
        callback: function(r) {
            try {
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: __(r.message.message), indicator: 'green' });

                    if (r.message.download_url) {
                        const link = document.createElement('a');
                        link.href = r.message.download_url;
                        link.setAttribute('download', r.message.filename || 'kpi_backup.json');
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }

                    if (r.message.backups_data) {
                        page._backups = r.message.backups_data.backups || [];
                        update_metrics_cards(page, r.message.backups_data);
                        render_backups_table(page);
                    } else {
                        load_backups(page);
                    }
                } else {
                    frappe.msgprint({
                        title: __('Export Error'),
                        indicator: 'red',
                        message: r.message ? r.message.message : __('Failed to export KPI backup.')
                    });
                }
            } catch (err) { console.error('Export callback error', err); }
        },
        error: function() {
            frappe.msgprint({
                title: __('Export Failed'),
                indicator: 'red',
                message: __('An error occurred while exporting KPI JSON backup.')
            });
        }
    });
}

function create_backup(page, backup_type) {
    const is_full = backup_type === 'all';
    const label = is_full ? 'Full System Backup' : 'Database Backup';

    frappe.show_alert({ message: __(`Generating ${label}... Please wait`), indicator: 'blue' });

    frappe.call({
        method: 'productix.api.backup.take_immediate_backup',
        args: {
            backup_type: backup_type,
            with_files: is_full
        },
        freeze: true,
        freeze_message: __(`Creating ${label}...`),
        callback: function(r) {
            try {
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: __(r.message.message), indicator: 'green' });

                    if (r.message.main_download_url) {
                        const link = document.createElement('a');
                        link.href = r.message.main_download_url;
                        link.setAttribute('download', '');
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }

                    if (r.message.backups_data) {
                        page._backups = r.message.backups_data.backups || [];
                        update_metrics_cards(page, r.message.backups_data);
                        render_backups_table(page);
                    } else {
                        load_backups(page);
                    }
                } else {
                    frappe.msgprint({
                        title: __('Backup Error'),
                        indicator: 'red',
                        message: r.message ? r.message.message : __('Failed to create backup.')
                    });
                }
            } catch (err) { console.error('Backup callback error', err); }
        },
        error: function() {
            frappe.msgprint({
                title: __('Backup Failed'),
                indicator: 'red',
                message: __('An error occurred while creating the backup.')
            });
        }
    });
}

// ---------------------------------------------------------------------------
// Restore flow: Preview -> Confirm -> Restore (server refuses without confirm=1)
// ---------------------------------------------------------------------------
function preview_restore_backup(page, filename) {
    frappe.call({
        method: 'productix.api.backup.preview_backup_file',
        args: { filename: filename },
        freeze: true,
        freeze_message: __('Inspecting backup file...'),
        callback: function(r) {
            try {
                const preview = r.message || {};
                if (!preview || !preview.exists) {
                    frappe.msgprint({ title: __('Preview Failed'), indicator: 'red', message: __('Could not inspect the backup file.') });
                    return;
                }

                let detailHtml = '';
                if (preview.kind === 'json') {
                    detailHtml += `<p><strong>Type:</strong> KPI Tracking JSON Backup</p>`;
                    if (preview.exported_at) {
                        detailHtml += `<p><strong>Exported on:</strong> ${frappe.utils.escape_html(preview.exported_at)}</p>`;
                    }
                    detailHtml += `<p><strong>Total records:</strong> ${preview.total_records || 0}</p>`;
                    const counts = preview.doctype_counts || {};
                    const keys = Object.keys(counts);
                    if (keys.length) {
                        detailHtml += `<hr style="margin: 8px 0;"><div style="max-height: 240px; overflow: auto; font-size: 12px;"><table class="table table-sm table-borderless mb-0" style="font-size: 12px;">`;
                        keys.forEach(function(k) {
                            detailHtml += `<tr><td style="padding: 2px 8px; color: #475569;">${frappe.utils.escape_html(k)}</td><td style="padding: 2px 8px; text-align: right; font-weight: 600;">${counts[k]}</td></tr>`;
                        });
                        detailHtml += `</table></div>`;
                    }
                } else if (preview.kind === 'sql') {
                    detailHtml += `<p><strong>Type:</strong> Database SQL Dump</p>`;
                    detailHtml += `<p><strong>Statements:</strong> ${preview.statement_count || 0}</p>`;
                } else {
                    detailHtml += `<p><strong>Type:</strong> ${frappe.utils.escape_html(preview.kind || 'Unsupported')}</p>`;
                }

                if (preview.note) {
                    detailHtml += `<p class="text-muted" style="font-size: 12px; margin-top: 8px;">${frappe.utils.escape_html(preview.note)}</p>`;
                }

                frappe.confirm(
                    `<h5 style="margin-bottom: 10px;">Restore <b>${frappe.utils.escape_html(filename)}</b>?</h5>` +
                    `<div style="font-size: 13px; color: #1e293b;">${detailHtml}</div>` +
                    `<div class="alert alert-warning mt-3" style="font-size: 12px;">Restoring replaces the listed tables/records in the database. Recipe Management data is never touched. Take a fresh backup before restoring.</div>`,
                    function() {
                        execute_restore(page, filename);
                    }
                );
            } catch (err) {
                console.error('Preview restore error', err);
                frappe.msgprint({ title: __('Preview Failed'), indicator: 'red', message: __('An unexpected error occurred while previewing the backup.') });
            }
        },
        error: function(err) {
            console.error('Preview restore API error', err);
            let msg = __('Could not inspect the backup file.');
            if (err && err.message) msg = err.message;
            frappe.msgprint({ title: __('Preview Failed'), indicator: 'red', message: msg });
        }
    });
}

function execute_restore(page, filename) {
    frappe.call({
        method: 'productix.api.backup.restore_backup_file',
        args: { filename: filename, confirm: 1 },
        freeze: true,
        freeze_message: __('Restoring backup records into database...'),
        callback: function(r) {
            try {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        title: __('Restore Successful'),
                        indicator: 'green',
                        message: __(r.message.message)
                    });
                }
                load_backups(page);
            } catch (err) { console.error('Restore callback error', err); }
        },
        error: function(err) {
            console.error('Restore API error', err);
            let msg = __('Restore failed.');
            if (err && err.message) msg = err.message;
            frappe.msgprint({ title: __('Restore Failed'), indicator: 'red', message: msg });
            load_backups(page);
        }
    });
}

function confirm_delete_backup(page, filename) {
    frappe.confirm(
        __(`Are you sure you want to permanently delete the backup <b>${filename}</b> from the server?`),
        function() {
            frappe.call({
                method: 'productix.api.backup.delete_backup_file',
                args: { filename: filename },
                freeze: true,
                freeze_message: __('Deleting backup...'),
                callback: function(r) {
                    try {
                        if (r.message && r.message.success) {
                            frappe.show_alert({ message: __(r.message.message), indicator: 'green' });
                            if (r.message.backups_data) {
                                page._backups = r.message.backups_data.backups || [];
                                update_metrics_cards(page, r.message.backups_data);
                                render_backups_table(page);
                            } else {
                                load_backups(page);
                            }
                        }
                    } catch (err) { console.error('Delete callback error', err); }
                }
            });
        }
    );
}

function handle_file_upload(page) {
    if (!page || !page.main || !page.main.length) return;
    const fileInput = page.main.find('#backup-file-input')[0];
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        frappe.msgprint(__('Please select a backup file (.sql.gz, .sql, .tar, .json, .zip) to upload.'));
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('doctype', 'DocType');
    formData.append('cmd', 'productix.api.backup.upload_backup_file');

    page.main.find('#upload-progress-container').show();
    page.main.find('#upload-status-text').text(`Uploading ${file.name} (${(file.size / (1024*1024)).toFixed(2)} MB)...`);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/method/productix.api.backup.upload_backup_file', true);
    xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);

    xhr.onload = function() {
        try {
            page.main.find('#upload-progress-container').hide();
            if (xhr.status === 200) {
                try {
                    const res = JSON.parse(xhr.responseText);
                    const msg = res.message || res;
                    if (msg && msg.success) {
                        frappe.show_alert({ message: __(msg.message), indicator: 'green' });
                        page.main.find('#backup-file-input').val('');
                        page.main.find('#backup-upload-section').slideUp(200);
                        if (msg.backups_data) {
                            page._backups = msg.backups_data.backups || [];
                            update_metrics_cards(page, msg.backups_data);
                            render_backups_table(page);
                        } else {
                            load_backups(page);
                        }
                    } else {
                        frappe.msgprint({ title: __('Upload Notice'), message: msg.message || 'Upload completed.' });
                        load_backups(page);
                    }
                } catch(e) {
                    frappe.show_alert({ message: __('Backup uploaded successfully!'), indicator: 'green' });
                    load_backups(page);
                }
            } else {
                frappe.msgprint({ title: __('Upload Error'), indicator: 'red', message: 'Failed to upload backup file. Check file format and size.' });
            }
        } catch (err) { console.error('Upload load error', err); }
    };

    xhr.onerror = function() {
        try {
            page.main.find('#upload-progress-container').hide();
            frappe.msgprint({ title: __('Network Error'), indicator: 'red', message: 'Network error during upload.' });
        } catch (err) { console.error(err); }
    };

    xhr.send(formData);
}
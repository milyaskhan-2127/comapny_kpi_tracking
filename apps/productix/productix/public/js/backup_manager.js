// Productix ERP — Enterprise Backup & Restore Manager

frappe.provide('productix.backup_manager');

productix.backup_manager = {
    page: null,
    wrapper: null,
    backups: [],
    filter_type: 'all',
    search_query: '',

    init: function(wrapper) {
        this.wrapper = $(wrapper);
        this.render_skeleton();
        this.check_permission_and_load();
    },

    check_permission_and_load: function() {
        const user = frappe.session.user;
        const is_admin = user === 'Administrator' ||
                         frappe.user.has_role('System Manager') ||
                         frappe.user.has_role('KPI Admin');

        if (!is_admin) {
            this.render_permission_denied();
            return;
        }

        this.load_backups();
    },

    render_skeleton: function() {
        // Clean out any old Frappe default elements
        this.wrapper.empty();
        this.wrapper.removeClass('no-border');

        const html = `
            <div class="productix-backup-container" style="padding: 24px; max-width: 1300px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                <!-- Header Card -->
                <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px; padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                    <div>
                        <div class="d-flex align-items-center gap-2">
                            <span style="font-size: 26px;">💾</span>
                            <h2 style="font-weight: 700; color: var(--text-color, #0f172a); margin: 0; font-size: 22px;">
                                Enterprise Backup & Restore Manager
                            </h2>
                        </div>
                        <p style="color: var(--text-muted, #64748b); margin: 6px 0 0 0; font-size: 14px;">
                            Generate immediate database dumps, download system archives directly to your PC, or upload existing backup archives.
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
                        <button class="btn btn-primary btn-sm btn-backup-db" style="display: flex; align-items: center; gap: 6px; background: #2563eb; border-color: #2563eb; font-weight: 600;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                            ⚡ Instant DB Backup & Download
                        </button>
                        <button class="btn btn-success btn-sm btn-backup-full" style="display: flex; align-items: center; gap: 6px; background: #059669; border-color: #059669; font-weight: 600; color: #fff;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                            🚀 Full System Backup & Download
                        </button>
                    </div>
                </div>

                <!-- KPI Summary Metric Cards -->
                <div class="row g-3 mb-4" id="backup-metrics-row">
                    <div class="col-md-3 col-sm-6">
                        <div style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                            <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Total Backups</div>
                            <div id="metric-total-count" style="font-size: 28px; font-weight: 700; color: #0f172a; margin-top: 4px;">-</div>
                            <div style="font-size: 12px; color: #10b981; margin-top: 2px;">Stored on local server</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-sm-6">
                        <div style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                            <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Database Dumps</div>
                            <div id="metric-db-count" style="font-size: 28px; font-weight: 700; color: #2563eb; margin-top: 4px;">-</div>
                            <div style="font-size: 12px; color: #64748b; margin-top: 2px;">SQL compressed (.sql.gz)</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-sm-6">
                        <div style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                            <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">Total Storage Used</div>
                            <div id="metric-total-size" style="font-size: 28px; font-weight: 700; color: #0f172a; margin-top: 4px;">-</div>
                            <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Private backup directory</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-sm-6">
                        <div style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
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
                                    <th style="padding: 14px 20px; font-weight: 600; color: #475569; width: 200px; text-align: right;">1-Click Actions</th>
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

        this.wrapper.html(html);
        this.bind_events();
    },

    bind_events: function() {
        const me = this;

        this.wrapper.find('.btn-refresh-backups').on('click', function() {
            me.load_backups(true);
        });

        this.wrapper.find('.btn-toggle-upload').on('click', function() {
            me.wrapper.find('#backup-upload-section').slideToggle(200);
        });

        this.wrapper.find('.btn-cancel-upload').on('click', function() {
            me.wrapper.find('#backup-upload-section').slideUp(200);
            me.wrapper.find('#backup-file-input').val('');
        });

        // Instant DB Backup & Direct Download
        this.wrapper.find('.btn-backup-db').on('click', function() {
            me.create_backup('db');
        });

        // Instant Full Backup & Direct Download
        this.wrapper.find('.btn-backup-full').on('click', function() {
            me.create_backup('all');
        });

        // Submit Upload
        this.wrapper.find('.btn-submit-upload').on('click', function() {
            me.handle_file_upload();
        });

        // Filter Tabs
        this.wrapper.find('.btn-filter').on('click', function() {
            me.wrapper.find('.btn-filter').removeClass('active btn-primary').addClass('btn-default');
            $(this).addClass('active btn-primary').removeClass('btn-default');
            me.filter_type = $(this).data('type');
            me.render_table();
        });

        // Search
        this.wrapper.find('#backup-search-input').on('input', function() {
            me.search_query = $(this).val().toLowerCase().trim();
            me.render_table();
        });
    },

    load_backups: function(show_alert) {
        const me = this;
        frappe.call({
            method: 'productix.api.backup.get_backups_list',
            callback: function(r) {
                if (r.message && r.message.success) {
                    me.backups = r.message.backups || [];
                    me.update_metrics(r.message);
                    me.render_table();
                    if (show_alert) {
                        frappe.show_alert({ message: __('Backups list refreshed'), indicator: 'green' });
                    }
                } else {
                    me.render_empty_or_error('Failed to retrieve backups from server.');
                }
            },
            error: function(err) {
                me.render_empty_or_error('Error connecting to backup service.');
            }
        });
    },

    update_metrics: function(data) {
        this.wrapper.find('#metric-total-count').text(data.total_count || 0);
        this.wrapper.find('#metric-db-count').text(data.db_count || 0);
        this.wrapper.find('#metric-total-size').text(data.total_size_formatted || '0 B');
        this.wrapper.find('#metric-latest-time').text(data.latest_backup || 'None');

        const db_count = this.backups.filter(b => b.is_db).length;
        const files_count = this.backups.filter(b => b.type === 'public_files' || b.type === 'private_files' || b.type === 'archive').length;
        const config_count = this.backups.filter(b => b.type === 'config').length;

        this.wrapper.find('#count-all').text(this.backups.length);
        this.wrapper.find('#count-db').text(db_count);
        this.wrapper.find('#count-files').text(files_count);
        this.wrapper.find('#count-config').text(config_count);
    },

    render_table: function() {
        const me = this;
        let filtered = this.backups;

        // Apply tab filter
        if (this.filter_type === 'database') {
            filtered = filtered.filter(b => b.is_db);
        } else if (this.filter_type === 'files') {
            filtered = filtered.filter(b => b.type === 'public_files' || b.type === 'private_files' || b.type === 'archive');
        } else if (this.filter_type === 'config') {
            filtered = filtered.filter(b => b.type === 'config');
        }

        // Apply search query
        if (this.search_query) {
            filtered = filtered.filter(b => b.filename.toLowerCase().includes(this.search_query));
        }

        const tbody = this.wrapper.find('#backups-table-body');
        tbody.empty();

        if (filtered.length === 0) {
            tbody.html(`
                <tr>
                    <td colspan="5" style="text-align: center; padding: 40px; color: #64748b;">
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" style="margin-bottom: 8px;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        <div style="font-weight: 500;">No backup files found matching criteria</div>
                        <small class="text-muted">Click "⚡ Instant DB Backup & Download" above to generate a new backup.</small>
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
            const tr = $(`
                <tr style="vertical-align: middle;">
                    <td style="padding: 12px 20px; font-weight: 500; color: #1e293b; font-family: monospace; font-size: 13px;">
                        <span style="margin-right: 6px;">📄</span> ${frappe.utils.escape_html(b.filename)}
                    </td>
                    <td style="padding: 12px 16px;">
                        <span style="background: ${style.bg}; color: ${style.color}; border: 1px solid ${style.border}; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap;">
                            ${b.type_label}
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
                            <a href="${b.download_url}" target="_blank" download="${frappe.utils.escape_html(b.filename)}" class="btn btn-default btn-xs btn-download-file" style="display: inline-flex; align-items: center; gap: 4px; color: #2563eb; font-weight: 600; border-color: #bfdbfe; background: #eff6ff;" title="Direct Download to PC">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                                Download
                            </a>
                            <button class="btn btn-default btn-xs btn-delete-file" data-filename="${frappe.utils.escape_html(b.filename)}" style="display: inline-flex; align-items: center; gap: 4px; color: #dc2626; border-color: #fecaca; background: #fef2f2;" title="Delete from server">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                                Delete
                            </button>
                        </div>
                    </td>
                </tr>
            `);

            tr.find('.btn-delete-file').on('click', function(e) {
                e.preventDefault();
                const fn = $(this).data('filename');
                me.confirm_delete_backup(fn);
            });

            tbody.append(tr);
        });
    },

    create_backup: function(backup_type) {
        const me = this;
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
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: __(r.message.message), indicator: 'green' });

                    // Auto-trigger direct download for user
                    if (r.message.main_download_url) {
                        const link = document.createElement('a');
                        link.href = r.message.main_download_url;
                        link.setAttribute('download', '');
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }

                    if (r.message.backups_data) {
                        me.backups = r.message.backups_data.backups || [];
                        me.update_metrics(r.message.backups_data);
                        me.render_table();
                    } else {
                        me.load_backups();
                    }
                } else {
                    frappe.msgprint({
                        title: __('Backup Error'),
                        indicator: 'red',
                        message: r.message ? r.message.message : __('Failed to create backup.')
                    });
                }
            },
            error: function(err) {
                frappe.msgprint({
                    title: __('Backup Failed'),
                    indicator: 'red',
                    message: __('An error occurred while creating the backup.')
                });
            }
        });
    },

    confirm_delete_backup: function(filename) {
        const me = this;
        frappe.confirm(
            __(`Are you sure you want to permanently delete the backup <b>${filename}</b> from the server?`),
            function() {
                frappe.call({
                    method: 'productix.api.backup.delete_backup_file',
                    args: { filename: filename },
                    freeze: true,
                    freeze_message: __('Deleting backup...'),
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({ message: __(r.message.message), indicator: 'green' });
                            if (r.message.backups_data) {
                                me.backups = r.message.backups_data.backups || [];
                                me.update_metrics(r.message.backups_data);
                                me.render_table();
                            } else {
                                me.load_backups();
                            }
                        }
                    }
                });
            }
        );
    },

    handle_file_upload: function() {
        const me = this;
        const fileInput = this.wrapper.find('#backup-file-input')[0];
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            frappe.msgprint(__('Please select a backup file (.sql.gz, .sql, .tar, .json, .zip) to upload.'));
            return;
        }

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('doctype', 'DocType');
        formData.append('cmd', 'productix.api.backup.upload_backup_file');

        this.wrapper.find('#upload-progress-container').show();
        this.wrapper.find('#upload-status-text').text(`Uploading ${file.name} (${(file.size / (1024*1024)).toFixed(2)} MB)...`);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/method/productix.api.backup.upload_backup_file', true);
        xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);

        xhr.onload = function() {
            me.wrapper.find('#upload-progress-container').hide();
            if (xhr.status === 200) {
                try {
                    const res = JSON.parse(xhr.responseText);
                    const msg = res.message || res;
                    if (msg && msg.success) {
                        frappe.show_alert({ message: __(msg.message), indicator: 'green' });
                        me.wrapper.find('#backup-file-input').val('');
                        me.wrapper.find('#backup-upload-section').slideUp(200);
                        if (msg.backups_data) {
                            me.backups = msg.backups_data.backups || [];
                            me.update_metrics(msg.backups_data);
                            me.render_table();
                        } else {
                            me.load_backups();
                        }
                    } else {
                        frappe.msgprint({ title: __('Upload Notice'), message: msg.message || 'Upload completed.' });
                        me.load_backups();
                    }
                } catch(e) {
                    frappe.show_alert({ message: __('Backup uploaded successfully!'), indicator: 'green' });
                    me.load_backups();
                }
            } else {
                frappe.msgprint({ title: __('Upload Error'), indicator: 'red', message: 'Failed to upload backup file. Check file format and size.' });
            }
        };

        xhr.onerror = function() {
            me.wrapper.find('#upload-progress-container').hide();
            frappe.msgprint({ title: __('Network Error'), indicator: 'red', message: 'Network error during upload.' });
        };

        xhr.send(formData);
    },

    render_permission_denied: function() {
        this.wrapper.empty().html(`
            <div style="text-align: center; padding: 60px 20px;">
                <div style="font-size: 48px; margin-bottom: 16px;">🔒</div>
                <h3 style="font-weight: 700; color: #0f172a;">Access Restricted</h3>
                <p style="color: #64748b; max-width: 500px; margin: 8px auto 24px auto;">
                    The Backup &amp; Restore Manager is reserved exclusively for Administrators and System Managers.
                </p>
                <button class="btn btn-primary" onclick="frappe.set_route('kpi-department-dashboard')">
                    Go to Department Dashboard
                </button>
            </div>
        `);
    },

    render_empty_or_error: function(msg) {
        this.wrapper.find('#backups-table-body').html(`
            <tr>
                <td colspan="5" style="text-align: center; padding: 40px; color: #dc2626;">
                    ${frappe.utils.escape_html(msg)}
                </td>
            </tr>
        `);
    }
};

// Core Frappe /app/backups Page Integration
function mount_productix_backup_manager() {
    const route = frappe.get_route() || [];
    if (route[0] === 'backups' || route[0] === 'kpi-backup-manager') {
        const page_container = $('div[data-page-route="backups"], div[data-page-route="kpi-backup-manager"]');
        if (page_container.length > 0) {
            if (page_container.find('.productix-backup-container').length === 0) {
                // Remove default Frappe "Get Backup" button that queues emails
                page_container.find('.page-actions button:contains("Get Backup"), .standard-actions button:contains("Get Backup")').remove();

                const target = page_container.find('.page-body, .layout-main-section, .page-content').first();
                const mount_el = target.length > 0 ? target : page_container;
                productix.backup_manager.init(mount_el);
            }
        }
    }
}

// Override Frappe standard backups page
frappe.pages['backups'] = frappe.pages['backups'] || {};
frappe.pages['backups'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Enterprise Backup & Restore Manager'),
        single_column: true
    });
    productix.backup_manager.page = page;
    productix.backup_manager.init(page.body);
};

// Hook into router and DOM changes
$(document).on('page-change', function() {
    setTimeout(mount_productix_backup_manager, 50);
    setTimeout(mount_productix_backup_manager, 300);
});

if (frappe.router) {
    frappe.router.on('change', function() {
        setTimeout(mount_productix_backup_manager, 50);
        setTimeout(mount_productix_backup_manager, 300);
    });
}

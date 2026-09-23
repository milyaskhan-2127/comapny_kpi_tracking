// Productix KPI Tracking — Machine Health Dashboard
// Views: Home grid (company/department machine cards) + per-machine detail
// drilldown. Defensive: every render path is guarded against blank screens.

frappe.pages['machine-health'] = frappe.pages['machine-health'] || {};

frappe.pages['machine-health'].on_page_load = function(wrapper) {
    try {
        const page = wrapper.page || frappe.ui.make_app_page({
            parent: wrapper,
            title: __('Machine Health Dashboard'),
            single_column: true
        });
        wrapper.page = page;
        if (page.main) page.main.addClass('kpi-tracking-app productix-machine-health-page');

        page._view = 'home';
        page._machines = [];
        page._ctx = {};
        page._status_filter = 'all';

        frappe.xcall('productix.kpi_tracking.api.dashboard.get_user_context').then((ctx) => {
            page._ctx = ctx || {};
            init_state(page);
            render_home(page);
        }).catch(() => {
            init_state(page);
            render_home(page);
        });
    } catch (err) {
        console.error('Machine health init error', err);
        show_fatal(wrapper, err);
    }
};

frappe.pages['machine-health'].refresh = function(wrapper) {
    try {
        const page = wrapper && wrapper.page;
        if (!page || !page.main || !page.main.length) return;
        if (page._view === 'detail' && page._detail_machine) {
            load_detail(page, page._detail_machine);
        } else {
            render_home(page);
        }
    } catch (err) {
        console.error('Machine health refresh error', err);
    }
};

function show_fatal(wrapper, err) {
    try {
        if (!wrapper || !wrapper.page || !wrapper.page.main) return;
        wrapper.page.main.html(`
            <div class="p-4" style="max-width: 760px; margin: 40px auto; text-align: center;">
                <h4>Machine Health could not load</h4>
                <p class="text-muted">An unexpected error occurred.</p>
                <pre style="text-align: left; max-height: 200px; overflow: auto; font-size: 12px;">${frappe.utils.escape_html(err && err.stack ? err.stack : String(err))}</pre>
                <button class="btn btn-primary btn-sm mt-2" onclick="window.location.reload()">Reload Page</button>
            </div>
        `);
    } catch (e) { /* ignore */ }
}

function init_state(page) {
    page._is_admin = !!(page._ctx.is_admin);
    page._is_ceo = !!(page._ctx.is_ceo);
    page._is_employee = !!(page._ctx.is_employee);
    page._can_view_machines = page._is_admin || (page._is_ceo && page._ctx.ceo_config && page._ctx.ceo_config.can_view_machines) || page._is_employee;
    page._department_names = (page._ctx.departments || []).slice();
}

function status_style(status) {
    const map = {
        'Healthy': { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0' },
        'Good': { bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' },
        'Warning': { bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' },
        'Critical': { bg: '#fef2f2', color: '#dc2626', border: '#fecaca' }
    };
    return map[status] || { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' };
}

function badge_html(status) {
    const s = status_style(status);
    return `<span class="machine-status-badge" style="background:${s.bg};color:${s.color};border:1px solid ${s.border};padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">${frappe.utils.escape_html(status || 'No Data')}</span>`;
}

// ---------------------------------------------------------------------------
// HOME VIEW
// ---------------------------------------------------------------------------
function render_home(page) {
    if (!page || !page.main || !page.main.length) return;
    try {
        if (!page._can_view_machines) {
            page.main.html(`
                <div class="p-4" style="max-width: 640px; margin: 60px auto; text-align: center;">
                    <h4>⛔ Access Restricted</h4>
                    <p class="text-muted">You do not have permission to view Machine Health.</p>
                </div>
            `);
            return;
        }

        page._view = 'home';
        page.set_title(__('Machine Health Dashboard'));

        if (page._is_admin) {
            page.set_primary_action(__('+ New Machine'), () => open_create_machine_modal(page), 'fa fa-plus');
        }

        page.main.html(`
            <div class="productix-mh-wrap" style="padding: 16px 0; max-width: 1400px; margin: 0 auto;">
                <div class="mb-3 d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <div>
                        <h2 style="font-weight: 700; color: var(--text-color, #0f172a); margin: 0; font-size: 20px;">Fleet Health Overview</h2>
                        <p class="text-muted mb-0" style="font-size: 13px;">Live status from the latest machine readings</p>
                    </div>
                    <div class="d-flex gap-2 align-items-center">
                        <select id="mh-status-filter" class="form-control form-control-sm" style="width: auto;">
                            <option value="all">All Statuses</option>
                            <option value="Healthy">Healthy</option>
                            <option value="Good">Good</option>
                            <option value="Warning">Warning</option>
                            <option value="Critical">Critical</option>
                            <option value="">No Data</option>
                        </select>
                        <button class="btn btn-default btn-sm btn-mh-refresh">🔄 Refresh</button>
                    </div>
                </div>
                <div id="mh-summary-cards" class="row g-3 mb-4"></div>
                <div id="mh-departments"></div>
            </div>
        `);

        page.main.find('.btn-mh-refresh').on('click', () => render_home(page));
        page.main.find('#mh-status-filter').on('change', function() {
            page._status_filter = $(this).val();
            render_machine_cards(page);
        });

        load_machines_home(page);
    } catch (err) {
        console.error('Machine health home render error', err);
        show_fatal(page, err);
    }
}

function load_machines_home(page) {
    frappe.call({
        method: 'productix.kpi_tracking.api.machine.get_machines',
        args: {},
        callback: function(r) {
            try {
                page._machines = (r.message && r.message.machines) || [];
                render_summary_cards(page);
                render_machine_cards(page);
            } catch (err) { console.error('Machine list error', err); }
        },
        error: function() {
            page.main.find('#mh-summary-cards').html(`
                <div class="col-12"><div class="alert alert-danger">Could not load machines. Check your permissions.</div></div>
            `);
        }
    });
}

function render_summary_cards(page) {
    const $wrap = page.main;
    const machines = page._machines || [];
    const total = machines.length;
    const healthy = machines.filter(m => m.health_status === 'Healthy').length;
    const good = machines.filter(m => m.health_status === 'Good').length;
    const warning = machines.filter(m => m.health_status === 'Warning').length;
    const critical = machines.filter(m => m.health_status === 'Critical').length;
    const no_data = machines.filter(m => !m.health_status).length;
    const avg = total ? Math.round((machines.reduce((s, m) => s + (m.health_score || 0), 0) / total) * 100) / 100 : 0;

    const card = (label, value, sub, color) => `
        <div class="col-md-2 col-sm-4 col-6">
            <div class="mh-summary-card" style="background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #64748b;">${label}</div>
                <div style="font-size: 24px; font-weight: 700; color: ${color}; margin-top: 2px;">${value}</div>
                <div style="font-size: 11px; color: #94a3b8;">${sub}</div>
            </div>
        </div>
    `;

    $wrap.find('#mh-summary-cards').html(
        card('Total Machines', total, 'Across fleet', '#0f172a') +
        card('Healthy', healthy, 'Score ≥ 85', '#15803d') +
        card('Good', good, 'Score 70–84', '#1d4ed8') +
        card('Warning', warning, 'Score 50–69', '#c2410c') +
        card('Critical', critical, 'Score < 50', '#dc2626') +
        card('Avg Score', avg, `${no_data} with no data`, '#7c3aed')
    );
}

function render_machine_cards(page) {
    const $wrap = page.main;
    const machines = (page._machines || []).slice();
    const filter = page._status_filter || 'all';
    let filtered = machines;
    if (filter !== 'all') filtered = filtered.filter(m => (m.health_status || '') === filter);

    const dept_names = page._ctx.department_list || [];
    const dept_map = {};
    (dept_names || []).forEach(d => { dept_map[d.name] = d.display_name || d.department_name || d.name; });

    const by_dept = {};
    filtered.forEach(m => {
        const key = m.department || 'Unassigned';
        if (!by_dept[key]) by_dept[key] = [];
        by_dept[key].push(m);
    });

    const dept_keys = Object.keys(by_dept).sort((a, b) => (dept_map[a] || a).localeCompare(dept_map[b] || b));

    let html = '';
    dept_keys.forEach(dept => {
        const list = by_dept[dept];
        const label = dept_map[dept] || dept;
        const crit = list.filter(m => m.health_status === 'Critical').length;
        html += `
            <div class="mh-dept-section mb-4" data-dept="${frappe.utils.escape_html(dept)}">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 style="font-weight: 600; margin: 0; font-size: 15px; color: #1e293b;">${frappe.utils.escape_html(label)}</h5>
                    <div class="d-flex gap-2" style="font-size: 11px; color: #64748b;">
                        <span>${list.length} machine(s)</span>
                        ${crit ? `<span class="text-danger font-weight-bold">${crit} critical</span>` : ''}
                    </div>
                </div>
                <div class="row g-3">
                    ${list.map(m => machine_card(m, page._is_admin)).join('')}
                </div>
            </div>
        `;
    });

    if (!html) {
        html = `
            <div class="text-center p-5" style="color: #94a3b8;">
                <div style="font-size: 32px;">🔍</div>
                <div style="font-weight: 500; color: #64748b;">No machines found${filter !== 'all' ? ' matching the selected status' : ''}</div>
                <div class="text-muted" style="font-size: 13px;">Machines appear here once created and linked to departments.</div>
            </div>
        `;
    }

    const $depts = $wrap.find('#mh-departments');
    $depts.html(html);
    $depts.find('.machine-card').on('click', function() {
        const name = $(this).data('machine');
        if (name) show_detail(page, name);
    });
}

function machine_card(m, is_admin) {
    const op = m.operating_status || '';
    const op_color = op === 'Operational' ? '#15803d' : (op === 'Idle' ? '#c2410c' : (op === 'Under Maintenance' ? '#1d4ed8' : '#64748b'));
    const op_dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${op_color};margin-right:4px;"></span>`;
    const score = m.health_score != null ? m.health_score : '—';
    return `
        <div class="col-md-4 col-lg-3">
            <div class="machine-card" data-machine="${frappe.utils.escape_html(m.name)}" style="background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px; padding: 14px; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: border-color 0.15s, transform 0.15s;">
                <div class="d-flex justify-content-between align-items-start">
                    <div style="min-width: 0;">
                        <div style="font-weight: 600; color: #0f172a; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${frappe.utils.escape_html(m.machine_name)}</div>
                        <div style="font-size: 11px; color: #94a3b8; font-family: monospace;">${frappe.utils.escape_html(m.machine_code || '')}</div>
                    </div>
                    ${badge_html(m.health_status)}
                </div>
                <div class="mt-3 d-flex align-items-end justify-content-between">
                    <div>
                        <div style="font-size: 26px; font-weight: 700; color: ${m.health_status === 'Critical' ? '#dc2626' : (m.health_status === 'Warning' ? '#c2410c' : '#0f172a')};">${score}</div>
                        <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Health Score</div>
                    </div>
                    <div>
                        <div style="font-size: 12px; color: #475569;">${op_dot}${frappe.utils.escape_html(op)}</div>
                        <div style="font-size: 11px; color: #94a3b8;">${m.last_reading_date ? 'Last reading ' + frappe.utils.escape_html(m.last_reading_date) : 'No readings yet'}</div>
                    </div>
                </div>
                <div class="mt-2" style="border-top: 1px solid var(--border-color, #f1f5f9); padding-top: 8px; font-size: 11px; color: #64748b;">
                    🔧 ${frappe.utils.escape_html(m.machine_type || '')} &nbsp;·&nbsp; 📍 ${frappe.utils.escape_html(m.location || '—')}
                </div>
            </div>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// DETAIL VIEW
// ---------------------------------------------------------------------------
function show_detail(page, machine_name) {
    page._view = 'detail';
    page._detail_machine = machine_name;
    frappe.set_route('machine-health', { machine: machine_name });
    load_detail(page, machine_name);
}

function load_detail(page, machine_name) {
    if (!page || !page.main || !page.main.length) return;
    page.main.html(`
        <div class="p-4 text-center"><div class="spinner-border text-primary"></div>
        <p class="text-muted mt-2">Loading machine details...</p></div>
    `);
    frappe.call({
        method: 'productix.kpi_tracking.api.machine.get_machine_detail',
        args: { machine_name: machine_name },
        freeze: false,
        callback: function(r) {
            try {
                if (!r.message) {
                    page.main.html('<div class="alert alert-danger p-4">Machine not found.</div>');
                    return;
                }
                render_detail(page, r.message);
            } catch (err) { console.error('Detail render error', err); }
        },
        error: function(err) {
            let msg = __('Could not load machine detail.');
            if (err && err.message) msg = err.message;
            page.main.html(`
                <div class="p-4 text-center">
                    <div class="alert alert-danger mx-auto" style="max-width: 480px;">${frappe.utils.escape_html(msg)}</div>
                    <button class="btn btn-default btn-sm btn-back-home">← Back to Fleet Overview</button>
                </div>
            `);
            page.main.find('.btn-back-home').on('click', () => back_home(page));
        }
    });
}

function render_detail(page, detail) {
    const m = detail.machine || {};
    const can_write = !!detail.can_write;

    page.set_title(m.machine_name || 'Machine Detail');
    if (page._is_admin) {
        page.set_primary_action(__('← Fleet Overview'), () => back_home(page), 'fa fa-arrow-left');
    }

    const params = detail.parameters || [];
    const linked_kpis = detail.linked_kpis || [];
    const alerts = detail.alerts || [];
    const history = detail.history || [];
    const trend = detail.trend || {};
    const prediction = detail.prediction || null;

    const hist_rows = history.slice(0, 20).map(h => `
        <tr>
            <td style="padding: 6px 10px;">${frappe.utils.escape_html(h.log_date || '')}</td>
            <td style="padding: 6px 10px; font-weight: 600;">${h.health_score != null ? h.health_score : '—'}</td>
            <td style="padding: 6px 10px;">${badge_html(h.health_status)}</td>
        </tr>
    `).join('');

    const alert_rows = alerts.map(a => `
        <div class="alert-row d-flex justify-content-between align-items-center" style="border-bottom: 1px solid var(--border-color, #f1f5f9); padding: 8px 0;">
            <div>
                <span class="me-2">${badge_html(a.severity)}</span>
                <span style="font-weight: 500; font-size: 13px; color: #1e293b;">${frappe.utils.escape_html(a.alert_type || 'Alert')}</span>
                <div style="font-size: 12px; color: #64748b;">${frappe.utils.escape_html(a.message || a.subject || '')}</div>
            </div>
            <div style="font-size: 11px; color: #94a3b8; white-space: nowrap;">${frappe.utils.escape_html(a.period || '')}</div>
        </div>
    `).join('') || '<div class="text-muted" style="font-size: 13px; padding: 12px 0;">No active alerts for this machine.</div>';

    const kpi_rows = linked_kpis.map(k => `
        <div class="d-flex justify-content-between align-items-center" style="border-bottom: 1px solid var(--border-color, #f1f5f9); padding: 7px 0;">
            <span style="font-size: 13px;">🎯 ${frappe.utils.escape_html(k.kpi_name || k.kpi)}</span>
            ${can_write ? `<button class="btn btn-xs btn-default btn-remove-kpi" data-kpi="${frappe.utils.escape_html(k.kpi)}">Remove</button>` : ''}
        </div>
    `).join('') || '<div class="text-muted" style="font-size: 13px; padding: 12px 0;">No KPIs linked. ' + (can_write ? 'Use "Add KPI" below.' : '') + '</div>';

    const pred_html = prediction ? `
        <div class="row g-2 mt-2">
            <div class="col-4 text-center"><div style="font-size: 18px; font-weight: 700; color: ${prediction.next_day < 50 ? '#dc2626' : '#0f172a'};">${prediction.next_day}</div><div style="font-size: 10px; color: #94a3b8;">Predicted (24h)</div></div>
            <div class="col-4 text-center"><div style="font-size: 18px; font-weight: 700; color: ${prediction.next_week < 50 ? '#dc2626' : '#0f172a'};">${prediction.next_week}</div><div style="font-size: 10px; color: #94a3b8;">Predicted (7d)</div></div>
            <div class="col-4 text-center"><div style="font-size: 18px; font-weight: 700; color: #7c3aed;">${prediction.confidence}%</div><div style="font-size: 10px; color: #94a3b8;">Confidence</div></div>
        </div>
    ` : '<div class="text-muted mt-2" style="font-size: 12px;">Prediction requires at least 5 history points. Submit readings to unlock.</div>';

    const trend_dir = trend.direction || 'Stable';
    const trend_color = trend_dir === 'Improving' ? '#15803d' : (trend_dir === 'Declining' ? '#dc2626' : '#64748b');

    const param_header = params.length ? params.map(p => `
        <div style="border:1px solid var(--border-color,#e2e8f0);border-radius:8px;padding:8px 10px;font-size:12px;">
            <div style="font-weight:600;color:#1e293b;">${frappe.utils.escape_html(p.parameter_name || p.parameter_code)}</div>
            <div style="color:#94a3b8;">${frappe.utils.escape_html(p.parameter_code)} · ${frappe.utils.escape_html(p.unit || '')}${p.is_required ? ' · required' : ''}</div>
        </div>
    `).join('') : '<div class="text-muted" style="font-size: 12px;">No parameters configured on this machine type.</div>';

    page.main.html(`
        <div class="productix-mh-detail" style="padding: 16px 0; max-width: 1400px; margin: 0 auto;">
            <button class="btn btn-default btn-sm mb-3 btn-back-home">← Back to Fleet Overview</button>

            <div class="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4" style="background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px; padding: 18px 22px;">
                <div>
                    <h2 style="font-weight: 700; margin: 0; font-size: 20px; color: #0f172a;">${frappe.utils.escape_html(m.machine_name)}</h2>
                    <div style="font-size: 12px; color: #94a3b8; font-family: monospace;">${frappe.utils.escape_html(m.machine_code || m.name)} · ${frappe.utils.escape_html(detail.machine_type_name || m.machine_type || '')}</div>
                </div>
                <div class="d-flex gap-3 align-items-center">
                    <div class="text-center">
                        <div style="font-size: 34px; font-weight: 800; color: ${m.health_status === 'Critical' ? '#dc2626' : (m.health_status === 'Warning' ? '#c2410c' : '#0f172a')};">${m.health_score != null ? m.health_score : '—'}</div>
                        <div style="font-size: 11px; color: #64748b;">Health Score</div>
                    </div>
                    <div>${badge_html(m.health_status)}</div>
                </div>
            </div>

            <div class="row g-3 mb-4">
                <div class="col-md-3 col-sm-6">
                    <div class="mh-info-card" style="background: var(--card-bg,#fff);border:1px solid var(--border-color,#e2e8f0);border-radius:10px;padding:12px;">
                        <div style="font-size: 11px;color:#94a3b8;">Operating Status</div>
                        <div style="font-weight: 600; font-size: 14px; color: #1e293b;">${frappe.utils.escape_html(m.operating_status || '—')}</div>
                    </div>
                </div>
                <div class="col-md-3 col-sm-6">
                    <div class="mh-info-card" style="background: var(--card-bg,#fff);border:1px solid var(--border-color,#e2e8f0);border-radius:10px;padding:12px;">
                        <div style="font-size: 11px;color:#94a3b8;">Trend (7d)</div>
                        <div style="font-weight: 600; font-size: 14px; color: ${trend_color};">${trend_dir} ${trend.slope ? '(' + trend.slope + ')' : ''}</div>
                    </div>
                </div>
                <div class="col-md-3 col-sm-6">
                    <div class="mh-info-card" style="background: var(--card-bg,#fff);border:1px solid var(--border-color,#e2e8f0);border-radius:10px;padding:12px;">
                        <div style="font-size: 11px;color:#94a3b8;">Last Reading</div>
                        <div style="font-weight: 600; font-size: 14px; color: #1e293b;">${frappe.utils.escape_html(m.last_reading_date || 'No data')}</div>
                    </div>
                </div>
                <div class="col-md-3 col-sm-6">
                    <div class="mh-info-card" style="background: var(--card-bg,#fff);border:1px solid var(--border-color,#e2e8f0);border-radius:10px;padding:12px;">
                        <div style="font-size: 11px;color:#94a3b8;">Location</div>
                        <div style="font-weight: 600; font-size: 14px; color: #1e293b;">${frappe.utils.escape_html(m.location || '—')}</div>
                    </div>
                </div>
            </div>

            <div class="row g-3 mb-4">
                <div class="col-lg-8">
                    <div class="card" style="border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px;">
                        <div class="card-header d-flex justify-content-between align-items-center" style="background: var(--card-bg,#fff); border-bottom: 1px solid var(--border-color,#e2e8f0); border-radius: 12px 12px 0 0;">
                            <span style="font-weight: 600; font-size: 14px;">Reading History</span>
                            <span style="font-size: 12px; color: #64748b;">${history.length} records</span>
                        </div>
                        <div class="card-body" style="max-height: 320px; overflow: auto; padding: 8px 14px;">
                            <table class="table table-sm mb-0" style="font-size: 13px;">
                                <thead><tr><th style="font-size: 11px;color:#94a3b8;">Date</th><th style="font-size: 11px;color:#94a3b8;">Score</th><th style="font-size: 11px;color:#94a3b8;">Status</th></tr></thead>
                                <tbody>${hist_rows}</tbody>
                            </table>
                        </div>
                    </div>

                    <div class="card mt-3" style="border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px;">
                        <div class="card-header" style="background: var(--card-bg,#fff); border-bottom: 1px solid var(--border-color,#e2e8f0); border-radius: 12px 12px 0 0;">
                            <span style="font-weight: 600; font-size: 14px;">📈 Health Prediction</span>
                        </div>
                        <div class="card-body" style="padding: 12px 16px;">${pred_html}</div>
                    </div>

                    <div class="card mt-3" style="border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px;">
                        <div class="card-header d-flex justify-content-between align-items-center" style="background: var(--card-bg,#fff); border-bottom: 1px solid var(--border-color,#e2e8f0); border-radius: 12px 12px 0 0;">
                            <span style="font-weight: 600; font-size: 14px;">🔗 Linked KPIs</span>
                            ${can_write ? `<button class="btn btn-xs btn-primary btn-add-kpi">+ Add KPI</button>` : ''}
                        </div>
                        <div class="card-body" style="padding: 8px 16px;">${kpi_rows}</div>
                    </div>
                </div>

                <div class="col-lg-4">
                    <div class="card" style="border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px;">
                        <div class="card-header" style="background: var(--card-bg,#fff); border-bottom: 1px solid var(--border-color,#e2e8f0); border-radius: 12px 12px 0 0;">
                            <span style="font-weight: 600; font-size: 14px;">⚙️ Machine Parameters</span>
                        </div>
                        <div class="card-body" style="padding: 12px 16px;">
                            <div class="d-flex flex-wrap gap-2">${param_header}</div>
                            ${can_write ? `<button class="btn btn-success btn-sm w-100 mt-3 btn-record-reading">📝 Record New Reading</button>` : ''}
                        </div>
                    </div>

                    <div class="card mt-3" style="border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px;">
                        <div class="card-header" style="background: var(--card-bg,#fff); border-bottom: 1px solid var(--border-color,#e2e8f0); border-radius: 12px 12px 0 0;">
                            <span style="font-weight: 600; font-size: 14px;">🚨 Alerts</span>
                        </div>
                        <div class="card-body" style="padding: 4px 16px; max-height: 300px; overflow: auto;">${alert_rows}</div>
                    </div>
                </div>
            </div>
        </div>
    `);

    const $wrap = page.main;
    $wrap.find('.btn-back-home').on('click', () => back_home(page));
    $wrap.find('.btn-add-kpi').on('click', () => open_add_kpi_modal(page, m.name));
    $wrap.find('.btn-remove-kpi').on('click', function() {
        const kpi = $(this).data('kpi');
        remove_kpi(page, m.name, kpi);
    });
    $wrap.find('.btn-record-reading').on('click', () => open_reading_modal(page, detail));
}

function back_home(page) {
    page._view = 'home';
    page._detail_machine = null;
    page.clear_actions();
    frappe.set_route('machine-health');
    render_home(page);
}

// ---------------------------------------------------------------------------
// READING MODAL
// ---------------------------------------------------------------------------
function open_reading_modal(page, detail) {
    const m = detail.machine || {};
    const params = detail.parameters || [];
    if (!params.length) {
        frappe.msgprint({ title: __('No Parameters'), message: __('This machine type has no parameters configured to record.') });
        return;
    }

    let formHtml = `
        <div class="form-group">
            <label>Reading Date</label>
            <input type="date" class="form-control reading-date" value="${frappe.datetime.get_today()}">
        </div>
    `;
    params.forEach(p => {
        formHtml += `
            <div class="form-group">
                <label>${frappe.utils.escape_html(p.parameter_name || p.parameter_code)} ${p.unit ? '(' + frappe.utils.escape_html(p.unit) + ')' : ''} ${p.is_required ? '<span class="text-danger">*</span>' : ''}</label>
                <input type="number" step="any" class="form-control reading-param" data-code="${frappe.utils.escape_html(p.parameter_code)}" data-name="${frappe.utils.escape_html(p.parameter_name || '')}" data-cat="${frappe.utils.escape_html(p.parameter_category || '')}" data-unit="${frappe.utils.escape_html(p.unit || '')}">
            </div>
        `;
    });
    formHtml += `
        <div class="form-group">
            <label>Notes</label>
            <textarea class="form-control reading-notes" rows="2"></textarea>
        </div>
    `;

    const d = new frappe.ui.Dialog({
        title: __('Record Reading — ' + (m.machine_name || '')),
        fields: [{ fieldtype: 'HTML', fieldname: 'body', options: formHtml }],
        primary_action_label: __('Submit Reading'),
        primary_action: function() {
            const dlg = this;
            const readings = [];
            dlg.$wrapper.find('.reading-param').each(function() {
                const $el = $(this);
                const val = $el.val();
                if (val !== '' && val != null) {
                    readings.push({
                        parameter_code: $el.data('code'),
                        parameter_name: $el.data('name') || $el.data('code'),
                        parameter_category: $el.data('cat') || '',
                        value: parseFloat(val),
                        unit: $el.data('unit') || '',
                    });
                }
            });
            const reading_date = dlg.$wrapper.find('.reading-date').val() || frappe.datetime.get_today();
            const notes = dlg.$wrapper.find('.reading-notes').val() || '';

            if (!readings.length) {
                frappe.msgprint(__('Enter at least one parameter value.'));
                return;
            }

            frappe.call({
                method: 'productix.kpi_tracking.api.machine.submit_machine_reading',
                args: { machine: m.name, reading_date: reading_date, readings: readings, notes: notes },
                freeze: true,
                freeze_message: __('Submitting reading...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({ message: __('Reading recorded — Health: ' + (r.message.health_status || '')), indicator: 'green' });
                        dlg.hide();
                        load_detail(page, m.name);
                    }
                },
                error: function(err) {
                    frappe.msgprint({ title: __('Submission Failed'), indicator: 'red', message: (err && err.message) || __('Could not submit reading.') });
                }
            });
        }
    });

    d.show();
}

// ---------------------------------------------------------------------------
// ADMIN: CREATE / ADD KPI
// ---------------------------------------------------------------------------
function open_create_machine_modal(page) {
    const html = `
        <div class="form-group"><label>Machine Name *</label><input class="form-control cm-name"></div>
        <div class="form-group"><label>Machine Code *</label><input class="form-control cm-code" placeholder="M-101"></div>
        <div class="form-group"><label>Department *</label><select class="form-control cm-dept"></select></div>
        <div class="form-group"><label>Machine Type *</label><select class="form-control cm-type"></select></div>
        <div class="form-group"><label>Operating Status</label><select class="form-control cm-op">
            <option>Operational</option><option>Idle</option><option>Under Maintenance</option><option>Decommissioned</option>
        </select></div>
        <div class="form-group"><label>Location</label><input class="form-control cm-location"></div>
        <div class="form-group"><label>Manufacturer</label><input class="form-control cm-manufacturer"></div>
        <div class="form-group"><label>Model</label><input class="form-control cm-model"></div>
        <div class="form-group"><label>Maintenance Frequency (Days)</label><input type="number" class="form-control cm-freq" value="90"></div>
        <div class="form-group"><label>Description</label><textarea class="form-control cm-desc" rows="2"></textarea></div>
    `;

    const d = new frappe.ui.Dialog({
        title: __('Create New Machine'),
        fields: [
            { fieldtype: 'HTML', fieldname: 'body', options: html }
        ],
        primary_action_label: __('Create Machine'),
        primary_action: function() {
            const dlg = this;
            const name = dlg.$wrapper.find('.cm-name').val();
            const code = dlg.$wrapper.find('.cm-code').val();
            const dept = dlg.$wrapper.find('.cm-dept').val();
            const mtype = dlg.$wrapper.find('.cm-type').val();
            if (!name || !code || !dept || !mtype) {
                frappe.msgprint(__('Name, Code, Department and Machine Type are required.'));
                return;
            }
            frappe.call({
                method: 'productix.kpi_tracking.api.machine.create_machine',
                args: {
                    machine_name: name,
                    machine_code: code,
                    machine_type: mtype,
                    department: dept,
                    operating_status: dlg.$wrapper.find('.cm-op').val(),
                    location: dlg.$wrapper.find('.cm-location').val() || null,
                    manufacturer: dlg.$wrapper.find('.cm-manufacturer').val() || null,
                    model_name: dlg.$wrapper.find('.cm-model').val() || null,
                    description: dlg.$wrapper.find('.cm-desc').val() || null,
                    maintenance_frequency_days: dlg.$wrapper.find('.cm-freq').val() || 90,
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({ message: __(r.message.message), indicator: 'green' });
                        dlg.hide();
                        render_home(page);
                    }
                },
                error: function(err) {
                    frappe.msgprint({ title: __('Create Failed'), indicator: 'red', message: (err && err.message) || __('Could not create machine.') });
                }
            });
        }
    });

    // Populate departments + machine types
    const deptOpts = (page._ctx.department_list || []).map(d => `<option value="${frappe.utils.escape_html(d.name)}">${frappe.utils.escape_html(d.display_name || d.department_name)}</option>`).join('');
    d.$wrapper.find('.cm-dept').html(deptOpts || '<option value="">No departments found</option>');

    frappe.call({
        method: 'productix.kpi_tracking.api.machine.get_machine_types',
        callback: function(r) {
            const types = (r.message || []).map(t => `<option value="${frappe.utils.escape_html(t.name)}">${frappe.utils.escape_html(t.type_name || t.name)}</option>`).join('');
            d.$wrapper.find('.cm-type').html(types || '<option value="">No machine types found</option>');
        }
    });

    d.show();
}

function open_add_kpi_modal(page, machine_name) {
    const html = `
        <div class="form-group"><label>Select KPI</label><select class="form-control add-kpi-select"></select></div>
    `;
    const d = new frappe.ui.Dialog({
        title: __('Add KPI to Machine'),
        fields: [{ fieldtype: 'HTML', fieldname: 'body', options: html }],
        primary_action_label: __('Add KPI'),
        primary_action: function() {
            const dlg = this;
            const kpi = dlg.$wrapper.find('.add-kpi-select').val();
            if (!kpi) {
                frappe.msgprint(__('Select a KPI.'));
                return;
            }
            frappe.call({
                method: 'productix.kpi_tracking.api.machine.add_machine_kpi',
                args: { machine: machine_name, kpi: kpi },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({ message: __(r.message.message), indicator: 'green' });
                        dlg.hide();
                        load_detail(page, machine_name);
                    }
                },
                error: function(err) {
                    frappe.msgprint({ title: __('Link Failed'), indicator: 'red', message: (err && err.message) || __('Could not link KPI.') });
                }
            });
        }
    });

    frappe.call({
        method: 'productix.kpi_tracking.api.dashboard.get_kpi_options',
        callback: function(r) {
            const rows = (r.message && r.message.kpis) || [];
            let opts = '';
            rows.forEach(k => {
                opts += `<option value="${frappe.utils.escape_html(k.name)}">${frappe.utils.escape_html(k.kpi_name || k.name)}</option>`;
            });
            d.$wrapper.find('.add-kpi-select').html(opts || '<option value="">No KPIs available</option>');
        }
    });

    d.show();
}

function remove_kpi(page, machine_name, kpi) {
    frappe.confirm(__('Remove this KPI from the machine?'), function() {
        frappe.call({
            method: 'productix.kpi_tracking.api.machine.remove_machine_kpi',
            args: { machine: machine_name, kpi: kpi },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: __(r.message.message), indicator: 'green' });
                    load_detail(page, machine_name);
                }
            }
        });
    });
}
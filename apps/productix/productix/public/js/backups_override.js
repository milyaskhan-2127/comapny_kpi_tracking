frappe.pages['backups'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Backup & Restore Manager'),
		single_column: true,
	});

	page.set_primary_action(__('Download Backup'), function() {
		show_download_dialog();
	}, 'download');

	page.set_secondary_action(__('Upload Backup'), function() {
		show_upload_dialog();
	});

	page.add_inner_button(__('Refresh'), function() {
		load_backups_list(page);
	});

	frappe.breadcrumbs.add('Setup');

	var container = $('<div class="productix-backup-wrapper" style="padding: 15px 0;"></div>').appendTo(page.body.addClass('no-border'));
	page.backup_container = container;

	load_backups_list(page);

	function show_download_dialog() {
		var d = new frappe.ui.Dialog({
			title: __('Download Immediate Backup'),
			fields: [
				{
					label: __('Backup Type'),
					fieldname: 'backup_type',
					fieldtype: 'Select',
					options: [
						{ label: 'Database Backup Only (.sql.gz)', value: 'db' },
						{ label: 'Full System Backup (Database + Files)', value: 'all' }
					],
					default: 'db',
					reqd: 1
				}
			],
			primary_action_label: __('Generate & Download Now'),
			primary_action: function(values) {
				d.hide();
				frappe.show_alert({ message: __('Generating backup... Please wait'), indicator: 'blue' });
				frappe.call({
					method: 'productix.api.backup.take_immediate_backup',
					args: {
						backup_type: values.backup_type,
						with_files: (values.backup_type === 'all')
					},
					freeze: true,
					freeze_message: __('Creating backup and preparing download...'),
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({ message: __(r.message.message), indicator: 'green' });
							if (r.message.main_download_url) {
								var link = document.createElement('a');
								link.href = r.message.main_download_url;
								link.setAttribute('download', '');
								document.body.appendChild(link);
								link.click();
								document.body.removeChild(link);
							}
							load_backups_list(page);
						} else {
							frappe.msgprint({
								title: __('Backup Notice'),
								indicator: 'red',
								message: (r.message ? r.message.message : __('Failed to create backup.'))
							});
						}
					}
				});
			}
		});
		d.show();
	}

	function show_upload_dialog() {
		var d = new frappe.ui.Dialog({
			title: __('Upload Backup File to Server'),
			fields: [
				{
					label: __('Select Backup File'),
					fieldname: 'backup_file',
					fieldtype: 'Attach',
					description: __('Supported formats: .sql, .sql.gz, .tar, .json, .zip'),
					reqd: 1
				}
			],
			primary_action_label: __('Upload to Server'),
			primary_action: function(values) {
				if (!values.backup_file) {
					frappe.msgprint(__('Please attach a backup file.'));
					return;
				}
				d.hide();
				frappe.show_alert({ message: __('Processing uploaded backup...'), indicator: 'blue' });
				load_backups_list(page);
			}
		});
		d.show();
	}

	function load_backups_list(page) {
		page.backup_container.html('<div style="text-align: center; padding: 40px; color: #64748b;"><div class="spinner-border spinner-border-sm text-primary"></div><span class="ms-2">Loading backups...</span></div>');
		frappe.call({
			method: 'productix.api.backup.get_backups_list',
			callback: function(r) {
				if (r.message && r.message.success) {
					render_backups_ui(page, r.message);
				} else {
					page.backup_container.html('<div class="alert alert-warning">Could not load backups list.</div>');
				}
			}
		});
	}

	function render_backups_ui(page, data) {
		var backups = data.backups || [];
		var html = `
			<div class="row g-3 mb-4">
				<div class="col-md-4 col-sm-6">
					<div style="background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px; padding: 16px;">
						<div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b;">Total Backups</div>
						<div style="font-size: 24px; font-weight: 700; color: #0f172a; margin-top: 4px;">${data.total_count || 0}</div>
						<div style="font-size: 12px; color: #10b981; margin-top: 2px;">Available on server</div>
					</div>
				</div>
				<div class="col-md-4 col-sm-6">
					<div style="background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px; padding: 16px;">
						<div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b;">Total Storage</div>
						<div style="font-size: 24px; font-weight: 700; color: #2563eb; margin-top: 4px;">${data.total_size_formatted || '0 B'}</div>
						<div style="font-size: 12px; color: #64748b; margin-top: 2px;">Private backup storage</div>
					</div>
				</div>
				<div class="col-md-4 col-sm-12">
					<div style="background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px; padding: 16px;">
						<div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b;">Latest Backup</div>
						<div style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 8px;">${data.latest_backup || 'None'}</div>
						<div style="font-size: 12px; color: #059669; margin-top: 2px;">Server timestamp</div>
					</div>
				</div>
			</div>

			<!-- Direct 2 Actions Toolbar & Upload Section -->
			<div class="card mb-4" style="border: 2px dashed #cbd5e1; background: #f8fafc; border-radius: 8px;">
				<div class="card-body text-center" style="padding: 24px;">
					<h5 style="font-weight: 600; margin-bottom: 6px;">Upload Backup File (.sql, .sql.gz, .tar, .json, .zip)</h5>
					<p class="text-muted" style="font-size: 13px; margin-bottom: 16px;">Select a backup file from your local machine to upload directly to the server.</p>
					<div class="d-flex justify-content-center align-items-center gap-2 flex-wrap">
						<input type="file" id="direct-upload-input" class="form-control form-control-sm" style="max-width: 340px;" accept=".sql.gz,.sql,.tar,.gz,.json,.zip,.tar.gz" />
						<button class="btn btn-primary btn-sm btn-do-upload" style="display: inline-flex; align-items: center; gap: 4px; font-weight: 600;">
							<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
							Upload to Server
						</button>
					</div>
					<div id="upload-status-box" style="display: none; margin-top: 12px;">
						<div class="progress" style="height: 6px; max-width: 320px; margin: 0 auto;">
							<div class="progress-bar progress-bar-striped progress-bar-animated" style="width: 100%;"></div>
						</div>
						<small class="text-muted mt-1 d-block">Uploading backup file...</small>
					</div>
				</div>
			</div>

			<!-- Backups Table -->
			<div class="card" style="border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px; overflow: hidden;">
				<div class="card-header bg-white d-flex justify-content-between align-items-center" style="padding: 12px 20px; border-bottom: 1px solid var(--border-color, #e2e8f0);">
					<span style="font-weight: 600;">Available Server Backups</span>
					<span class="badge bg-light text-dark">${backups.length} Files</span>
				</div>
				<div class="table-responsive">
					<table class="table table-hover mb-0" style="font-size: 13px; vertical-align: middle;">
						<thead style="background: #f8fafc;">
							<tr>
								<th style="padding: 12px 20px;">File Name</th>
								<th style="padding: 12px 16px; width: 170px;">Type</th>
								<th style="padding: 12px 16px; width: 120px;">Size</th>
								<th style="padding: 12px 16px; width: 170px;">Created Date</th>
								<th style="padding: 12px 20px; width: 230px; text-align: right;">1-Click Actions</th>
							</tr>
						</thead>
						<tbody>
							${backups.length === 0 ? '<tr><td colspan="5" class="text-center text-muted p-4">No backups found. Click "Download Backup" above to generate one.</td></tr>' : ''}
							${backups.map(function(b) {
								var is_restorable = b.filename.endsWith('.sql') || b.filename.endsWith('.sql.gz') || b.filename.endsWith('.json');
								return `
									<tr>
										<td style="padding: 12px 20px; font-weight: 500; font-family: monospace;">
											📄 ${frappe.utils.escape_html(b.filename)}
										</td>
										<td style="padding: 12px 16px;">
											<span class="badge bg-light text-primary border" style="font-size: 11px;">${b.type_label}</span>
										</td>
										<td style="padding: 12px 16px; font-weight: 600;">${b.size_formatted}</td>
										<td style="padding: 12px 16px; color: #64748b;">${b.created_at}</td>
										<td style="padding: 12px 20px; text-align: right;">
											<a href="${b.download_url}" target="_blank" download="${frappe.utils.escape_html(b.filename)}" class="btn btn-default btn-xs" style="color: #2563eb; margin-right: 4px;" title="Download to PC">
												⬇️ Download
											</a>
											${is_restorable ? `
											<button class="btn btn-default btn-xs btn-restore-backup" data-filename="${frappe.utils.escape_html(b.filename)}" style="color: #059669; font-weight: 600; margin-right: 4px;" title="Restore data to database">
												🔄 Restore
											</button>
											` : ''}
											<button class="btn btn-default btn-xs btn-del-backup" data-filename="${frappe.utils.escape_html(b.filename)}" style="color: #dc2626;" title="Delete backup file">
												🗑️ Delete
											</button>
										</td>
									</tr>
								`;
							}).join('')}
						</tbody>
					</table>
				</div>
			</div>
		`;

		page.backup_container.html(html);

		// Bind upload button
		page.backup_container.find('.btn-do-upload').on('click', function() {
			var fileInput = page.backup_container.find('#direct-upload-input')[0];
			if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
				frappe.msgprint(__('Please select a backup file to upload.'));
				return;
			}
			var file = fileInput.files[0];
			var formData = new FormData();
			formData.append('file', file);
			formData.append('cmd', 'productix.api.backup.upload_backup_file');

			page.backup_container.find('#upload-status-box').show();

			var xhr = new XMLHttpRequest();
			xhr.open('POST', '/api/method/productix.api.backup.upload_backup_file', true);
			xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);

			xhr.onload = function() {
				page.backup_container.find('#upload-status-box').hide();
				if (xhr.status === 200) {
					frappe.show_alert({ message: __('Backup uploaded successfully!'), indicator: 'green' });
					load_backups_list(page);
				} else {
					frappe.msgprint({ title: __('Upload Error'), indicator: 'red', message: 'Failed to upload backup file.' });
				}
			};
			xhr.onerror = function() {
				page.backup_container.find('#upload-status-box').hide();
				frappe.msgprint({ title: __('Network Error'), indicator: 'red', message: 'Error uploading file.' });
			};
			xhr.send(formData);
		});

		// Bind restore buttons
		page.backup_container.find('.btn-restore-backup').on('click', function() {
			var fn = $(this).data('filename');
			frappe.confirm(__('Are you sure you want to restore and import data from backup <b>' + fn + '</b> into the database?'), function() {
				frappe.call({
					method: 'productix.api.backup.restore_backup_file',
					args: { filename: fn },
					freeze: true,
					freeze_message: __('Restoring backup records into database...'),
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.msgprint({
								title: __('Restore Successful'),
								indicator: 'green',
								message: __(r.message.message)
							});
							load_backups_list(page);
						}
					}
				});
			});
		});

		// Bind delete buttons
		page.backup_container.find('.btn-del-backup').on('click', function() {
			var fn = $(this).data('filename');
			frappe.confirm(__('Are you sure you want to delete backup <b>' + fn + '</b>?'), function() {
				frappe.call({
					method: 'productix.api.backup.delete_backup_file',
					args: { filename: fn },
					freeze: true,
					freeze_message: __('Deleting backup...'),
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({ message: __(r.message.message), indicator: 'green' });
							load_backups_list(page);
						}
					}
				});
			});
		});
	}
};

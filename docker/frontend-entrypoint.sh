#!/bin/sh
# Productix ERP — frontend container entrypoint.
# Renders the parametrized nginx template (no hard-coded site names) and
# starts nginx. sed is guaranteed in the frappe image base.
set -e

TEMPLATE=/etc/nginx/conf.d/frappe.conf.template
CONF=/etc/nginx/conf.d/frappe.conf
SITE_NAME="${NGINX_SITE_NAME:-${FRAPPE_SITE_NAME_HEADER:-productix.local}}"

if [ -f "$TEMPLATE" ]; then
    sed "s/__SITE_NAME__/${SITE_NAME}/g" "$TEMPLATE" > "$CONF"
fi

exec nginx -g 'daemon off;'
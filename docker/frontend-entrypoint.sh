#!/bin/sh
# ============================================================================
# Productix ERP - frontend container entrypoint
#
# Renders the parametrized nginx template (no hard-coded site names) and
# starts nginx. POSIX sh only: compose runs this with `sh`, and compose also
# strips CR before exec so a Windows checkout cannot break it either.
# ============================================================================
set -eu

TEMPLATE=/etc/nginx/conf.d/frappe.conf.template
CONF=/etc/nginx/conf.d/frappe.conf
SITE_NAME="${NGINX_SITE_NAME:-${FRAPPE_SITE_NAME_HEADER:-productix.local}}"

if [ ! -f "$TEMPLATE" ]; then
    echo "[frontend] ERROR: nginx template $TEMPLATE is missing (docker-compose.yml mount)." >&2
    exit 1
fi

# shellcheck disable=SC2016
sed "s/__SITE_NAME__/${SITE_NAME}/g" "$TEMPLATE" > "$CONF"

echo "[frontend] starting nginx (site=$SITE_NAME)"
exec nginx -g 'daemon off;'

#!/bin/sh
# Sanctioned pre-retirement DB backup. Runs INSIDE the mariadb container via:
#   Get-Content scripts/backup_retirement.sh -Raw | docker compose exec -T -u root mariadb sh -s
# Reads the root password from the container env (no secret stored in this file).
# Creates gzip dumps of the two legacy-referencing sites' databases under
# /var/lib/mysql-files/ and verifies each with gunzip -t.
set -e
TS=$(date +%Y%m%d_%H%M%S)
D=/var/lib/mysql-files
mkdir -p "$D"
: "${MARIADB_ROOT_PASSWORD:=${MYSQL_ROOT_PASSWORD:?no root password env in container}}"

mysqldump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction --routines --triggers _5a5cc2442a2840be 2>/tmp/dump_err.log \
  | gzip > "$D/productix_local_pretirement_$TS.sql.gz"
gunzip -t "$D/productix_local_pretirement_$TS.sql.gz" && echo "LOCAL_GZIP_OK $TS"

mysqldump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction --routines --triggers _650d82d1cc877d44 2>>/tmp/dump_err.log \
  | gzip > "$D/productix_ref_pretirement_$TS.sql.gz"
gunzip -t "$D/productix_ref_pretirement_$TS.gz" 2>/dev/null || gunzip -t "$D/productix_ref_pretirement_$TS.sql.gz" && echo "REF_GZIP_OK $TS"

# adopt the earlier truncated-but-valid dump (PS arg-splitting artifact) under a clear name
if [ -f "$D/backup_pretirement_local_" ]; then
  mv -f "$D/backup_pretirement_local_" "$D/productix_local_pretirement_earlier_manual.sql.gz" 2>/dev/null || true
fi
ls -la "$D"
echo "---dump stderr---"
cat /tmp/dump_err.log 2>/dev/null || true

# Rollback

Git is the rollback safety net. The legacy monolithic `productix` app is
committed as a clean baseline on `main` (`456bcd7`); all modular app work is
uncommitted/untracked on top. The repository is **never pushed**, so every
state is recoverable locally.

## 1. Before you start migrating

- Take a DB + files backup: `./backup.sh`.
- Record the exact site name and installed-apps list
  (`bench --site <site> execute frappe.utils.change_log.get_versions`).

## 2. Rollback during a fresh deployment

Nothing destructive has happened — remove the site and recreate:

```bash
bench --site <site> drop-site --root-password '<root>' --force
# or for the Docker stack:
docker compose down -v   # destroys db-data volume — only if you have no data to keep
```

Then re-run setup with the wanted `PRODUCTIX_APPS`.

## 3. Rollback after `install-app` on an existing DB (pre-migrate)

If you installed new apps but **have not** run `bench migrate` yet:

```bash
bench --site <site> uninstall-app productix_recipe   # repeat per new app
bench --site <site> clear-cache
```

No ownership patch has run, so Module Def rows are untouched and the old app
keeps working. Verify with `env/bin/python scripts/migration_check.py <site>` (from the bench root).

## 4. Rollback after `migrate` (ownership patch ran)

The patch only flips `tabModule Def.app` values and preserves legacy rows.
To reverse:

1. Restore the pre-migration DB backup (migration_point backup):
   `bench --site <site> restore --with-public-files --with-private-files <pre-migrate-dump.gz>`
2. Optionally uninstall the new apps and reinstall the old `productix` app
   from the committed baseline folder.
3. `bench --site <site> migrate && bench --site <site> clear-cache`.

## 5. Rollback after retiring the old app

The old app code remains in the repo at `apps/productix` (baseline commit).
To go back to the monolith:

1. Re-add `productix` to `apps.txt` / `apps.json`.
2. `bench --site <site> install-app productix --force` (tables already exist).
3. Manually flip any Module Def rows the ownership patch re-pointed back to
   `productix` (or restore from the dump — simplest).
4. Migrate + verify business flows.

## 6. Feature-module removal without rollback

Removing a module from the install set is supported and isolated:

- Uninstall the app (`bench --site <site> uninstall-app productix_kpi`).
- Remaining apps' hooks/workers must not error (`tests/README.md` §3);
- Re-adding later is a plain `install-app` (idempotent).

## 7. RTO/RPO notes

- Backups: site files + DB dumps land in `./backups/` (git-ignored).
- Keep the pre-migration dump until the post-retirement smoke run is green.
- Rehearse rollback on a staging clone **before** touching production.
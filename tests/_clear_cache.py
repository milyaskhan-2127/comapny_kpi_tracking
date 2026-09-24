# Clear the site's frappe cache (incl. the app->modules map) — piped into
# `bench --site <site> console` by tests/_clear_cache.sh.
frappe.clear_cache()
print("CACHE_CLEARED")

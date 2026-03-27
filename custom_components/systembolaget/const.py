"""Constants for Systembolaget integration."""

DOMAIN = "systembolaget"

# API (uses same key as the website's Next.js frontend — no registration needed)
API_BASE = "https://api-extern.systembolaget.se"
SITE_BASE = "https://www.systembolaget.se"
_FALLBACK_KEY = "cfc702aed3094c86b92d6d4ff7a54c84"

CONF_STORE_ID = "store_id"
CONF_WATCHED_PRODUCTS = "watched_products"
CONF_CATEGORIES = "categories"
CONF_POLL_INTERVAL = "poll_interval"

DEFAULT_CATEGORIES = "Vin,Öl,Sprit"
DEFAULT_POLL_INTERVAL = 3600
DEFAULT_WATCHED_PRODUCTS = ""
NEW_ARRIVALS_LIMIT = 40

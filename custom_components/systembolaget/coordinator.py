"""Systembolaget coordinator — uses the same JSON API as systembolaget.se."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, API_BASE, SITE_BASE, _FALLBACK_KEY,
    CONF_STORE_ID, CONF_WATCHED_PRODUCTS,
    CONF_CATEGORIES, CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL, DEFAULT_CATEGORIES, NEW_ARRIVALS_LIMIT,
)

_LOGGER = logging.getLogger(__name__)
_TZ = ZoneInfo("Europe/Stockholm")
_KEY_RE = re.compile(r'NEXT_PUBLIC_API_KEY_APIM["\s:]+([a-f0-9]{32})')
_SCRIPT_RE = re.compile(r'/_next/static/chunks/pages/_app[^"\']+\.js')

_BASE_HEADERS = {
    "Origin": SITE_BASE,
    "Referer": f"{SITE_BASE}/",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant-Systembolaget/1.0)",
}


class SystembolagetCoordinator(DataUpdateCoordinator):
    """Fetches and caches Systembolaget data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = int(
            entry.options.get(CONF_POLL_INTERVAL)
            or entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=interval))
        self.entry = entry
        self._api_key: str = _FALLBACK_KEY
        self._key_fetched: datetime | None = None  # refresh key every 24h

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _cfg(self, key: str, default="") -> str:
        return self.entry.options.get(key) or self.entry.data.get(key, default)

    def _watched_ids(self) -> list[str]:
        raw = self._cfg(CONF_WATCHED_PRODUCTS)
        return [p.strip() for p in raw.split(",") if p.strip()]

    def _categories(self) -> list[str]:
        raw = self._cfg(CONF_CATEGORIES, DEFAULT_CATEGORIES)
        return [c.strip() for c in raw.split(",") if c.strip()]

    async def _ensure_api_key(self, http: aiohttp.ClientSession) -> None:
        """Extract the frontend API key from the Next.js bundle (cached 24h)."""
        now = datetime.now(_TZ)
        if self._key_fetched and (now - self._key_fetched) < timedelta(hours=24):
            return

        try:
            async with http.get(SITE_BASE, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                html = await resp.text()

            # Find _app JS chunk
            m = _SCRIPT_RE.search(html)
            if not m:
                raise ValueError("_app script not found in HTML")

            js_url = f"{SITE_BASE}{m.group(0)}"
            async with http.get(js_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    raise ValueError(f"_app JS HTTP {resp.status}")
                js = await resp.text()

            km = _KEY_RE.search(js)
            if not km:
                raise ValueError("API key not found in JS bundle")

            self._api_key = km.group(1)
            self._key_fetched = now
            _LOGGER.debug("[Systembolaget] API key refreshed from bundle")

        except Exception as exc:
            _LOGGER.warning(
                "[Systembolaget] Could not extract API key (%s) — using fallback", exc
            )
            self._api_key = _FALLBACK_KEY
            self._key_fetched = now  # don't retry for 24h

    def _headers(self) -> dict:
        return {**_BASE_HEADERS, "Ocp-Apim-Subscription-Key": self._api_key}

    # ── Main update ───────────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict:
        try:
            return await self._fetch()
        except UpdateFailed:
            raise
        except Exception as exc:
            raise UpdateFailed(f"Systembolaget: {exc}") from exc

    async def _fetch(self) -> dict:
        store_id = self._cfg(CONF_STORE_ID)
        watched_ids = self._watched_ids()
        categories = self._categories()

        async with aiohttp.ClientSession() as http:
            await self._ensure_api_key(http)

            store = await self._fetch_store(http, store_id) if store_id else {}
            new_arrivals = await self._fetch_new_arrivals(http, categories)

            products: dict[str, dict] = {}
            for pid in watched_ids:
                try:
                    products[pid] = await self._fetch_product(http, pid, store_id)
                except Exception as exc:
                    _LOGGER.warning("Failed to fetch product %s: %s", pid, exc)
                    products[pid] = {"error": str(exc), "product_id": pid}

        return {"store": store, "new_arrivals": new_arrivals, "products": products}

    # ── Store ────────────────────────────────────────────────────────────────

    async def _fetch_store(self, http: aiohttp.ClientSession, store_id: str) -> dict:
        # Try the V2 Store detail endpoint first — returns full opening hours
        detail = await self._fetch_store_v2(http, store_id)
        if detail:
            return detail

        # Fallback: sitesearch (may lack openingHours)
        url = f"{API_BASE}/sb-api-ecommerce/v1/sitesearch/site"
        params = {"q": store_id, "includePredictions": "false"}
        async with http.get(
            url, params=params, headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning("[Systembolaget] Store lookup HTTP %s", resp.status)
                return {}
            data = await resp.json(content_type=None)

        stores = data.get("siteSearchResults", [])
        store = next(
            (s for s in stores if str(s.get("siteId", "")) == str(store_id)), None
        ) or (stores[0] if stores else {})
        return self._parse_store(store)

    async def _fetch_store_v2(self, http: aiohttp.ClientSession, store_id: str) -> dict:
        """Fetch full store details including opening hours from V2 endpoint."""
        url = f"{API_BASE}/site/V2/Store/{store_id}"
        try:
            async with http.get(
                url, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json(content_type=None)
            return self._parse_store(data)
        except Exception as exc:
            _LOGGER.debug("[Systembolaget] V2 store detail failed: %s", exc)
            return {}

    def _parse_store(self, s: dict) -> dict:
        now = datetime.now(_TZ)
        today_str = now.strftime("%Y-%m-%d")
        today_hours = "–"

        # openingHours can appear under different keys depending on endpoint
        hours_list = (
            s.get("openingHours")
            or s.get("StoreOpeningHours")
            or s.get("storeOpeningHours")
            or []
        )
        for h in hours_list:
            # V2 uses "Date", sitesearch uses "date"
            date_val = h.get("date") or h.get("Date") or ""
            if date_val.startswith(today_str):
                open_from = ":".join((h.get("openFrom") or h.get("OpenFrom") or "").split(":")[:2])
                open_to = ":".join((h.get("openTo") or h.get("OpenTo") or "").split(":")[:2])
                today_hours = f"{open_from}–{open_to}" if open_from and open_to else "Stängt"
                break

        # is_open: prefer time-based calculation (API value is often stale/cached)
        if today_hours not in ("–", "Stängt"):
            try:
                tf = dtime(*[int(x) for x in today_hours.split("–")[0].split(":")])
                tt = dtime(*[int(x) for x in today_hours.split("–")[1].split(":")])
                is_open = tf <= now.time() < tt
            except Exception:
                is_open = False
        else:
            is_open = False

        pos = s.get("position") or s.get("Position") or {}
        return {
            "store_id": str(s.get("siteId") or s.get("SiteId") or ""),
            "name": s.get("displayName") or s.get("name") or s.get("Name") or "",
            "address": s.get("streetAddress") or s.get("address") or s.get("Address") or "",
            "city": s.get("city") or s.get("City") or "",
            "postal_code": s.get("postalCode") or s.get("PostalCode") or "",
            "is_open": is_open,
            "today_hours": today_hours,
            "latitude": pos.get("latitude") or pos.get("Latitude"),
            "longitude": pos.get("longitude") or pos.get("Longitude"),
        }

    # ── New arrivals ─────────────────────────────────────────────────────────

    async def _fetch_new_arrivals(
        self, http: aiohttp.ClientSession, categories: list[str]
    ) -> list[dict]:
        # Fetch each category independently, then interleave so every category
        # is represented equally in the final list.
        per_cat = max(8, NEW_ARRIVALS_LIMIT // max(len(categories), 1) + 4)
        cats = categories[:4]
        buckets: list[list[dict]] = []

        for cat in cats:
            params = {
                "size": str(per_cat),
                "page": "1",
                "sortBy": "ProductLaunchDate",
                "sortDirection": "Descending",
                "categoryLevel1": cat,
            }
            try:
                async with http.get(
                    f"{API_BASE}/sb-api-ecommerce/v1/productsearch/search",
                    params=params,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.debug("[Systembolaget] New arrivals %s: HTTP %s", cat, resp.status)
                        buckets.append([])
                        continue
                    data = await resp.json(content_type=None)
                buckets.append([self._parse_product(p) for p in data.get("products", [])])
            except Exception as exc:
                _LOGGER.warning("[Systembolaget] New arrivals error for %s: %s", cat, exc)
                buckets.append([])

        # Round-robin interleave: take one from each bucket in turn
        seen: set[str] = set()
        unique: list[dict] = []
        max_len = max((len(b) for b in buckets), default=0)
        for i in range(max_len):
            for bucket in buckets:
                if i < len(bucket):
                    p = bucket[i]
                    pid = p["product_id"]
                    if pid and pid not in seen:
                        seen.add(pid)
                        unique.append(p)

        return unique[:NEW_ARRIVALS_LIMIT]

    # ── Watched product ───────────────────────────────────────────────────────

    async def _fetch_product(
        self, http: aiohttp.ClientSession, product_id: str, store_id: str
    ) -> dict:
        # Global lookup
        params = {"size": "1", "page": "1", "textQuery": product_id}
        async with http.get(
            f"{API_BASE}/sb-api-ecommerce/v1/productsearch/search",
            params=params,
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"HTTP {resp.status}")
            data = await resp.json(content_type=None)

        products = data.get("products", [])
        # Find exact match on productId or productNumber
        match = next(
            (p for p in products if str(p.get("productId", "")) == product_id
             or str(p.get("productNumber", "")) == product_id
             or str(p.get("productNumberShort", "")) == product_id),
            products[0] if products else None,
        )
        if not match:
            raise UpdateFailed(f"Produkt {product_id} hittades inte")

        result = self._parse_product(match)

        # Check store assortment if store configured
        if store_id:
            store_params = {
                "size": "1", "page": "1",
                "textQuery": product_id,
                "storeId": store_id,
                "isInStoreAssortmentSearch": "true",
            }
            try:
                async with http.get(
                    f"{API_BASE}/sb-api-ecommerce/v1/productsearch/search",
                    params=store_params,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        sdata = await resp.json(content_type=None)
                        sproducts = sdata.get("products", [])
                        in_store = any(
                            str(p.get("productId", "")) == result["product_id"]
                            or str(p.get("productNumber", "")) == product_id
                            for p in sproducts
                        )
                        result["in_store_assortment"] = in_store
            except Exception as exc:
                _LOGGER.debug("[Systembolaget] Store assortment check failed: %s", exc)

        return result

    def _parse_product(self, p: dict) -> dict:
        product_id = str(p.get("productId") or p.get("productNumber") or "")
        bold = p.get("productNameBold") or ""
        thin = p.get("productNameThin") or ""
        name = f"{bold} {thin}".strip() if thin else bold
        price = p.get("price") or 0.0

        return {
            "product_id": product_id,
            "product_number": str(p.get("productNumber") or ""),
            "name": name,
            "price": round(float(price), 2),
            "category": p.get("categoryLevel1") or "",
            "subcategory": p.get("categoryLevel2") or "",
            "alcohol_pct": float(p.get("alcoholPercentage") or 0.0),
            "volume_ml": int(p.get("volume") or 0),
            "country": p.get("country") or p.get("originLevel1") or "",
            "producer": p.get("producerName") or "",
            "vintage": str(p.get("vintage") or ""),
            "packaging": p.get("packagingLevel1") or "",
            "is_organic": bool(p.get("isOrganic", False)),
            "is_news": bool(p.get("isNews", False)),
            "is_out_of_stock": bool(p.get("isCompletelyOutOfStock", False)),
            "is_discontinued": bool(p.get("isDiscontinued", False)),
            "in_stock": not bool(p.get("isCompletelyOutOfStock", False)),
            "in_store_assortment": None,  # filled by _fetch_product if store set
            "assortment": p.get("assortmentText") or p.get("assortment") or "",
            "taste": p.get("taste") or "",
            "image_url": f"https://product-cdn.systembolaget.se/productimages/{product_id}/{product_id}.png" if product_id else "",
        }

    # ── Services ──────────────────────────────────────────────────────────────

    async def search_products(self, query: str, size: int = 10) -> list[dict]:
        """Search products by name/number."""
        params = {"size": str(min(size, 30)), "page": "1", "textQuery": query}
        async with aiohttp.ClientSession() as http:
            await self._ensure_api_key(http)
            async with http.get(
                f"{API_BASE}/sb-api-ecommerce/v1/productsearch/search",
                params=params,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Search failed: HTTP {resp.status}")
                data = await resp.json(content_type=None)
        return [self._parse_product(p) for p in data.get("products", [])]

    async def search_stores(self, query: str) -> list[dict]:
        """Search stores by city or name."""
        params = {"q": query, "includePredictions": "false"}
        async with aiohttp.ClientSession() as http:
            await self._ensure_api_key(http)
            async with http.get(
                f"{API_BASE}/sb-api-ecommerce/v1/sitesearch/site",
                params=params,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Store search failed: HTTP {resp.status}")
                data = await resp.json(content_type=None)
        return [self._parse_store(s) for s in data.get("siteSearchResults", [])[:20]]

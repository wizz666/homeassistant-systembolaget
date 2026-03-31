"""Config flow for Systembolaget — 3-step: city → pick store → settings."""
from __future__ import annotations

import re
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN, API_BASE, SITE_BASE, _FALLBACK_KEY,
    CONF_STORE_ID, CONF_WATCHED_PRODUCTS, CONF_CATEGORIES, CONF_POLL_INTERVAL,
    DEFAULT_CATEGORIES, DEFAULT_POLL_INTERVAL, DEFAULT_WATCHED_PRODUCTS,
)

_KEY_RE = re.compile(r'NEXT_PUBLIC_API_KEY_APIM["\s:]+([a-f0-9]{32})')
_SCRIPT_RE = re.compile(r'/_next/static/chunks/pages/_app[^"\']+\.js')
_HEADERS_BASE = {
    "Origin": SITE_BASE,
    "Referer": f"{SITE_BASE}/",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant-Systembolaget/1.0)",
}


async def _get_api_key() -> str:
    """Extract API key from systembolaget.se Next.js bundle."""
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(SITE_BASE, timeout=aiohttp.ClientTimeout(total=8)) as r:
                html = await r.text()
            m = _SCRIPT_RE.search(html)
            if m:
                async with http.get(f"{SITE_BASE}{m.group(0)}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                    js = await r.text()
                km = _KEY_RE.search(js)
                if km:
                    return km.group(1)
    except Exception:
        pass
    return _FALLBACK_KEY


async def _search_stores(api_key: str, query: str) -> list[dict]:
    headers = {**_HEADERS_BASE, "Ocp-Apim-Subscription-Key": api_key}
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                f"{API_BASE}/sb-api-ecommerce/v1/sitesearch/site",
                params={"q": query, "includePredictions": "false"},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return []
                data = await r.json(content_type=None)
        return data.get("siteSearchResults", [])[:25]
    except Exception:
        return []


class SystembolagetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str = _FALLBACK_KEY
        self._store_id: str = ""
        self._store_options: list[dict] = []

    async def async_step_user(self, user_input=None):
        """Step 1 — enter city name to search for nearby stores."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict = {}
        if user_input is not None:
            city = (user_input.get("city") or "").strip()
            if not city:
                errors["city"] = "city_required"
            else:
                self._api_key = await _get_api_key()
                stores = await _search_stores(self._api_key, city)
                if not stores:
                    errors["city"] = "no_stores_found"
                else:
                    self._store_options = [
                        {
                            "label": f"{s.get('displayName') or s.get('name', 'Okänd')} — {s.get('streetAddress', '')}",
                            "value": str(s.get("siteId", "")),
                        }
                        for s in stores
                        if s.get("siteId")
                    ]
                    return await self.async_step_store()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("city"): str}),
            errors=errors,
        )

    async def async_step_store(self, user_input=None):
        """Step 2 — pick store from search results."""
        errors: dict = {}
        if user_input is not None:
            self._store_id = user_input.get(CONF_STORE_ID, "")
            if not self._store_id:
                errors[CONF_STORE_ID] = "store_required"
            else:
                return await self.async_step_settings()

        return self.async_show_form(
            step_id="store",
            data_schema=vol.Schema({
                vol.Required(CONF_STORE_ID): selector.selector({
                    "select": {"options": self._store_options, "mode": "list"},
                }),
            }),
            errors=errors,
        )

    async def async_step_settings(self, user_input=None):
        """Step 3 — categories, watched products, poll interval."""
        if user_input is not None:
            return self.async_create_entry(
                title="Systembolaget",
                data={
                    CONF_STORE_ID: self._store_id,
                    CONF_WATCHED_PRODUCTS: user_input.get(CONF_WATCHED_PRODUCTS, DEFAULT_WATCHED_PRODUCTS),
                    CONF_CATEGORIES: user_input.get(CONF_CATEGORIES, DEFAULT_CATEGORIES),
                    CONF_POLL_INTERVAL: int(user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)),
                    "_api_key_cache": self._api_key,
                },
            )

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Optional(CONF_WATCHED_PRODUCTS, default=DEFAULT_WATCHED_PRODUCTS): str,
                vol.Optional(CONF_CATEGORIES, default=DEFAULT_CATEGORIES): str,
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SystembolagetOptionsFlow(config_entry)


class SystembolagetOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Normalise watched products: strip spaces, remove empty entries
            raw = user_input.get(CONF_WATCHED_PRODUCTS, "")
            cleaned = ",".join(p.strip() for p in raw.split(",") if p.strip())
            user_input[CONF_WATCHED_PRODUCTS] = cleaned
            return self.async_create_entry(title="", data=user_input)

        cur = {**self._entry.data, **self._entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_STORE_ID, default=cur.get(CONF_STORE_ID, "")): str,
                vol.Optional(
                    CONF_WATCHED_PRODUCTS,
                    default=cur.get(CONF_WATCHED_PRODUCTS, DEFAULT_WATCHED_PRODUCTS),
                    description={"suggested_value": cur.get(CONF_WATCHED_PRODUCTS, "")},
                ): selector.selector({
                    "text": {"multiline": False, "suffix": "kommaseparerade ID:n, t.ex. 77602,12345"}
                }),
                vol.Optional(CONF_CATEGORIES, default=cur.get(CONF_CATEGORIES, DEFAULT_CATEGORIES)): str,
                vol.Optional(CONF_POLL_INTERVAL, default=int(cur.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))): int,
            }),
            description_placeholders={
                "watched_help": "Ange ett eller flera produkt-ID:n från systembolaget.se, separerade med komma. Exempel: 77602,12345,98765"
            },
        )

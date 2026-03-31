"""Systembolaget integration."""
from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN
from .coordinator import SystembolagetCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    # Carry over last known data so sensors don't flash empty/closed during reload
    last_data = hass.data[DOMAIN].pop(f"{entry.entry_id}_last_data", None)
    coordinator = SystembolagetCoordinator(hass, entry, last_data=last_data)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    # ── Services ──────────────────────────────────────────────────────────────

    async def _handle_refresh(call):
        await coordinator.async_refresh()

    async def _handle_search_product(call):
        query = call.data.get("query", "")
        size = int(call.data.get("size", 10))
        if not query:
            _LOGGER.warning("[Systembolaget] search_product: query is required")
            return
        try:
            results = await coordinator.search_products(query, size)
            _LOGGER.info("[Systembolaget] Search '%s' → %d results", query, len(results))
            for r in results:
                _LOGGER.info(
                    "  ID:%-8s  %s kr  %s  %s",
                    r["product_id"], r["price"], r["name"][:40], r["category"],
                )
            await hass.services.async_call(
                "persistent_notification", "create",
                {
                    "title": f"Systembolaget: sök '{query}'",
                    "message": "\n".join(
                        f"**{r['name']}** (ID: {r['product_id']}) — {r['price']} kr — {r['category']}"
                        for r in results
                    ) or "Inga träffar.",
                    "notification_id": "systembolaget_search",
                },
            )
        except UpdateFailed as exc:
            _LOGGER.error("[Systembolaget] Search failed: %s", exc)

    async def _handle_search_store(call):
        city = call.data.get("city", "")
        if not city:
            _LOGGER.warning("[Systembolaget] search_store: city is required")
            return
        try:
            stores = await coordinator.search_stores(city)
            await hass.services.async_call(
                "persistent_notification", "create",
                {
                    "title": f"Systembolaget: butiker i '{city}'",
                    "message": "\n".join(
                        f"**{s['name']}** — ID: {s['store_id']} — {s['address']}, {s['city']}"
                        for s in stores
                    ) or "Inga butiker hittades.",
                    "notification_id": "systembolaget_store_search",
                },
            )
        except UpdateFailed as exc:
            _LOGGER.error("[Systembolaget] Store search failed: %s", exc)

    hass.services.async_register(DOMAIN, "refresh", _handle_refresh)
    hass.services.async_register(DOMAIN, "search_product", _handle_search_product)
    hass.services.async_register(DOMAIN, "search_store", _handle_search_store)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        # Preserve last fetched data so the next setup can show it immediately
        if coordinator and coordinator.data:
            hass.data[DOMAIN][f"{entry.entry_id}_last_data"] = coordinator.data
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

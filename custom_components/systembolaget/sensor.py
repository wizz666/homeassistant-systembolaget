"""Systembolaget sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_WATCHED_PRODUCTS, DEFAULT_WATCHED_PRODUCTS
from .coordinator import SystembolagetCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SystembolagetCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        SystembolagetNyheterSensor(coordinator, entry),
        SystembolagetButikSensor(coordinator, entry),
    ]

    watched_raw = entry.options.get(CONF_WATCHED_PRODUCTS) or entry.data.get(CONF_WATCHED_PRODUCTS, DEFAULT_WATCHED_PRODUCTS)
    watched_ids = [p.strip() for p in watched_raw.split(",") if p.strip()]
    for pid in watched_ids:
        entities.append(SystembolagetProductSensor(coordinator, entry, pid))

    async_add_entities(entities)


# ── Base ──────────────────────────────────────────────────────────────────────

class _SensorBase(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: SystembolagetCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry

    async def async_added_to_hass(self) -> None:
        self._coordinator.async_add_listener(self.async_write_ha_state)

    @property
    def _data(self) -> dict:
        return self._coordinator.data or {}

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Systembolaget",
            "manufacturer": "Systembolaget",
            "model": "Bevakare",
            "entry_type": "service",
        }


# ── Nyheter ───────────────────────────────────────────────────────────────────

class SystembolagetNyheterSensor(_SensorBase):
    _attr_icon = "mdi:new-box"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_nyheter"
        self._attr_name = "Nyheter"

    @property
    def native_value(self) -> int:
        return len(self._data.get("new_arrivals", []))

    @property
    def native_unit_of_measurement(self) -> str:
        return "produkter"

    @property
    def extra_state_attributes(self) -> dict:
        arrivals = self._data.get("new_arrivals", [])
        return {
            "products": arrivals,
            "count": len(arrivals),
        }


# ── Butik ─────────────────────────────────────────────────────────────────────

class SystembolagetButikSensor(_SensorBase):
    _attr_icon = "mdi:store"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_butik"
        self._attr_name = "Butik"

    @property
    def native_value(self) -> str:
        store = self._data.get("store", {})
        if not store:
            return "Ingen butik konfigurerad"
        return "Öppet" if store.get("is_open") else "Stängd"

    @property
    def extra_state_attributes(self) -> dict:
        store = self._data.get("store", {})
        return {
            "name": store.get("name", ""),
            "address": store.get("address", ""),
            "city": store.get("city", ""),
            "phone": store.get("phone", ""),
            "today_hours": store.get("today_hours", "–"),
            "store_id": store.get("store_id", ""),
            "is_open": store.get("is_open", False),
        }


# ── Produkt ───────────────────────────────────────────────────────────────────

class SystembolagetProductSensor(_SensorBase):

    def __init__(self, coordinator, entry, product_id: str) -> None:
        super().__init__(coordinator, entry)
        self._product_id = product_id
        self._attr_unique_id = f"{entry.entry_id}_product_{product_id}"
        self._attr_name = f"Produkt {product_id}"

    @property
    def _product(self) -> dict:
        return self._data.get("products", {}).get(self._product_id, {})

    @property
    def icon(self) -> str:
        cat = self._product.get("category", "").lower()
        if "öl" in cat or "beer" in cat:
            return "mdi:glass-mug-variant"
        if "vin" in cat or "wine" in cat:
            return "mdi:glass-wine"
        if "cider" in cat:
            return "mdi:glass-pint-outline"
        if "alkoholfritt" in cat:
            return "mdi:cup-water"
        return "mdi:bottle-tonic"

    @property
    def native_value(self) -> str:
        p = self._product
        if not p or "error" in p:
            return "Ej hittad"
        price = p.get("price")
        return f"{price:.2f} kr" if price else "–"

    @property
    def extra_state_attributes(self) -> dict:
        p = self._product
        if not p:
            return {"product_id": self._product_id}
        return {
            "product_id": self._product_id,
            "name": p.get("name", ""),
            "price": p.get("price"),
            "category": p.get("category", ""),
            "subcategory": p.get("subcategory", ""),
            "alcohol_pct": p.get("alcohol_pct"),
            "volume_ml": p.get("volume_ml"),
            "country": p.get("country", ""),
            "producer": p.get("producer", ""),
            "vintage": p.get("vintage", ""),
            "in_stock": p.get("in_stock", False),
            "stock_count": p.get("stock_count", 0),
            "is_new": p.get("is_new", False),
        }

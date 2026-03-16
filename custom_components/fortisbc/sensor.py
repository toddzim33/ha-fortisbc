"""FortisBC sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FortisbcCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FortisBC sensors."""
    coordinator: FortisbcCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    data = coordinator.data or {}

    # Gas sensor
    if data.get("gas"):
        entities.append(FortisbcGasUsageSensor(coordinator))
        entities.append(FortisbcGasCostSensor(coordinator))

    # Electric sensors — one set per account
    for i, acct in enumerate(data.get("electric", [])):
        label = acct.premise_address or f"Electric {i + 1}"
        entities.append(FortisbcElectricUsageSensor(coordinator, i, label))
        entities.append(FortisbcElectricCostSensor(coordinator, i, label))

    async_add_entities(entities)


class _FortisbcBase(CoordinatorEntity):
    """Base class for FortisBC sensors."""

    def __init__(self, coordinator: FortisbcCoordinator, unique_suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"fortisbc_{unique_suffix}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "fortisbc")},
            "name": "FortisBC",
            "manufacturer": "FortisBC",
        }


class FortisbcElectricUsageSensor(_FortisbcBase, SensorEntity):
    """Current billing period electricity usage in kWh."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: FortisbcCoordinator, index: int, label: str) -> None:
        super().__init__(coordinator, f"electric_{index}_kwh")
        self._index = index
        self._attr_name = f"FortisBC Electric Usage ({label})"

    @property
    def native_value(self):
        accounts = (self.coordinator.data or {}).get("electric", [])
        if self._index >= len(accounts):
            return None
        period = accounts[self._index].current_period
        return period.usage if period else None

    @property
    def extra_state_attributes(self):
        accounts = (self.coordinator.data or {}).get("electric", [])
        if self._index >= len(accounts):
            return {}
        account = accounts[self._index]
        period = account.current_period
        if not period:
            return {}
        return {
            "bill_start": period.start_date.isoformat(),
            "bill_end": period.end_date.isoformat(),
            "days_in_period": period.days,
            "premise": account.premise_address,
            "rate": account.rate_id,
            "hourly_available": account.hourly_available,
        }


class FortisbcElectricCostSensor(_FortisbcBase, SensorEntity):
    """Current billing period electricity cost in CAD."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "CAD"

    def __init__(self, coordinator: FortisbcCoordinator, index: int, label: str) -> None:
        super().__init__(coordinator, f"electric_{index}_cost")
        self._index = index
        self._attr_name = f"FortisBC Electric Cost ({label})"

    @property
    def native_value(self):
        accounts = (self.coordinator.data or {}).get("electric", [])
        if self._index >= len(accounts):
            return None
        period = accounts[self._index].current_period
        return period.amount_due if period else None


class FortisbcGasUsageSensor(_FortisbcBase, SensorEntity):
    """Current billing period natural gas usage in GJ."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "GJ"
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: FortisbcCoordinator) -> None:
        super().__init__(coordinator, "gas_gj")
        self._attr_name = "FortisBC Gas Usage"

    @property
    def native_value(self):
        gas = (self.coordinator.data or {}).get("gas")
        if not gas:
            return None
        period = gas.current_period
        return period.usage if period else None

    @property
    def extra_state_attributes(self):
        gas = (self.coordinator.data or {}).get("gas")
        if not gas:
            return {}
        period = gas.current_period
        if not period:
            return {}
        return {
            "bill_start": period.start_date.isoformat(),
            "bill_end": period.end_date.isoformat(),
            "days_in_period": period.days,
            "avg_temperature": period.avg_temperature,
        }


class FortisbcGasCostSensor(_FortisbcBase, SensorEntity):
    """Current billing period natural gas cost in CAD."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "CAD"
    _attr_icon = "mdi:currency-usd"

    def __init__(self, coordinator: FortisbcCoordinator) -> None:
        super().__init__(coordinator, "gas_cost")
        self._attr_name = "FortisBC Gas Cost"

    @property
    def native_value(self):
        gas = (self.coordinator.data or {}).get("gas")
        if not gas:
            return None
        period = gas.current_period
        return period.amount_due if period else None

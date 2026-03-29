"""FortisBC sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

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

    # Gas sensors
    if data.get("gas"):
        entities.append(FortisbcGasUsageSensor(coordinator))
        entities.append(FortisbcGasM3Sensor(coordinator))
        entities.append(FortisbcGasCostSensor(coordinator))
        entities.append(FortisbcGasRateSensor(coordinator))

    # Electric sensors — one usage + one cost + one rate per SA
    for i, acct in enumerate(data.get("electric", [])):
        label = acct.premise_address or f"Electric {i + 1}"
        entities.append(FortisbcElectricUsageSensor(coordinator, i, label))
        entities.append(FortisbcElectricCostSensor(coordinator, i, label))
        entities.append(FortisbcElectricRateSensor(coordinator, i, label))

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
    def last_reset(self):
        accounts = (self.coordinator.data or {}).get("electric", [])
        if self._index >= len(accounts):
            return None
        period = accounts[self._index].current_period
        if not period:
            return None
        return dt_util.start_of_local_day(period.start_date)

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
    _attr_icon = "mdi:currency-usd"

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
        return period.cost if period else None

    @property
    def last_reset(self):
        accounts = (self.coordinator.data or {}).get("electric", [])
        if self._index >= len(accounts):
            return None
        period = accounts[self._index].current_period
        if not period:
            return None
        return dt_util.start_of_local_day(period.start_date)

    @property
    def extra_state_attributes(self):
        accounts = (self.coordinator.data or {}).get("electric", [])
        if self._index >= len(accounts):
            return {}
        period = accounts[self._index].current_period
        if not period:
            return {}
        return {
            "bill_start": period.start_date.isoformat(),
            "bill_end": period.end_date.isoformat(),
            "days_in_period": period.days,
        }


class FortisbcGasUsageSensor(_FortisbcBase, SensorEntity):
    """Current billing period natural gas usage in GJ (raw portal value).

    SensorStateClass.MEASUREMENT keeps this out of the Energy dashboard dropdowns —
    it's a display-only sensor. The m³ sensor (FortisbcGasM3Sensor) is the one
    that appears in the Energy gas section.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
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


# FortisBC bills gas in GJ; the Energy dashboard requires m³.
# Conversion uses a typical BC interior calorific value of ~38.2 MJ/m³
# (FortisBC's actual factor varies slightly by region and season).
_GJ_TO_M3 = 1000.0 / 38.2


class FortisbcGasM3Sensor(_FortisbcBase, SensorEntity):
    """Current billing period gas usage in m³ — for the Energy dashboard gas section."""

    _attr_device_class = SensorDeviceClass.GAS
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: FortisbcCoordinator) -> None:
        super().__init__(coordinator, "gas_m3")
        self._attr_name = "FortisBC Gas Usage (m³)"

    @property
    def native_value(self):
        gas = (self.coordinator.data or {}).get("gas")
        if not gas:
            return None
        period = gas.current_period
        if not period:
            return None
        return round(period.usage * _GJ_TO_M3, 2)

    @property
    def last_reset(self):
        gas = (self.coordinator.data or {}).get("gas")
        if not gas:
            return None
        period = gas.current_period
        if not period:
            return None
        return dt_util.start_of_local_day(period.start_date)

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
            "gj_raw": period.usage,
            "conversion_factor": f"{_GJ_TO_M3:.4f} m³/GJ (approx. 38.2 MJ/m³)",
        }


class FortisbcGasCostSensor(_FortisbcBase, SensorEntity):
    """Current billing period gas cost in CAD.

    FortisBC only finalises the cost when the bill is issued (end of period).
    While the period is in progress, cost is derived from current usage × the
    effective rate from the most recently completed bill.  This keeps the HA
    statistics sum non-zero and growing so the Energy dashboard can track costs.

    last_reset is always the start of the *current* billing period so it aligns
    with the gas m³ sensor and HA correctly bins both sensors together.
    """

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "CAD"
    _attr_icon = "mdi:currency-usd"

    def __init__(self, coordinator: FortisbcCoordinator) -> None:
        super().__init__(coordinator, "gas_cost")
        self._attr_name = "FortisBC Gas Cost"

    def _gas(self):
        return (self.coordinator.data or {}).get("gas")

    def _last_billed_rate_per_m3(self, gas) -> float | None:
        """Return CAD/m³ from the most recent completed bill."""
        for period in gas.billing_periods:
            if period.cost is not None and period.usage:
                usage_m3 = period.usage * _GJ_TO_M3
                if usage_m3:
                    return period.cost / usage_m3
        return None

    @property
    def native_value(self):
        gas = self._gas()
        if not gas:
            return None
        period = gas.current_period
        if not period:
            return None
        # Use finalized cost when available; otherwise estimate from usage × rate.
        if period.cost is not None:
            return period.cost
        rate = self._last_billed_rate_per_m3(gas)
        if rate is None:
            return None
        return round(period.usage * _GJ_TO_M3 * rate, 2)

    @property
    def last_reset(self):
        gas = self._gas()
        if not gas or not gas.current_period:
            return None
        return dt_util.start_of_local_day(gas.current_period.start_date)

    @property
    def extra_state_attributes(self):
        gas = self._gas()
        if not gas:
            return {}
        period = gas.current_period
        if not period:
            return {}
        rate = self._last_billed_rate_per_m3(gas)
        return {
            "bill_start": period.start_date.isoformat(),
            "bill_end": period.end_date.isoformat(),
            "days_in_period": period.days,
            "cost_finalized": period.cost is not None,
            "rate_used_cad_per_m3": round(rate, 4) if rate else None,
        }


class FortisbcElectricRateSensor(_FortisbcBase, SensorEntity):
    """Effective electricity rate in CAD/kWh derived from billing period cost ÷ usage.

    Use this as the 'current price' entity in the Energy dashboard so HA can
    calculate approximate daily costs from metered usage.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "CAD/kWh"
    _attr_icon = "mdi:currency-usd"
    _attr_suggested_display_precision = 4

    def __init__(self, coordinator: FortisbcCoordinator, index: int, label: str) -> None:
        super().__init__(coordinator, f"electric_{index}_rate")
        self._index = index
        self._attr_name = f"FortisBC Electric Rate ({label})"

    @property
    def native_value(self):
        accounts = (self.coordinator.data or {}).get("electric", [])
        if self._index >= len(accounts):
            return None
        period = accounts[self._index].current_period
        if not period or not period.cost or not period.usage:
            return None
        return round(period.cost / period.usage, 4)

    @property
    def extra_state_attributes(self):
        accounts = (self.coordinator.data or {}).get("electric", [])
        if self._index >= len(accounts):
            return {}
        period = accounts[self._index].current_period
        if not period:
            return {}
        return {
            "bill_cost": period.cost,
            "bill_usage_kwh": period.usage,
            "bill_start": period.start_date.isoformat(),
            "bill_end": period.end_date.isoformat(),
        }


class FortisbcGasRateSensor(_FortisbcBase, SensorEntity):
    """Effective gas rate in CAD/m³ derived from billing period cost ÷ usage.

    Use this as the 'current price' entity in the Energy dashboard gas section.
    Uses the most recent billed period (same as GasCostSensor).
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "CAD/m³"
    _attr_icon = "mdi:currency-usd"
    _attr_suggested_display_precision = 4

    def __init__(self, coordinator: FortisbcCoordinator) -> None:
        super().__init__(coordinator, "gas_rate")
        self._attr_name = "FortisBC Gas Rate"

    @property
    def _last_billed_period(self):
        gas = (self.coordinator.data or {}).get("gas")
        if not gas:
            return None
        for period in gas.billing_periods:
            if period.cost is not None:
                return period
        return None

    @property
    def native_value(self):
        period = self._last_billed_period
        if not period or not period.cost or not period.usage:
            return None
        usage_m3 = round(period.usage * _GJ_TO_M3, 4)
        if not usage_m3:
            return None
        return round(period.cost / usage_m3, 4)

    @property
    def extra_state_attributes(self):
        period = self._last_billed_period
        if not period:
            return {}
        return {
            "bill_cost": period.cost,
            "bill_usage_gj": period.usage,
            "bill_usage_m3": round(period.usage * _GJ_TO_M3, 2),
            "bill_start": period.start_date.isoformat(),
            "bill_end": period.end_date.isoformat(),
        }

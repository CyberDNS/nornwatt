"""What devices are for (purpose), which devices belong together (a switch and
the device it switches, a car and its charger), and the past of a consumer
without a meter — what the UI builds its pages from."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from nornwatt.core.config import AppConfig
from nornwatt.core.device_model import (
    DeviceConfigError,
    Purpose,
    controlled_devices,
    device_purpose,
    parse_devices,
)
from nornwatt.loader.energy_dashboard import add_dashboard_consumers
from nornwatt.plugins.learned.forecast import LearnedConsumptionForecast
from nornwatt.server import Application

SPECS = {
    "grid": {"category": "meter", "type": "tasmota", "host": "h"},
    "pv": {"category": "pv", "type": "homeassistant_sensor",
           "capabilities": {"power_w": {"entity": "sensor.pv"}}},
    "bat": {"category": "battery", "type": "zendure", "cloud_key": "k", "product_key": "p",
            "device_key": "d",
            "params": {"capacity_kwh": 7.6, "max_charge_kw": 1.2, "max_discharge_kw": 0.8}},
    "car": {"category": "vehicle", "type": "homeassistant_vehicle", "params": {"capacity_kwh": 60}},
    "wallbox": {"category": "charger", "type": "openwb_mqtt", "params": {"default_vehicle": "car"}},
    "garage": {"category": "charger", "type": "openwb_mqtt"},
    "aquarium_plug": {"category": "switch", "type": "homeassistant_switch",
                      "params": {"rated_power_w": 200}},
    "aquarium_cooler": {
        "category": "thermal_load", "type": "homeassistant_thermal",
        "controlled_by": "aquarium_plug",
        "params": {"bottom_threshold": 24, "top_threshold": 25,
                   "active_rate_per_h": 1.0, "drift_rate_per_h": 0.3},
    },
    "lamp_plug": {"category": "switch", "type": "homeassistant_switch",
                  "params": {"rated_power_w": 40}},
    "heat_pump": {"category": "consumer", "type": "generic_consumer",
                  "params": {"purpose": "heating_cooling"}},
    "washing": {"category": "consumer", "type": "generic_consumer"},
}


def test_the_purpose_follows_the_category_except_for_consumers_and_switches() -> None:
    specs = parse_devices(SPECS)
    purpose = {d: device_purpose(s, specs) for d, s in specs.items()}
    assert purpose == {
        "grid": Purpose.METERING, "pv": Purpose.GENERATION, "bat": Purpose.STORAGE,
        "car": Purpose.MOBILITY, "wallbox": Purpose.MOBILITY, "garage": Purpose.MOBILITY,
        # A plug is for what it switches; one that switches nothing is an appliance.
        "aquarium_plug": Purpose.HEATING_COOLING, "aquarium_cooler": Purpose.HEATING_COOLING,
        "lamp_plug": Purpose.APPLIANCE,
        # A consumer says it itself; an appliance unless it says otherwise.
        "heat_pump": Purpose.HEATING_COOLING, "washing": Purpose.APPLIANCE,
    }


def test_an_unknown_purpose_is_rejected() -> None:
    with pytest.raises(DeviceConfigError) as exc:
        parse_devices({"x": {"category": "consumer", "type": "generic_consumer",
                             "params": {"purpose": "sauna"}}})
    assert any("purpose" in e for e in exc.value.errors)


def test_a_switch_names_the_devices_it_switches() -> None:
    specs = parse_devices(SPECS)
    assert controlled_devices("aquarium_plug", specs) == ["aquarium_cooler"]
    assert controlled_devices("lamp_plug", specs) == []


def _app(specs) -> Application:
    app = Application.__new__(Application)
    app._cfg = SimpleNamespace(devices=specs)
    return app


def test_the_status_says_what_belongs_together() -> None:
    specs = parse_devices(SPECS)
    app = _app(specs)
    assert app._device_relations(specs["aquarium_cooler"]) == {
        "purpose": "heating_cooling", "controlled_by": "aquarium_plug", "controls": [],
    }
    assert app._device_relations(specs["aquarium_plug"]) == {
        "purpose": "heating_cooling", "controlled_by": None, "controls": ["aquarium_cooler"],
    }
    assert app._device_relations(None) == {"purpose": None, "controlled_by": None, "controls": []}


def test_a_car_savings_group_names_the_car_whose_page_shows_it() -> None:
    """Savings are kept per charger; the group of a charger with a default
    car links to that car, one without to the charger itself."""
    specs = parse_devices(SPECS)
    app = _app(specs)
    app._storage_constraints = []
    app._power_charges = None
    app._threshold_constraints = []
    app._fleet = SimpleNamespace(
        chargers={d: s for d, s in specs.items() if s.category.value == "charger"},
        vehicles={d: s for d, s in specs.items() if s.category.value == "vehicle"},
    )
    groups = {g["id"]: g for g in app._savings_groups()}
    assert groups["wallbox"]["vehicle_id"] == "car"
    assert groups["wallbox"]["label"] == "Car"
    assert groups["garage"]["vehicle_id"] is None


# ── a consumer imported from the Energy dashboard ─────────────────────────────

PREFS = {"device_consumption": [
    {"stat_consumption": "sensor.ac_energy", "stat_rate": "sensor.ac_power", "name": "Climate Cinema"},
    {"stat_consumption": "sensor.tv_energy", "stat_rate": "sensor.tv_power", "name": "Television"},
]}


def test_dashboard_consumers_can_be_marked_as_heating_or_cooling() -> None:
    app = AppConfig(default_tariff_id="household", devices={})
    add_dashboard_consumers(app, PREFS, {"import_consumers": True, "heating_cooling": ["climate cinema"]})
    assert device_purpose(app.devices["climate_cinema"], app.devices) is Purpose.HEATING_COOLING
    assert device_purpose(app.devices["television"], app.devices) is Purpose.APPLIANCE


# ── the past of a consumer without a meter ────────────────────────────────────

NOW = datetime(2026, 11, 28, 12, 30, tzinfo=UTC)
HOUSE, RACK = "sensor.house_power", "sensor.rack_power"


class _HA:
    """Hourly statistics: the house at 850 W, the rack (own meter) at 300 W."""

    def __init__(self) -> None:
        self.start: datetime | None = None

    async def get_statistics(self, ids, start, period="hour", **_kw):
        self.start = start
        hours = [start + timedelta(hours=h) for h in range(6)]
        return {
            HOUSE: [{"start": t, "mean": 850.0} for t in hours],
            RACK: [{"start": t, "mean": 300.0} for t in hours],
        }


async def test_a_virtual_consumer_has_the_residual_as_its_history() -> None:
    """The baseline is not measured: its past is the house's consumption
    minus the consumers with their own meter, per hour."""
    ha = _HA()
    provider = LearnedConsumptionForecast("baseline_forecast", ha, HOUSE, subtract=[RACK], clock=lambda: NOW)
    begin = NOW - timedelta(hours=3)
    watts = await provider.hourly_history(begin, NOW)
    assert ha.start == begin.replace(minute=0)
    assert set(watts.values()) == {550.0}
    assert all(begin.replace(minute=0) <= t < NOW for t in watts)

    specs = parse_devices({
        "baseline": {"category": "consumer", "type": "generic_consumer"},
        "rack": {"category": "consumer", "type": "homeassistant_sensor",
                 "capabilities": {"power_w": {"entity": RACK}}},
    })
    app = _app(specs)
    app._device_forecast_providers = {"baseline": provider}

    hourly = await app._virtual_history("baseline", begin, NOW, hourly=True)
    assert [r["power_w"] for r in hourly] == [550.0] * len(hourly)
    assert all(begin <= datetime.fromisoformat(r["t"]) < NOW for r in hourly)
    # In 5-minute steps every hour is repeated, so the energy stays the same.
    fine = await app._virtual_history("baseline", begin, NOW, hourly=False)
    assert len(fine) == 36 and fine[0]["pos_w"] == 550.0
    # A measured device keeps its own history.
    assert await app._virtual_history("rack", begin, NOW, hourly=True) is None

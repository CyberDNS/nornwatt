"""Browser test: devices that belong together, and pages in the order of time.

Serves the real frontend with mocked API answers of a house with a cooler on
a plug, a heat pump that is only measured, and a car at a charger:

* a plug and the device it switches are one device (one row, one page);
* a device is listed under what it is for (the heat pump under heating and
  cooling although Nornwatt only measures it);
* every device page reads now, future, past, and a section a device has
  nothing for says why;
* a row of the savings opens the page that shows it (a car's savings are kept
  per charger and shown with the car; battery wear on the batteries page).

Needs the built frontend and Playwright with Chromium (see test_savings_ranges).
"""

from __future__ import annotations

import functools
import http.server
import json
import threading
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from test_savings_ranges import FRONTEND, _savings, page  # noqa: F401


def _device(device_id: str, label: str, category: str, purpose: str, **extra) -> dict:
    return {
        "device_id": device_id, "label": label, "category": category, "purpose": purpose,
        "power_w": 0.0, "soc_pct": None, "available": True, "is_virtual": False,
        "control": None, "control_targets": [], "controlled_by": None, "controls": [], **extra,
    }


STATUS = {
    "configuration": {"state": "running", "problems": [], "devices": 7, "homeassistant": None},
    "timestamp": datetime.now().astimezone().isoformat(),
    "grid_power_w": 420.0, "current_price_eur_per_kwh": 0.3, "pv_opportunity_price_eur_per_kwh": 0.08,
    "control": {"aq": "active", "cp": "active", "bat": "active"},
    "setpoints": [], "ledger": [],
    "devices": [
        _device("grid", "Grid meter", "meter", "metering", power_w=420.0),
        _device("bat", "Battery", "battery", "storage", soc_pct=50.0, control="active", control_targets=["bat"]),
        _device("aq", "Aquarium", "thermal_load", "heating_cooling", control="active",
                control_targets=["aq"], controlled_by="aq_plug"),
        _device("aq_plug", "Aquarium plug", "switch", "heating_cooling", control="active",
                control_targets=["aq"], controls=["aq"]),
        _device("hp", "Heat pump", "consumer", "heating_cooling", power_w=900.0),
        _device("car", "Family car", "vehicle", "mobility", soc_pct=40.0, power_w=None,
                control="active", control_targets=["cp"]),
        _device("cp", "Wallbox", "charger", "mobility", available=False, control="active",
                control_targets=["cp"]),
    ],
}
VEHICLES = [{"vehicle_id": "car", "label": "Family car", "charger_id": None, "connected": False,
             "soc_pct": 40.0, "next_days": [], "charge_limit_soc_pct": 90.0}]
CHARGERS = [{"charger_id": "cp", "label": "Wallbox", "plugged": False, "power_w": 0.0,
             "default_vehicle": "car", "session": None, "vehicles": [{"vehicle_id": "car", "label": "Family car"}]}]
GROUPS = [
    {"id": "batteries", "kind": "batteries", "label": "Batteries"},
    {"id": "battery_wear", "kind": "wear", "label": "Battery wear"},
    # Kept per charger, shown with its default car.
    {"id": "cp", "kind": "car", "label": "Family car", "vehicle_id": "car", "charger_id": "cp"},
    {"id": "aq", "kind": "device", "label": "Aquarium", "unit": "°C",
     "bottom_threshold": 18.0, "top_threshold": 20.5},
]


def _answer(path: str, query: dict) -> object:
    if path == "/api/status":
        return STATUS
    if path == "/api/vehicles":
        return VEHICLES
    if path == "/api/chargers":
        return CHARGERS
    if path == "/api/savings":
        data = _savings(float(query.get("hours", ["24"])[0]), 96)
        data["groups"] = GROUPS
        for holder in [data["totals"], data["all_time"], *data["buckets"]]:
            holder["components"]["battery_wear"] = -0.02
        return data
    if path == "/api/savings/slots":
        return {"totals": None, "slots": []}
    if path == "/api/history":
        now = datetime.now().astimezone().replace(second=0, microsecond=0)
        rows = [{"t": (now - timedelta(minutes=5 * i)).isoformat(), "power_w": 100.0, "soc_pct": None,
                 "pos_w": 100.0, "neg_w": 0.0} for i in range(12)]
        ids = [d for d in query.get("device_ids", [""])[0].split(",") if d]
        return {"resolution": "5m", "bucket_minutes": 5, "measurements": {d: rows for d in ids},
                "derived": [], "ledger": {}}
    if path in ("/api/learned", "/api/ledger"):
        return []
    if path == "/api/controllable":
        return {"devices": []}
    return {}


@pytest.fixture
def server():
    if not (FRONTEND / "index.html").exists():
        pytest.skip("frontend not built (npm run build in frontend/)")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:  # quiet
            pass

        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path == "/api/stream":
                self.send_response(404)
                self.end_headers()
                return
            if url.path.startswith("/api/"):
                body = json.dumps(_answer(url.path, parse_qs(url.query))).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
                return
            if "." not in url.path.rsplit("/", 1)[-1]:
                self.path = "/index.html"
            super().do_GET()

    Handler.extensions_map = {**Handler.extensions_map, ".js": "application/javascript"}
    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(FRONTEND))
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_a_plug_and_its_device_are_one_and_devices_are_listed_by_purpose(server, page) -> None:  # noqa: F811
    expect = sync_api.expect
    page.goto(f"{server}/#/devices")
    heating = page.get_by_test_id("devices-heating_cooling")
    expect(heating).to_be_visible()
    rows = heating.locator(".link-row")
    # The cooler with its plug named on its row, and the heat pump that is only measured.
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("Aquarium")
    expect(rows.nth(0)).to_contain_text("through Aquarium plug")
    expect(rows.nth(1)).to_contain_text("Heat pump")
    # Cars first, then the chargers no car is plugged in at.
    mobility = page.get_by_test_id("devices-mobility")
    expect(mobility.locator("h3")).to_have_text(["Cars", "Chargers"])
    expect(mobility.get_by_test_id("devices-cars").locator(".link-row")).to_contain_text(["Family car"])
    expect(mobility.get_by_test_id("devices-chargers").locator(".link-row")).to_contain_text(["Wallbox"])
    # A charger without a car is not a fault.
    charger = page.get_by_test_id("devices-mobility").locator(".link-row", has_text="Wallbox")
    expect(charger).to_contain_text("no car plugged in")
    expect(charger.locator(".status-dot.off")).to_have_count(0)

    # The plug has no page of its own: it opens the cooler's.
    page.goto(f"{server}/#/devices/aq_plug")
    page.wait_for_url("**/#/devices/aq")
    expect(page.get_by_test_id("switched-through")).to_contain_text("Aquarium plug")
    assert page.errors == []


def test_a_device_page_reads_now_future_past_and_says_why_a_part_is_empty(server, page) -> None:  # noqa: F811
    expect = sync_api.expect
    page.goto(f"{server}/#/devices/hp")
    for when in ("now", "future", "past"):
        expect(page.get_by_test_id(f"section-{when}")).to_be_visible()
    order = page.evaluate(
        "[...document.querySelectorAll('[data-testid^=\"section-\"]')].map(e => e.dataset.testid)"
    )
    assert order == ["section-now", "section-future", "section-past"]
    expect(page.get_by_test_id("control-level")).to_have_text("Measured only")
    # Nothing is planned, saved or learned for a device that is only measured: each part says so.
    expect(page.get_by_test_id("device-future-none")).to_be_visible()
    expect(page.get_by_test_id("device-savings-none")).to_contain_text("only measures this device")
    expect(page.get_by_test_id("device-learned-none")).to_be_visible()
    expect(page.get_by_test_id("device-history")).to_be_visible()
    assert page.errors == []


def test_savings_rows_open_the_page_that_shows_them(server, page) -> None:  # noqa: F811
    expect = sync_api.expect
    page.goto(f"{server}/#/savings")
    breakdown = page.get_by_test_id("savings-breakdown")
    # A car's savings are kept per charger: the row opens the car, not the charger as a car.
    breakdown.locator(".link-row", has_text="Family car").click()
    page.wait_for_url("**/#/cars/car#saved")
    expect(page.get_by_text("Unknown car")).to_have_count(0)
    expect(page.get_by_test_id("device-savings")).to_be_visible()

    page.goto(f"{server}/#/savings")
    page.get_by_test_id("savings-breakdown").locator(".link-row", has_text="Battery wear").click()
    page.wait_for_url("**/#/batteries#wear")
    expect(page.locator("#wear")).to_contain_text("Battery wear")
    assert page.errors == []


def test_a_car_and_the_charger_it_is_plugged_in_at_are_shown_together(server, page) -> None:  # noqa: F811
    """Plugged in, the charger moves under its car; the other chargers stay under Chargers."""
    expect = sync_api.expect
    plugged = [{**CHARGERS[0], "plugged": True, "session": {"vehicle_id": "car", "guest": False}}]
    page.route("**/api/chargers", lambda route: route.fulfill(json=plugged))
    page.goto(f"{server}/#/devices")
    cars = page.get_by_test_id("devices-mobility").get_by_test_id("devices-cars").locator(".link-row")
    expect(cars).to_have_count(2)
    expect(cars.nth(0)).to_contain_text("Family car")
    expect(cars.nth(1)).to_contain_text("Wallbox")
    expect(cars.nth(1)).to_contain_text("plugged in here")
    expect(page.get_by_test_id("devices-chargers")).to_have_count(0)
    assert page.errors == []


def test_heating_and_appliances_show_their_own_devices_when_switching(server, page) -> None:  # noqa: F811
    """Both pages are one component: the list has to follow the page."""
    expect = sync_api.expect
    appliance = _device("tv", "Television", "consumer", "appliance", power_w=80.0)
    status = {**STATUS, "devices": [*STATUS["devices"], appliance]}
    page.route("**/api/status", lambda route: route.fulfill(json=status))
    page.goto(f"{server}/#/heating")
    cards = page.locator(".dev-card .dev-label")
    expect(cards).to_have_text(["Aquarium", "Heat pump"])
    for _ in range(2):
        page.get_by_role("link", name="Appliances").click()
        expect(cards).to_have_text(["Television"])
        page.get_by_role("link", name="Heating & cooling").click()
        expect(cards).to_have_text(["Aquarium", "Heat pump"])
    assert page.errors == []


def test_the_cars_page_reads_now_future_past(server, page) -> None:  # noqa: F811
    expect = sync_api.expect
    page.goto(f"{server}/#/cars")
    expect(page.get_by_test_id("section-past")).to_be_visible()
    order = page.evaluate(
        "[...document.querySelectorAll('[data-testid^=\"section-\"]')].map(e => e.dataset.testid)"
    )
    assert order == ["section-now", "section-future", "section-past"]
    past = page.get_by_test_id("section-past")
    expect(past.get_by_test_id("device-history")).to_contain_text("Family car")
    expect(past.get_by_test_id("device-savings")).to_contain_text("Family car")
    assert page.errors == []

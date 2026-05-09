"""Routing behavior tests for local fallback ETAs and map route geometry."""

from __future__ import annotations

import asyncio

from services import routing


def test_travel_time_uses_local_fallback_when_external_routing_is_disabled(monkeypatch) -> None:
    routing._travel_time_cache.clear()
    monkeypatch.setenv("RAID_DISABLE_EXTERNAL_ROUTING", "1")

    async def fail_fetch(*_args, **_kwargs):
        raise AssertionError("external ETA routing should not be called")

    async def no_traffic(*_args, **_kwargs):
        return 1.0

    monkeypatch.setattr(routing, "_fetch_route_json", fail_fetch)
    monkeypatch.setattr(routing, "get_traffic_multiplier", no_traffic)

    eta = asyncio.run(routing.get_travel_time(28.614, 77.209, 28.5672, 77.21, city="Delhi"))

    assert eta > 0


def test_route_polyline_uses_road_geometry_when_eta_routing_is_disabled(monkeypatch) -> None:
    routing._polyline_cache.clear()
    monkeypatch.setenv("RAID_DISABLE_EXTERNAL_ROUTING", "1")
    monkeypatch.setenv("RAID_DISABLE_ROUTE_GEOMETRY", "0")
    calls = []

    async def fake_fetch(*_args, params, timeout_seconds):
        calls.append({"params": params, "timeout_seconds": timeout_seconds})
        return {
            "routes": [
                {
                    "geometry": {
                        "coordinates": [
                            [77.209, 28.614],
                            [77.2095, 28.6],
                            [77.21, 28.5672],
                        ],
                    },
                },
            ],
        }

    monkeypatch.setattr(routing, "_fetch_route_json", fake_fetch)

    route = asyncio.run(routing.get_route_polyline(28.614, 77.209, 28.5672, 77.21))

    assert route == [
        [28.614, 77.209],
        [28.6, 77.2095],
        [28.5672, 77.21],
    ]
    assert calls == [
        {
            "params": {"overview": "full", "geometries": "geojson", "annotations": "false"},
            "timeout_seconds": routing._ROUTE_GEOMETRY_TIMEOUT_SECONDS,
        },
    ]


def test_route_polyline_can_be_disabled_for_offline_mode(monkeypatch) -> None:
    routing._polyline_cache.clear()
    monkeypatch.setenv("RAID_DISABLE_ROUTE_GEOMETRY", "1")

    async def fail_fetch(*_args, **_kwargs):
        raise AssertionError("route geometry should not be called")

    monkeypatch.setattr(routing, "_fetch_route_json", fail_fetch)

    route = asyncio.run(routing.get_route_polyline(28.614, 77.209, 28.5672, 77.21))

    assert route == []

from __future__ import annotations

import asyncio
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from repositories.database import fetch_all, fetch_one
from services.geo_service import get_active_traffic_multiplier, score_route
from services.scoring_service import (
    evaluate_ambulance,
    evaluate_hospital,
    select_best_dispatch,
)
from services.nlp_triage import triage_incident


class DispatchState(TypedDict):
    incident_id: str
    patient_id: Optional[str]
    incident: Optional[dict]
    patient: Optional[dict]
    triage: Optional[dict]
    ambulance_candidates: list
    hospital_candidates: list
    route_data: Optional[dict]
    dispatch_plan: Optional[dict]
    error: Optional[str]


async def intake_node(state: DispatchState) -> dict[str, Any]:
    incident = await fetch_one("incidents", state["incident_id"])
    patient = None
    if state.get("patient_id"):
        patient = await fetch_one("patients", state["patient_id"])
    return {"incident": incident, "patient": patient}


async def triage_node(state: DispatchState) -> dict[str, Any]:
    complaint = (
        state["patient"]["chief_complaint"]
        if state.get("patient")
        else state["incident"]["description"]
    )
    sos = state["patient"]["sos_mode"] if state.get("patient") else False
    city = state["incident"].get("city") if state.get("incident") else None
    result = await triage_incident(complaint, city=city, sos_mode=sos)
    return {"triage": result}


async def ambulance_node(state: DispatchState) -> dict[str, Any]:
    ambulances = await fetch_all("ambulances")
    incident = state["incident"]
    city = incident["city"]
    eligible_ambulances = [
        ambulance
        for ambulance in ambulances
        if ambulance["city"] == city and ambulance["status"] in {"available", "at_hospital"}
    ]
    scored_results = await asyncio.gather(
        *[evaluate_ambulance(ambulance, incident) for ambulance in eligible_ambulances]
    )
    scored = [
        {**result, "_record": ambulance}
        for ambulance, result in zip(eligible_ambulances, scored_results, strict=False)
    ]
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {"ambulance_candidates": scored}


async def hospital_node(state: DispatchState) -> dict[str, Any]:
    hospitals = await fetch_all("hospitals")
    incident = state["incident"]
    patient = state.get("patient")
    city_hospitals = [hospital for hospital in hospitals if hospital["city"] == incident["city"]]
    scored_results = await asyncio.gather(
        *[
            evaluate_hospital(
                hospital,
                incident,
                patient,
                incident["location_lat"],
                incident["location_lng"],
                state.get("triage"),
            )
            for hospital in city_hospitals
        ]
    )
    scored = [
        {
            **result,
            "_record": hospital,
            "_patient": patient,
        }
        for hospital, result in zip(city_hospitals, scored_results, strict=False)
    ]
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {"hospital_candidates": scored}


async def route_node(state: DispatchState) -> dict[str, Any]:
    incident = state["incident"]
    best_amb = state["ambulance_candidates"][0] if state["ambulance_candidates"] else None
    best_hosp = state["hospital_candidates"][0] if state["hospital_candidates"] else None

    if not best_amb or not best_hosp:
        return {"route_data": {}}

    ambulance_record = best_amb["_record"]
    hospital_record = best_hosp["_record"]
    traffic_multiplier = get_active_traffic_multiplier(incident["city"])
    pickup_route = await score_route(
        ambulance_record["current_lat"],
        ambulance_record["current_lng"],
        incident["location_lat"],
        incident["location_lng"],
        traffic_multiplier,
        incident["city"],
    )
    hospital_route = await score_route(
        incident["location_lat"],
        incident["location_lng"],
        hospital_record["lat"],
        hospital_record["lng"],
        traffic_multiplier,
        incident["city"],
    )
    route = {
        "pickup_route": pickup_route,
        "hospital_route": hospital_route,
        "eta_minutes": round(
            pickup_route["travel_time_minutes"] + hospital_route["travel_time_minutes"],
            2,
        ),
        "distance_km": round(
            pickup_route["distance_km"] + hospital_route["distance_km"],
            3,
        ),
        "score": round(
            max(
                0.0,
                1.0
                - (
                    (
                        pickup_route["travel_time_minutes"]
                        + hospital_route["travel_time_minutes"]
                    )
                    / 45.0
                ),
            ),
            3,
        ),
    }
    return {"route_data": route}


async def allocate_node(state: DispatchState) -> dict[str, Any]:
    incident = dict(state["incident"] or {})
    patient = state.get("patient")
    if patient and not incident.get("patient_id"):
        incident["patient_id"] = patient["id"]

    ambulances = await fetch_all("ambulances")
    hospitals = await fetch_all("hospitals")
    plan = await select_best_dispatch(incident, ambulances, hospitals, patient, state.get("triage"))
    return {"dispatch_plan": plan}


async def explain_node(state: DispatchState) -> dict[str, Any]:
    from services.llm_service import generate_explanation
    plan = state.get('dispatch_plan')
    if not plan:
        return {'dispatch_plan': plan}

    text = await generate_explanation(
        incident=state.get('incident', {}),
        patient=state.get('patient'),
        ambulance_id=plan.get('ambulance_id', ''),
        hospital_id=plan.get('hospital_id', ''),
        eta_minutes=plan.get('eta_minutes', 0),
        ambulance_score=plan.get('ambulance_score', 0),
        hospital_score=plan.get('hospital_score', 0),
        final_score=plan.get('final_score', 0),
        rejected_hospitals=plan.get('rejected_hospitals', []),
    )
    plan['explanation_text'] = text
    return {"dispatch_plan": plan}


def build_dispatch_graph():
    graph = StateGraph(DispatchState)
    graph.add_node("intake", intake_node)
    graph.add_node("triage", triage_node)
    graph.add_node("ambulance", ambulance_node)
    graph.add_node("hospital", hospital_node)
    graph.add_node("route", route_node)
    graph.add_node("allocate", allocate_node)
    graph.add_node("explain", explain_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "triage")
    graph.add_edge("triage", "ambulance")
    graph.add_edge("ambulance", "hospital")
    graph.add_edge("hospital", "route")
    graph.add_edge("route", "allocate")
    graph.add_edge("allocate", "explain")
    graph.add_edge("explain", END)

    return graph.compile()


dispatch_graph = build_dispatch_graph()


async def run_dispatch_pipeline(incident_id: str, patient_id: Optional[str] = None):
    initial_state: DispatchState = {
        "incident_id": incident_id,
        "patient_id": patient_id,
        "incident": None,
        "patient": None,
        "triage": None,
        "ambulance_candidates": [],
        "hospital_candidates": [],
        "route_data": None,
        "dispatch_plan": None,
        "error": None,
    }
    result = await dispatch_graph.ainvoke(initial_state)
    return result["dispatch_plan"]

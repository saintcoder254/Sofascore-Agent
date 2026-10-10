import asyncio, time

class MatchAcquisitionEngine:
    """Build the evidence bundle and preserve explicit component-level failures."""
    def __init__(self, fusion):
        self.fusion = fusion

    async def enrich_event(self, event_id):
        p = self.fusion.primary
        base = {}
        errors = {}
        tasks = {
            "event": p.event(event_id),
            "statistics": p.event_statistics(event_id),
            "shotmap": p.event_shotmap(event_id),
            "incidents": p.event_incidents(event_id),
            "lineups": p.event_lineups(event_id),
            "h2h": p.event_h2h(event_id),
        }
        for key, task in tasks.items():
            try:
                value = await task
                base[key] = value if isinstance(value, dict) else {"error": "invalid_payload_type"}
                if base[key].get("error"):
                    errors[key] = str(base[key]["error"])
            except Exception as exc:
                base[key] = {"error": repr(exc)}
                errors[key] = repr(exc)

        event = base.get("event") or {}
        teams = [event.get("homeTeam") or {}, event.get("awayTeam") or {}]
        history = {}
        for side, team in zip(("home", "away"), teams):
            tid = team.get("id")
            if not tid:
                history[side] = {"events": [], "error": "missing_team_id"}
                errors["history_" + side] = "missing_team_id"
                continue
            pages = []
            page_errors = []
            for page in (0, 1):
                try:
                    result = await p.team_last_events(tid, page)
                    if isinstance(result, dict):
                        pages.append(result)
                        if result.get("error"):
                            page_errors.append(str(result["error"]))
                    else:
                        page_errors.append("invalid_payload_type")
                except Exception as exc:
                    pages.append({"events": [], "error": repr(exc)})
                    page_errors.append(repr(exc))
            history[side] = {"events": [e for x in pages for e in (x.get("events") or [])][:20]}
            if page_errors:
                history[side]["errors"] = page_errors
                errors["history_" + side] = page_errors
        base["history"] = history

        odds = {}
        for suffix in ("1", "2"):
            path = f"/event/{event_id}/odds/{suffix}"
            try:
                result = await p.get_json(path)
                odds[suffix] = result if isinstance(result, dict) else {"error": "invalid_payload_type"}
                if odds[suffix].get("error"):
                    errors["odds_" + suffix] = str(odds[suffix]["error"])
            except Exception as exc:
                odds[suffix] = {"error": repr(exc)}
                errors["odds_" + suffix] = repr(exc)
        base["odds"] = odds
        base["retrieved_at"] = time.time()
        base["acquisition_diagnostics"] = {
            "requested_event_id": str(event_id),
            "component_count": len(tasks) + 2,
            "error_count": len(errors),
            "errors": errors,
            "complete": not errors,
        }
        return base

    async def acquire(self, event_id):
        bundle = await self.enrich_event(event_id)
        try:
            bundle["verification"] = await self.fusion.verify_futbol24()
            bundle["final_results"] = await self.fusion.verify_final_results(bundle["verification"])
            observations = [{"source": "sofascore", "retrieved_at": bundle.get("retrieved_at", time.time()),
                             "payload": bundle.get("event") or {}}]
            event = bundle.get("event") or {}
            home = str((event.get("homeTeam") or {}).get("name") or "").strip().casefold()
            away = str((event.get("awayTeam") or {}).get("name") or "").strip().casefold()
            for source_payload in bundle["final_results"].get("sources", []) or []:
                source = str(source_payload.get("source") or "")
                for witness in source_payload.get("events", []) or []:
                    wh = str((witness.get("homeTeam") or {}).get("name") or "").strip().casefold()
                    wa = str((witness.get("awayTeam") or {}).get("name") or "").strip().casefold()
                    if home and away and home == wh and away == wa:
                        observations.append({"source": source,
                                             "retrieved_at": source_payload.get("retrieved_at", time.time()),
                                             "payload": witness})
            bundle["verification_diagnostics"] = {
                "required_independent_sources": 2,
                "matched_fixture_sources": sorted({o["source"] for o in observations if o.get("source") != "sofascore"}),
                "matched_fixture_source_count": len({o["source"] for o in observations if o.get("source") != "sofascore"}),
            }
            bundle["data_trust"] = self.fusion.trust_mesh.evaluate(observations, {"now": time.time()})
        except Exception as exc:
            bundle["verification"] = {"error": repr(exc), "events": []}
            bundle["data_trust"] = {"state": "QUARANTINED", "hard_blocks": ["TRUST_PIPELINE_ERROR"],
                                    "error": repr(exc)}
            bundle["verification_diagnostics"] = {"error": repr(exc), "matched_fixture_source_count": 0}
        return bundle

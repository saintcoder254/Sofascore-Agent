import asyncio, time, re, unicodedata

class MatchAcquisitionEngine:
    """Build the complete evidence bundle used by the UMIOS probability engine."""
    def __init__(self,fusion): self.fusion=fusion

    @staticmethod
    def _team_key(value):
        value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
        value = re.sub(r"\b(fc|sc|cf|afc|club|football|soccer)\b", " ", value)
        return re.sub(r"[^a-z0-9]", "", value)

    @classmethod
    def _same_team(cls, left, right):
        a, b = cls._team_key(left), cls._team_key(right)
        return bool(a and b and a == b)

    @classmethod
    def _same_fixture(cls, target, candidate):
        th, ta = (target.get("homeTeam") or {}).get("name"), (target.get("awayTeam") or {}).get("name")
        ch, ca = (candidate.get("homeTeam") or {}).get("name"), (candidate.get("awayTeam") or {}).get("name")
        return cls._same_team(th, ch) and cls._same_team(ta, ca)

    async def enrich_event(self,event_id):
        # Alternate-source IDs must never be passed to SofaScore endpoints.
        # Until FotMob payload normalization is qualified for every required
        # evidence section, preserve the raw evidence and fail the UMIOS gate.
        if str(event_id).startswith("fotmob:"):
            source_id = str(event_id).split(":", 1)[1]
            try:
                raw = await self.fusion.fotmob.match_details(source_id)
                bundle = self.fusion.fotmob.normalize_match_details(raw)
                # Team histories are fetched from the same provider using IDs
                # in the match-details response; no empty placeholder is treated as data.
                history = {}
                target_event = bundle.get("event") or {}
                for side in ("home", "away"):
                    team = target_event.get(side + "Team") or {}
                    team_id = team.get("id")
                    if not team_id:
                        history[side] = {"source": "fotmob", "events": [], "error": "FOTMOB_TEAM_ID_MISSING"}
                        continue
                    try:
                        team_payload = await self.fusion.fotmob.team_details(team_id)
                        history[side] = self.fusion.fotmob.normalize_team_history(team_payload, team_id)
                    except Exception as history_exc:
                        history[side] = {"source": "fotmob", "events": [], "error": "FOTMOB_TEAM_HISTORY_UNAVAILABLE",
                                         "detail": repr(history_exc)}
                bundle["history"] = history
                home_name = (target_event.get("homeTeam") or {}).get("name")
                away_name = (target_event.get("awayTeam") or {}).get("name")
                try:
                    odds = await self.fusion.fotmob.external_odds(home_name, away_name, target_event.get("date"))
                    bundle["odds"] = {"h2h": odds}
                except Exception as odds_exc:
                    bundle["odds"] = {"h2h": {"source": "the_odds_api", "markets": [],
                                                "error": "EXTERNAL_ODDS_UNAVAILABLE", "detail": repr(odds_exc),
                                                "retrieved_at": time.time()}}
                # The bundle remains blocked unless all hard requirements are met.
            except Exception as exc:
                now = time.time()
                return {
                    "event": {"id": str(event_id), "source": "fotmob",
                              "source_event_id": source_id, "normalization_state": "UNQUALIFIED",
                              "error": repr(exc)},
                    "statistics": {"error": "FOTMOB_ACQUISITION_FAILED"},
                    "shotmap": {"error": "FOTMOB_ACQUISITION_FAILED"},
                    "incidents": {"error": "FOTMOB_ACQUISITION_FAILED"},
                    "lineups": {"error": "FOTMOB_ACQUISITION_FAILED"},
                    "h2h": {"error": "FOTMOB_ACQUISITION_FAILED"},
                    "history": {"home": {"events": []}, "away": {"events": []}},
                    "odds": {"1": {"error": "FOTMOB_ACQUISITION_FAILED"},
                             "2": {"error": "FOTMOB_ACQUISITION_FAILED"}},
                    "verification": {"events": [], "error": "INDEPENDENT_VERIFICATION_REQUIRED"},
                    "final_results": {"sources": []},
                    "data_trust": {"state": "QUARANTINED",
                                   "hard_blocks": ["FOTMOB_ACQUISITION_FAILED"]},
                    "retrieved_at": now,
                }
            try:
                verification = await self.fusion.verify_futbol24()
                final_results = await self.fusion.verify_final_results(verification)
                bundle["verification"] = verification
                bundle["final_results"] = final_results
                event = bundle.get("event") or {}
                eh = str((event.get("homeTeam") or {}).get("name") or "").strip().lower()
                ea = str((event.get("awayTeam") or {}).get("name") or "").strip().lower()
                observations = [{"source": "fotmob",
                                 "retrieved_at": bundle.get("retrieved_at", time.time()),
                                 "payload": event}]
                verified_matches = []
                for source_payload in final_results.get("sources", []) or []:
                    source = str(source_payload.get("source") or "")
                    if source == "fotmob":
                        continue  # never count the same provider as independent verification
                    for candidate in source_payload.get("events", []) or []:
                        if self._same_fixture(event, candidate):
                            verified_matches.append((source, source_payload, candidate))
                            observations.append({"source": source,
                                                 "retrieved_at": source_payload.get("retrieved_at", time.time()),
                                                 "payload": candidate})
                bundle["verification"] = {
                    "events": [candidate for _, _, candidate in verified_matches],
                    "sources": sorted({source for source, _, _ in verified_matches}),
                    "retrieved_at": time.time(),
                    **({"error": "INDEPENDENT_FIXTURE_MATCH_NOT_FOUND"} if not verified_matches else {}),
                }
                # Remove only blockers whose required evidence is now actually present.
                blocks = list((bundle.get("data_trust") or {}).get("hard_blocks", []))
                if verified_matches:
                    blocks = [b for b in blocks if b != "ALTERNATE_SOURCE_EVIDENCE_REQUIRES_INDEPENDENT_VERIFICATION"]
                histories = bundle.get("history") or {}
                if all((histories.get(side) or {}).get("events") for side in ("home", "away")):
                    blocks = [b for b in blocks if b != "FOTMOB_TEAM_HISTORY_UNAVAILABLE"]
                odds_bundle = bundle.get("odds") or {}
                if any(m.get("markets") for m in odds_bundle.values() if isinstance(m, dict)):
                    blocks = [b for b in blocks if b != "FOTMOB_MARKET_ODDS_UNAVAILABLE"]
                trust = self.fusion.trust_mesh.evaluate(observations, {"now": time.time()})
                trust.setdefault("hard_blocks", [])
                for block in blocks:
                    if block not in trust["hard_blocks"]:
                        trust["hard_blocks"].append(block)
                trust["state"] = "QUARANTINED" if trust["hard_blocks"] else trust.get("state", "QUARANTINED")
                bundle["data_trust"] = trust
            except Exception as exc:
                bundle["verification"] = {"events": [], "error": repr(exc)}
                bundle["data_trust"] = {"state": "QUARANTINED",
                                        "hard_blocks": ["TRUST_PIPELINE_ERROR"],
                                        "error": repr(exc)}
            return bundle
        p=self.fusion.primary
        base={}
        tasks={
            "event":p.event(event_id),"statistics":p.event_statistics(event_id),
            "shotmap":p.event_shotmap(event_id),"incidents":p.event_incidents(event_id),
            "lineups":p.event_lineups(event_id),"h2h":p.event_h2h(event_id),
        }
        for key,task in tasks.items():
            try: base[key]=await task
            except Exception as exc: base[key]={"error":repr(exc)}
        event=base.get("event") or {}
        teams=[event.get("homeTeam") or {},event.get("awayTeam") or {}]
        history={}
        for side,team in zip(("home","away"),teams):
            tid=team.get("id")
            if not tid: history[side]={"events":[],"error":"missing_team_id"}; continue
            try:
                pages=[]
                for page in (0,1):
                    try: pages.append(await p.team_last_events(tid,page))
                    except Exception as exc: pages.append({"events":[],"error":repr(exc)})
                history[side]={"events":[e for x in pages for e in (x.get("events") or [])][:20]}
            except Exception as exc: history[side]={"events":[],"error":repr(exc)}
        base["history"]=history
        odds={}
        for path in (f"/event/{event_id}/odds/1",f"/event/{event_id}/odds/2"):
            try: odds[path.rsplit("/",1)[-1]]=await p.get_json(path)
            except Exception as exc: odds[path.rsplit("/",1)[-1]]={"error":repr(exc)}
        base["odds"]=odds;base["retrieved_at"]=time.time()
        return base

    async def acquire(self,event_id):
        bundle=await self.enrich_event(event_id)
        # FotMob acquisition already performs independent fixture verification and
        # builds its own trust envelope. Do not overwrite that gate with the
        # generic SofaScore path, which can mislabel the source and drop blockers.
        if str(event_id).startswith("fotmob:"):
            return bundle
        try:
            bundle["verification"]=await self.fusion.verify_futbol24()
            bundle["final_results"]=await self.fusion.verify_final_results(bundle["verification"])
            observations=[{"source":"sofascore","retrieved_at":bundle.get("retrieved_at",time.time()),"payload":bundle.get("event") or {}}]
            for source_payload in bundle["final_results"].get("sources",[]) or []:
                source=str(source_payload.get("source") or "")
                for event in source_payload.get("events",[]) or []:
                    eh=str((bundle.get("event") or {}).get("homeTeam",{}).get("name","")).strip().lower()
                    ea=str((bundle.get("event") or {}).get("awayTeam",{}).get("name","")).strip().lower()
                    wh=str((event.get("homeTeam") or {}).get("name","")).strip().lower()
                    wa=str((event.get("awayTeam") or {}).get("name","")).strip().lower()
                    if eh and ea and eh==wh and ea==wa:
                        observations.append({"source":source,"retrieved_at":source_payload.get("retrieved_at",time.time()),"payload":event})
            bundle["data_trust"]=self.fusion.trust_mesh.evaluate(observations,{"now":time.time()})
        except Exception as exc:
            bundle["verification"]={"error":repr(exc)}
            bundle["data_trust"]={"state":"QUARANTINED","hard_blocks":["TRUST_PIPELINE_ERROR"],"error":repr(exc)}
        return bundle

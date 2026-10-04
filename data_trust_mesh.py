"""OMEGA Data Trust Mesh v1.

Deterministic multi-agent data-integrity layer. It does not invent values or
silently choose a convenient source. Every synthesis decision is accompanied
by provenance, freshness, completeness, conflict, consensus, and quarantine
signals.
"""
import hashlib
import json
import math
import time
from collections import defaultdict

class TrustAgent:
    name = "base"
    def run(self, bundle, context):
        raise NotImplementedError

class ProvenanceAgent(TrustAgent):
    name = "provenance"
    def run(self, bundle, context):
        observations = bundle.get("observations") or []
        valid, invalid = [], []
        for o in observations:
            source = str(o.get("source") or "").strip()
            payload = o.get("payload")
            retrieved = o.get("retrieved_at")
            if not source or payload is None or retrieved is None:
                invalid.append({"source": source or None, "reason": "MISSING_PROVENANCE"})
                continue
            try:
                ts = float(retrieved)
                if not math.isfinite(ts):
                    raise ValueError
            except (TypeError, ValueError):
                invalid.append({"source": source, "reason": "INVALID_RETRIEVED_AT"})
                continue
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
            valid.append({**o, "payload_hash": hashlib.sha256(canonical.encode()).hexdigest()})
        return {"state": "PASS" if valid and not invalid else ("CAUTION" if valid else "BLOCK"),
                "valid": valid, "invalid": invalid}

class FreshnessAgent(TrustAgent):
    name = "freshness"
    def __init__(self, max_age_seconds=180):
        self.max_age = float(max_age_seconds)
    def run(self, bundle, context):
        now = float(context.get("now") or time.time())
        rows = []
        for o in bundle.get("observations") or []:
            try: age = max(0.0, now - float(o["retrieved_at"]))
            except (KeyError, TypeError, ValueError): age = float("inf")
            rows.append({"source": o.get("source"), "age_seconds": age, "fresh": age <= self.max_age})
        fresh = [x for x in rows if x["fresh"]]
        return {"state": "PASS" if fresh else "BLOCK", "max_age_seconds": self.max_age,
                "observations": rows, "fresh_sources": [x["source"] for x in fresh]}

class CompletenessAgent(TrustAgent):
    name = "completeness"
    def run(self, bundle, context):
        results = []
        for o in bundle.get("observations") or []:
            p = o.get("payload") or {}
            home = (p.get("homeTeam") or {}).get("name")
            away = (p.get("awayTeam") or {}).get("name")
            results.append({"source": o.get("source"), "home": bool(home), "away": bool(away),
                            "complete_identity": bool(home and away)})
        good = [x for x in results if x["complete_identity"]]
        return {"state": "PASS" if good else "BLOCK", "observations": results,
                "complete_sources": [x["source"] for x in good]}

class ConflictAgent(TrustAgent):
    name = "conflict"
    CRITICAL = ("home", "away", "status", "home_score", "away_score")
    def _value(self, payload, field):
        event = payload or {}
        if field == "home": return (event.get("homeTeam") or {}).get("name")
        if field == "away": return (event.get("awayTeam") or {}).get("name")
        if field == "home_score": return (event.get("homeTeam") or {}).get("score")
        if field == "away_score": return (event.get("awayTeam") or {}).get("score")
        if field == "status": return ((event.get("status") or {}).get("type") or {}).get("state")
        if field == "kickoff": return event.get("startTimestamp") or event.get("timestamp") or event.get("date")
        return None
    @staticmethod
    def _norm(v):
        return None if v is None else str(v).strip().lower()
    def run(self, bundle, context):
        conflicts = []
        for field in self.CRITICAL:
            values = defaultdict(list)
            for o in bundle.get("observations") or []:
                v = self._value(o.get("payload"), field)
                if v is not None: values[self._norm(v)].append(o.get("source"))
            if len(values) > 1:
                conflicts.append({"field": field, "values": dict(values)})
        return {"state": "BLOCK" if conflicts else "PASS", "conflicts": conflicts}

class ConsensusAgent(TrustAgent):
    name = "consensus"
    DEFAULT_WEIGHTS = {"sofascore":1.00,"espn":0.95,"fotmob":0.95,"futbol24":0.90,"scores24":0.60}
    def __init__(self, min_independent_sources=2, weights=None):
        self.minimum = max(2, int(min_independent_sources))
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
    def run(self, bundle, context):
        sources = {str(o.get("source")) for o in bundle.get("observations") or [] if o.get("source")}
        votes, result_sources = defaultdict(float), defaultdict(set)
        for o in bundle.get("observations") or []:
            p = o.get("payload") or {}
            h, a = (p.get("homeTeam") or {}).get("score"), (p.get("awayTeam") or {}).get("score")
            if h is None or a is None: continue
            try: h, a = int(float(h)), int(float(a))
            except (TypeError, ValueError): continue
            result = "HOME" if h > a else "AWAY" if h < a else "DRAW"
            src = str(o.get("source"))
            votes[result] += self.weights.get(src, 0.50)
            result_sources[result].add(src)
        candidates = [{"result":k,"weighted_support":round(v,4),
                       "independent_sources":sorted(result_sources[k]),
                       "source_count":len(result_sources[k])} for k,v in votes.items()]
        candidates.sort(key=lambda x:(-x["source_count"],-x["weighted_support"],x["result"]))
        winner = candidates[0] if candidates else None
        if winner:
            state = "PASS" if winner["source_count"] >= self.minimum else "BLOCK"
            mode = "RESULT_CONSENSUS"
        else:
            identities=set()
            for o in bundle.get("observations") or []:
                p=o.get("payload") or {}
                h=(p.get("homeTeam") or {}).get("name")
                a=(p.get("awayTeam") or {}).get("name")
                if h and a:
                    identities.add((str(h).strip().lower(),str(a).strip().lower()))
            state = "PASS" if len(identities)==1 and len(sources) >= self.minimum else "BLOCK"
            mode = "IDENTITY_CONSENSUS"
        return {"state":state,"mode":mode,"required_sources":self.minimum,"available_sources":sorted(sources),
                "candidates":candidates,"winner":winner}

class AnomalyAgent(TrustAgent):
    name = "anomaly"
    def run(self, bundle, context):
        anomalies = []
        for o in bundle.get("observations") or []:
            p = o.get("payload") or {}
            for side in ("homeTeam","awayTeam"):
                score = (p.get(side) or {}).get("score")
                if score is None: continue
                try:
                    n = int(float(score))
                    if n < 0 or n > 30: raise ValueError
                except (TypeError, ValueError):
                    anomalies.append({"source":o.get("source"),"field":side+".score","value":score})
        return {"state":"BLOCK" if anomalies else "PASS","anomalies":anomalies}

class SynthesisAgent(TrustAgent):
    name = "synthesis"
    def run(self, bundle, context):
        obs = bundle.get("observations") or []
        fields, conflicts = {}, []
        getters = {
            "home":lambda p:(p.get("homeTeam") or {}).get("name"),
            "away":lambda p:(p.get("awayTeam") or {}).get("name"),
            "home_score":lambda p:(p.get("homeTeam") or {}).get("score"),
            "away_score":lambda p:(p.get("awayTeam") or {}).get("score"),
            "status":lambda p:((p.get("status") or {}).get("type") or {}).get("state"),
            "kickoff":lambda p:p.get("startTimestamp") or p.get("timestamp") or p.get("date"),
        }
        for field,getter in getters.items():
            vals=[(str(o.get("source")),getter(o.get("payload") or {})) for o in obs]
            vals=[x for x in vals if x[1] is not None]
            if not vals: continue
            groups=defaultdict(list)
            for src,v in vals: groups[str(v).strip().lower()].append((src,v))
            if len(groups)==1: fields[field]=vals[0][1]
            else: conflicts.append({"field":field,"values":{k:[x[0] for x in v] for k,v in groups.items()}})
        hard_conflicts=[x for x in conflicts if x.get("field")!="kickoff"]
        state="PASS" if fields and not hard_conflicts else ("BLOCK" if hard_conflicts else "CAUTION")
        return {"state":state,"canonical":fields,"conflicts":conflicts,"hard_conflicts":hard_conflicts}

class DataTrustMesh:
    VERSION="OMEGA-DATA-TRUST-MESH-v1"
    def __init__(self,max_age_seconds=180,min_independent_sources=2,source_weights=None):
        self.agents=[ProvenanceAgent(),FreshnessAgent(max_age_seconds),CompletenessAgent(),
                     ConflictAgent(),ConsensusAgent(min_independent_sources,source_weights),
                     AnomalyAgent(),SynthesisAgent()]
    def evaluate(self,observations,context=None):
        context=dict(context or {}); context.setdefault("now",time.time())
        bundle={"observations":list(observations or [])}; reports={}
        for agent in self.agents: reports[agent.name]=agent.run(bundle,context)
        hard=[]
        for name in ("provenance","freshness","completeness","conflict","anomaly"):
            if reports[name]["state"]=="BLOCK": hard.append(name.upper()+"_BLOCK")
        if reports["consensus"]["state"]=="BLOCK": hard.append("CONSENSUS_BLOCK")
        if reports["synthesis"]["state"]=="BLOCK": hard.append("SYNTHESIS_BLOCK")
        state="QUARANTINED" if hard else ("TRUSTED" if reports["consensus"]["state"]=="PASS" and reports["synthesis"]["state"]=="PASS" else "CAUTION")
        valid=reports["provenance"]["valid"]
        envelope={"version":self.VERSION,"state":state,"hard_blocks":hard,
                  "canonical":reports["synthesis"].get("canonical",{}),
                  "consensus":reports["consensus"],"reports":reports,
                  "provenance":[{"source":o.get("source"),"retrieved_at":o.get("retrieved_at"),
                                 "payload_hash":v["payload_hash"]} for o,v in zip(bundle["observations"],valid)],
                  "evaluated_at":context["now"]}
        envelope["envelope_hash"]=hashlib.sha256(json.dumps(envelope,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
        return envelope

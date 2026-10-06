"""Real-corpus brute-force runner for Basketball OMEGA.

Downloads a public historical NBA betting SQLite release at runtime. It does
not commit the raw corpus. Prediction-time team statistics are restricted to
records dated strictly before the game date. The repository walk-forward
trainer, evaluator, and promotion gate remain authoritative.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, subprocess, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path

DB_URL = "https://github.com/NBA-Betting/NBA_Betting/releases/download/v0.1.0-pre/nba_betting_database.zip"
DB_SHA256 = "c0f0bfc0a7dc6a98fad7f2b40670b861a8c4483a66b69aea86a57955946ca97e"
MIN_OOS = 250

def ts(value):
    s=str(value).replace("Z","+00:00")
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()

def download(url, dest):
    subprocess.run(["curl","-L","--fail","--retry","5","--retry-delay","2","-o",str(dest),url],check=True)

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def latest_team_state(conn, team, game_date):
    row=conn.execute("""
      SELECT off_rating, def_rating, pace
      FROM team_nbastats_general_advanced
      WHERE team_name=? AND to_date < ?
      ORDER BY to_date DESC LIMIT 1
    """,(team,game_date)).fetchone()
    if not row: return None
    return {"ortg":float(row[0] or 110.0),"drtg":float(row[1] or 110.0),
            "pace":float(row[2] or 99.0)}

def build_examples(db):
    from basketball_omega.historical_dataset import BasketballTrainingExample
    conn=sqlite3.connect(db)
    rows=conn.execute("""
      SELECT g.game_id,g.game_datetime,g.home_team,g.away_team,g.open_line,
             g.home_score,g.away_score,l.current_line,l.line_last_update
      FROM games g LEFT JOIN lines l ON l.game_id=g.game_id
      WHERE g.game_completed=1 AND g.home_score IS NOT NULL
        AND g.away_score IS NOT NULL
      ORDER BY g.game_datetime,g.game_id
    """).fetchall()
    examples=[]; skipped=0; closing_count=0
    for gid,gdt,home,away,open_line,hs,as_,close_line,close_ts in rows:
        if not gdt: skipped+=1; continue
        game_ts=ts(gdt); game_date=str(gdt)[:10]
        h=latest_team_state(conn,home,game_date)
        a=latest_team_state(conn,away,game_date)
        if not h or not a: skipped+=1; continue
        markets=[]
        if open_line is not None:
            markets.append({"market":"spread","line":float(open_line),"price":-110,
                            "side":"home","source":"NBA_Betting_release",
                            "is_opening":True,"is_closing":False})
        if close_line is not None and close_ts:
            try:
                if ts(close_ts) <= game_ts:
                    markets.append({"market":"spread","line":float(close_line),"price":-110,
                                    "side":"home","source":"NBA_Betting_release",
                                    "is_opening":False,"is_closing":True})
                    closing_count+=1
            except Exception: pass
        examples.append(BasketballTrainingExample(
            fixture_id=str(gid),cutoff_at=game_ts-1.0,
            home_team_id=str(home),away_team_id=str(away),
            features={"teams":{str(home):h,str(away):a},"players":{},"lineups":[],
                      "markets":markets,"context":{"source":"NBA_Betting_release",
                      "pit_date":game_date}},
            target_home_win=int(float(hs)>float(as_)),
            target_margin=float(hs)-float(as_),
            target_total=float(hs)+float(as_),
            outcome_at=game_ts+1.0))
    conn.close()
    return examples, {"source_games":len(rows),"usable_examples":len(examples),
                      "skipped":skipped,"closing_line_rows":closing_count}

def baseline_report(rows):
    from basketball_omega.evaluation import EvaluationReport
    import math
    rows=[r for r in rows if r.entry_spread is not None]
    if not rows:
        return EvaluationReport(0,math.inf,math.inf,math.inf,math.inf,math.inf,0,0,10,True)
    def market_prob(r):
        if r.entry_spread is None:
            return 0.5
        z=max(-35.0,min(35.0,-float(r.entry_spread)/7.0))
        return 1.0/(1.0+math.exp(-z))
    b=sum((market_prob(r)-r.actual_home_win)**2 for r in rows)/len(rows)
    ll=-sum(r.actual_home_win*math.log(max(market_prob(r),1e-12))+
            (1-r.actual_home_win)*math.log(max(1-market_prob(r),1e-12)) for r in rows)/len(rows)
    mm=sum(abs((-float(r.entry_spread) if r.entry_spread is not None else 0.0)-r.actual_margin) for r in rows)/len(rows)
    tt=sum(abs(220.0-r.actual_total) for r in rows)/len(rows)
    ece=0.0
    for bidx in range(10):
        lo=bidx/10; hi=(bidx+1)/10
        group=[r for r in rows if lo <= market_prob(r) < hi or (bidx==9 and market_prob(r)==1)]
        if group:
            conf=sum(market_prob(r) for r in group)/len(group)
            acc=sum(r.actual_home_win for r in group)/len(group)
            ece += len(group)/len(rows)*abs(conf-acc)
    return EvaluationReport(len(rows),b,ll,ece,mm,tt,0.0,0,10,True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="artifacts/basketball_bruteforce_report.json")
    ap.add_argument("--min-train",type=int,default=250)
    args=ap.parse_args()
    from basketball_omega.agents.walk_forward import BasketballWalkForwardTrainer
    from basketball_omega.evaluation import evaluate,report_dict
    from basketball_omega.promotion import WalkForwardPromotionGate
    from basketball_omega.promotion_markets import MarketPromotionGate
    from basketball_omega.clv import verify_clv

    with tempfile.TemporaryDirectory() as td:
        z=Path(td)/"nba_betting_database.zip"
        download(DB_URL,z)
        digest=sha256(z)
        if digest != DB_SHA256:
            raise RuntimeError(f"corpus_checksum_mismatch:{digest}")
        with zipfile.ZipFile(z) as archive:
            names=[n for n in archive.namelist() if n.endswith(".db")]
            if not names: raise RuntimeError("no_sqlite_database_in_release")
            archive.extract(names[0],td)
            db=Path(td)/names[0]
        examples,coverage=build_examples(db)
        if len(examples) < args.min_train + MIN_OOS:
            raise RuntimeError(f"insufficient_real_corpus:{len(examples)}")
        trainer=BasketballWalkForwardTrainer(min_train=args.min_train)
        rows=trainer.run(examples)
        # Candidate and market baseline must share the identical PIT/OOS fixture set.
        rows=[r for r in rows if r.entry_spread is not None]
        if len(rows) < MIN_OOS:
            raise RuntimeError(f"insufficient_oos_rows:{len(rows)}")
        candidate=evaluate(rows)
        baseline=baseline_report(rows)
        decision=WalkForwardPromotionGate(min_samples=MIN_OOS,min_clv=0.0).evaluate(baseline,candidate)
        market_gate=MarketPromotionGate(min_samples=MIN_OOS,require_clv=True,min_clv=0.0)
        spread_decision=market_gate.evaluate_spread(baseline,candidate)
        totals_decision=market_gate.evaluate_totals(baseline,candidate)
        clv=verify_clv(rows,source="NBA_Betting_release",min_samples=MIN_OOS)
        payload={"status":"PROMOTED" if decision.eligible else "RESEARCH_NO_BET",
                 "corpus":{"url":DB_URL,"sha256":digest,"expected_sha256":DB_SHA256,
                           "coverage":coverage},
                 "walk_forward":{"min_train":args.min_train,"oos_rows":len(rows),
                                 "chronological":candidate.chronological},
                 "baseline":report_dict(baseline),"candidate":report_dict(candidate),
                 "promotion":{"eligible":decision.eligible,
                              "reasons":list(decision.reasons),
                              "required_samples":decision.required_samples},
                 "market_promotion":{
                     "spread":{"eligible":spread_decision.eligible,"reasons":list(spread_decision.reasons),
                               "samples":spread_decision.samples},
                     "totals":{"eligible":totals_decision.eligible,"reasons":list(totals_decision.reasons),
                               "samples":totals_decision.samples},
                     "clv":{"status":clv.status,"samples":clv.samples,"mean_clv":clv.mean_clv,
                            "source":clv.source},
                     "production_eligible":{
                         "spread":spread_decision.eligible and clv.status=="VERIFIED",
                         "totals":totals_decision.eligible and clv.status=="VERIFIED"
                     }
                 }}
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2,sort_keys=True))
    print(json.dumps(payload,indent=2,sort_keys=True))
    if not decision.eligible:
        raise SystemExit(2)

if __name__=="__main__":
    main()

# Basketball OMEGA Source Mesh

The source mesh is intentionally redundant.

Primary: NBA Stats through nba_api. Official player, team, game and play-by-play endpoints are available; PBP v3 is preferred over deprecated PBP v2.

Historical archive: shufinskiy/nba_data, which provides multi-source PBP and shot data from 1996/97 onward and matchup data from 2017/18 onward.

Independent cross-check: Basketball-Reference acquisition for game/PBP evidence.

Adapters are transport-injected, so production HTTP headers, proxies, caching and local archival can be added without contaminating the mathematical model.

Source hierarchy is evidence weighting, not permission to silently overwrite disagreement. Conflicts remain auditable and are surfaced to reconciliation.

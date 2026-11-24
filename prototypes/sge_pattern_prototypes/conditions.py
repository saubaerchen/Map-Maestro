"""PROTOTYPE — throwaway. Conditional pattern mining: when does a player / the team change position or plan?

For each map+side, every measurable condition is tested against each outcome with Fisher's exact test.
Player outcomes  : player's zone at first contact (early rounds, first kill <= 35s), 'forward' (attacker space on CT)
Team outcomes    : CT 3+ stack in a zone; T plant site / no plant
Conditions       : own weapon (sniper / Operator), teammate has Operator, SGE buy type, ENEMY buy type,
                   enemy has a sniper, after win/loss, leading/trailing, half, agent played,
                   previous round on this side planted X / failed or succeeded hit on X
"""
import os
import re
import sys
from collections import Counter, defaultdict

from scipy.stats import fisher_exact

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from lib.constants import AGENT_MAP  # noqa: E402

AGENTS = {k.lower(): v for k, v in AGENT_MAP.items()}
EARLY = 35
FORWARD = re.compile(r"(Lobby|Main|T Spawn)")
PLAYERS = ["azury", "musashi", "Fizzy", "foe", "H1ber"]
MIN_IN, MIN_OUT, MIN_EFFECT, MAX_P = 3, 3, 0.30, 0.15


def round_conditions(r):
    c = {}
    c[f"SGE {r['tier']} buy"] = True
    c[f"enemy {r['oppTier']} buy"] = True
    c["enemy has a sniper"] = r["oppSnipers"] > 0
    if r["ctx"] != "pistol":
        c[r["ctx"]] = True
    s, o = r["scoreBefore"]
    c["SGE leading" if s > o else ("SGE trailing" if s < o else "score tied")] = True
    c[f"{r['half']} half"] = True
    ops = [p for p, w in r["weapons"].items() if w == "Operator"]
    c["SGE have an Operator"] = bool(ops)
    if r["prevPlant"]:
        side_word = "attackers planted" if r["side"] == "CT" else "SGE planted"
        c[f"previous round: {side_word} {r['prevPlant']}"] = True
        if r["side"] == "T":
            c[f"after a {'successful' if r['prevSameSideWon'] else 'failed'} {r['prevPlant']} hit"] = True
    if r["prevSameSideWon"] is not None:
        c["lost previous round on this side" if not r["prevSameSideWon"] else "won previous round on this side"] = True
    return {k for k, v in c.items() if v}


def player_conditions(r, p):
    c = set()
    if r["wcat"].get(p) == "Sniper":
        c.add(f"{p} has a sniper")
    if r["weapons"].get(p) == "Operator":
        c.add(f"{p} has the Operator")
    if any(w == "Operator" for q, w in r["weapons"].items() if q != p):
        c.add("a teammate has the Operator")
    if r["wcat"].get(p) in ("SMG", "Shotgun"):
        c.add(f"{p} on SMG/shotgun")
    ag = AGENTS.get((r["agents"].get(p) or "").lower())
    if ag:
        c.add(f"{p} on {ag}")
    return c


ALL_P = []


def test(rounds, outcome, conds_of, subject):
    """rounds: list; outcome(r)->bool|None; conds_of(r)->set."""
    rs = [r for r in rounds if outcome(r) is not None]
    keys = [f"{r['matchId']}|{r['round']}" for r in rs]
    allc = Counter(c for r in rs for c in conds_of(r))
    found = []
    for c, n_in in allc.items():
        inn = [r for r in rs if c in conds_of(r)]
        out = [r for r in rs if c not in conds_of(r)]
        if len(inn) < MIN_IN or len(out) < MIN_OUT:
            continue
        a = sum(1 for r in inn if outcome(r))
        b = sum(1 for r in out if outcome(r))
        si, so = a / len(inn), b / len(out)
        p = fisher_exact([[a, len(inn) - a], [b, len(out) - b]])[1]
        inkeys = frozenset(f"{r['matchId']}|{r['round']}" for r in inn)
        part = min(tuple(sorted(inkeys)), tuple(sorted(set(keys) - inkeys)))
        ALL_P.append({"p": p, "key": (subject, part)})
        if abs(si - so) < MIN_EFFECT or (a < 2 and si > so):
            continue
        if p > MAX_P:
            continue
        found.append({"subject": subject, "cond": c, "inN": len(inn), "inHit": a, "outN": len(out), "outHit": b,
                      "effect": round(si - so, 2), "p": round(p, 3),
                      "rounds": [f"{r['matchId']}|{r['round']}" for r in inn], "part": part})
    return found


def mine(data):
    findings = []
    R = data["rounds"]
    for mp in data["maps"]:
        for side in ("CT", "T"):
            rs = [r for r in R if r["map"] == mp and r["side"] == side]
            early = [r for r in rs if r["snap"] and r["fkT"] is not None and r["fkT"] <= EARLY]
            # player zones
            for p in PLAYERS:
                pr = [r for r in early if any(s["p"] == p for s in r["snap"])]
                zone = {id(r): next(s for s in r["snap"] if s["p"] == p) for r in pr}
                zones = Counter(zone[id(r)]["zone"] for r in pr)
                cond = lambda r, p=p: round_conditions(r) | player_conditions(r, p)
                for z, n in zones.items():
                    if n < 2 or z.endswith("Spawn"):
                        continue
                    for f in test(pr, lambda r, z=z: zone[id(r)]["zone"] == z, cond, f"{p} plays {z}"):
                        f.update(map=mp, side=side, player=p, kind="player-zone", zone=z)
                        findings.append(f)
                if side == "CT":
                    for f in test(pr, lambda r: bool(FORWARD.search(zone[id(r)]["call"])), cond, f"{p} plays forward (attacker space)"):
                        f.update(map=mp, side=side, player=p, kind="player-forward")
                        findings.append(f)
            # team outcomes
            if side == "CT":
                for z in ("A", "B", "C", "Mid"):
                    stack = lambda r, z=z: sum(1 for s in r["snap"] if s["zone"] == z) >= 3
                    if sum(1 for r in early if stack(r)) < 2:
                        continue
                    for f in test(early, stack, round_conditions, f"SGE stack {z} (3+ players)"):
                        f.update(map=mp, side=side, player=None, kind="team-stack", zone=z)
                        findings.append(f)
            else:
                for site in ("A", "B", "C"):
                    if sum(1 for r in rs if r["plantSite"] == site) < 2:
                        continue
                    for f in test(rs, lambda r, s=site: (r["plantSite"] == s) if r["plantSite"] else None, round_conditions, f"SGE plant {site} (of planted rounds)"):
                        f.update(map=mp, side=side, player=None, kind="team-plant", zone=site)
                        findings.append(f)
                rep = lambda r: (r["plantSite"] == r["prevPlant"]) if (r["plantSite"] and r["prevPlant"]) else None
                for f in test(rs, rep, round_conditions, "SGE hit the same site as their previous T round"):
                    f.update(map=mp, side=side, player=None, kind="team-repeat")
                    findings.append(f)
                for f in test(rs, lambda r: r["plantSite"] is None, round_conditions, "SGE don't plant"):
                    f.update(map=mp, side=side, player=None, kind="team-noplant")
                    findings.append(f)
    # de-duplicate mirror findings (e.g. 'after win' vs 'after loss' on the same outcome): keep lower p
    best = {}
    for f in findings:
        k = (f["map"], f["side"], f["subject"], f["part"])
        if k not in best or len(f["cond"]) < len(best[k]["cond"]):
            best[k] = f
    uniq = {}
    for t in ALL_P:
        uniq.setdefault(t["key"], t["p"])
    ps = sorted(uniq.values())
    m = len(ps)
    def qval(p):
        rank = sum(1 for x in ps if x <= p)
        return min(1.0, p * m / max(rank, 1))
    out = sorted(best.values(), key=lambda f: (f["p"], -abs(f["effect"])))
    for f in out:
        f["q"] = round(qval(f["p"]), 3)
        del f["part"]
    print(f"unique tests run: {m}")
    for f in out:
        si, so = f["inHit"] / f["inN"], f["outHit"] / f["outN"]
        f["strength"] = "strong" if f["q"] <= 0.10 else ("lean" if f["p"] <= 0.05 else "weak")
        verb = "much more" if f["effect"] > 0 else "much less"
        f["text"] = (f"{f['subject']} {verb} when {f['cond']}: {f['inHit']}/{f['inN']} ({round(si*100)}%) "
                     f"vs {f['outHit']}/{f['outN']} ({round(so*100)}%) otherwise")
    return out


def themes(F):
    """Findings that corroborate each other: same map+side+condition, 2+ subjects, same zone/plan direction."""
    groups = defaultdict(list)
    for f in F:
        if f["p"] > 0.1:
            continue
        cond = f["cond"].replace("won previous round on this side", "after win").replace("lost previous round on this side", "after loss")
        tgt = f.get("zone") or f["kind"]
        groups[(f["map"], f["side"], cond, tgt, f["effect"] > 0)].append(f)
    out = []
    for (mp, side, cond, tgt, up), fs in groups.items():
        subj = sorted({f["player"] or "team" for f in fs})
        if len(subj) < 2:
            continue
        rounds = sorted({k for f in fs for k in f["rounds"]})
        label = tgt if len(tgt) <= 3 else tgt.replace("player-", "").replace("team-", "")
        out.append({"map": mp, "side": side, "cond": cond, "target": tgt, "up": up, "subjects": subj,
                    "minP": min(f["p"] for f in fs), "rounds": rounds,
                    "text": (f"{mp} {side}: when {cond}, {', '.join(subj)} play forward {'more' if up else 'less'}" if label == "forward" else
                             f"{mp} {side}: when {cond}, {', '.join(subj)} {'move toward' if up else 'move away from'} {label}"),
                    "items": [f["text"] for f in fs]})
    return sorted(out, key=lambda t: (-len(t["subjects"]), t["minP"]))


if __name__ == "__main__":
    from compute import compute
    data = compute()
    F = mine(data)
    print(f"{len(F)} findings ({sum(f['strength']=='strong' for f in F)} strong)\n")
    for f in F[:60]:
        print(f"[{f['strength']:6} p={f['p']:.3f}] {f['map']:7} {f['side']:2} | {f['text']}")

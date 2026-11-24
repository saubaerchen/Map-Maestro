import sys

SRC = r"C:\Users\Vincent\Claude\DataRead_Claude\veto-history-site\extra-data.js"
PUB = r"C:\Users\Vincent\Claude\DataRead_Claude\veto-history-site-publish\extra-data.js"

BAR_MARCH = """      {
        "date": "2026-03-21",
        "opponent": "FOKUS",
        "opponentAbbr": "FKS",
        "score": "1 - 2",
        "source": "https://liquipedia.net/valorant/Match:ID_dPQ6IbYwd5_0003",
        "decider": "Split",
        "deciderScore": "8:13",
        "ban1":  { "map": "Corrode", "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" },
        "ban2":  { "map": "Haven",   "type": "ban",  "ownerLabel": "FKS", "ownerKind": "opp" },
        "pick1": { "map": "Bind",    "type": "pick", "ownerLabel": "BAR", "ownerKind": "team", "score": "13:11" },
        "pick2": { "map": "Pearl",   "type": "pick", "ownerLabel": "FKS", "ownerKind": "opp",  "score": "14:12" },
        "ban3":  { "map": "Abyss",   "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" },
        "ban4":  { "map": "Breeze",  "type": "ban",  "ownerLabel": "FKS", "ownerKind": "opp" }
      },
      {
        "date": "2026-03-19",
        "opponent": "Enterprise Esports",
        "opponentAbbr": "EP",
        "score": "0 - 2",
        "source": "https://liquipedia.net/valorant/Match:ID_dPQ6IbYwd5_0001",
        "decider": "Split",
        "deciderScore": "",
        "ban1":  { "map": "Breeze",  "type": "ban",  "ownerLabel": "EP",  "ownerKind": "opp" },
        "ban2":  { "map": "Corrode", "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" },
        "pick1": { "map": "Pearl",   "type": "pick", "ownerLabel": "EP",  "ownerKind": "opp",  "score": "14:12" },
        "pick2": { "map": "Bind",    "type": "pick", "ownerLabel": "BAR", "ownerKind": "team", "score": "2:13" },
        "ban3":  { "map": "Haven",   "type": "ban",  "ownerLabel": "EP",  "ownerKind": "opp" },
        "ban4":  { "map": "Abyss",   "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" }
      },
      {
        "date": "2026-03-08",
        "opponent": "DNSTY",
        "opponentAbbr": "DNSTY",
        "score": "3 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_75el8yRLvz_R02-M001",
        "decider": "Corrode",
        "deciderScore": "",
        "ban1":  { "map": "Abyss",   "type": "ban",  "ownerLabel": "BAR",   "ownerKind": "team" },
        "ban2":  { "map": "Bind",    "type": "ban",  "ownerLabel": "DNSTY", "ownerKind": "opp" },
        "pick1": { "map": "Split",   "type": "pick", "ownerLabel": "BAR",   "ownerKind": "team", "score": "13:15" },
        "pick2": { "map": "Breeze",  "type": "pick", "ownerLabel": "DNSTY", "ownerKind": "opp",  "score": "5:13" },
        "ban3":  { "map": "Pearl",   "type": "pick", "ownerLabel": "BAR",   "ownerKind": "team", "score": "13:6" },
        "ban4":  { "map": "Haven",   "type": "pick", "ownerLabel": "DNSTY", "ownerKind": "opp",  "score": "2:13" }
      }
"""

UCAM_MARCH = """      {
        "date": "2026-03-28",
        "opponent": "Mandatory",
        "opponentAbbr": "MDR",
        "score": "2 - 3",
        "source": "https://liquipedia.net/valorant/Match:ID_FniMAeAZDq_R02-M002",
        "decider": "Pearl",
        "deciderScore": "4:13",
        "ban1":  { "map": "Breeze",  "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" },
        "ban2":  { "map": "Bind",    "type": "ban",  "ownerLabel": "MDR",  "ownerKind": "opp" },
        "pick1": { "map": "Abyss",   "type": "pick", "ownerLabel": "UCAM", "ownerKind": "team", "score": "13:11" },
        "pick2": { "map": "Haven",   "type": "pick", "ownerLabel": "MDR",  "ownerKind": "opp",  "score": "13:7" },
        "ban3":  { "map": "Split",   "type": "pick", "ownerLabel": "UCAM", "ownerKind": "team", "score": "13:3" },
        "ban4":  { "map": "Corrode", "type": "pick", "ownerLabel": "MDR",  "ownerKind": "opp",  "score": "15:13" }
      },
      {
        "date": "2026-03-27",
        "opponent": "Enterprise Esports",
        "opponentAbbr": "EP",
        "score": "0 - 2",
        "source": "https://liquipedia.net/valorant/Match:ID_FniMAeAZDq_R02-M001",
        "decider": "Bind",
        "deciderScore": "",
        "ban1":  { "map": "Corrode", "type": "ban",  "ownerLabel": "EP",   "ownerKind": "opp" },
        "ban2":  { "map": "Pearl",   "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" },
        "pick1": { "map": "Split",   "type": "pick", "ownerLabel": "EP",   "ownerKind": "opp",  "score": "17:15" },
        "pick2": { "map": "Abyss",   "type": "pick", "ownerLabel": "UCAM", "ownerKind": "team", "score": "17:19" },
        "ban3":  { "map": "Haven",   "type": "ban",  "ownerLabel": "EP",   "ownerKind": "opp" },
        "ban4":  { "map": "Breeze",  "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" }
      },
      {
        "date": "2026-03-26",
        "opponent": "Mandatory",
        "opponentAbbr": "MDR",
        "score": "2 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_FniMAeAZDq_R01-M001",
        "decider": "Pearl",
        "deciderScore": "13:11",
        "ban1":  { "map": "Abyss",   "type": "ban",  "ownerLabel": "MDR",  "ownerKind": "opp" },
        "ban2":  { "map": "Breeze",  "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" },
        "pick1": { "map": "Corrode", "type": "pick", "ownerLabel": "MDR",  "ownerKind": "opp",  "score": "13:11" },
        "pick2": { "map": "Bind",    "type": "pick", "ownerLabel": "UCAM", "ownerKind": "team", "score": "13:4" },
        "ban3":  { "map": "Split",   "type": "ban",  "ownerLabel": "MDR",  "ownerKind": "opp" },
        "ban4":  { "map": "Haven",   "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" }
      }
"""

RB_MARCH = """      {
        "date": "2026-03-23",
        "opponent": "GNG Amazigh",
        "opponentAbbr": "GNG",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_7cRRYOaFhA_0006",
        "decider": "Corrode",
        "deciderScore": "",
        "ban1":  { "map": "Bind",    "type": "ban",  "ownerLabel": "RB",  "ownerKind": "team" },
        "ban2":  { "map": "Breeze",  "type": "ban",  "ownerLabel": "GNG", "ownerKind": "opp" },
        "pick1": { "map": "Split",   "type": "pick", "ownerLabel": "RB",  "ownerKind": "team", "score": "13:7" },
        "pick2": { "map": "Haven",   "type": "pick", "ownerLabel": "GNG", "ownerKind": "opp",  "score": "6:13" },
        "ban3":  { "map": "Pearl",   "type": "ban",  "ownerLabel": "RB",  "ownerKind": "team" },
        "ban4":  { "map": "Abyss",   "type": "ban",  "ownerLabel": "GNG", "ownerKind": "opp" }
      },
      {
        "date": "2026-03-22",
        "opponent": "Mandatory",
        "opponentAbbr": "MDR",
        "score": "0 - 2",
        "source": "https://liquipedia.net/valorant/Match:ID_7cRRYOaFhA_0004",
        "decider": "Corrode",
        "deciderScore": "",
        "ban1":  { "map": "Haven",   "type": "ban",  "ownerLabel": "RB",  "ownerKind": "team" },
        "ban2":  { "map": "Split",   "type": "ban",  "ownerLabel": "MDR", "ownerKind": "opp" },
        "pick1": { "map": "Breeze",  "type": "pick", "ownerLabel": "RB",  "ownerKind": "team", "score": "8:13" },
        "pick2": { "map": "Pearl",   "type": "pick", "ownerLabel": "MDR", "ownerKind": "opp",  "score": "13:10" },
        "ban3":  { "map": "Abyss",   "type": "ban",  "ownerLabel": "RB",  "ownerKind": "team" },
        "ban4":  { "map": "Bind",    "type": "ban",  "ownerLabel": "MDR", "ownerKind": "opp" }
      },
      {
        "date": "2026-03-20",
        "opponent": "MIR",
        "opponentAbbr": "M1R",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_7cRRYOaFhA_0002",
        "decider": "Haven",
        "deciderScore": "",
        "ban1":  { "map": "Abyss",   "type": "ban",  "ownerLabel": "RB",  "ownerKind": "team" },
        "ban2":  { "map": "Corrode", "type": "ban",  "ownerLabel": "M1R", "ownerKind": "opp" },
        "pick1": { "map": "Split",   "type": "pick", "ownerLabel": "RB",  "ownerKind": "team", "score": "13:0" },
        "pick2": { "map": "Bind",    "type": "pick", "ownerLabel": "M1R", "ownerKind": "opp",  "score": "7:13" },
        "ban3":  { "map": "Pearl",   "type": "ban",  "ownerLabel": "RB",  "ownerKind": "team" },
        "ban4":  { "map": "Breeze",  "type": "ban",  "ownerLabel": "M1R", "ownerKind": "opp" }
      }
"""

BAR_ANCHOR_OLD = '        "ban4":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" }\n      }\n    ]\n  },\n  "besiktas":'
BAR_ANCHOR_NEW = '        "ban4":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" }\n      },\n' + BAR_MARCH + '    ]\n  },\n  "besiktas":'

UCAM_ANCHOR_OLD = '        "ban4":  { "map": "Fracture", "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" }\n      }\n    ]\n  }\n};'
UCAM_ANCHOR_NEW = '        "ban4":  { "map": "Fracture", "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" }\n      },\n' + UCAM_MARCH + '    ]\n  }\n};'

RB_ANCHOR_OLD = '        "ban4":  { "map": "Split",    "type": "ban",  "ownerLabel": "BJK",  "ownerKind": "team" }\n      }\n    ]\n  },\n  "reborn":'
RB_ANCHOR_NEW = '        "ban4":  { "map": "Split",    "type": "ban",  "ownerLabel": "BJK",  "ownerKind": "team" }\n      }\n    ]\n  },\n  "reborn":'

def patch(content, path):
    changed = False

    new = content.replace(BAR_ANCHOR_OLD, BAR_ANCHOR_NEW)
    if new != content:
        content = new
        print(f"  BAR march entries added")
        changed = True
    else:
        print(f"  WARNING: BAR anchor not found in {path}")

    new = content.replace(UCAM_ANCHOR_OLD, UCAM_ANCHOR_NEW)
    if new != content:
        content = new
        print(f"  UCAM march entries added")
        changed = True
    else:
        print(f"  WARNING: UCAM anchor not found in {path}")

    rb_end_marker = '        "ban4":  { "map": "Fracture", "type": "ban",  "ownerLabel": "RB",  "ownerKind": "team" }\n      }\n    ]\n  },\n  "ucam":'
    rb_end_new = '        "ban4":  { "map": "Fracture", "type": "ban",  "ownerLabel": "RB",  "ownerKind": "team" }\n      },\n' + RB_MARCH + '    ]\n  },\n  "ucam":'
    rb_end_marker2 = '        "ban4":  { "map": "Bind",     "type": "ban",  "ownerLabel": "FUT", "ownerKind": "opp" }\n      }\n    ]\n  },\n  "ucam":'
    rb_end_new2 = '        "ban4":  { "map": "Bind",     "type": "ban",  "ownerLabel": "FUT", "ownerKind": "opp" }\n      },\n' + RB_MARCH + '    ]\n  },\n  "ucam":'
    new = content.replace(rb_end_marker, rb_end_new)
    if new != content:
        content = new
        print(f"  REBORN march entries added")
        changed = True
    else:
        new = content.replace(rb_end_marker2, rb_end_new2)
        if new != content:
            content = new
            print(f"  REBORN march entries added (alt anchor)")
            changed = True
        else:
            print(f"  WARNING: REBORN anchor not found in {path}")

    return content, changed

for path in [SRC, PUB]:
    print(f"\n{path}")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    patched, changed = patch(content, path)
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(patched)
        print(f"  Written OK")
    else:
        print(f"  No changes written")

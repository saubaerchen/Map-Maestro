import re, sys

SRC = r"C:\Users\Vincent\Claude\DataRead_Claude\veto-history-site\extra-data.js"
PUB = r"C:\Users\Vincent\Claude\DataRead_Claude\veto-history-site-publish\extra-data.js"

WIP_NEW = """      {
        "date": "2026-05-05",
        "opponent": "Mandatory",
        "opponentAbbr": "MDR",
        "score": "3 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_pMaVC3y83m_R02-M002",
        "decider": "Split",
        "deciderScore": "",
        "ban1":  { "map": "Bind",     "type": "ban",  "ownerLabel": "MDR", "ownerKind": "opp" },
        "ban2":  { "map": "Haven",    "type": "ban",  "ownerLabel": "WIP", "ownerKind": "team" },
        "pick1": { "map": "Pearl",    "type": "pick", "ownerLabel": "MDR", "ownerKind": "opp",  "score": "10:13" },
        "pick2": { "map": "Fracture", "type": "pick", "ownerLabel": "WIP", "ownerKind": "team", "score": "13:11" },
        "ban3":  { "map": "Breeze",   "type": "pick", "ownerLabel": "MDR", "ownerKind": "opp",  "score": "13:10" },
        "ban4":  { "map": "Lotus",    "type": "pick", "ownerLabel": "WIP", "ownerKind": "team", "score": "13:7" }
      },
      {
        "date": "2026-05-04",
        "opponent": "F9 EICAR",
        "opponentAbbr": "F9",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_pMaVC3y83m_R01-M003",
        "decider": "Pearl",
        "deciderScore": "",
        "ban1":  { "map": "Haven",    "type": "ban",  "ownerLabel": "WIP", "ownerKind": "team" },
        "ban2":  { "map": "Fracture", "type": "ban",  "ownerLabel": "F9",  "ownerKind": "opp" },
        "pick1": { "map": "Lotus",    "type": "pick", "ownerLabel": "WIP", "ownerKind": "team", "score": "13:7" },
        "pick2": { "map": "Split",    "type": "pick", "ownerLabel": "F9",  "ownerKind": "opp",  "score": "7:13" },
        "ban3":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "WIP", "ownerKind": "team" },
        "ban4":  { "map": "Bind",     "type": "ban",  "ownerLabel": "F9",  "ownerKind": "opp" }
      },
      {
        "date": "2026-05-03",
        "opponent": "JOBlife",
        "opponentAbbr": "JL",
        "score": "1 - 2",
        "source": "https://liquipedia.net/valorant/Match:ID_pMaVC3y83m_R01-M001",
        "decider": "Lotus",
        "deciderScore": "7:13",
        "ban1":  { "map": "Fracture", "type": "ban",  "ownerLabel": "JL",  "ownerKind": "opp" },
        "ban2":  { "map": "Haven",    "type": "ban",  "ownerLabel": "WIP", "ownerKind": "team" },
        "pick1": { "map": "Split",    "type": "pick", "ownerLabel": "JL",  "ownerKind": "opp",  "score": "13:10" },
        "pick2": { "map": "Bind",     "type": "pick", "ownerLabel": "WIP", "ownerKind": "team", "score": "13:8" },
        "ban3":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "JL",  "ownerKind": "opp" },
        "ban4":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "WIP", "ownerKind": "team" }
      },
"""

JL_NEW = """      {
        "date": "2026-05-04",
        "opponent": "Mandatory",
        "opponentAbbr": "MDR",
        "score": "2 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_pMaVC3y83m_R02-M001",
        "decider": "Pearl",
        "deciderScore": "13:8",
        "ban1":  { "map": "Bind",     "type": "ban",  "ownerLabel": "MDR", "ownerKind": "opp" },
        "ban2":  { "map": "Fracture", "type": "ban",  "ownerLabel": "JL",  "ownerKind": "team" },
        "pick1": { "map": "Haven",    "type": "pick", "ownerLabel": "MDR", "ownerKind": "opp",  "score": "13:6" },
        "pick2": { "map": "Split",    "type": "pick", "ownerLabel": "JL",  "ownerKind": "team", "score": "13:6" },
        "ban3":  { "map": "Lotus",    "type": "ban",  "ownerLabel": "MDR", "ownerKind": "opp" },
        "ban4":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "JL",  "ownerKind": "team" }
      },
      {
        "date": "2026-05-03",
        "opponent": "WIP Esports",
        "opponentAbbr": "WIP",
        "score": "2 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_pMaVC3y83m_R01-M001",
        "decider": "Lotus",
        "deciderScore": "13:7",
        "ban1":  { "map": "Fracture", "type": "ban",  "ownerLabel": "JL",  "ownerKind": "team" },
        "ban2":  { "map": "Haven",    "type": "ban",  "ownerLabel": "WIP", "ownerKind": "opp" },
        "pick1": { "map": "Split",    "type": "pick", "ownerLabel": "JL",  "ownerKind": "team", "score": "13:10" },
        "pick2": { "map": "Bind",     "type": "pick", "ownerLabel": "WIP", "ownerKind": "opp",  "score": "13:8" },
        "ban3":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "JL",  "ownerKind": "team" },
        "ban4":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "WIP", "ownerKind": "opp" }
      },
"""

MIR_NEW = """      {
        "date": "2026-04-21",
        "opponent": "Enterprise Esports",
        "opponentAbbr": "EP",
        "score": "2 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_7KMRtUcQ7H_R02-M001",
        "decider": "Pearl",
        "deciderScore": "13:10",
        "ban1":  { "map": "Bind",     "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "ban2":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "EP",  "ownerKind": "opp" },
        "pick1": { "map": "Lotus",    "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "13:11" },
        "pick2": { "map": "Split",    "type": "pick", "ownerLabel": "EP",  "ownerKind": "opp",  "score": "13:6" },
        "ban3":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "ban4":  { "map": "Fracture", "type": "ban",  "ownerLabel": "EP",  "ownerKind": "opp" }
      },
      {
        "date": "2026-04-18",
        "opponent": "Formulation Gaming",
        "opponentAbbr": "FMG",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_7KMRtUcQ7H_R01-M002",
        "decider": "Pearl",
        "deciderScore": "",
        "ban1":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "FMG", "ownerKind": "opp" },
        "ban2":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "pick1": { "map": "Lotus",    "type": "pick", "ownerLabel": "FMG", "ownerKind": "opp",  "score": "11:13" },
        "pick2": { "map": "Fracture", "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "13:6" },
        "ban3":  { "map": "Bind",     "type": "ban",  "ownerLabel": "FMG", "ownerKind": "opp" },
        "ban4":  { "map": "Split",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" }
      },
      {
        "date": "2026-04-14",
        "opponent": "UNIWAY",
        "opponentAbbr": "UNI",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_KzQvKhMGrg_0006",
        "decider": "Fracture",
        "deciderScore": "",
        "ban1":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "UNI", "ownerKind": "opp" },
        "ban2":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "pick1": { "map": "Breeze",   "type": "pick", "ownerLabel": "UNI", "ownerKind": "opp",  "score": "6:13" },
        "pick2": { "map": "Lotus",    "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "13:4" },
        "ban3":  { "map": "Bind",     "type": "ban",  "ownerLabel": "UNI", "ownerKind": "opp" },
        "ban4":  { "map": "Split",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" }
      },
      {
        "date": "2026-04-13",
        "opponent": "XtremeDogs",
        "opponentAbbr": "XTD",
        "score": "2 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_AvOtgduD7A_0007",
        "decider": "Fracture",
        "deciderScore": "16:14",
        "ban1":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "XTD", "ownerKind": "opp" },
        "ban2":  { "map": "Bind",     "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "pick1": { "map": "Lotus",    "type": "pick", "ownerLabel": "XTD", "ownerKind": "opp",  "score": "8:13" },
        "pick2": { "map": "Split",    "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "9:13" },
        "ban3":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "XTD", "ownerKind": "opp" },
        "ban4":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" }
      },
      {
        "date": "2026-04-12",
        "opponent": "EVOPLAY",
        "opponentAbbr": "EVO",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_0NHnGt7KPB_0006",
        "decider": "Split",
        "deciderScore": "",
        "ban1":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "ban2":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "EVO", "ownerKind": "opp" },
        "pick1": { "map": "Fracture", "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "15:13" },
        "pick2": { "map": "Lotus",    "type": "pick", "ownerLabel": "EVO", "ownerKind": "opp",  "score": "5:13" },
        "ban3":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "ban4":  { "map": "Bind",     "type": "ban",  "ownerLabel": "EVO", "ownerKind": "opp" }
      },
      {
        "date": "2026-04-11",
        "opponent": "VR2",
        "opponentAbbr": "VR2",
        "score": "0 - 2",
        "source": "https://liquipedia.net/valorant/Match:ID_r5QdOJP1qt_0007",
        "decider": "Fracture",
        "deciderScore": "",
        "ban1":  { "map": "Split",    "type": "ban",  "ownerLabel": "VR2", "ownerKind": "opp" },
        "ban2":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "pick1": { "map": "Lotus",    "type": "pick", "ownerLabel": "VR2", "ownerKind": "opp",  "score": "13:10" },
        "pick2": { "map": "Breeze",   "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "3:13" },
        "ban3":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "VR2", "ownerKind": "opp" },
        "ban4":  { "map": "Bind",     "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" }
      },
      {
        "date": "2026-04-06",
        "opponent": "Full Box 200",
        "opponentAbbr": "FB2",
        "score": "2 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_cmadtfcavE_0005",
        "decider": "Lotus",
        "deciderScore": "13:5",
        "ban1":  { "map": "Fracture", "type": "ban",  "ownerLabel": "FB2", "ownerKind": "opp" },
        "ban2":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "pick1": { "map": "Pearl",    "type": "pick", "ownerLabel": "FB2", "ownerKind": "opp",  "score": "13:3" },
        "pick2": { "map": "Breeze",   "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "13:3" },
        "ban3":  { "map": "Split",    "type": "ban",  "ownerLabel": "FB2", "ownerKind": "opp" },
        "ban4":  { "map": "Bind",     "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" }
      },
      {
        "date": "2026-04-05",
        "opponent": "Bitfix Gaming",
        "opponentAbbr": "BFG",
        "score": "0 - 2",
        "source": "https://liquipedia.net/valorant/Match:ID_mN8xJkH8LA_0008",
        "decider": "Lotus",
        "deciderScore": "",
        "ban1":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "ban2":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "BFG", "ownerKind": "opp" },
        "pick1": { "map": "Fracture", "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "4:13" },
        "pick2": { "map": "Bind",     "type": "pick", "ownerLabel": "BFG", "ownerKind": "opp",  "score": "13:8" },
        "ban3":  { "map": "Split",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "ban4":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "BFG", "ownerKind": "opp" }
      },
      {
        "date": "2026-04-04",
        "opponent": "Team Liquid Academy",
        "opponentAbbr": "TL",
        "score": "2 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_CKFczx07Yi_0005",
        "decider": "Fracture",
        "deciderScore": "13:7",
        "ban1":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "ban2":  { "map": "Bind",     "type": "ban",  "ownerLabel": "TL",  "ownerKind": "opp" },
        "pick1": { "map": "Lotus",    "type": "pick", "ownerLabel": "M1R", "ownerKind": "team", "score": "1:13" },
        "pick2": { "map": "Split",    "type": "pick", "ownerLabel": "TL",  "ownerKind": "opp",  "score": "8:13" },
        "ban3":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" },
        "ban4":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "TL",  "ownerKind": "opp" }
      },
"""

BAR_NEW = """      {
        "date": "2026-05-12",
        "opponent": "UCAM Esports",
        "opponentAbbr": "UCAM",
        "score": "1 - 3",
        "source": "https://liquipedia.net/valorant/Match:ID_60rzdJJTdK_R06-M001",
        "decider": "Pearl",
        "deciderScore": "",
        "ban1":  { "map": "Haven",    "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "opp" },
        "ban2":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "BAR",  "ownerKind": "team" },
        "pick1": { "map": "Lotus",    "type": "pick", "ownerLabel": "UCAM", "ownerKind": "opp",  "score": "13:9" },
        "pick2": { "map": "Fracture", "type": "pick", "ownerLabel": "BAR",  "ownerKind": "team", "score": "9:13" },
        "ban3":  { "map": "Bind",     "type": "pick", "ownerLabel": "UCAM", "ownerKind": "opp",  "score": "13:11" },
        "ban4":  { "map": "Split",    "type": "pick", "ownerLabel": "BAR",  "ownerKind": "team", "score": "9:13" }
      },
      {
        "date": "2026-05-11",
        "opponent": "Otakar Esports",
        "opponentAbbr": "OTK",
        "score": "3 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_60rzdJJTdK_R05-M002",
        "decider": "Split",
        "deciderScore": "",
        "ban1":  { "map": "Lotus",    "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" },
        "ban2":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "OTK", "ownerKind": "opp" },
        "pick1": { "map": "Bind",     "type": "pick", "ownerLabel": "BAR", "ownerKind": "team", "score": "13:10" },
        "pick2": { "map": "Haven",    "type": "pick", "ownerLabel": "OTK", "ownerKind": "opp",  "score": "4:13" },
        "ban3":  { "map": "Fracture", "type": "pick", "ownerLabel": "BAR", "ownerKind": "team", "score": "13:8" },
        "ban4":  { "map": "Breeze",   "type": "pick", "ownerLabel": "OTK", "ownerKind": "opp" }
      },
      {
        "date": "2026-05-05",
        "opponent": "Ramboot Club",
        "opponentAbbr": "RBT",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_60rzdJJTdK_R04-M001",
        "decider": "Split",
        "deciderScore": "",
        "ban1":  { "map": "Lotus",    "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" },
        "ban2":  { "map": "Bind",     "type": "ban",  "ownerLabel": "RBT", "ownerKind": "opp" },
        "pick1": { "map": "Fracture", "type": "pick", "ownerLabel": "BAR", "ownerKind": "team", "score": "13:4" },
        "pick2": { "map": "Pearl",    "type": "pick", "ownerLabel": "RBT", "ownerKind": "opp",  "score": "5:13" },
        "ban3":  { "map": "Haven",    "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" },
        "ban4":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "RBT", "ownerKind": "opp" }
      },
      {
        "date": "2026-05-04",
        "opponent": "Falke Esports",
        "opponentAbbr": "FLK",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_60rzdJJTdK_R03-M004",
        "decider": "Fracture",
        "deciderScore": "",
        "ban1":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "FLK", "ownerKind": "opp" },
        "ban2":  { "map": "Lotus",    "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" },
        "pick1": { "map": "Haven",    "type": "pick", "ownerLabel": "FLK", "ownerKind": "opp",  "score": "11:13" },
        "pick2": { "map": "Bind",     "type": "pick", "ownerLabel": "BAR", "ownerKind": "team", "score": "13:11" },
        "ban3":  { "map": "Split",    "type": "ban",  "ownerLabel": "FLK", "ownerKind": "opp" },
        "ban4":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "BAR", "ownerKind": "team" }
      },
"""

BJK_NEW = """      {
        "date": "2026-05-04",
        "opponent": "Misa Esports",
        "opponentAbbr": "MISA",
        "score": "3 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_X5I9feP7vq_R04-M002",
        "decider": "Breeze",
        "deciderScore": "",
        "ban1":  { "map": "Haven",    "type": "ban",  "ownerLabel": "BJK",  "ownerKind": "team" },
        "ban2":  { "map": "Fracture", "type": "ban",  "ownerLabel": "MISA", "ownerKind": "opp" },
        "pick1": { "map": "Bind",     "type": "pick", "ownerLabel": "BJK",  "ownerKind": "team", "score": "13:1" },
        "pick2": { "map": "Split",    "type": "pick", "ownerLabel": "MISA", "ownerKind": "opp",  "score": "13:2" },
        "ban3":  { "map": "Lotus",    "type": "pick", "ownerLabel": "BJK",  "ownerKind": "team", "score": "13:8" },
        "ban4":  { "map": "Pearl",    "type": "pick", "ownerLabel": "MISA", "ownerKind": "opp",  "score": "11:13" }
      },
      {
        "date": "2026-05-03",
        "opponent": "REBORN",
        "opponentAbbr": "RBN",
        "score": "1 - 2",
        "source": "https://liquipedia.net/valorant/Match:ID_X5I9feP7vq_R04-M001",
        "decider": "Breeze",
        "deciderScore": "8:13",
        "ban1":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "RBN", "ownerKind": "opp" },
        "ban2":  { "map": "Haven",    "type": "ban",  "ownerLabel": "BJK", "ownerKind": "team" },
        "pick1": { "map": "Split",    "type": "pick", "ownerLabel": "RBN", "ownerKind": "opp",  "score": "13:5" },
        "pick2": { "map": "Lotus",    "type": "pick", "ownerLabel": "BJK", "ownerKind": "team", "score": "17:15" },
        "ban3":  { "map": "Bind",     "type": "ban",  "ownerLabel": "RBN", "ownerKind": "opp" },
        "ban4":  { "map": "Fracture", "type": "ban",  "ownerLabel": "BJK", "ownerKind": "team" }
      },
"""

UCAM_NEW = """      {
        "date": "2026-05-12",
        "opponent": "Barça eSports",
        "opponentAbbr": "BAR",
        "score": "3 - 1",
        "source": "https://liquipedia.net/valorant/Match:ID_60rzdJJTdK_R06-M001",
        "decider": "Pearl",
        "deciderScore": "",
        "ban1":  { "map": "Haven",    "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" },
        "ban2":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "BAR",  "ownerKind": "opp" },
        "pick1": { "map": "Lotus",    "type": "pick", "ownerLabel": "UCAM", "ownerKind": "team", "score": "13:9" },
        "pick2": { "map": "Fracture", "type": "pick", "ownerLabel": "BAR",  "ownerKind": "opp",  "score": "9:13" },
        "ban3":  { "map": "Bind",     "type": "pick", "ownerLabel": "UCAM", "ownerKind": "team", "score": "11:13" },
        "ban4":  { "map": "Split",    "type": "pick", "ownerLabel": "BAR",  "ownerKind": "opp",  "score": "9:13" }
      },
      {
        "date": "2026-05-03",
        "opponent": "Otakar Esports",
        "opponentAbbr": "OTK",
        "score": "2 - 0",
        "source": "https://liquipedia.net/valorant/Match:ID_60rzdJJTdK_R05-M001",
        "decider": "Haven",
        "deciderScore": "",
        "ban1":  { "map": "Breeze",   "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" },
        "ban2":  { "map": "Pearl",    "type": "ban",  "ownerLabel": "OTK",  "ownerKind": "opp" },
        "pick1": { "map": "Bind",     "type": "pick", "ownerLabel": "UCAM", "ownerKind": "team", "score": "13:4" },
        "pick2": { "map": "Split",    "type": "pick", "ownerLabel": "OTK",  "ownerKind": "opp",  "score": "4:13" },
        "ban3":  { "map": "Fracture", "type": "ban",  "ownerLabel": "UCAM", "ownerKind": "team" },
        "ban4":  { "map": "Lotus",    "type": "ban",  "ownerLabel": "OTK",  "ownerKind": "opp" }
      },
"""

def patch(content):
    content = content.replace(
        '        "ban4":  { "map": "Breeze",   "type": "pick", "ownerLabel": "WIP", "ownerKind": "team", "score": "1:13" }\n      },\n      {\n        "date": "2026-04-26",\n        "opponent": "Caldya Esport",',
        '        "ban4":  { "map": "Breeze",   "type": "pick", "ownerLabel": "WIP", "ownerKind": "team", "score": "1:13" }\n      },\n' + WIP_NEW + '      {\n        "date": "2026-04-26",\n        "opponent": "Caldya Esport",'
    )

    content = content.replace(
        '        "ban4":  { "map": "Bind",     "type": "ban",  "ownerLabel": "JL",  "ownerKind": "team" }\n      },\n      {\n        "date": "2026-04-26",\n        "opponent": "Mandatory",',
        '        "ban4":  { "map": "Bind",     "type": "ban",  "ownerLabel": "JL",  "ownerKind": "team" }\n      },\n' + JL_NEW + '      {\n        "date": "2026-04-26",\n        "opponent": "Mandatory",'
    )

    content = content.replace(
        '        "ban4":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" }\n      }\n    ]\n  },\n  "barcelona":',
        '        "ban4":  { "map": "Haven",    "type": "ban",  "ownerLabel": "M1R", "ownerKind": "team" }\n      },\n' + MIR_NEW + '    ]\n  },\n  "barcelona":'
    )

    content = content.replace(
        '  "barcelona": {\n    "name": "Barça eSports",\n    "ownerLabel": "BAR",\n    "subtitle": "2026 veto history",\n    "rows": [\n      {\n        "date": "2026-04-28",',
        '  "barcelona": {\n    "name": "Barça eSports",\n    "ownerLabel": "BAR",\n    "subtitle": "2026 veto history",\n    "rows": [\n' + BAR_NEW + '      {\n        "date": "2026-04-28",'
    )

    content = content.replace(
        '  "besiktas": {\n    "name": "Beşiktaş Esports",\n    "ownerLabel": "BJK",\n    "subtitle": "2026 veto history",\n    "rows": [\n      {\n        "date": "2026-04-13",',
        '  "besiktas": {\n    "name": "Beşiktaş Esports",\n    "ownerLabel": "BJK",\n    "subtitle": "2026 veto history",\n    "rows": [\n' + BJK_NEW + '      {\n        "date": "2026-04-13",'
    )

    content = content.replace(
        '  "ucam": {\n    "name": "UCAM Esports",\n    "ownerLabel": "UCAM",\n    "subtitle": "2026 veto history",\n    "rows": [\n      {\n        "date": "2026-04-28",',
        '  "ucam": {\n    "name": "UCAM Esports",\n    "ownerLabel": "UCAM",\n    "subtitle": "2026 veto history",\n    "rows": [\n' + UCAM_NEW + '      {\n        "date": "2026-04-28",'
    )

    return content

for path in [SRC, PUB]:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    patched = patch(content)
    if patched == content:
        print(f"WARNING: No changes made to {path} - check anchors!")
        sys.exit(1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(patched)
    print(f"OK: {path}")

print("Done. Verify match counts:")
for path in [PUB]:
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    for team in ["wip", "joblife", "mir", "barcelona", "besiktas", "ucam"]:
        import re
        n = len(re.findall(r'"date":', c[c.find(f'"{team}"'):c.find(f'"{team}"')+50000]))
        print(f"  {team}: {n} entries")

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.constants import OPERATOR_UUID
from lib.stats_engine import get_team_side_per_round

ANALYSIS_DIR = ROOT / "data" / "analysis"
OUTPUT_FILE = ROOT / "veto-history-site-publish" / "defensive-early-data.js"
SGE_RAW_FILE = ROOT / "data" / "raw" / "sge_2026_raw_responses.jsonl"
FKS_RAW_FILE = ROOT / "data" / "raw" / "fks_2026_raw_responses.jsonl"
RZN_RAW_FILE = ROOT / "data" / "raw" / "rzn_2026_raw_responses.jsonl"
EP_RAW_FILE  = ROOT / "data" / "raw" / "ep_2026_raw_responses.jsonl"
JL_RAW_FILE  = ROOT / "data" / "raw" / "jl_2026_raw_responses.jsonl"
WIP_RAW_FILE = ROOT / "data" / "raw" / "wip_2026_raw_responses.jsonl"
NVJ_RAW_FILE = ROOT / "data" / "raw" / "nvj_2026_raw_responses.jsonl"
TL_RAW_FILE  = ROOT / "data" / "raw" / "tl_2026_raw_responses.jsonl"
M1R_RAW_FILE  = ROOT / "data" / "raw" / "m1r_2026_raw_responses.jsonl"
BAR_RAW_FILE  = ROOT / "data" / "raw" / "bar_2026_raw_responses.jsonl"
BJK_RAW_FILE  = ROOT / "data" / "raw" / "bjk_2026_raw_responses.jsonl"
RB_RAW_FILE   = ROOT / "data" / "raw" / "rb_2026_raw_responses.jsonl"
UCAM_RAW_FILE = ROOT / "data" / "raw" / "ucam_2026_raw_responses.jsonl"
MDR_RAW_FILE  = ROOT / "data" / "raw" / "mdr_2026_raw_responses.jsonl"
MISA_RAW_FILE = ROOT / "data" / "raw" / "misa_2026_raw_responses.jsonl"
PLM_RAW_FILE  = ROOT / "data" / "raw" / "plm_2026_raw_responses.jsonl"
AQD_RAW_FILE  = ROOT / "data" / "raw" / "aqd_2026_raw_responses.jsonl"
GHO_RAW_FILE  = ROOT / "data" / "raw" / "gho_2026_raw_responses.jsonl"
CGN_RAW_FILE  = ROOT / "data" / "raw" / "cgn_2026_raw_responses.jsonl"
SGE_PREFIXES = ("SGE ",)
FKS_PREFIXES = ("FKS ",)
RZN_PREFIXES = ("RZN ",)
EP_PREFIXES  = ("EP ",)
JL_PREFIXES  = ("JL ",)
WIP_PREFIXES = ("WIP ",)
NVJ_PREFIXES = ("NVJ ",)
TL_PREFIXES  = ("TL ",)
M1R_PREFIXES  = ("M1R ",)
BAR_PREFIXES  = ("BAR ",)
BJK_PREFIXES  = ("BJK ",)
RB_PREFIXES   = ("RB ",)
UCAM_PREFIXES = ("UCAM ",)
MDR_PREFIXES  = ("MDR ",)
MISA_PREFIXES = ("MISA ",)
PLM_PREFIXES  = ("PXL ",)
AQD_PREFIXES  = ("QAD ",)
GHO_PREFIXES  = ("GHS ",)
CGN_PREFIXES  = ("CGN ",)
MARSHAL_UUID = "C4883E50-4494-202C-3EC3-6B8A9284F00B"
OUTLAW_UUID  = "5F0AAF7A-4289-3998-D5FF-EB9A5CF7EF5C"
SNIPER_UUIDS = {OPERATOR_UUID.upper(), MARSHAL_UUID.upper(), OUTLAW_UUID.upper()}
OP_OUTLAW_UUIDS = {OPERATOR_UUID.upper(), OUTLAW_UUID.upper()}

MAP_TRANSFORMS = {
    "Abyss":   {"xMultiplier": 8.8e-05,  "yMultiplier": -7.2e-05,  "xScalarToAdd": 0.497,    "yScalarToAdd": 0.560},
    "Ascent":  {"xMultiplier": 7.0e-05, "yMultiplier": 7.0e-05, "xScalarToAdd": 0.426758, "yScalarToAdd": 0.813895, "swap_xy": True},
    "Bind":    {"xMultiplier": 5.9e-05,  "yMultiplier": -5.9e-05,  "xScalarToAdd": 0.576941, "yScalarToAdd": 0.967566},
    "Breeze":  {"xMultiplier": 7.0e-05,  "yMultiplier": -7.0e-05,  "xScalarToAdd": 0.465123, "yScalarToAdd": 0.833078},
    "Corrode": {"xMultiplier": 7.0e-05,  "yMultiplier": -7.0e-05,  "xScalarToAdd": 0.526158, "yScalarToAdd": 0.5},
    "Fracture": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05,  "xScalarToAdd": 0.556952, "yScalarToAdd": 1.155886},
    "Haven":   {"xMultiplier": 7.5e-05,  "yMultiplier": -7.5e-05,  "xScalarToAdd": 1.09345,  "yScalarToAdd": 0.642728},
    "Lotus":   {"xMultiplier": 7.2e-05,  "yMultiplier": -7.2e-05,  "xScalarToAdd": 0.454789, "yScalarToAdd": 0.917752},
    "Pearl":   {"xMultiplier": 7.8e-05,  "yMultiplier": -7.8e-05,  "xScalarToAdd": 0.480469, "yScalarToAdd": 0.916016},
    "Split":   {"xMultiplier": 7.8e-05,  "yMultiplier": -7.8e-05,  "xScalarToAdd": 0.842188, "yScalarToAdd": 0.697578},
}

TEAM_SOURCES = {
    "eintracht": [
        ("ct", "Bind",   "sge_bind_ct_early_team_positioning_last3.json"),
        ("t",  "Bind",   "sge_bind_t_early_team_positioning_last3.json"),
        ("ct", "Breeze", "sge_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze", "sge_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",  "sge_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",  "sge_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",  "sge_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",  "sge_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "sge_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "sge_split_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "sge_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "sge_fracture_t_early_team_positioning_last3.json"),
    ],
    "fokus": [
        ("ct", "Ascent",   "fks_ascent_ct_early_team_positioning_last3.json"),
        ("t",  "Ascent",   "fks_ascent_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "fks_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "fks_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "fks_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "fks_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "fks_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "fks_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "fks_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "fks_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "fks_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "fks_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "fks_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "fks_split_t_early_team_positioning_last3.json"),
    ],
    "rizon": [
        ("ct", "Bind",   "rzn_bind_ct_early_team_positioning_last3.json"),
        ("t",  "Bind",   "rzn_bind_t_early_team_positioning_last3.json"),
        ("ct", "Breeze", "rzn_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze", "rzn_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Haven",  "rzn_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",  "rzn_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",  "rzn_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",  "rzn_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Split",  "rzn_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",  "rzn_split_t_early_team_positioning_last3.json"),
    ],
    "enterprise": [
        ("ct", "Ascent",   "ep_ascent_ct_early_team_positioning_last3.json"),
        ("t",  "Ascent",   "ep_ascent_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "ep_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "ep_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "ep_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "ep_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "ep_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "ep_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "ep_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "ep_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "ep_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "ep_split_t_early_team_positioning_last3.json"),
    ],
    "joblife": [
        ("ct", "Ascent", "jl_ascent_ct_early_team_positioning_last3.json"),
        ("t",  "Ascent", "jl_ascent_t_early_team_positioning_last3.json"),
        ("ct", "Breeze", "jl_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze", "jl_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Haven",  "jl_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",  "jl_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",  "jl_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",  "jl_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",  "jl_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",  "jl_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",  "jl_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",  "jl_split_t_early_team_positioning_last3.json"),
    ],
    "wip": [
        ("ct", "Bind",     "wip_bind_ct_early_team_positioning_last3.json"),
        ("t",  "Bind",     "wip_bind_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "wip_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "wip_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "wip_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "wip_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "wip_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "wip_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "wip_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "wip_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "wip_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "wip_split_t_early_team_positioning_last3.json"),
    ],
    "nvjunior": [
        ("ct", "Ascent",   "nvj_ascent_ct_early_team_positioning_last3.json"),
        ("t",  "Ascent",   "nvj_ascent_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "nvj_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "nvj_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "nvj_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "nvj_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "nvj_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "nvj_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "nvj_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "nvj_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "nvj_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "nvj_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "nvj_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "nvj_split_t_early_team_positioning_last3.json"),
    ],
    "liquidacademy": [
        ("ct", "Breeze",   "tl_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "tl_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "tl_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "tl_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "tl_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "tl_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "tl_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "tl_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "tl_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "tl_split_t_early_team_positioning_last3.json"),
    ],
    "mir": [
        ("ct", "Ascent",   "m1r_ascent_ct_early_team_positioning_last3.json"),
        ("t",  "Ascent",   "m1r_ascent_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "m1r_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "m1r_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "m1r_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "m1r_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "m1r_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "m1r_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "m1r_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "m1r_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "m1r_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "m1r_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "m1r_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "m1r_split_t_early_team_positioning_last3.json"),
    ],
    "barcelona": [
        ("ct", "Ascent",   "bar_ascent_ct_early_team_positioning_last3.json"),
        ("t",  "Ascent",   "bar_ascent_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "bar_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "bar_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "bar_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "bar_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "bar_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "bar_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "bar_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "bar_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "bar_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "bar_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "bar_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "bar_split_t_early_team_positioning_last3.json"),
    ],
    "besiktas": [
        ("ct", "Bind",     "bjk_bind_ct_early_team_positioning_last3.json"),
        ("t",  "Bind",     "bjk_bind_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "bjk_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "bjk_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "bjk_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "bjk_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "bjk_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "bjk_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "bjk_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "bjk_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "bjk_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "bjk_split_t_early_team_positioning_last3.json"),
    ],
    "reborn": [
        ("ct", "Bind",     "rb_bind_ct_early_team_positioning_last3.json"),
        ("t",  "Bind",     "rb_bind_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "rb_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "rb_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "rb_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "rb_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "rb_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "rb_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "rb_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "rb_split_t_early_team_positioning_last3.json"),
    ],
    "ucam": [
        ("ct", "Bind",     "ucam_bind_ct_early_team_positioning_last3.json"),
        ("t",  "Bind",     "ucam_bind_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "ucam_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "ucam_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "ucam_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "ucam_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "ucam_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "ucam_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "ucam_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "ucam_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "ucam_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "ucam_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "ucam_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "ucam_split_t_early_team_positioning_last3.json"),
    ],
    "mandatory": [
        ("ct", "Breeze",   "mdr_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "mdr_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "mdr_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "mdr_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "mdr_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "mdr_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "mdr_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "mdr_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "mdr_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "mdr_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "mdr_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "mdr_split_t_early_team_positioning_last3.json"),
    ],
    "misa": [
        ("ct", "Ascent",   "misa_ascent_ct_early_team_positioning_last3.json"),
        ("t",  "Ascent",   "misa_ascent_t_early_team_positioning_last3.json"),
        ("ct", "Breeze",   "misa_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "misa_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "misa_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "misa_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "misa_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "misa_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "misa_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "misa_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "misa_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "misa_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "misa_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "misa_split_t_early_team_positioning_last3.json"),
    ],
    "pixellumina": [
        ("ct", "Bind",   "plm_bind_ct_early_team_positioning_last3.json"),
        ("t",  "Bind",   "plm_bind_t_early_team_positioning_last3.json"),
        ("ct", "Haven",  "plm_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",  "plm_haven_t_early_team_positioning_last3.json"),
        ("ct", "Split",  "plm_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",  "plm_split_t_early_team_positioning_last3.json"),
    ],
    "alqadsiah": [
        ("ct", "Breeze", "aqd_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze", "aqd_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Haven",  "aqd_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",  "aqd_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",  "aqd_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",  "aqd_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Split",  "aqd_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",  "aqd_split_t_early_team_positioning_last3.json"),
    ],
    "ghools": [
        ("ct", "Bind",   "gho_bind_ct_early_team_positioning_last3.json"),
        ("t",  "Bind",   "gho_bind_t_early_team_positioning_last3.json"),
    ],
    "cgn": [
        ("ct", "Breeze",   "cgn_breeze_ct_early_team_positioning_last3.json"),
        ("t",  "Breeze",   "cgn_breeze_t_early_team_positioning_last3.json"),
        ("ct", "Fracture", "cgn_fracture_ct_early_team_positioning_last3.json"),
        ("t",  "Fracture", "cgn_fracture_t_early_team_positioning_last3.json"),
        ("ct", "Haven",    "cgn_haven_ct_early_team_positioning_last3.json"),
        ("t",  "Haven",    "cgn_haven_t_early_team_positioning_last3.json"),
        ("ct", "Lotus",    "cgn_lotus_ct_early_team_positioning_last3.json"),
        ("t",  "Lotus",    "cgn_lotus_t_early_team_positioning_last3.json"),
        ("ct", "Pearl",    "cgn_pearl_ct_early_team_positioning_last3.json"),
        ("t",  "Pearl",    "cgn_pearl_t_early_team_positioning_last3.json"),
        ("ct", "Split",    "cgn_split_ct_early_team_positioning_last3.json"),
        ("t",  "Split",    "cgn_split_t_early_team_positioning_last3.json"),
    ],
}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def detect_team_context(match_obj: dict, prefixes: tuple[str, ...]) -> dict | None:
    team_id = None
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("gameName", "").startswith(prefixes):
            team_id = player.get("teamId")
            break
    if team_id is None:
        return None

    team_players = []
    for player in match_obj.get("players", []):
        if player.get("isObserver"):
            continue
        if player.get("teamId") == team_id:
            team_players.append(player)

    return {"teamId": team_id, "teamPlayers": team_players}


def clean_player_name(name: str, prefixes: tuple[str, ...] = SGE_PREFIXES) -> str:
    for prefix in prefixes:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def location_for_puuid(entries: list[dict] | None, puuid: str) -> dict | None:
    if not entries:
        return None
    for entry in entries:
        if entry.get("puuid") == puuid:
            return entry.get("location")
    return None


def normalize_xy(map_name: str, x: float, y: float) -> tuple[float, float]:
    transform = MAP_TRANSFORMS.get(map_name)
    if not transform:
        return 50.0, 50.0
    if transform.get("swap_xy"):
        x, y = y, x
    norm_x = (y * transform["xMultiplier"] + transform["xScalarToAdd"]) * 100
    norm_y = (x * transform["yMultiplier"] + transform["yScalarToAdd"]) * 100
    return norm_x, norm_y


def build_sge_sniper_points_for_dataset(dataset: dict, side_code: str, matches_by_id: dict[str, dict], prefixes: tuple[str, ...] = SGE_PREFIXES) -> dict:
    map_name = dataset.get("map", "")
    selected_maps = dataset.get("selectedMaps", [])
    points: list[dict] = []

    for sample in selected_maps:
        match_id = sample.get("matchId")
        if not match_id:
            continue
        match_obj = matches_by_id.get(match_id)
        if not match_obj:
            continue

        context = detect_team_context(match_obj, prefixes)
        if context is None:
            continue
        team_puuids = {player.get("puuid") for player in context.get("teamPlayers", []) if player.get("puuid")}
        puuid_to_name = {
            player.get("puuid"): clean_player_name(player.get("gameName", ""), prefixes)
            for player in context.get("teamPlayers", [])
        }
        all_name_by_puuid = {
            player.get("puuid"): player.get("gameName", "")
            for player in match_obj.get("players", [])
            if player.get("puuid")
        }
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            round_side = sides.get(round_num)
            if side_code == "ct" and round_side != "def":
                continue
            if side_code == "t" and round_side != "atk":
                continue

            for player_stats in rr.get("playerStats", []):
                killer_puuid = player_stats.get("puuid")
                if killer_puuid not in team_puuids:
                    continue
                for kill in player_stats.get("kills", []):
                    damage_item = str(kill.get("finishingDamage", {}).get("damageItem", "")).upper()
                    if damage_item not in SNIPER_UUIDS:
                        continue
                    killer_loc = location_for_puuid(kill.get("playerLocations"), killer_puuid)
                    if not killer_loc:
                        continue
                    kx = killer_loc.get("x")
                    ky = killer_loc.get("y")
                    if kx is None or ky is None:
                        continue
                    norm_x, norm_y = normalize_xy(map_name, kx, ky)

                    payload = {
                        "x": kx,
                        "y": ky,
                        "normX": norm_x,
                        "normY": norm_y,
                        "roundNum": round_num,
                        "timeSinceRoundStartMillis": kill.get("timeSinceRoundStartMillis"),
                        "date": sample.get("date"),
                        "opponent": sample.get("opponent"),
                        "score": sample.get("score"),
                        "matchId": match_id,
                        "player": puuid_to_name.get(killer_puuid, killer_puuid),
                        "victim": all_name_by_puuid.get(kill.get("victim"), kill.get("victim")),
                    }
                    victim_loc = kill.get("victimLocation")
                    if victim_loc and victim_loc.get("x") is not None and victim_loc.get("y") is not None:
                        vx = victim_loc.get("x")
                        vy = victim_loc.get("y")
                        payload["victimX"] = vx
                        payload["victimY"] = vy
                        vnx, vny = normalize_xy(map_name, vx, vy)
                        payload["victimNormX"] = vnx
                        payload["victimNormY"] = vny
                    points.append(payload)

    return {"count": len(points), "points": points}


def build_sge_all_fk_points_for_dataset(dataset: dict, side_code: str, matches_by_id: dict[str, dict], prefixes: tuple[str, ...] = SGE_PREFIXES) -> dict:
    """All rounds where the team got the first kill — killer + victim positions."""
    map_name = dataset.get("map", "")
    selected_maps = dataset.get("selectedMaps", [])
    points: list[dict] = []

    for sample in selected_maps:
        match_id = sample.get("matchId")
        if not match_id:
            continue
        match_obj = matches_by_id.get(match_id)
        if not match_obj:
            continue

        context = detect_team_context(match_obj, prefixes)
        if context is None:
            continue
        team_puuids = {player.get("puuid") for player in context.get("teamPlayers", []) if player.get("puuid")}
        puuid_to_name = {
            player.get("puuid"): clean_player_name(player.get("gameName", ""), prefixes)
            for player in context.get("teamPlayers", [])
        }
        all_name_by_puuid = {
            player.get("puuid"): player.get("gameName", "")
            for player in match_obj.get("players", [])
            if player.get("puuid")
        }
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)

        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            round_side = sides.get(round_num)
            if side_code == "ct" and round_side != "def":
                continue
            if side_code == "t" and round_side != "atk":
                continue

            # Collect all kills, find the earliest one
            all_kills: list[tuple[int, str, dict]] = []
            for player_stats in rr.get("playerStats", []):
                killer_puuid = player_stats.get("puuid")
                for kill in player_stats.get("kills", []):
                    t = kill.get("timeSinceRoundStartMillis")
                    if t is None:
                        continue
                    # fall deaths / self-kills (e.g. a team jumping into the void on Abyss) are not first kills
                    if killer_puuid == kill.get("victim") or (kill.get("finishingDamage") or {}).get("damageType") == "Fall":
                        continue
                    all_kills.append((t, killer_puuid, kill))
            if not all_kills:
                continue
            all_kills.sort(key=lambda e: e[0])
            first_t, first_killer_puuid, first_kill = all_kills[0]

            # Only record rounds where SGE got the first kill
            if first_killer_puuid not in team_puuids:
                continue

            killer_loc = location_for_puuid(first_kill.get("playerLocations"), first_killer_puuid)
            if not killer_loc:
                continue
            kx = killer_loc.get("x")
            ky = killer_loc.get("y")
            if kx is None or ky is None:
                continue
            norm_x, norm_y = normalize_xy(map_name, kx, ky)
            if not (-10 <= norm_x <= 110 and -10 <= norm_y <= 110):
                continue   # broken coordinates (e.g. -50000)

            payload = {
                "x": kx, "y": ky,
                "normX": norm_x, "normY": norm_y,
                "roundNum": round_num,
                "timeSinceRoundStartMillis": first_t,
                "date": sample.get("date"),
                "opponent": sample.get("opponent"),
                "score": sample.get("score"),
                "matchId": match_id,
                "player": puuid_to_name.get(first_killer_puuid, first_killer_puuid),
                "victim": all_name_by_puuid.get(first_kill.get("victim"), first_kill.get("victim")),
                "plantSite": rr.get("plantSite", ""),
            }
            victim_loc = first_kill.get("victimLocation")
            if victim_loc and victim_loc.get("x") is not None and victim_loc.get("y") is not None:
                vx, vy = victim_loc["x"], victim_loc["y"]
                payload["victimX"] = vx
                payload["victimY"] = vy
                vnx, vny = normalize_xy(map_name, vx, vy)
                payload["victimNormX"] = vnx
                payload["victimNormY"] = vny
            points.append(payload)

    return {"count": len(points), "points": points}


def build_sniper_round_keys(dataset: dict, side_code: str, matches_by_id: dict[str, dict], prefixes: tuple[str, ...]) -> list[str]:
    """Returns list of 'matchId|roundNum' where any team player had Op/Outlaw in economy.weapon."""
    selected_maps = dataset.get("selectedMaps", [])
    keys: list[str] = []
    for sample in selected_maps:
        match_id = sample.get("matchId")
        if not match_id:
            continue
        match_obj = matches_by_id.get(match_id)
        if not match_obj:
            continue
        context = detect_team_context(match_obj, prefixes)
        if context is None:
            continue
        team_puuids = {p.get("puuid") for p in context.get("teamPlayers", []) if p.get("puuid")}
        sides = get_team_side_per_round(SimpleNamespace(round_results=match_obj.get("roundResults", [])), team_puuids)
        for rr in match_obj.get("roundResults", []):
            round_num = rr.get("roundNum")
            round_side = sides.get(round_num)
            if side_code == "ct" and round_side != "def":
                continue
            if side_code == "t" and round_side != "atk":
                continue
            for ps in rr.get("playerStats", []):
                if ps.get("puuid") not in team_puuids:
                    continue
                weapon = str(ps.get("economy", {}).get("weapon", "")).upper()
                if weapon in OP_OUTLAW_UUIDS:
                    keys.append(f"{match_id}|{round_num}")
                    break
    return keys


def main() -> None:
    payload: dict[str, dict] = {team_key: {"ct": {}, "t": {}} for team_key in TEAM_SOURCES}
    missing: list[str] = []

    for team_key, sources in TEAM_SOURCES.items():
        for side, map_name, file_name in sources:
            path = ANALYSIS_DIR / file_name
            if not path.exists():
                missing.append(str(path))
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            payload[team_key][side][map_name] = data

    # Add sniper + all-FK data for SGE
    sge_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(SGE_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("eintracht", {}).get(side, {}).items():
            payload["eintracht"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, sge_matches, SGE_PREFIXES,
            )
            payload["eintracht"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, sge_matches, SGE_PREFIXES,
            )
            payload["eintracht"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, sge_matches, SGE_PREFIXES,
            )

    # Add sniper + all-FK data for FKS
    fks_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(FKS_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("fokus", {}).get(side, {}).items():
            payload["fokus"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, fks_matches, FKS_PREFIXES,
            )
            payload["fokus"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, fks_matches, FKS_PREFIXES,
            )
            payload["fokus"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, fks_matches, FKS_PREFIXES,
            )

    # Add sniper + all-FK data for RZN
    rzn_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(RZN_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("rizon", {}).get(side, {}).items():
            payload["rizon"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, rzn_matches, RZN_PREFIXES,
            )
            payload["rizon"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, rzn_matches, RZN_PREFIXES,
            )
            payload["rizon"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, rzn_matches, RZN_PREFIXES,
            )

    # Add sniper + all-FK data for Enterprise (EP)
    ep_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(EP_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("enterprise", {}).get(side, {}).items():
            payload["enterprise"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, ep_matches, EP_PREFIXES,
            )
            payload["enterprise"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, ep_matches, EP_PREFIXES,
            )
            payload["enterprise"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, ep_matches, EP_PREFIXES,
            )

    # Add sniper + all-FK data for JOBlife (JL)
    jl_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(JL_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("joblife", {}).get(side, {}).items():
            payload["joblife"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, jl_matches, JL_PREFIXES,
            )
            payload["joblife"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, jl_matches, JL_PREFIXES,
            )
            payload["joblife"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, jl_matches, JL_PREFIXES,
            )

    # Add sniper + all-FK data for WIP Esports
    wip_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(WIP_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("wip", {}).get(side, {}).items():
            payload["wip"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, wip_matches, WIP_PREFIXES,
            )
            payload["wip"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, wip_matches, WIP_PREFIXES,
            )
            payload["wip"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, wip_matches, WIP_PREFIXES,
            )

    # Add sniper + all-FK data for NAVI Junior
    nvj_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(NVJ_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("nvjunior", {}).get(side, {}).items():
            payload["nvjunior"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, nvj_matches, NVJ_PREFIXES,
            )
            payload["nvjunior"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, nvj_matches, NVJ_PREFIXES,
            )
            payload["nvjunior"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, nvj_matches, NVJ_PREFIXES,
            )

    # Add sniper + all-FK data for Team Liquid Academy
    tl_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(TL_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("liquidacademy", {}).get(side, {}).items():
            payload["liquidacademy"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, tl_matches, TL_PREFIXES,
            )
            payload["liquidacademy"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, tl_matches, TL_PREFIXES,
            )
            payload["liquidacademy"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, tl_matches, TL_PREFIXES,
            )

    # Add sniper + all-FK data for MIR
    m1r_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(M1R_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("mir", {}).get(side, {}).items():
            payload["mir"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, m1r_matches, M1R_PREFIXES,
            )
            payload["mir"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, m1r_matches, M1R_PREFIXES,
            )
            payload["mir"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, m1r_matches, M1R_PREFIXES,
            )

    bar_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(BAR_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("barcelona", {}).get(side, {}).items():
            payload["barcelona"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, bar_matches, BAR_PREFIXES,
            )
            payload["barcelona"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, bar_matches, BAR_PREFIXES,
            )
            payload["barcelona"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, bar_matches, BAR_PREFIXES,
            )

    bjk_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(BJK_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("besiktas", {}).get(side, {}).items():
            payload["besiktas"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, bjk_matches, BJK_PREFIXES,
            )
            payload["besiktas"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, bjk_matches, BJK_PREFIXES,
            )
            payload["besiktas"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, bjk_matches, BJK_PREFIXES,
            )

    rb_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(RB_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("reborn", {}).get(side, {}).items():
            payload["reborn"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, rb_matches, RB_PREFIXES,
            )
            payload["reborn"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, rb_matches, RB_PREFIXES,
            )
            payload["reborn"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, rb_matches, RB_PREFIXES,
            )

    ucam_matches = {
        match.get("matchInfo", {}).get("matchId"): match
        for match in load_jsonl(UCAM_RAW_FILE)
        if match.get("matchInfo", {}).get("matchId")
    }
    for side in ("ct", "t"):
        for map_name, dataset in payload.get("ucam", {}).get(side, {}).items():
            payload["ucam"][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                dataset, side, ucam_matches, UCAM_PREFIXES,
            )
            payload["ucam"][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                dataset, side, ucam_matches, UCAM_PREFIXES,
            )
            payload["ucam"][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                dataset, side, ucam_matches, UCAM_PREFIXES,
            )

    for team_key, raw_file, prefixes in [
        ("mandatory",    MDR_RAW_FILE,  MDR_PREFIXES),
        ("misa",         MISA_RAW_FILE, MISA_PREFIXES),
        ("pixellumina",  PLM_RAW_FILE,  PLM_PREFIXES),
        ("alqadsiah",    AQD_RAW_FILE,  AQD_PREFIXES),
        ("ghools",       GHO_RAW_FILE,  GHO_PREFIXES),
        ("cgn",          CGN_RAW_FILE,  CGN_PREFIXES),
    ]:
        matches_by_id = {
            match.get("matchInfo", {}).get("matchId"): match
            for match in load_jsonl(raw_file)
            if match.get("matchInfo", {}).get("matchId")
        }
        for side in ("ct", "t"):
            for map_name, dataset in payload.get(team_key, {}).get(side, {}).items():
                payload[team_key][side][map_name]["sniper"] = build_sge_sniper_points_for_dataset(
                    dataset, side, matches_by_id, prefixes,
                )
                payload[team_key][side][map_name]["all_fk"] = build_sge_all_fk_points_for_dataset(
                    dataset, side, matches_by_id, prefixes,
                )
                payload[team_key][side][map_name]["sniperRoundKeys"] = build_sniper_round_keys(
                    dataset, side, matches_by_id, prefixes,
                )

    OUTPUT_FILE.write_text(
        "const defensiveEarlyData = " + json.dumps(payload, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"Wrote: {OUTPUT_FILE}")
    if missing:
        print("Missing source files:")
        for item in missing:
            print(f"- {item}")


if __name__ == "__main__":
    main()

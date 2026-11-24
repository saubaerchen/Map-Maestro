import json, re, sys
from collections import defaultdict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
sys.stdout.reconfigure(encoding='utf-8')

with open('veto-history-site-publish/extra-data.js', encoding='utf-8') as f:
    raw = f.read()
raw = re.sub(r'^const extraVetoHistoryData\s*=\s*', '', raw.strip())
raw = re.sub(r';\s*$', '', raw.strip())
raw = re.sub(r',(\s*[}\]])', r'\1', raw)
data = json.loads(raw)

CL3_KEYS = ['enterprise','ucam','nvjunior','joblife','mandatory','liquidacademy',
            'fokus','misa','cgn','alqadsiah','mir','barcelona','pixellumina','besiktas','ghools','reborn']

CL3_LABELS = {
    'EP','UCAM','NVJ','NAVI.J','JL','MDR','TL','TL.A','FKS','MISA',
    'CGN','AQD','QAD','M1R','MIR','BAR','PLM','PXL','BJK','GHO','RB'
}
LABEL_DISPLAY = {
    'EP':'EP','UCAM':'UCAM','NVJ':'NVJ','NAVI.J':'NVJ','JL':'JL','MDR':'MDR',
    'TL':'TL','TL.A':'TL','FKS':'FKS','MISA':'MISA','CGN':'CGN',
    'AQD':'AQD','QAD':'AQD','M1R':'M1R','MIR':'M1R','BAR':'BAR',
    'PLM':'PLM','PXL':'PLM','BJK':'BJK','GHO':'GHO','RB':'RB'
}
TEAM_ORDER = {k: i for i, k in enumerate(CL3_KEYS)}

# Dedup
seen_source, seen_abbr = set(), set()
deduped = []
for k in CL3_KEYS:
    if k not in data:
        continue
    for row in data[k]['rows']:
        src = row.get('source', '').strip()
        b1  = row.get('ban1', {})
        b2  = row.get('ban2', {})
        l1  = b1.get('ownerLabel', '')
        l2  = b2.get('ownerLabel', '')
        date = row.get('date', '')
        if src:
            if src not in seen_source:
                seen_source.add(src)
                deduped.append((k, row))
        else:
            if l1 and l2:
                key = (date, tuple(sorted([l1, l2])))
                if key not in seen_abbr:
                    seen_abbr.add(key)
                    deduped.append((k, row))
            else:
                deduped.append((k, row))

# Filter CL3 vs CL3
cl3_matches = []
for k, row in deduped:
    l1 = row.get('ban1', {}).get('ownerLabel', '')
    l2 = row.get('ban2', {}).get('ownerLabel', '')
    if l1 in CL3_LABELS and l2 in CL3_LABELS:
        cl3_matches.append((k, row))

MAPS = ['Ascent','Bind','Breeze','Fracture','Haven','Lotus','Pearl','Split']

def disp(lbl):
    return LABEL_DISPLAY.get(lbl, lbl)

# Build flat records
records = []
for k, row in cl3_matches:
    b1 = row.get('ban1', {});  b2 = row.get('ban2', {})
    p1 = row.get('pick1', {}); p2 = row.get('pick2', {})
    b3 = row.get('ban3', {});  b4 = row.get('ban4', {})
    records.append({
        'team_key':  k,
        'date':      row.get('date', ''),
        'team_a':    disp(b1.get('ownerLabel', '')),
        'team_b':    disp(b2.get('ownerLabel', '')),
        'score':     row.get('score', ''),
        'ban1':      b1.get('map', ''), 'ban1_by':  disp(b1.get('ownerLabel', '')),
        'ban2':      b2.get('map', ''), 'ban2_by':  disp(b2.get('ownerLabel', '')),
        'pick1':     p1.get('map', ''), 'pick1_by': disp(p1.get('ownerLabel', '')),
        'pick2':     p2.get('map', ''), 'pick2_by': disp(p2.get('ownerLabel', '')),
        'ban3':      b3.get('map', ''), 'ban3_by':  disp(b3.get('ownerLabel', '')),
        'ban4':      b4.get('map', ''), 'ban4_by':  disp(b4.get('ownerLabel', '')),
        'decider':   row.get('decider', '') or '',
        'source':    row.get('source', ''),
    })

records_by_team = sorted(records, key=lambda r: (TEAM_ORDER.get(r['team_key'], 99), r['date']))
records_by_date = sorted(records, key=lambda r: r['date'])

# Summary
fw_ban  = defaultdict(int)
fw_pick = defaultdict(int)
for r in records:
    if r['ban1']  in MAPS: fw_ban[r['ban1']]   += 1
    if r['ban2']  in MAPS: fw_ban[r['ban2']]   += 1
    if r['pick1'] in MAPS: fw_pick[r['pick1']] += 1
    if r['pick2'] in MAPS: fw_pick[r['pick2']] += 1

# Styles
hdr_fill  = PatternFill('solid', fgColor='1a1a2e')
hdr_font  = Font(bold=True, color='FFFFFF', name='Calibri', size=10)
grp_fills = [PatternFill('solid', fgColor='E8F0FE'), PatternFill('solid', fgColor='F5F5F5')]
thin = Side(style='thin', color='CCCCCC')
bdr  = Border(bottom=thin)
center = Alignment(horizontal='center', vertical='center')
left   = Alignment(horizontal='left',   vertical='center')

HEADERS = ['#','Date','Team A','Team B','Score',
           'Ban 1','Ban 1 By','Ban 2','Ban 2 By',
           'Pick 1','Pick 1 By','Pick 2','Pick 2 By',
           'Ban 3','Ban 3 By','Ban 4','Ban 4 By',
           'Decider','Source']
WIDTHS   = [5,12,10,10,9,12,9,12,9,12,9,12,9,12,9,12,9,12,55]

def write_match_sheet(ws, rows, group_key):
    ws.row_dimensions[1].height = 20
    for ci, (h, w) in enumerate(zip(HEADERS, WIDTHS), 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font = hdr_font; c.fill = hdr_fill; c.alignment = center
        ws.column_dimensions[get_column_letter(ci)].width = w
    prev, fi = None, 0
    for i, r in enumerate(rows, 1):
        grp = r[group_key]
        if grp != prev:
            fi = 1 - fi; prev = grp
        fill = grp_fills[fi]
        vals = [i, r['date'], r['team_a'], r['team_b'], r['score'],
                r['ban1'], r['ban1_by'], r['ban2'], r['ban2_by'],
                r['pick1'], r['pick1_by'], r['pick2'], r['pick2_by'],
                r['ban3'], r['ban3_by'], r['ban4'], r['ban4_by'],
                r['decider'], r['source']]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(row=i+1, column=ci, value=v)
            c.fill = fill; c.border = bdr
            c.alignment = left if ci == 19 else center
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:{get_column_letter(len(HEADERS))}1'

wb = openpyxl.Workbook()

ws1 = wb.active; ws1.title = 'By Team'
write_match_sheet(ws1, records_by_team, 'team_key')

ws2 = wb.create_sheet('By Date')
write_match_sheet(ws2, records_by_date, 'date')

# Summary tab
ws3 = wb.create_sheet('Summary')
title_font = Font(bold=True, name='Calibri', size=11)
sub_font   = Font(bold=True, name='Calibri', size=10, color='FFFFFF')
sub_fill   = PatternFill('solid', fgColor='2E4057')
num_font   = Font(name='Calibri', size=10)

def sh(ws, row, col, val, font=None, fill=None, align=None):
    c = ws.cell(row=row, column=col, value=val)
    if font:  c.font  = font
    if fill:  c.fill  = fill
    if align: c.alignment = align
    return c

n = len(records)
sh(ws3, 1, 1, f'CL3 vs CL3 — First-Wave Bans & Picks ({n} matches)', font=title_font)

ban_sorted  = sorted(fw_ban.items(),  key=lambda x: -x[1])
pick_sorted = sorted(fw_pick.items(), key=lambda x: -x[1])

for ci, h in enumerate(['Map', 'Bans', '% matches'], 1):
    sh(ws3, 3, ci, h, font=sub_font, fill=sub_fill, align=center)
for i, (m, c) in enumerate(ban_sorted, 1):
    sh(ws3, 3+i, 1, m, font=num_font)
    sh(ws3, 3+i, 2, c, font=num_font, align=center)
    sh(ws3, 3+i, 3, f'{c/n*100:.0f}%', font=num_font, align=center)

for ci, h in enumerate(['Map', 'Picks', '% matches'], 1):
    sh(ws3, 3, 5+ci-1, h, font=sub_font, fill=sub_fill, align=center)
for i, (m, c) in enumerate(pick_sorted, 1):
    sh(ws3, 3+i, 5, m, font=num_font)
    sh(ws3, 3+i, 6, c, font=num_font, align=center)
    sh(ws3, 3+i, 7, f'{c/n*100:.0f}%', font=num_font, align=center)

for col, w in zip(['A','B','C','D','E','F','G'], [14,10,12,4,14,10,12]):
    ws3.column_dimensions[col].width = w

out = 'Challengers 3/cl3_cl3_matches.xlsx'
wb.save(out)
print(f'Saved: {out}  ({n} matches, 3 tabs)')

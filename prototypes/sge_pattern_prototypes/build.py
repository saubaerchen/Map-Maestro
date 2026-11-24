"""PROTOTYPE — throwaway. Builds 7 standalone feature pages (Eintracht data only) into ./out/<feature>/index.html."""
import json
import os
import shutil

from compute import HERE, ROOT, compute
from conditions import mine, themes

OUT = os.path.join(HERE, "out")
MAP_DIR = os.path.join(ROOT, "veto-history-site-publish", "maps")

FEATURES = [
    ("1_callouts", 4181, "Callout translation", "Can positions be read as named callouts instead of dots?"),
    ("2_ct_setups", 4182, "CT setup fingerprints", "Does SGE repeat the same defensive spread (players per site) — and when do they change it?"),
    ("3_anchors", 4183, "Player anchor maps", "Who holds the same spot every round, and who rotates/plays aggressive?"),
    ("4_t_tendencies", 4184, "T-side tendencies by round type", "Where and how fast does SGE hit on pistol / eco / force / full buys, after wins vs losses?"),
    ("5_opening_duels", 4185, "Opening-duel profile", "Who takes the first fights, from where, and does it pay off?"),
    ("6_all_games", 4186, "All-games vs last-3 tendencies", "How different does the picture look using every official game instead of the last 3?"),
    ("7_vetoes", 4187, "Veto tendencies", "What does SGE ban first, pick, and leave as decider?"),
    ("9_explained", 4189, "Behaviours explained", "What exactly does each conditional behaviour mean — and which rounds prove it?"),
    ("8_conditions", 4188, "Conditional logic", "Under which measurable conditions (weapon, economy, score, previous round) does a player or the team change position or plan?"),
]

CSS = """
:root{--bg:#0f1419;--card:#161d24;--line:#26313b;--txt:#e6edf3;--mut:#8b98a5;--acc:#4ade80}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.45 Inter,Segoe UI,sans-serif}
.proto{background:#7c2d12;color:#fff;padding:6px 16px;font:600 12px monospace;letter-spacing:.04em}
header{padding:18px 20px 6px}h1{margin:0;font:700 26px 'Space Grotesk',Inter,sans-serif}.q{color:var(--mut);margin:4px 0 0}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:10px 20px}
button,select{background:var(--card);color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font:inherit;cursor:pointer}
button.on{background:var(--acc);color:#04130a;border-color:var(--acc);font-weight:600}
main{padding:6px 20px 40px}.grid{display:grid;gap:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
table{border-collapse:collapse;width:100%}th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}tr.click{cursor:pointer}tr.click:hover,tr.sel{background:#1f2a33}
.mapbox{position:relative;width:100%;aspect-ratio:1;background:#0b1014;border-radius:8px;overflow:hidden}
.mapframe{position:absolute;inset:0}.mapframe.rot{transform:rotate(90deg)}
.mapframe img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;opacity:.55}
.dot{position:absolute;width:10px;height:10px;margin:-5px 0 0 -5px;border-radius:50%;border:1.5px solid #000;z-index:2}
.lbl{position:absolute;transform:translate(-50%,-50%);font:600 9px Inter,sans-serif;color:#cbd5e1;text-shadow:0 0 3px #000,0 0 3px #000;white-space:nowrap;z-index:1;pointer-events:none}
.mut{color:var(--mut)}.pill{display:inline-block;padding:1px 7px;border-radius:99px;background:#1f2a33;margin:1px 3px 1px 0;font-size:12px}
.bar2{height:8px;border-radius:4px;background:var(--acc)}.legend span{margin-right:12px}.sw{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:-1px}
.state{font:12px monospace;color:var(--mut);padding:8px 20px;border-top:1px solid var(--line)}
.mapframe.rot .lbl{transform:translate(-50%,-50%) rotate(-90deg)}
.concl{padding:8px 10px;border:1px solid var(--line);border-left:4px solid #64748b;border-radius:6px;margin:6px 0;cursor:pointer;background:#121a21}
.concl:hover,.concl.sel{background:#1f2a33}.concl.strong{border-left-color:var(--acc)}.concl.lean{border-left-color:#f59e0b}.concl.info{border-left-color:#64748b}
.concl .tag{display:inline-block;font:700 10px monospace;text-transform:uppercase;margin-right:8px;padding:1px 5px;border-radius:4px;background:#0b1014;color:var(--mut)}
.concl.strong .tag{color:var(--acc)}.concl.lean .tag{color:#f59e0b}
"""

SHARED_JS = r"""
const COLORS={azury:'#1565C0',musashi:'#F9A825',Fizzy:'#C62828',foe:'#2E7D32',H1ber:'#E91E63'};
const ROT=new Set(['Haven','Split']);
const pct=(a,b)=>b?Math.round(100*a/b)+'%':'—';
const frac=(a,b)=>`${a}/${b}`+(b?` <span class=mut>(${pct(a,b)})</span>`:'');
function mapBox(map,dots,labels){
  const l=(labels||[]).map(c=>`<div class=lbl style="left:${c.nx}%;top:${c.ny}%">${c.label}</div>`).join('');
  const d=dots.map(p=>`<div class=dot title="${p.title||p.p}" style="left:${p.nx}%;top:${p.ny}%;background:${p.color||COLORS[p.p]||'#9E9E9E'};opacity:${p.op??0.9}"></div>`).join('');
  return `<div class=mapbox><div class="mapframe ${ROT.has(map)?'rot':''}"><img src="maps/${map}.png">${l}${d}</div></div>`;
}
function legend(){return '<div class=legend>'+Object.entries(COLORS).map(([p,c])=>`<span><i class=sw style="background:${c}"></i>${p}</span>`).join('')+'</div>';}
function topN(counter,n){return Object.entries(counter).sort((a,b)=>b[1]-a[1]).slice(0,n);}
function count(arr,f){const c={};arr.forEach(x=>{const k=f(x);if(k!=null)c[k]=(c[k]||0)+1});return c;}
function mapButtons(state,maps,withAll,onChange){
  return (withAll?['All',...maps]:maps).map(m=>`<button class="${state.map===m?'on':''}" onclick="${onChange}('${m}')">${m}</button>`).join('');
}
function showState(o){document.getElementById('state').textContent='state: '+JSON.stringify(o);}
// ---- conclusions helpers ----
const EARLY_S=35;                       // first kill within 35s = positions still show the setup
const FORWARD=/(Lobby|Main|T Spawn)/;   // attacker-side approaches = CT player is playing forward
const ZORDER=['A','Mid','B','C','CT Spawn','T Spawn'];
function lvl(n,share,strongN,strongShare){return n>=strongN&&share>=strongShare?'strong':'lean';}
function modal(counter){const t=topN(counter,1)[0];return t?{k:t[0],n:t[1]}:{k:null,n:0};}
function avgZone(rs,z){return rs.length?rs.reduce((s,r)=>s+r.snap.filter(p=>p.zone===z).length,0)/rs.length:0;}
function zonesOf(rs){return ZORDER.filter(z=>rs.some(r=>r.snap.some(p=>p.zone===z)));}
function conclList(C,sel,fn){
  if(!C.length)return '<p class=mut>No conclusions — sample too small.</p>';
  return C.map((c,i)=>`<div class="concl ${c.lvl} ${sel===i?'sel':''}" onclick="${fn}(${i})"><span class=tag>${c.lvl}</span>${c.text}${c.rounds?` <span class=mut>· ${c.rounds.length} rounds ▸</span>`:''}</div>`).join('');
}
"""

PAGES = {}

PAGES["1_callouts"] = r"""
const S={map:DATA.maps[0],side:'CT',ri:0};
function rounds(){return DATA.rounds.filter(r=>r.map===S.map&&r.side===S.side&&r.snap.length);}
function setMap(m){S.map=m;S.ri=0;render()} function setSide(s){S.side=s;S.ri=0;render()} function pick(i){S.ri=i;render()}
function render(){
  const R=rounds(), r=R[S.ri];
  document.getElementById('bar').innerHTML=mapButtons(S,DATA.maps,false,'setMap')+' &nbsp; '+['CT','T'].map(s=>`<button class="${S.side===s?'on':''}" onclick="setSide('${s}')">${s}</button>`).join('');
  const list=R.map((x,i)=>`<tr class="click ${i===S.ri?'sel':''}" onclick="pick(${i})"><td>${x.date}</td><td>vs ${x.opp}</td><td>R${x.round}</td><td>${x.tier}</td><td>FK ${x.fkT}s</td></tr>`).join('');
  const trans=r?r.snap.map(p=>`<tr><td><i class=sw style="background:${COLORS[p.p]}"></i>${p.p}</td><td><b>${p.call}</b></td></tr>`).join(''):'';
  const fk=r&&r.fk?`<p>First kill at <b>${r.fk.t}s</b>: ${r.fk.killer||'opp'} (${r.fk.killerCall}) → ${r.fk.victim||'opp'} (${r.fk.victimCall}) — ${r.fk.sgeKill?'SGE got it':'SGE lost it'}</p>`:'';
  const players=Object.keys(COLORS).map(p=>{const pts=DATA.rounds.filter(x=>x.map===S.map&&x.side===S.side).flatMap(x=>x.snap.filter(s=>s.p===p));
     const c=count(pts,s=>s.call);return `<tr><td>${p}</td><td>${pts.length}</td><td>${topN(c,4).map(([k,v])=>`<span class=pill>${k} ${pct(v,pts.length)}</span>`).join('')}</td></tr>`}).join('');
  document.getElementById('main').innerHTML=`<div class=grid style="grid-template-columns:minmax(320px,560px) 1fr">
   <div class=card>${mapBox(S.map,r?r.snap:[],DATA.callouts[S.map])}${legend()}</div>
   <div class=grid><div class=card><h3>Round as text</h3>${r?`<p class=mut>${r.date} vs ${r.opp} · R${r.round} · ${S.side} · ${r.tier} · ${r.won?'won':'lost'}</p>`:''}${fk}<table>${trans}</table></div>
   <div class=card><h3>Where each player stands at the first kill (${S.side}, all ${S.map} rounds)</h3><table><tr><th>Player</th><th>n</th><th>Top callouts</th></tr>${players}</table></div>
   <div class=card style="max-height:320px;overflow:auto"><h3>Rounds (${R.length})</h3><table>${list}</table></div></div></div>`;
  showState({map:S.map,side:S.side,round:r&&`${r.date} R${r.round}`});
}
render();
"""

PAGES["2_ct_setups"] = r"""
const S={map:DATA.maps[0],fp:null};
function setMap(m){S.map=m;S.fp=null;render()} function pickFp(f){S.fp=f;render()}
function render(){
  const R=DATA.rounds.filter(r=>r.map===S.map&&r.side==='CT'&&r.fp);
  document.getElementById('bar').innerHTML=mapButtons(S,DATA.maps,false,'setMap')+` <span class=mut>CT rounds with a first-kill snapshot: ${R.length}</span>`;
  const groups={};R.forEach(r=>(groups[r.fp]=groups[r.fp]||[]).push(r));
  const rows=Object.entries(groups).sort((a,b)=>b[1].length-a[1].length).map(([fp,rs])=>{
    const w=rs.filter(r=>r.won).length, c=count(rs,r=>r.ctx), t=count(rs,r=>r.tier);
    const avg=(rs.reduce((s,r)=>s+r.fkT,0)/rs.length).toFixed(1);
    return `<tr class="click ${S.fp===fp?'sel':''}" onclick="pickFp('${fp}')"><td><b>${fp}</b></td><td>${frac(rs.length,R.length)}<div class=bar2 style="width:${100*rs.length/R.length}%"></div></td><td>${frac(w,rs.length)}</td><td>${avg}s</td>
      <td>${['pistol','after win','after loss'].map(k=>c[k]?`<span class=pill>${k} ${c[k]}</span>`:'').join('')}</td><td>${['eco','force','full'].map(k=>t[k]?`<span class=pill>${k} ${t[k]}</span>`:'').join('')}</td></tr>`}).join('');
  const sel=S.fp?groups[S.fp]:R;
  const dots=sel.flatMap(r=>r.snap.map(p=>({...p,op:0.75,title:`${p.p} · ${p.call} · ${r.date} R${r.round}`})));
  const zoneSpread=['A','Mid','B','C'].filter(z=>R.some(r=>r.snap.some(p=>p.zone===z))).map(z=>{const avg=(R.reduce((s,r)=>s+r.snap.filter(p=>p.zone===z).length,0)/R.length).toFixed(1);return `<span class=pill>${z}: avg ${avg} players</span>`}).join('');
  document.getElementById('main').innerHTML=`<div class=grid style="grid-template-columns:1fr minmax(300px,480px)">
   <div class=card><h3>Defensive spread at the first kill — ${S.map}</h3><p class=mut>Players per zone (A/Mid/B/C/spawn) at the moment of the first kill. Click a row to plot those rounds.</p><p>${zoneSpread}</p>
   <table><tr><th>Setup</th><th>Rounds</th><th>Won</th><th>Avg FK</th><th>Context</th><th>Buy</th></tr>${rows}</table></div>
   <div class=card><h3>${S.fp||'All setups'} <span class=mut>(${sel.length} rounds)</span></h3>${mapBox(S.map,dots,DATA.callouts[S.map].filter(c=>!c.label.includes('Spawn')))}${legend()}</div></div>`;
  showState({map:S.map,setup:S.fp,rounds:sel.length});
}
render();
"""

PAGES["3_anchors"] = r"""
const S={map:DATA.maps[0],side:'CT'};
function setMap(m){S.map=m;render()} function setSide(s){S.side=s;render()}
function render(){
  document.getElementById('bar').innerHTML=mapButtons(S,DATA.maps,false,'setMap')+' &nbsp; '+['CT','T'].map(s=>`<button class="${S.side===s?'on':''}" onclick="setSide('${s}')">${s}</button>`).join('');
  const R=DATA.rounds.filter(r=>r.map===S.map&&r.side===S.side);
  const cards=Object.keys(COLORS).map(p=>{
    const pts=R.flatMap(r=>r.snap.filter(s=>s.p===p).map(s=>({...s,title:`${s.call} · ${r.date} R${r.round}`})));
    if(!pts.length) return `<div class=card><h3>${p}</h3><p class=mut>no snapshots</p></div>`;
    const cz=count(pts,s=>s.zone), cc=count(pts,s=>s.call); const [tz,tzn]=topN(cz,1)[0]; const cons=Math.round(100*tzn/pts.length);
    const role=cons>=70?'fixed anchor':cons>=45?'mostly '+tz:'rotator / flexible';
    return `<div class=card><h3><i class=sw style="background:${COLORS[p]}"></i>${p} <span class=mut>· ${role}</span></h3>${mapBox(S.map,pts)}
      <p><b>${tz}</b> in ${cons}% of ${pts.length} rounds</p><p>${topN(cc,3).map(([k,v])=>`<span class=pill>${k} ${pct(v,pts.length)}</span>`).join('')}</p>
      <p class=mut>${topN(cz,4).map(([k,v])=>`${k} ${v}`).join(' · ')}</p></div>`}).join('');
  document.getElementById('main').innerHTML=`<p class=mut>Position of each player at the first kill of every ${S.side} round on ${S.map} (${R.length} rounds). "Consistency" = share of rounds in their most common zone.</p><div class=grid style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr))">${cards}</div>`;
  showState({map:S.map,side:S.side,rounds:R.length});
}
render();
"""

PAGES["4_t_tendencies"] = r"""
const S={map:'All'};
function setMap(m){S.map=m;render()}
function render(){
  document.getElementById('bar').innerHTML=mapButtons(S,DATA.maps,true,'setMap');
  const R=DATA.rounds.filter(r=>r.side==='T'&&(S.map==='All'||r.map===S.map));
  const sites=['A','B','C'].filter(s=>R.some(r=>r.plantSite===s));
  const row=(label,rs)=>{const n=rs.length;if(!n)return '';const w=rs.filter(r=>r.won).length;
    return `<tr><td><b>${label}</b></td><td>${n}</td>${sites.map(s=>{const k=rs.filter(r=>r.plantSite===s);return `<td>${k.length?frac(k.length,n):'—'}${k.length?`<br><span class=mut>avg ${(k.reduce((a,r)=>a+r.plantT,0)/k.length).toFixed(0)}s · won ${pct(k.filter(r=>r.won).length,k.length)}</span>`:''}</td>`}).join('')}
      <td>${frac(rs.filter(r=>!r.plantSite).length,n)}</td><td>${frac(w,n)}</td><td>${frac(rs.filter(r=>r.fk&&r.fk.sgeKill).length,n)}</td></tr>`};
  const tiers=['pistol','eco','force','full'].map(t=>row(t,R.filter(r=>r.tier===t))).join('');
  const ctx=['after win','after loss'].map(c=>row(c,R.filter(r=>r.ctx===c))).join('');
  const list=R.map(r=>`<tr><td>${r.map}</td><td>${r.date} vs ${r.opp}</td><td>R${r.round}</td><td>${r.tier}</td><td>${r.ctx}</td><td>${r.plantSite?r.plantSite+' @'+r.plantT+'s':'—'}</td><td>${r.fk?`${r.fk.sgeKill?'✔':'✘'} ${r.fk.t}s ${r.fk.sgeKill?r.fk.killerCall:r.fk.victimCall}`:''}</td><td>${r.won?'W':'L'}</td></tr>`).join('');
  const head=`<tr><th></th><th>Rounds</th>${sites.map(s=>`<th>Plant ${s}</th>`).join('')}<th>No plant</th><th>Won</th><th>Won opening duel</th></tr>`;
  document.getElementById('main').innerHTML=`<div class=grid><div class=card><h3>T side — ${S.map} (${R.length} rounds)</h3><table>${head}<tr><td colspan=9 class=mut>by buy type</td></tr>${tiers}<tr><td colspan=9 class=mut>by previous round</td></tr>${ctx}${row('ALL',R)}</table></div>
   <div class=card style="max-height:420px;overflow:auto"><h3>Round log</h3><table><tr><th>Map</th><th>Match</th><th>Rnd</th><th>Buy</th><th>Context</th><th>Plant</th><th>Opening duel</th><th></th></tr>${list}</table></div></div>`;
  showState({map:S.map,rounds:R.length});
}
render();
"""

PAGES["5_opening_duels"] = r"""
const S={map:'All',side:'Both'};
function setMap(m){S.map=m;render()} function setSide(s){S.side=s;render()}
function render(){
  document.getElementById('bar').innerHTML=mapButtons(S,DATA.maps,true,'setMap')+' &nbsp; '+['Both','CT','T'].map(s=>`<button class="${S.side===s?'on':''}" onclick="setSide('${s}')">${s}</button>`).join('');
  const R=DATA.rounds.filter(r=>r.fk&&(S.map==='All'||r.map===S.map)&&(S.side==='Both'||r.side===S.side));
  const teamFk=R.filter(r=>r.fk.sgeKill).length;
  const rows=Object.keys(COLORS).map(p=>{
    const fk=R.filter(r=>r.fk.sgeKill&&r.fk.killer===p), fd=R.filter(r=>!r.fk.sgeKill&&r.fk.victim===p);
    const fkw=fk.filter(r=>r.won).length, tr=fd.filter(r=>r.fk.traded).length;
    return `<tr><td><i class=sw style="background:${COLORS[p]}"></i><b>${p}</b></td><td>${fk.length}</td><td>${fd.length}</td><td><b>${fk.length-fd.length>0?'+':''}${fk.length-fd.length}</b></td>
     <td>${frac(fk.length,fk.length+fd.length)}</td><td>${frac(fkw,fk.length)}</td><td>${frac(tr,fd.length)}</td>
     <td>${topN(count(fk,r=>r.fk.killerCall),3).map(([k,v])=>`<span class=pill>${k} ${v}</span>`).join('')}</td>
     <td>${topN(count(fd,r=>r.fk.victimCall),3).map(([k,v])=>`<span class=pill>${k} ${v}</span>`).join('')}</td></tr>`}).join('');
  const times=R.map(r=>r.fk.t).sort((a,b)=>a-b); const med=times.length?times[Math.floor(times.length/2)]:0;
  document.getElementById('main').innerHTML=`<div class=card><h3>Opening duels — ${S.map} · ${S.side} (${R.length} rounds)</h3>
   <p>SGE win the opening duel in ${frac(teamFk,R.length)} · median first contact ${med}s · rounds won after winning it: ${frac(R.filter(r=>r.fk.sgeKill&&r.won).length,teamFk)} · after losing it: ${frac(R.filter(r=>!r.fk.sgeKill&&r.won).length,R.length-teamFk)}</p>
   <table><tr><th>Player</th><th>FK</th><th>FD</th><th>Net</th><th>Duel win</th><th>Round won after FK</th><th>FD traded (5s)</th><th>Where they get FKs</th><th>Where they die first</th></tr>${rows}</table></div>`;
  showState({map:S.map,side:S.side,rounds:R.length});
}
render();
"""

PAGES["6_all_games"] = r"""
function stats(rs){const ct=rs.filter(r=>r.side==='CT'),t=rs.filter(r=>r.side==='T'),pi=rs.filter(r=>r.tier==='pistol'),fk=rs.filter(r=>r.fk);
  const pl=t.filter(r=>r.plantSite);const sp=s=>pl.filter(r=>r.plantSite===s).length;
  return {ct:frac(ct.filter(r=>r.won).length,ct.length),t:frac(t.filter(r=>r.won).length,t.length),pistol:frac(pi.filter(r=>r.won).length,pi.length),
   fk:frac(fk.filter(r=>r.fk.sgeKill).length,fk.length),plants:['A','B','C'].filter(sp).map(s=>`${s} ${pct(sp(s),pl.length)}`).join(' · ')||'—',
   plantT:pl.length?(pl.reduce((a,r)=>a+r.plantT,0)/pl.length).toFixed(0)+'s':'—'}}
function render(){
  document.getElementById('bar').innerHTML='<span class=mut>The live site panels use the last 3 maps per map. This compares that window with every official game we have.</span>';
  const blocks=DATA.maps.map(m=>{const ms=DATA.matches.filter(x=>x.map===m).sort((a,b)=>b.date.localeCompare(a.date));const last=new Set(ms.slice(0,3).map(x=>x.matchId));
    const all=DATA.rounds.filter(r=>r.map===m), l3=all.filter(r=>last.has(r.matchId)); const a=stats(all), b=stats(l3);
    const row=(k,lab)=>`<tr><td>${lab}</td><td>${b[k]}</td><td>${a[k]}</td><td>${b[k]===a[k]?'':'<span class=pill>differs</span>'}</td></tr>`;
    return `<div class=card><h3>${m} <span class=mut>· ${ms.length} official maps (${ms.map(x=>x.date.slice(5)+' '+x.opp+' '+x.score).join(', ')})</span></h3>
     <table><tr><th></th><th>Last 3 maps (${l3.length} rnds)</th><th>All games (${all.length} rnds)</th><th></th></tr>${row('ct','CT rounds won')}${row('t','T rounds won')}${row('pistol','Pistols won')}${row('fk','Opening duels won')}${row('plants','T plant split')}${row('plantT','Avg plant time')}</table></div>`}).join('');
  document.getElementById('main').innerHTML=`<div class=grid style="grid-template-columns:repeat(auto-fill,minmax(420px,1fr))">${blocks}</div>`;
  showState({maps:DATA.maps.length,rounds:DATA.rounds.length});
}
render();
"""

PAGES["7_vetoes"] = r"""
function parse(v){if(!v)return null;const steps=[];let rem=null;v.split(';').map(s=>s.trim()).filter(Boolean).forEach(s=>{let m=s.match(/^(.*)\s+(ban|pick)\s+(\S+)$/);if(m){steps.push({who:m[1],kind:m[2],map:m[3]});return}m=s.match(/^(\S+)\s+remains$/);if(m)rem=m[1]});return {steps,rem}}
function render(){
  const V=DATA.vetoes.map(v=>({...v,p:parse(v.veto)})).filter(v=>v.p);
  const own=s=>s.who.toUpperCase().includes('SGE')||s.who.includes('Eintracht');
  const firstBan=count(V,v=>v.p.steps.find(s=>own(s)&&s.kind==='ban')?.map), bans=count(V.flatMap(v=>v.p.steps.filter(s=>own(s)&&s.kind==='ban')),s=>s.map);
  const picks=V.flatMap(v=>v.p.steps.filter(s=>own(s)&&s.kind==='pick').map(s=>{const mp=v.maps.find(x=>x.map===s.map);let res='not played';if(mp){const i=mp.teams[0].includes('Eintracht')?0:1;res=mp.score[i]>mp.score[1-i]?'W':'L';res+=` ${mp.score[i]}-${mp.score[1-i]}`}return {map:s.map,res,opp:v.opp}}));
  const oppBans=count(V.flatMap(v=>v.p.steps.filter(s=>!own(s)&&s.kind==='ban')),s=>s.map), dec=count(V,v=>v.p.rem);
  const pill=c=>topN(c,10).map(([k,n])=>`<span class=pill>${k} ×${n}</span>`).join('');
  const list=DATA.vetoes.map(v=>`<tr><td>${v.date}</td><td>${v.opp}</td><td>${v.result.join('-')}</td><td class=mut>${v.event}</td><td>${v.veto||'<span class=mut>no veto on VLR</span>'}</td></tr>`).join('');
  const all=[...new Set(DATA.vetoes.flatMap(v=>v.maps.map(m=>m.map)).concat(Object.keys(bans)).concat(Object.keys(oppBans)))];
  const pool=all.map(m=>{const pl=DATA.vetoes.flatMap(v=>v.maps.filter(x=>x.map===m));const w=pl.filter(x=>{const i=x.teams[0].includes('Eintracht')?0:1;return x.score[i]>x.score[1-i]}).length;
     return `<tr><td>${m}</td><td>${bans[m]||0}</td><td>${picks.filter(p=>p.map===m).length}</td><td>${oppBans[m]||0}</td><td>${dec[m]||0}</td><td>${pl.length?frac(w,pl.length):'—'}</td></tr>`}).join('');
  document.getElementById('main').innerHTML=`<div class=grid style="grid-template-columns:1fr 1fr">
   <div class=card><h3>SGE first ban</h3>${pill(firstBan)}<h3>All SGE bans</h3>${pill(bans)}<h3>SGE picks</h3>${picks.map(p=>`<span class=pill>${p.map} (${p.res} vs ${p.opp})</span>`).join('')}<h3>Opponents ban vs SGE</h3>${pill(oppBans)}<h3>Deciders</h3>${pill(dec)}</div>
   <div class=card><h3>Map pool view</h3><table><tr><th>Map</th><th>SGE bans</th><th>SGE picks</th><th>Opp bans</th><th>Decider</th><th>SGE map record</th></tr>${pool}</table></div>
   <div class=card style="grid-column:1/-1"><h3>Veto log (${V.length} with veto, ${DATA.vetoes.length} matches)</h3><table>${list}</table></div></div>`;
  showState({vetoes:V.length});
}
render();
"""

# ---------------------------------------------------------------- v2: conclusions (overrides pages 2 and 4)
PAGES["2_ct_setups"] = r"""
const S={map:DATA.maps[0],sel:0,fp:null};
function setMap(m){S.map=m;S.sel=0;S.fp=null;render()} function pickC(i){S.sel=i;S.fp=null;render()} function pickFp(f){S.fp=f;S.sel=null;render()}
function assignText(rs){ // typical player per zone inside a set of rounds
  const by={};Object.keys(COLORS).forEach(p=>{const m=modal(count(rs.flatMap(r=>r.snap.filter(s=>s.p===p)),s=>s.zone));if(m.k)(by[m.k]=by[m.k]||[]).push(p)});
  return ZORDER.filter(z=>by[z]).map(z=>`${z}: <b>${by[z].join(', ')}</b>`).join(' · ');
}
function ctConclusions(map){
  const R=DATA.rounds.filter(r=>r.map===map&&r.side==='CT'&&r.snap.length), E=R.filter(r=>r.fkT<=EARLY_S), C=[];
  if(E.length<4){C.push({lvl:'info',text:`Only ${E.length} CT rounds with a first kill inside ${EARLY_S}s — too few for setup conclusions.`});}
  // 1 default setup
  const g={};E.forEach(r=>(g[r.fp]=g[r.fp]||[]).push(r));const gs=Object.entries(g).sort((a,b)=>b[1].length-a[1].length);
  if(gs.length&&E.length>=4){const [fp,rs]=gs[0];const sh=rs.length/E.length;
    C.push({lvl:lvl(rs.length,sh,5,0.35),rounds:rs,text:`<b>Default setup ${fp}</b> in ${frac(rs.length,E.length)} of early CT rounds. In those rounds: ${assignText(rs)}.`});
    const spread=zonesOf(E).filter(z=>!z.includes('Spawn')).map(z=>`${z} ${avgZone(E,z).toFixed(1)}`).join(' · ');
    C.push({lvl:'info',rounds:E,text:`Average players per zone at first contact: ${spread}.`});}
  // 2 anchors / flex
  Object.keys(COLORS).forEach(p=>{const pts=E.flatMap(r=>r.snap.filter(s=>s.p===p).map(s=>({s,r})));if(pts.length<4)return;
    const zc=modal(count(pts,x=>x.s.zone)),sh=zc.n/pts.length,calls=topN(count(pts.filter(x=>x.s.zone===zc.k),x=>x.s.call),2).map(([k])=>k).join(' / ');
    const rs=pts.map(x=>x.r);
    if(sh>=0.7)C.push({lvl:lvl(pts.length,sh,6,0.7),rounds:rs,text:`<b>${p} anchors ${zc.k}</b> (${frac(zc.n,pts.length)}) — usually ${calls}.`});
    else if(sh<0.45){const z2=topN(count(pts,x=>x.s.zone),2);C.push({lvl:'lean',rounds:rs,text:`<b>${p} is the flexible player</b>: ${z2.map(([z,n])=>`${z} ${pct(n,pts.length)}`).join(' / ')} — rotates or fills where needed.`});}
  });
  // 3 forward play
  Object.keys(COLORS).forEach(p=>{const pts=R.flatMap(r=>r.snap.filter(s=>s.p===p&&FORWARD.test(s.call)).map(s=>({s,r})));const n=R.filter(r=>r.snap.some(s=>s.p===p)).length;
    if(pts.length>=3&&pts.length/n>=0.2)C.push({lvl:lvl(pts.length,pts.length/n,5,0.3),rounds:pts.map(x=>x.r),text:`<b>${p} plays forward</b> into attacker space in ${frac(pts.length,n)} rounds (${topN(count(pts,x=>x.s.call),2).map(([k,v])=>k+' '+v).join(', ')}).`});});
  // 4 adaptation after loss vs win
  const aw=E.filter(r=>r.ctx==='after win'),al=E.filter(r=>r.ctx==='after loss');
  if(aw.length>=3&&al.length>=3)zonesOf(E).filter(z=>!z.includes('Spawn')).forEach(z=>{const a=avgZone(al,z),b=avgZone(aw,z);
    if(Math.abs(a-b)>=0.6)C.push({lvl:lvl(Math.min(al.length,aw.length),Math.abs(a-b)/2,5,0.4),rounds:al,text:`<b>After a lost round they ${a>b?'add':'pull'} a player ${a>b?'to':'from'} ${z}</b>: ${a.toFixed(1)} players there vs ${b.toFixed(1)} after a win (${al.length} vs ${aw.length} rounds).`});});
  // 5 buy type
  const lowBuy=R.filter(r=>r.tier==='eco'||r.tier==='force'),full=R.filter(r=>r.tier==='full');
  if(lowBuy.length>=3){const fwd=rs=>rs.filter(r=>r.snap.some(s=>FORWARD.test(s.call))).length;const a=fwd(lowBuy)/lowBuy.length,b=full.length?fwd(full)/full.length:0;
    if(a-b>=0.25)C.push({lvl:lvl(lowBuy.length,a,5,0.5),rounds:lowBuy,text:`<b>On eco/force CT rounds they push up</b>: someone is in attacker space in ${pct(fwd(lowBuy),lowBuy.length)} of those rounds vs ${pct(Math.round(b*full.length),full.length)} on full buys — expect early aggression when they're poor.`});
    else C.push({lvl:'info',rounds:lowBuy,text:`Eco/force CT rounds (${lowBuy.length}): no clear change in aggression vs full buys.`});}
  // 6 setup outcomes
  const big=gs.filter(([,rs])=>rs.length>=3).map(([fp,rs])=>({fp,rs,w:rs.filter(r=>r.won).length/rs.length})).sort((a,b)=>b.w-a.w);
  if(big.length>=2&&big[0].w-big[big.length-1].w>=0.3){const b=big[0],w=big[big.length-1];
    C.push({lvl:'lean',rounds:b.rs,text:`<b>Their best setup: ${b.fp}</b> — won ${frac(b.rs.filter(r=>r.won).length,b.rs.length)}.`});
    C.push({lvl:'lean',rounds:w.rs,text:`<b>Their weakest setup: ${w.fp}</b> — won ${frac(w.rs.filter(r=>r.won).length,w.rs.length)}. Hit the side it leaves thin.`});}
  // 7 first contact + weak spot
  const F=DATA.rounds.filter(r=>r.map===map&&r.side==='CT'&&r.fk);
  const spot=r=>r.fk.sgeKill?r.fk.killerCall:r.fk.victimCall, cs=count(F,spot), t=modal(cs);
  if(t.k&&t.n>=3){const rs=F.filter(r=>spot(r)===t.k);C.push({lvl:lvl(t.n,t.n/F.length,6,0.25),rounds:rs,text:`<b>First contact most often at ${t.k}</b> (${frac(t.n,F.length)} rounds) — SGE win it ${frac(rs.filter(r=>r.fk.sgeKill).length,t.n)}.`});}
  const deaths=F.filter(r=>!r.fk.sgeKill),dc=modal(count(deaths,r=>r.fk.victimCall));
  if(dc.k&&dc.n>=3){const rs=deaths.filter(r=>r.fk.victimCall===dc.k);const who=modal(count(rs,r=>r.fk.victim));
    C.push({lvl:lvl(dc.n,dc.n/Math.max(deaths.length,1),5,0.3),rounds:rs,text:`<b>Weak spot: they lose the first duel most at ${dc.k}</b> (${dc.n} of ${deaths.length} first deaths), mostly <b>${who.k}</b> (${who.n}).`});}
  const late=R.filter(r=>r.fkT>EARLY_S);if(late.length>=3)C.push({lvl:'info',rounds:late,text:`${frac(late.length,R.length)} CT rounds have no fight before ${EARLY_S}s — attackers take their time vs SGE (those rounds are excluded from the setup statements).`});
  return {C,R,E,gs};
}
function render(){
  const {C,R,E,gs}=ctConclusions(S.map);
  document.getElementById('bar').innerHTML=mapButtons(S,DATA.maps,false,'setMap')+` <span class=mut>CT rounds: ${R.length} · early (first kill ≤${EARLY_S}s): ${E.length}</span>`;
  const evidence=S.fp?(gs.find(([f])=>f===S.fp)||[null,[]])[1]:(S.sel!=null&&C[S.sel]?.rounds)||E;
  const dots=evidence.flatMap(r=>r.snap.map(p=>({...p,op:0.8,title:`${p.p} · ${p.call} · ${r.date} vs ${r.opp} R${r.round} · FK ${r.fkT}s · ${r.won?'won':'lost'}`})));
  const rows=gs.map(([fp,rs])=>`<tr class="click ${S.fp===fp?'sel':''}" onclick="pickFp('${fp}')"><td><b>${fp}</b></td><td>${frac(rs.length,E.length)}</td><td>${frac(rs.filter(r=>r.won).length,rs.length)}</td><td class=mut>${assignText(rs)}</td></tr>`).join('');
  const ev=evidence.map(r=>`<tr><td>${r.date} vs ${r.opp}</td><td>R${r.round}</td><td>${r.tier}</td><td>${r.ctx}</td><td>FK ${r.fkT}s ${r.fk?(r.fk.sgeKill?'✔':'✘'):''}</td><td>${r.won?'W':'L'}</td></tr>`).join('');
  document.getElementById('main').innerHTML=`<div class=grid style="grid-template-columns:1fr minmax(320px,500px)">
   <div class=grid><div class=card><h3>What's happening — SGE CT on ${S.map}</h3><p class=mut>Click a statement to plot the rounds behind it. <b>strong</b> = enough rounds and a clear split · <b>lean</b> = indication only.</p>${conclList(C,S.sel,'pickC')}</div>
   <div class=card><h3>All setups (early rounds)</h3><table><tr><th>Setup</th><th>Rounds</th><th>Won</th><th>Who stands where</th></tr>${rows}</table></div></div>
   <div class=grid><div class=card><h3>Evidence <span class=mut>(${evidence.length} rounds)</span></h3>${mapBox(S.map,dots,DATA.callouts[S.map].filter(c=>!c.label.includes('Spawn')))}${legend()}</div>
   <div class=card style="max-height:300px;overflow:auto"><table>${ev}</table></div></div></div>`;
  showState({map:S.map,conclusions:C.length,selected:S.fp||(C[S.sel]&&C[S.sel].text.replace(/<[^>]+>/g,'').slice(0,60))});
}
render();
"""

PAGES["4_t_tendencies"] = r"""
const S={map:DATA.maps[0],sel:0};
function setMap(m){S.map=m;S.sel=0;render()} function pickC(i){S.sel=i;render()}
function siteSplit(rs){const pl=rs.filter(r=>r.plantSite);const c=count(pl,r=>r.plantSite);return {pl,c,txt:['A','B','C'].filter(s=>c[s]).map(s=>`${s} ${pct(c[s],pl.length)}`).join(' · ')||'no plants'};}
function tConclusions(map){
  const R=DATA.rounds.filter(r=>r.side==='T'&&(map==='All'||r.map===map)),C=[];
  const all=siteSplit(R),top=modal(all.c);
  if(all.pl.length>=4){const sh=top.n/all.pl.length;
    C.push(sh>=0.5?{lvl:lvl(all.pl.length,sh,8,0.65),rounds:all.pl.filter(r=>r.plantSite===top.k),text:`<b>They prefer ${top.k}</b>: ${frac(top.n,all.pl.length)} of plants (${all.txt}).`}
                  :{lvl:'info',rounds:all.pl,text:`No clear site preference: ${all.txt} over ${all.pl.length} plants.`});}
  ['pistol','eco','force','full'].forEach(t=>{const rs=R.filter(r=>r.tier===t);if(rs.length<3)return;const sp=siteSplit(rs),m=modal(sp.c),np=rs.length-sp.pl.length;
    if(t==='eco'&&np/rs.length>=0.6)C.push({lvl:lvl(rs.length,np/rs.length,5,0.6),rounds:rs,text:`<b>On ecos they rarely plant</b> (${frac(np,rs.length)} no plant) — expect saves / pick hunting, won ${frac(rs.filter(r=>r.won).length,rs.length)}.`});
    else if(m.k&&m.n/Math.max(sp.pl.length,1)>=0.6&&m.n>=3)C.push({lvl:lvl(m.n,m.n/sp.pl.length,5,0.7),rounds:sp.pl.filter(r=>r.plantSite===m.k),text:`<b>${t[0].toUpperCase()+t.slice(1)} rounds go ${m.k}</b>: ${frac(m.n,sp.pl.length)} of ${t} plants (${sp.txt}).`});
    else C.push({lvl:'info',rounds:rs,text:`${t[0].toUpperCase()+t.slice(1)} rounds (${rs.length}): ${sp.txt}, no plant ${np}, won ${frac(rs.filter(r=>r.won).length,rs.length)}.`});});
  const aw=siteSplit(R.filter(r=>r.ctx==='after win')),al=siteSplit(R.filter(r=>r.ctx==='after loss'));
  if(aw.pl.length>=3&&al.pl.length>=3)['A','B','C'].forEach(s=>{const a=(al.c[s]||0)/al.pl.length,b=(aw.c[s]||0)/aw.pl.length;
    if(a-b>=0.2)C.push({lvl:lvl(al.pl.length,a-b,6,0.3),rounds:al.pl.filter(r=>r.plantSite===s),text:`<b>After a lost round they go ${s} more</b>: ${pct(al.c[s]||0,al.pl.length)} of plants vs ${pct(aw.c[s]||0,aw.pl.length)} after a win.`});});
  ['A','B','C'].forEach(s=>{const pl=R.filter(r=>r.plantSite===s);if(pl.length<3)return;const avg=pl.reduce((a,r)=>a+r.plantT,0)/pl.length,fast=pl.filter(r=>r.plantT<=40);
    if(fast.length/pl.length>=0.4)C.push({lvl:lvl(fast.length,fast.length/pl.length,4,0.5),rounds:fast,text:`<b>${s} is hit fast</b>: ${frac(fast.length,pl.length)} plants within 40s (avg ${avg.toFixed(0)}s) — be set early on ${s}.`});
    else if(avg>=65)C.push({lvl:lvl(pl.length,1,5,0),rounds:pl,text:`<b>${s} is a late hit</b>: avg plant at ${avg.toFixed(0)}s — default first, then commit to ${s}.`});
    const w=pl.filter(r=>r.won).length;if(pl.length>=4&&(w/pl.length>=0.75||w/pl.length<=0.35))C.push({lvl:'lean',rounds:pl,text:`When they plant ${s} they win ${frac(w,pl.length)} — ${w/pl.length>=0.75?'their strong site, retakes there are hard':'their post-plant on '+s+' is beatable'}.`});});
  const F=R.filter(r=>r.fk&&r.fk.sgeKill),fc=modal(count(F,r=>r.fk.killerCall));
  if(fc.k&&fc.n>=3){const rs=F.filter(r=>r.fk.killerCall===fc.k);const who=modal(count(rs,r=>r.fk.killer));C.push({lvl:lvl(fc.n,fc.n/F.length,5,0.2),rounds:rs,text:`<b>Their opening picks come from ${fc.k}</b> (${fc.n} of ${F.length} T first kills), mostly <b>${who.k}</b>.`});}
  const D=R.filter(r=>r.fk&&!r.fk.sgeKill),dc=modal(count(D,r=>r.fk.victimCall));
  if(dc.k&&dc.n>=3){const rs=D.filter(r=>r.fk.victimCall===dc.k);const who=modal(count(rs,r=>r.fk.victim));C.push({lvl:lvl(dc.n,dc.n/D.length,5,0.25),rounds:rs,text:`<b>They die first at ${dc.k}</b> (${dc.n} of ${D.length}), mostly <b>${who.k}</b> — hold that angle.`});}
  const pis=R.filter(r=>r.tier==='pistol');if(pis.length)C.push({lvl:'info',rounds:pis,text:`Pistol plans: ${pis.map(r=>`${r.map.slice(0,3)} ${r.plantSite||'—'}${r.won?'✔':'✘'}`).join(', ')}.`});
  return {C,R};
}
function render(){
  const {C,R}=tConclusions(S.map);
  document.getElementById('bar').innerHTML=mapButtons(S,DATA.maps,true,'setMap')+` <span class=mut>T rounds: ${R.length}</span>`;
  const ev=(S.sel!=null&&C[S.sel]?.rounds)||R;
  const dots=ev.flatMap(r=>r.snap.map(p=>({...p,op:0.8,title:`${p.p} · ${p.call} · ${r.date} vs ${r.opp} R${r.round}`})));
  const evRows=ev.map(r=>`<tr><td>${r.map}</td><td>${r.date} vs ${r.opp}</td><td>R${r.round}</td><td>${r.tier}</td><td>${r.ctx}</td><td>${r.plantSite?r.plantSite+' @'+r.plantT+'s':'—'}</td><td>${r.fk?`${r.fk.sgeKill?'✔':'✘'} ${r.fk.t}s ${r.fk.sgeKill?r.fk.killerCall:r.fk.victimCall}`:''}</td><td>${r.won?'W':'L'}</td></tr>`).join('');
  document.getElementById('main').innerHTML=`<div class=grid style="grid-template-columns:1fr minmax(320px,500px)">
   <div class=grid><div class=card><h3>What's happening — SGE T side on ${S.map}</h3><p class=mut>Click a statement to see its rounds.</p>${conclList(C,S.sel,'pickC')}</div>
   <div class=card style="max-height:360px;overflow:auto"><h3>Evidence rounds (${ev.length})</h3><table>${evRows}</table></div></div>
   <div class=card><h3>Positions at first contact</h3>${S.map==='All'?'<p class=mut>Pick a single map to plot positions.</p>':mapBox(S.map,dots,DATA.callouts[S.map].filter(c=>!c.label.includes('Spawn')))+legend()}</div></div>`;
  showState({map:S.map,conclusions:C.length,selected:C[S.sel]&&C[S.sel].text.replace(/<[^>]+>/g,'').slice(0,60)});
}
render();
"""

PAGES["8_conditions"] = r"""
const S={player:'All',map:'All',side:'All',str:'p05',sel:null,theme:null};
const RK={};DATA.rounds.forEach(r=>RK[r.matchId+'|'+r.round]=r);
function f(k,v){S[k]=v;S.sel=null;S.theme=null;render()} function pick(i){S.sel=i;S.theme=null;render()} function pickT(i){S.theme=i;S.sel=null;render()}
function btns(k,vals){return vals.map(v=>`<button class="${S[k]===v?'on':''}" onclick="f('${k}','${v}')">${v}</button>`).join('')}
function list(){return DATA.findings.filter(x=>(S.player==='All'||(S.player==='team'?!x.player:x.player===S.player))&&(S.map==='All'||x.map===S.map)&&(S.side==='All'||x.side===S.side)&&(S.str==='all'||x.p<=0.05))}
function evidence(x){
  const inK=new Set(x.rounds), early=r=>r.snap.length&&r.fkT<=35;
  const pool=DATA.rounds.filter(r=>r.map===x.map&&r.side===x.side&&(x.player?early(r):true));
  const dots=[];
  pool.forEach(r=>{const inside=inK.has(r.matchId+'|'+r.round);
    r.snap.filter(s=>!x.player||s.p===x.player).forEach(s=>dots.push({...s,op:inside?0.95:0.25,color:inside?undefined:'#9E9E9E',title:`${s.p} · ${s.call} · ${r.date} R${r.round} · ${inside?'IN condition':'outside'}`}))});
  const rows=x.rounds.map(k=>RK[k]).filter(Boolean).map(r=>{const sp=x.player?r.snap.find(s=>s.p===x.player):null;
    const w=x.player?(r.weapons[x.player]||''):Object.entries(r.weapons).filter(([,w])=>w==='Operator').map(([p])=>p+' OP').join(', ');
    return `<tr><td>${r.date} vs ${r.opp}</td><td>R${r.round}</td><td>${r.tier} / opp ${r.oppTier}</td><td>${w}</td><td>${sp?sp.call:(r.plantSite?'plant '+r.plantSite:'—')}</td><td>${r.won?'W':'L'}</td></tr>`}).join('');
  return {dots,rows};
}
function render(){
  const players=['All','team',...Object.keys(COLORS)];
  document.getElementById('bar').innerHTML=btns('player',players)+' &nbsp; '+btns('map',['All',...DATA.maps])+' &nbsp; '+btns('side',['All','CT','T'])+' &nbsp; '+
    `<button class="${S.str==='p05'?'on':''}" onclick="f('str','p05')">p ≤ 0.05</button><button class="${S.str==='all'?'on':''}" onclick="f('str','all')">all (p ≤ 0.15)</button>`;
  const L=list(), x=S.sel!=null?L[S.sel]:null, t=S.theme!=null?DATA.themes[S.theme]:null;
  const items=L.map((y,i)=>`<div class="concl ${y.strength==='strong'?'strong':(y.p<=0.05?'lean':'info')} ${S.sel===i?'sel':''}" onclick="pick(${i})"><span class=tag>${y.map} ${y.side}</span>${y.text} <span class=mut>· p=${y.p} · q=${y.q}</span></div>`).join('')||'<p class=mut>No findings for this filter.</p>';
  const th=DATA.themes.filter(y=>(S.map==='All'||y.map===S.map)&&(S.side==='All'||y.side===S.side)&&(S.player==='All'||y.subjects.includes(S.player))).map(y=>{const i=DATA.themes.indexOf(y);
    return `<div class="concl strong ${S.theme===i?'sel':''}" onclick="pickT(${i})"><span class=tag>${y.subjects.length} agree</span><b>${y.text}</b><div class=mut style="margin-top:4px">${y.items.map(s=>'• '+s).join('<br>')}</div></div>`}).join('');
  let right='<p class=mut>Click a finding: the player\'s positions inside the condition are coloured, all other rounds grey — so you see the shift on the map.</p>';
  if(x){const e=evidence(x);right=`<h3>${x.map} ${x.side} — ${x.subject}</h3><p>${x.text}</p>${mapBox(x.map,e.dots,DATA.callouts[x.map].filter(c=>!c.label.includes('Spawn')))}<p class=mut>coloured = “${x.cond}” · grey = other rounds</p><div style="max-height:260px;overflow:auto"><table><tr><th>Match</th><th>Rnd</th><th>Buy</th><th>Weapon</th><th>Position</th><th></th></tr>${e.rows}</table></div>`;}
  if(t){const dots=t.rounds.map(k=>RK[k]).filter(Boolean).flatMap(r=>r.snap.filter(s=>t.subjects.includes(s.p)).map(s=>({...s,title:`${s.p} · ${s.call} · ${r.date} R${r.round}`})));
    right=`<h3>${t.text}</h3>${mapBox(t.map,dots,DATA.callouts[t.map].filter(c=>!c.label.includes('Spawn')))}${legend()}<p class=mut>${t.rounds.length} rounds in the condition</p>`;}
  document.getElementById('main').innerHTML=`<div class=grid style="grid-template-columns:1fr minmax(320px,500px)">
   <div class=grid><div class=card><h3>Corroborated patterns <span class=mut>— 2+ players (or player + team) shift the same way under the same condition</span></h3>${th||'<p class=mut>none for this filter</p>'}</div>
   <div class=card><h3>Single findings (${L.length})</h3><p class=mut>Fisher exact test per condition, ~2,600 tests on 13 maps: some single findings will be chance. Trust corroborated patterns and low q-values more. Conditions overlap (enemy sniper ≈ enemy full buy; own sniper ≈ own full buy).</p>${items}</div></div>
   <div class=card>${right}</div></div>`;
  showState({filter:{player:S.player,map:S.map,side:S.side,str:S.str},shown:L.length,selected:x&&x.text.slice(0,70)});
}
render();

"""

PAGES["9_explained"] = r"""
document.head.insertAdjacentHTML('beforeend',`<style>
.ov{position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:50;overflow:auto}
.ovbox{max-width:1500px;margin:18px auto;background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.ovhead{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.big{font:700 22px 'Space Grotesk',Inter,sans-serif;margin:0 0 6px}
.read{background:#10241a;border:1px solid #1f5135;border-radius:8px;padding:10px 12px;margin:10px 0;font-size:15px}
.num{display:grid;grid-template-columns:140px 1fr 1fr;gap:6px 14px;align-items:center;margin:8px 0}
.barw{background:#0b1014;border-radius:4px;height:16px;position:relative;overflow:hidden}.barf{height:100%;border-radius:4px}
.barl{position:absolute;left:6px;top:0;font:600 11px/16px Inter;color:#fff;text-shadow:0 0 3px #000}
.maps2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.maps2 h4{margin:4px 0 6px}
.tabs button{margin-right:6px}.ev td{font-size:13px}.ev tr.hl{background:#2a3a1f}
.hit{color:var(--acc);font-weight:600}.miss{color:#f87171}
.dot.ring{width:16px;height:16px;margin:-8px 0 0 -8px;border:3px solid #fff;z-index:5}
.plant{position:absolute;width:14px;height:14px;margin:-7px 0 0 -7px;transform:rotate(45deg);border:2px solid #000;z-index:3}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
.bcard{cursor:pointer}.bcard:hover{border-color:var(--acc)}.bcard .t{font-weight:700;font-size:15px}.detail{background:#121a21;border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-top:8px;font-size:13px}
</style>`);
const AGGR_RE=FORWARD;
const zoneOf=(r,p)=>{const s=r.snap.find(x=>x.p===p);return s?s:null};
const early=r=>r.snap.length&&r.fkT!=null&&r.fkT<=EARLY_S;
const SITE_COL={A:'#3b82f6',B:'#f97316',C:'#a855f7'};
// ---------- the 8 behaviours (explicit, auditable definitions) ----------
const B=[
 {id:1,title:'foe with a sniper on Split CT plays B; without one, A',map:'Split',side:'CT',subjects:['foe'],needEarly:true,
  read:'On Split defence foe is the sniper player. <b>With a sniper</b> foe holds <b>B</b> (B Back / Garage / Site) in about half the rounds, otherwise plays Mid with it. <b>Without a sniper</b> foe is almost never on B (1 of 10) and plays <b>A</b> instead (7 of 10). Seeing foe\'s weapon tells you whether B or A gets foe.',
  cond:r=>r.wcat.foe==='Sniper',condLabel:'foe has a sniper',notLabel:'foe has no sniper',
  outcome:(r,p)=>{const s=zoneOf(r,p);return s?{hit:s.zone==='B',txt:s.call}:null},outcomeLabel:'plays B',
  key:r=>`foe: ${r.weapons.foe||'?'}`},
 {id:2,title:'Ascent CT, SGE on eco: the whole team pushes forward',map:'Ascent',side:'CT',subjects:['foe','musashi','azury','H1ber'],needEarly:true,
  read:'When SGE are broke on Ascent defence they don\'t sit on sites — four players push into attacker space (Mains / Lobbies) looking for early picks. On their eco rounds, clear close to spawn exits and expect contact early.',
  cond:r=>r.tier==='eco',condLabel:'SGE eco buy',notLabel:'SGE pistol/force/full buy',
  outcome:(r,p)=>{const s=zoneOf(r,p);return s?{hit:AGGR_RE.test(s.call),txt:s.call}:null},outcomeLabel:'plays forward (attacker space)',
  key:r=>`SGE avg loadout ${r.avgLoadout}`},
 {id:3,title:'Split T: after a successful B hit, nobody goes A',map:'Split',side:'T',subjects:['foe','musashi','H1ber'],needEarly:true,
  read:'After SGE win a round by hitting B on Split attack, foe, musashi and H1ber stay off A the next round — they go back to B or mid. A won B round is a strong sign the next one is not A.',
  cond:r=>r.prevPlant==='B'&&r.prevSameSideWon===true,condLabel:'previous T round: won a B hit',notLabel:'all other T rounds',
  outcome:(r,p)=>{const s=zoneOf(r,p);return s?{hit:s.zone==='A',txt:s.call}:null},outcomeLabel:'plays A',
  key:r=>`prev: ${r.prevPlant||'—'} ${r.prevSameSideWon===true?'won':r.prevSameSideWon===false?'lost':''}`},
 {id:4,title:'Split T: after an A plant they go A again',map:'Split',side:'T',subjects:['foe','musashi','H1ber'],needEarly:true,
  read:'After an A plant on Split attack, foe, musashi and H1ber line up on A again the next round. If they planted A last round, expect A pressure again.',
  cond:r=>r.prevPlant==='A',condLabel:'previous T round: planted A',notLabel:'previous T round: no A plant',
  outcome:(r,p)=>{const s=zoneOf(r,p);return s?{hit:s.zone==='A',txt:s.call}:null},outcomeLabel:'plays A',
  key:r=>`prev plant: ${r.prevPlant||'—'}`},
 {id:5,title:'Enemy has a sniper → Ascent T: Fizzy, azury, foe shift to A and avoid Mid',map:'Ascent',side:'T',subjects:['Fizzy','azury','foe'],needEarly:true,
  read:'On Ascent attack, an enemy Operator pushes SGE out of Mid: Fizzy, azury and foe play the A side instead. If you show an OP, expect A-side pressure rather than mid control.',
  cond:r=>r.oppSnipers>0,condLabel:'enemy has a sniper',notLabel:'no enemy sniper',
  outcome:(r,p)=>{const s=zoneOf(r,p);return s?{hit:s.zone==='A',txt:s.call}:null},outcomeLabel:'plays A',
  extra:{label:'plays Mid',fn:(r,p)=>{const s=zoneOf(r,p);return s?s.zone==='Mid':null}},
  key:r=>`enemy snipers: ${r.oppSnipers}`},
 {id:6,title:'Enemy force buy → Lotus T: SGE hit B',map:'Lotus',side:'T',subjects:['team'],needEarly:false,plants:true,
  read:'On Lotus attack, when the enemy is on a force buy SGE go <b>B</b> (otherwise mostly A). On your force-buy rounds, B is the likely hit.',
  cond:r=>r.oppTier==='force',condLabel:'enemy force buy',notLabel:'enemy pistol/eco/full buy',filter:r=>!!r.plantSite,
  outcome:(r)=>({hit:r.plantSite==='B',txt:'plant '+r.plantSite+' @'+r.plantT+'s'}),outcomeLabel:'plant B (of planted rounds)',
  key:r=>`enemy avg loadout ${r.oppAvg}`},
 {id:7,title:'Enemy force buy → Split CT: 3-man B stack',map:'Split',side:'CT',subjects:['team'],needEarly:true,
  read:'On Split defence, when the enemy is on a force buy SGE stack <b>B with three players</b> (they never do it otherwise). On your force buys, A is likely light.',
  cond:r=>r.oppTier==='force',condLabel:'enemy force buy',notLabel:'enemy pistol/eco/full buy',
  outcome:(r)=>{const n=r.snap.filter(s=>s.zone==='B').length;return {hit:n>=3,txt:`${n} on B`}},outcomeLabel:'3+ players on B',
  key:r=>`enemy avg loadout ${r.oppAvg}`},
 {id:8,title:"Fizzy's Lotus CT position depends on the agent",map:'Lotus',side:'CT',subjects:['Fizzy'],needEarly:true,
  read:'Fizzy\'s Lotus defence spot follows the agent: on <b>Omen</b> Fizzy plays A, on <b>Harbor</b> Fizzy plays B. The agent select tells you where Fizzy will be.',
  filter:r=>['Omen','Harbor'].includes(r.agentNames.Fizzy),
  cond:r=>r.agentNames.Fizzy==='Omen',condLabel:'Fizzy on Omen',notLabel:'Fizzy on Harbor',
  outcome:(r,p)=>{const s=zoneOf(r,p);return s?{hit:s.zone==='A',txt:s.call}:null},outcomeLabel:'plays A',
  extra:{label:'plays B',fn:(r,p)=>{const s=zoneOf(r,p);return s?s.zone==='B':null}},
  key:r=>`Fizzy: ${r.agentNames.Fizzy}`},
];
// ---------- stats ----------
function lf(n){let s=0;for(let i=2;i<=n;i++)s+=Math.log(i);return s}
function fisher(a,b,c,d){const n=a+b+c+d,r1=a+b,c1=a+c,lp=k=>lf(r1)+lf(n-r1)+lf(c1)+lf(n-c1)-lf(n)-lf(k)-lf(r1-k)-lf(c1-k)-lf(n-r1-c1+k);
  const p0=lp(a);let p=0;for(let k=Math.max(0,r1+c1-n);k<=Math.min(r1,c1);k++){const v=lp(k);if(v<=p0+1e-9)p+=Math.exp(v)}return Math.min(1,p)}
function eligible(b){return DATA.rounds.filter(r=>r.map===b.map&&r.side===b.side&&(!b.needEarly||early(r))&&(!b.filter||b.filter(r)))}
function tally(b,rs,p,fn){let n=0,h=0;rs.forEach(r=>{const o=fn(r,p);if(o==null)return;n++;if(o===true||o.hit)h++});return {n,h}}
function summary(b){const R=eligible(b),IN=R.filter(b.cond),OUT=R.filter(r=>!b.cond(r));
  const rows=b.subjects.map(p=>{const a=tally(b,IN,p,b.outcome),c=tally(b,OUT,p,b.outcome);return {p,a,c,pv:fisher(a.h,a.n-a.h,c.h,c.n-c.h)}});
  const ex=b.extra?b.subjects.map(p=>{const a=tally(b,IN,p,b.extra.fn),c=tally(b,OUT,p,b.extra.fn);return {p,a,c}}):null;
  return {R,IN,OUT,rows,ex}}
// ---------- rendering ----------
const S={open:null,tab:'in',hl:null};
function bar(h,n,col){const w=n?100*h/n:0;return `<div class=barw><div class=barf style="width:${w}%;background:${col}"></div><span class=barl>${h}/${n} · ${n?Math.round(w):0}%</span></div>`}
function dotsFor(b,rs,hl){
  if(b.plants){return rs.filter(r=>r.plantXY).map(r=>{const k=r.matchId+'|'+r.round,on=!hl||hl===k;return `<div class=plant title="${r.date} vs ${r.opp} R${r.round} · plant ${r.plantSite} @${r.plantT}s" style="left:${r.plantXY[0]}%;top:${r.plantXY[1]}%;background:${SITE_COL[r.plantSite]};opacity:${on?1:.15}"></div>`}).join('')}
  return rs.flatMap(r=>{const k=r.matchId+'|'+r.round,on=!hl||hl===k;return r.snap.filter(s=>b.subjects.includes('team')||b.subjects.includes(s.p)||(hl===k)).map(s=>
    `<div class="dot ${hl===k?'ring':''}" title="${s.p} · ${s.call} · ${r.date} vs ${r.opp} R${r.round}" style="left:${s.nx}%;top:${s.ny}%;background:${COLORS[s.p]};opacity:${on?(b.subjects.includes(s.p)||b.subjects.includes('team')?0.95:0.6):0.12}"></div>`)}).join('')}
function mapWith(b,rs,hl){const labels=DATA.callouts[b.map].filter(c=>!c.label.includes('Spawn')).map(c=>`<div class=lbl style="left:${c.nx}%;top:${c.ny}%">${c.label}</div>`).join('');
  return `<div class=mapbox><div class="mapframe ${ROT.has(b.map)?'rot':''}"><img src="maps/${b.map}.png">${labels}${dotsFor(b,rs,hl)}</div></div>`}
function evRow(b,r){const k=r.matchId+'|'+r.round;
  const outs=b.subjects.map(p=>{const o=b.outcome(r,p);return o?`<span class="${o.hit?'hit':'miss'}">${p==='team'?'':p+': '}${o.txt}${o.hit?' ✓':''}</span>`:`<span class=mut>${p}: —</span>`}).join('<br>');
  return `<tr class="click ${S.hl===k?'hl':''}" onclick="hl('${k}')"><td>${r.date}<br><span class=mut>vs ${r.opp}</span></td><td>R${r.round}</td><td>${r.scoreBefore[0]}-${r.scoreBefore[1]}</td><td>${r.tier}<br><span class=mut>opp ${r.oppTier}</span></td><td>${b.key(r)}</td><td>${outs}</td><td>${r.won?'<span class=hit>W</span>':'<span class=miss>L</span>'}</td></tr>`}
function detail(k){const r=DATA.rounds.find(x=>x.matchId+'|'+x.round===k);if(!r)return '';
  return `<div class=detail><b>${r.date} vs ${r.opp} · R${r.round} · ${r.side} · score ${r.scoreBefore[0]}-${r.scoreBefore[1]} · ${r.won?'won':'lost'}</b><br>
   Positions at first contact (${r.fkT}s): ${r.snap.map(s=>`<span class=pill><i class=sw style="background:${COLORS[s.p]}"></i>${s.p} ${s.call} · ${r.weapons[s.p]||''} · ${r.agentNames[s.p]||''}</span>`).join('')}<br>
   ${r.fk?`First kill: ${r.fk.killer||'enemy'} (${r.fk.killerCall}) → ${r.fk.victim||'enemy'} (${r.fk.victimCall}) — ${r.fk.sgeKill?'SGE won it':'SGE lost it'}`:''} ${r.plantSite?` · plant ${r.plantSite} @${r.plantT}s`:''}</div>`}
function openB(i){S.open=i;S.tab='in';S.hl=null;render()} function closeB(){S.open=null;render()} function tab(t){S.tab=t;render()} function hl(k){S.hl=S.hl===k?null:k;render()}
function nav(d){S.open=(S.open+d+B.length)%B.length;S.tab='in';S.hl=null;render()}
function overlay(b){const s=summary(b),inC=SITE_COL.B,ouC='#64748b';
  const nums=s.rows.map(x=>`<div><i class=sw style="background:${COLORS[x.p]||'#e5e7eb'}"></i><b>${x.p}</b> <span class=mut>p=${x.pv.toFixed(3)}</span></div><div>${bar(x.a.h,x.a.n,'#22c55e')}</div><div>${bar(x.c.h,x.c.n,ouC)}</div>`).join('');
  const exNums=s.ex?s.ex.map(x=>`<div class=mut>${x.p} ${b.extra.label}</div><div>${bar(x.a.h,x.a.n,'#16a34a')}</div><div>${bar(x.c.h,x.c.n,ouC)}</div>`).join(''):'';
  const list=(S.tab==='in'?s.IN:s.OUT).map(r=>evRow(b,r)).join('');
  return `<div class=ov onclick="if(event.target===this)closeB()"><div class=ovbox>
   <div class=ovhead><div><div class=mut>Behaviour ${b.id} of ${B.length} · ${b.map} ${b.side} · Eintracht Frankfurt</div><p class=big>${b.title}</p></div>
   <div><button onclick="nav(-1)">◀</button> <button onclick="nav(1)">▶</button> <button onclick="closeB()">✕ close</button></div></div>
   <div class=read>💡 ${b.read}</div>
   <div class=card><h3>The numbers — “${b.outcomeLabel}”</h3>
    <div class=num><div></div><div><b>${b.condLabel}</b> <span class=mut>(${s.IN.length} rounds)</span></div><div><b>${b.notLabel}</b> <span class=mut>(${s.OUT.length} rounds)</span></div>${nums}${exNums}</div>
    <p class=mut>Bars = rounds where the outcome happened / rounds the player was seen. ${b.needEarly?`Positions are taken at the first kill in rounds where it happens within ${EARLY_S}s (so they still show the setup, not rotations).`:'All planted rounds counted.'} p = Fisher exact test (small samples — read as a lean, not a rule).</p></div>
   <div class=maps2 style="margin-top:12px"><div class=card><h4>✅ ${b.condLabel} <span class=mut>(${s.IN.length})</span></h4>${mapWith(b,s.IN,S.tab==='in'?S.hl:null)}</div>
     <div class=card><h4>➖ ${b.notLabel} <span class=mut>(${s.OUT.length})</span></h4>${mapWith(b,s.OUT,S.tab==='out'?S.hl:null)}</div></div>
   ${b.plants?`<p class=mut>◆ plant spots: <span style="color:${SITE_COL.A}">A</span> · <span style="color:${SITE_COL.B}">B</span> · <span style="color:${SITE_COL.C}">C</span></p>`:legend()}
   <div class=card style="margin-top:12px"><h3>Every piece of evidence</h3>
    <div class=tabs><button class="${S.tab==='in'?'on':''}" onclick="tab('in')">${b.condLabel} (${s.IN.length})</button><button class="${S.tab==='out'?'on':''}" onclick="tab('out')">${b.notLabel} (${s.OUT.length})</button>
     <span class=mut>Click a round to highlight it on the map (white ring) and see all five positions.</span></div>
    ${S.hl?detail(S.hl):''}
    <div style="max-height:420px;overflow:auto"><table class=ev><tr><th>Match</th><th>Rnd</th><th>Score</th><th>Buy</th><th>Key fact</th><th>Outcome (✓ = ${b.outcomeLabel})</th><th></th></tr>${list}</table></div></div>
  </div></div>`}
function render(){
  document.getElementById('bar').innerHTML='<span class=mut>8 behaviours found in the conditional analysis (port 4188). Click one to open the explanation and all evidence.</span>';
  const cards=B.map((b,i)=>{const s=summary(b),x=s.rows[0];
    return `<div class="card bcard" onclick="openB(${i})"><div class=mut>${b.id} · ${b.map} ${b.side}</div><div class=t>${b.title}</div>
     <div class=num style="grid-template-columns:1fr 1fr"><div class=mut>${b.condLabel}</div><div class=mut>${b.notLabel}</div><div>${bar(x.a.h,x.a.n,'#22c55e')}</div><div>${bar(x.c.h,x.c.n,'#64748b')}</div></div>
     <div class=mut>${b.subjects.length>1?b.subjects.join(', ')+' · ':''}${s.IN.length+s.OUT.length} rounds of evidence ▸</div></div>`}).join('');
  document.getElementById('main').innerHTML=`<div class=cards>${cards}</div>`+(S.open!=null?overlay(B[S.open]):'');
  showState({open:S.open!=null?B[S.open].id:null,tab:S.tab,highlight:S.hl});
}
render();

"""

HTML = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{title}</title><style>{css}</style></head><body>
<div class=proto>PROTOTYPE · throwaway · Eintracht Frankfurt data only (13 official maps since 2026-09-01) · port {port}</div>
<header><h1>{num}. {title}</h1><p class=q>Question: {question}</p></header>
<div class=bar id=bar></div><main id=main></main><div class=state id=state></div>
<script>const DATA={data};</script><script>{shared}</script><script>{page}</script></body></html>"""


def main():
    data = compute()
    data["findings"] = mine(data)
    data["themes"] = themes(data["findings"])
    payload = json.dumps(data, separators=(",", ":"))
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    for i, (key, port, title, q) in enumerate(FEATURES, 1):
        d = os.path.join(OUT, key)
        os.makedirs(os.path.join(d, "maps"))
        for m in data["maps"]:
            shutil.copy(os.path.join(MAP_DIR, f"{m}.png"), os.path.join(d, "maps", f"{m}.png"))
        html = HTML.format(title=title, css=CSS, port=port, num=i, question=q, data=payload, shared=SHARED_JS, page=PAGES[key])
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(html)
        print(f"built {key} -> http://127.0.0.1:{port}/")


if __name__ == "__main__":
    main()

<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Harnais streaMLytics</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f6f5f1;--surface:#ffffff;--ink:#1d1d1b;--muted:#6b6a64;--line:#e2e0d8;
  --accent:#2f5d8a;--ok:#2e7d4f;--ok-bg:#e3f2e8;--warn:#9a6a00;--warn-bg:#fbf0d4;
  --bad:#b3261e;--bad-bg:#fbe3e0;--hole:#6b4fa0;--hole-bg:#ece5f7;--na:#6b6a64;--na-bg:#ecebe6;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#141413;--surface:#1e1e1c;--ink:#ecebe6;--muted:#a19f97;--line:#33322e;
  --accent:#7fb0e0;--ok:#7fcf9c;--ok-bg:#1d3326;--warn:#e6b84d;--warn-bg:#3a2f12;
  --bad:#f08a80;--bad-bg:#3d1c19;--hole:#b9a0e6;--hole-bg:#2b2340;--na:#a19f97;--na-bg:#2a2926;}}
:root[data-theme="dark"]{
  --bg:#141413;--surface:#1e1e1c;--ink:#ecebe6;--muted:#a19f97;--line:#33322e;
  --accent:#7fb0e0;--ok:#7fcf9c;--ok-bg:#1d3326;--warn:#e6b84d;--warn-bg:#3a2f12;
  --bad:#f08a80;--bad-bg:#3d1c19;--hole:#b9a0e6;--hole-bg:#2b2340;--na:#a19f97;--na-bg:#2a2926;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "IBM Plex Sans",system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.6rem;margin:0 0 4px;font-weight:600}
.sub{color:var(--muted);font-size:.9rem}
code,.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.82rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:20px 0}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card b{display:block;font-size:1.6rem;font-weight:600}
.card span{color:var(--muted);font-size:.82rem}
nav.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);overflow-x:auto;margin-top:8px}
nav.tabs button{background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);
  padding:10px 12px;font:inherit;cursor:pointer;white-space:nowrap}
nav.tabs button[aria-selected="true"]{color:var(--ink);border-color:var(--accent);font-weight:500}
section{display:none;padding-top:16px}section.on{display:block}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
select,input{font:inherit;background:var(--surface);color:var(--ink);border:1px solid var(--line);
  border-radius:8px;padding:6px 8px;max-width:100%}
input{flex:1;min-width:160px}
.list{display:flex;flex-direction:column;gap:8px}
.item{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.item .top{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:baseline}
.item .id{font-family:"IBM Plex Mono",monospace;font-size:.8rem;color:var(--muted)}
.item .en{flex:1 1 320px;font-weight:500}
.meta{color:var(--muted);font-size:.84rem;margin-top:4px;overflow-wrap:anywhere}
.pill{display:inline-block;border-radius:999px;padding:1px 9px;font-size:.76rem;font-weight:500;white-space:nowrap}
.s-active{background:var(--ok-bg);color:var(--ok)}
.s-verte{background:var(--warn-bg);color:var(--warn)}
.s-rouge{background:var(--bad-bg);color:var(--bad)}
.s-trou{background:var(--hole-bg);color:var(--hole)}
.s-na{background:var(--na-bg);color:var(--na)}
.tag{border:1px solid var(--line);color:var(--muted)}
.dom{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px;margin-bottom:16px}
.dom .item{padding:8px 12px}
.bar{display:flex;height:6px;border-radius:3px;overflow:hidden;margin-top:6px;background:var(--na-bg)}
.bar i{display:block}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);font-size:.86rem;vertical-align:top}
th{color:var(--muted);font-weight:500;cursor:pointer;user-select:none}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.tw{overflow-x:auto}
.zero{color:var(--bad)}
.note{color:var(--muted);font-size:.85rem;margin:8px 0 14px}
.theme{float:right;background:var(--surface);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:4px 10px;font:inherit;cursor:pointer}
@media (max-width:600px){.hide-sm{display:none}}
</style>
</head>
<body>
<main>
<button class="theme" id="theme" aria-label="Changer de thème">◐</button>
<h1>Harnais streaMLytics</h1>
<div class="sub">Généré depuis <span class="mono">{{COMMIT}}</span> · <span id="hdr"></span></div>
<div class="cards" id="cards"></div>
<nav class="tabs" role="tablist" id="tabs"></nav>
<section id="t-req">
  <div class="dom" id="doms"></div>
  <div class="filters">
    <select id="f-dom"><option value="">Tous les domaines</option></select>
    <select id="f-met"><option value="">Toutes les méthodes</option></select>
    <select id="f-por"><option value="">Toutes les portées</option></select>
    <select id="f-eta"><option value="">Tous les états</option></select>
    <input id="f-q" type="search" placeholder="Rechercher (id, énoncé, preuve)">
  </div>
  <div class="note" id="req-count"></div>
  <div class="list" id="reqs"></div>
</section>
<section id="t-act">
  <p class="note">Ce que les transcripts ont enregistré. Un hook qui n'imprime rien ne laisse aucune trace : « aucune trace » ne veut pas dire « jamais déclenché ».</p>
  <div class="filters"><select id="a-kind"><option value="">Tous les types</option></select></div>
  <div class="tw"><table id="acts"><thead><tr>
    <th data-k="comp">Composant</th><th data-k="kind">Type</th><th data-k="n" class="n">n</th>
    <th data-k="last" class="hide-sm">Dernière</th><th data-k="ms" class="n hide-sm">ms moy.</th>
    <th data-k="echecs" class="n hide-sm">Échecs</th><th data-k="reqs" class="hide-sm">Exigences</th>
  </tr></thead><tbody></tbody></table></div>
</section>
<section id="t-opp"><div class="list" id="opps"></div></section>
<section id="t-inv"><p class="note">Connu, en attente d'un déclencheur ou d'une décision — aucun geste aujourd'hui.</p><div class="list" id="inv"></div></section>
<section id="t-base">
  <p class="note">Les exigences de portée <b>générique</b> : ce qui part dans la baseline v2, avec la méthode qui les tient.</p>
  <div class="list" id="base"></div>
</section>
<section id="t-pre">
  <p class="note">Ce que la note de départ affirmait, et ce que la mesure a trouvé.</p>
  <div class="list" id="pre"></div>
</section>
</main>
<script>
const P = {{DATA}};
const D = P.data, R = D.exigences;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cls = e => ({"active":"s-active","verte, non prouvée":"s-verte","rouge":"s-rouge","trou":"s-trou"}[e] || "s-na");
const COL = {"active":"var(--ok)","verte, non prouvée":"var(--warn)","rouge":"var(--bad)","trou":"var(--hole)","non rejouée":"var(--na)"};
const pill = e => `<span class="pill ${cls(e)}">${esc(e)}</span>`;
const day = t => t ? t.slice(0,10) : "—";

try{const t=localStorage.getItem("hr-theme"); if(t) document.documentElement.dataset.theme=t;}catch(e){}
$("#theme").onclick=()=>{const r=document.documentElement;
  const dark = r.dataset.theme ? r.dataset.theme==="dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  r.dataset.theme = dark ? "light" : "dark"; try{localStorage.setItem("hr-theme",r.dataset.theme)}catch(e){}};

$("#hdr").textContent = (D.rejoue ? "preuves rejouées" : "preuves NON rejouées (structure seule)")
  + " · " + (D.activite_mesuree ? `activité sur ${D.seances} séances` : "activité non mesurée");

const E = P.resume.etats, comps = Object.entries(D.composants);
const zero = comps.filter(([,c]) => c.activite && c.activite.n === 0 && !c.activite.note
  && !(c.declencheurs && c.declencheurs.length)).length;
const cards = [["active",E["active"]||0,"actives — vertes et vues rouges"],
  ["verte, non prouvée",E["verte, non prouvée"]||0,"vertes, jamais vues rouges"],
  ["rouge",E["rouge"]||0,"preuves rouges"],["trou",R.filter(r=>r.etat==="trou"&&!r.differe).length,"trous (à écrire)"],
  [null,P.resume.generiques,"génériques → baseline v2"],[null,zero,"orphelins — 0 usage, aucun déclencheur"]];
$("#cards").innerHTML = cards.map(([e,n,l]) =>
  `<div class="card"><b style="color:${e?COL[e]:"var(--ink)"}">${n}</b><span>${l}</span></div>`).join("");

const TABS=[["t-req",`Exigences (${R.length})`],["t-act",`Activité (${comps.length})`],
  ["t-opp",`Opportunités (${P.opportunites.length})`],["t-inv",`Inventaire (${P.inventaire.length})`],["t-base",`Baseline v2 (${P.resume.generiques})`],
  ["t-pre","Prémisses corrigées"]];
$("#tabs").innerHTML = TABS.map(([id,l],i)=>`<button role="tab" data-t="${id}" aria-selected="${i===0}">${l}</button>`).join("");
const show = id => { document.querySelectorAll("section").forEach(s=>s.classList.toggle("on",s.id===id));
  document.querySelectorAll("#tabs button").forEach(b=>b.setAttribute("aria-selected",b.dataset.t===id));
  try{localStorage.setItem("hr-tab",id)}catch(e){} };
$("#tabs").onclick = e => e.target.dataset.t && show(e.target.dataset.t);
let start="t-req"; try{start=localStorage.getItem("hr-tab")||start}catch(e){}
show(document.getElementById(start)?start:"t-req");

// domains
const domName = k => (D.domaines[k]||{}).nom || k;
$("#doms").innerHTML = Object.entries(P.resume.domaines).sort().map(([k,c])=>{
  const tot=Object.values(c).reduce((a,b)=>a+b,0);
  const bar=P.etats.map(e=>c[e]?`<i style="width:${100*c[e]/tot}%;background:${COL[e]}"></i>`:"").join("");
  return `<div class="item" data-dom="${esc(k)}" style="cursor:pointer"><div class="top"><span class="en">${esc(domName(k))}</span><span class="id">${tot}</span></div>
    <div class="meta">${P.etats.filter(e=>c[e]).map(e=>`${c[e]} ${e}`).join(" · ")}</div><div class="bar">${bar}</div></div>`;}).join("");
$("#doms").onclick = e => { const d=e.target.closest("[data-dom]"); if(d){ $("#f-dom").value=d.dataset.dom; draw(); } };

const opts = (sel, vals, lab=v=>v) => [...new Set(vals)].filter(Boolean).sort()
  .forEach(v => sel.insertAdjacentHTML("beforeend",`<option value="${esc(v)}">${esc(lab(v))}</option>`));
opts($("#f-dom"), R.map(r=>r.domaine), domName); opts($("#f-met"), R.map(r=>r.methode));
opts($("#f-por"), R.map(r=>r.portee)); opts($("#f-eta"), R.map(r=>r.etat));

const reqCard = r => {
  const red = r.vu_rouge ? (r.vu_rouge.date ? `vu rouge le ${esc(r.vu_rouge.date)}${r.vu_rouge.perime?" <b class=zero>(périmé)</b>":""} — ${esc(r.vu_rouge.detail||"")}` : `${esc(r.vu_rouge.comment)} — ${esc(r.vu_rouge.detail||"")}`) : "";
  return `<div class="item"><div class="top"><span class="id">${esc(r.id)}</span><span class="en">${esc(r.enonce)}</span>
    ${pill(r.etat)}<span class="pill tag">${esc(r.methode||"?")}${r.methode_deduite?" (déduite)":""}</span><span class="pill tag">${esc(r.portee)}</span></div>
    <div class="meta">${esc(domName(r.domaine))} · ${esc(r.priorite||"")}${r.preuve?` · preuve <code>${esc(r.preuve)}</code>`:""}${r.a_ecrire?` · à écrire : ${esc(r.a_ecrire)}`:""}</div>
    ${red?`<div class="meta">${red}</div>`:""}
    ${r.composants&&r.composants.length?`<div class="meta">composants : ${r.composants.map(c=>`<code>${esc(c)}</code>`).join(" ")}</div>`:""}
    ${r.ecart?`<div class="meta">écart : ${esc(r.ecart)}</div>`:""}
    ${r.opportunite?`<div class="meta">➜ ${esc(r.opportunite)}</div>`:""}</div>`;};

function draw(){
  const f={d:$("#f-dom").value,m:$("#f-met").value,p:$("#f-por").value,e:$("#f-eta").value,q:$("#f-q").value.toLowerCase()};
  const rows=R.filter(r=>(!f.d||r.domaine===f.d)&&(!f.m||r.methode===f.m)&&(!f.p||r.portee===f.p)&&(!f.e||r.etat===f.e)
    &&(!f.q||[r.id,r.enonce,r.preuve,r.a_ecrire,r.opportunite].join(" ").toLowerCase().includes(f.q)));
  $("#req-count").textContent=`${rows.length} exigence(s) sur ${R.length}`;
  $("#reqs").innerHTML=rows.map(reqCard).join("");
}
["#f-dom","#f-met","#f-por","#f-eta","#f-q"].forEach(s=>$(s).addEventListener("input",draw)); draw();

// activity
const act = comps.map(([comp,c])=>{const a=c.activite||{};return {comp,kind:a.kind||"?",n:a.n??null,last:a.last||"",
  ms:a.ms??null,echecs:a.echecs??null,note:a.note,reqs:c.exigences.join(", ")}});
opts($("#a-kind"), act.map(a=>a.kind));
let sk="n", sd=1;
function drawAct(){
  const k=$("#a-kind").value;
  const rows=act.filter(a=>!k||a.kind===k).sort((x,y)=>{const a=x[sk]??-1,b=y[sk]??-1;return (a>b?1:a<b?-1:0)*sd*(sk==="n"||sk==="ms"||sk==="echecs"||sk==="last"?-1:1)});
  $("#acts tbody").innerHTML=rows.map(a=>`<tr><td><code>${esc(a.comp.replace(/^\.claude\//,""))}</code>${a.n===0?(a.note?`<div class="meta">${esc(a.note)}</div>`:`<div class="meta zero">jamais vu</div>`):""}</td>
    <td>${esc(a.kind)}</td><td class="n ${a.n===0?"zero":""}">${a.n??"—"}</td><td class="hide-sm">${day(a.last)}</td>
    <td class="n hide-sm">${a.ms??"—"}</td><td class="n hide-sm ${a.echecs?"zero":""}">${a.echecs??"—"}</td><td class="hide-sm mono">${esc(a.reqs)}</td></tr>`).join("");
}
$("#acts thead").onclick=e=>{const k=e.target.dataset.k;if(!k)return; sd = sk===k ? -sd : 1; sk=k; drawAct();};
$("#a-kind").oninput=drawAct; drawAct();

// opportunities
const OC={"preuve rouge":"s-rouge","trou":"s-trou","différé":"s-na","manuel":"s-na","suivi manqué":"s-trou","mesurée":"s-active","vu rouge périmé":"s-verte","à muter":"s-verte","orphelin":"s-trou","dormant":"s-na","hook lent":"s-na","défaut ouvert":"s-rouge","billet à répondre":"s-trou"};
$("#opps").innerHTML=P.opportunites.map(o=>`<div class="item"><div class="top"><span class="pill ${OC[o.type]||"s-na"}">${esc(o.type)}</span>
  <span class="id">${esc(o.ref)}</span></div><div class="meta" style="color:var(--ink)">${esc(o.texte)}</div></div>`).join("") || "<p class=note>Aucune.</p>";
$("#inv").innerHTML=P.inventaire.map(o=>`<div class="item"><div class="top"><span class="pill ${OC[o.type]||"s-na"}">${esc(o.type)}</span>
  <span class="id">${esc(o.ref)}</span></div><div class="meta" style="color:var(--ink)">${esc(o.texte)}</div></div>`).join("") || "<p class=note>Aucune.</p>";

// baseline
const gen=R.filter(r=>r.portee==="generique");
const byM={}; gen.forEach(r=>(byM[r.methode||"?"] ||= []).push(r));
$("#base").innerHTML=Object.entries(byM).sort().map(([m,rs])=>`<h3 style="margin:12px 0 4px;font-size:1rem">${esc(m)} <span class="id">(${rs.length})</span></h3>`+rs.map(reqCard).join("")).join("");

// premises
const pre=R.filter(r=>r.premisse_corrigee);
$("#pre").innerHTML=pre.map(r=>`<div class="item"><div class="top"><span class="id">${esc(r.id)}</span><span class="en">${esc(r.enonce)}</span></div>
  <div class="meta" style="color:var(--ink)">${esc(r.premisse_corrigee)}</div></div>`).join("") || "<p class=note>Aucune.</p>";
</script>
</body>
</html>

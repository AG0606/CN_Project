'use strict';
const ALL=JSON.parse(document.getElementById('experiment-data').textContent),$=id=>document.getElementById(id);
const fmt=(v,n=1)=>v==null?'—':Number(v).toFixed(n),pct=(v,n=1)=>v==null?'—':fmt(100*v,n)+'%';
const mean=(rows,key)=>{const v=rows.map(r=>r[key]).filter(Number.isFinite);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null;};
const pooled=rows=>{const o=rows.reduce((s,r)=>s+r.offered_mb,0);return o?rows.reduce((s,r)=>s+r.served_mb,0)/o:null;};
const positions={geant:[[150,275],[620,225],[330,115],[600,70],[310,425],[570,465],[825,370],[115,105]],abilene:[[690,355],[745,395],[655,170],[475,235],[620,435],[715,235],[575,290],[215,380],[855,155],[170,260],[175,95],[835,285]]};
const shortNames=['ATL-M5','ATL','CHI','DEN','HOU','IND','KC','LA','NYC','SUN','SEA','WDC'];
let active='geant',D=ALL.geant,selectedRun=null,timer=null,revision=0;
const cache=new Map();
function options(el,items,value){el.replaceChildren(...items.map(([v,t])=>{const o=document.createElement('option');o.value=v;o.textContent=t;return o;}));if(items.some(x=>x[0]===value))el.value=value;}
function cells(body,values,selected=false){const tr=document.createElement('tr');if(selected)tr.className='selected';values.forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td);});body.append(tr);}
function stop(){if(timer){clearInterval(timer);timer=null;}$('play').textContent='Play';}
function subset(capacity=Number($('capacity').value),view=$('view').value){return D.summary.filter(r=>r.scenario===$('scenario').value&&r.capacity_mbps===capacity&&ALL.labels[r.policy]&&(view==='paper3'&&capacity===10||r.model_seed===42||r.model_seed===-1));}
function choose(){stop();const old=$('policy').value;options($('policy'),Object.entries(ALL.labels),old||'multipath_carbon_gnn');refresh();}
function switchTab(kind){
 stop();active=kind;D=ALL[kind];selectedRun=null;
 document.querySelectorAll('[data-tab]').forEach(b=>{const yes=b.dataset.tab===kind;b.setAttribute('aria-selected',String(yes));b.tabIndex=yes?0:-1;});
 $('dashboard').setAttribute('aria-labelledby','tab-'+kind);
 options($('scenario'),[['congested','Congested · 1.6×'],['normal','Normal'],['bursty','Seeded bursts']],'congested');
 options($('capacity'),[['10','10 Mbps'],['20','20 Mbps'],['40','40 Mbps']],'10');
 const labels=kind==='geant'?D.manifest.graph.countries:shortNames;
 options($('flow'),D.manifest.traffic_manifest.pairs.map(([a,b],i)=>[String(i),labels[a]+' → '+labels[b]]),'0');
 $('step').value=0;forecast();notes();choose();
}
async function refresh(){
 const ticket=++revision;stop();selectedRun=null;
 const rows=subset(),policy=$('policy').value,group=rows.filter(r=>r.policy===policy),cap=Number($('capacity').value);
 D.manifest.graph.capacity_mbps=cap;
 $('m-score').textContent=fmt(mean(group,'forwarding_score'),2);$('m-served').textContent=pct(pooled(group),3);
 $('m-overload').textContent=fmt(mean(group,'overload_minutes'),2);$('m-changes').textContent=fmt(mean(group,'route_changes'),2);
 $('graph-note').textContent=(active==='geant'?'GÉANT eight-node subgraph':'Abilene 12-router backbone')+' · '+cap+' Mbps per direction · replay is day 1; cards/table aggregate seven days';
 $('run-tag').textContent='DAY 1 · SEED 42';
 $('table-note').textContent=D.days.join(', ')+' · '+$('scenario').value+' · '+cap+' Mbps · '+(cap===10&&$('view').value==='paper3'?'three neural seeds (7, 42, 123), matching Table 3':'seed 42 + deterministic controls, matching Table 4')+'. Cards use the same seven-day aggregation as this table.';
 $('comparison').replaceChildren();Object.entries(ALL.labels).forEach(([p,label])=>{const g=rows.filter(r=>r.policy===p);if(g.length)cells($('comparison'),[label,fmt(mean(g,'forwarding_score'),2),pct(pooled(g),3),fmt(mean(g,'overload_minutes'),2),pct(mean(g,'p95_utilization')),fmt(mean(g,'route_changes'),2),fmt(mean(g,'decision_ms_mean'),2)+' ms'],p===policy);});
 capacityTable();diagnostics();
 $('status').textContent='2,058 audited runs · loading final-period replay…';$('play').disabled=true;
 try{
  const key=$('scenario').value+'_'+cap+'_'+policy,id=active+'_'+key;
  if(!cache.has(id)){
   const bytes=Uint8Array.from(atob(D.runs[key]),c=>c.charCodeAt(0));
   const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'));
   cache.set(id,JSON.parse(await new Response(stream).text()));
  }
  if(ticket!==revision)return;
  selectedRun=cache.get(id);selectedRun.summary.carbon_year=active==='geant'?2022:2004;
  $('step').max=selectedRun.records.length-1;if(Number($('step').value)>=selectedRun.records.length)$('step').value=0;
  $('status').textContent='AUDIT PASSED · 2,058 runs · 395,136 intervals · 12 checkpoints';$('play').disabled=false;renderReplay();
 }catch(error){if(ticket===revision){$('status').textContent='Replay unavailable: '+error.message+'. Summary tables remain available. Open in a current Chrome or Edge browser.';$('network').innerHTML='';}}
}
function capacityTable(){
 const panel=$('service-first-panel');panel.hidden=false;
 panel.querySelector('h2').textContent='Table 4 · capacity sensitivity';
 $('service-first-note').textContent='Same selected workload at 10 / 20 / 40 Mbps; seed 42 is fixed. Each cell shows pooled served % / mean carbon score.';
 panel.querySelector('thead').innerHTML='<tr><th>Policy</th><th>10 Mbps</th><th>20 Mbps</th><th>40 Mbps</th></tr>';
 $('service-first-comparison').replaceChildren();
 ['reactive_carbon','equal_split','service_first_gnn','multipath_carbon_gnn','multipath_carbon_persistence'].forEach(p=>cells($('service-first-comparison'),[ALL.labels[p],...[10,20,40].map(c=>{const g=subset(c,'paper4').filter(r=>r.policy===p);return pct(pooled(g),3)+' / '+fmt(mean(g,'forwarding_score'),2);})]));
 panel.querySelector('p.meta').textContent='Traffic scaling and selected pairs are fixed across capacities. These are assumed capacities, not measured historical link speeds. Results can improve or regress; all capacities are retained.';
}
function diagnostics(){
 $('tradeoff-panel').hidden=true;
 const panel=$('multipath-panel');panel.hidden=false;panel.querySelector('h2').textContent='Perfect-demand check · offline diagnostic';
 $('multipath-scenario').parentElement.hidden=true;
 $('multipath-note').textContent='Table 5: 10 Mbps, seed 42, zero margin for both sides; selected workload. Replace forecasts with actual next-three-bin demand, keeping the planner fixed.';
 panel.querySelector('thead').innerHTML='<tr><th>Planner</th><th>Causal → perfect score</th><th>Causal → perfect served %</th><th>Causal → perfect overload min/day</th></tr>';
 $('multipath-comparison').replaceChildren();
 const rows=D.summary.filter(r=>r.capacity_mbps===10&&r.scenario===$('scenario').value);
 [['service_first_gnn_no_margin','perfect_service_first','Service-first'],['multipath_carbon_gnn_no_margin','perfect_multipath_carbon','Carbon multipath']].forEach(([a,b,label])=>{const x=rows.filter(r=>r.policy===a),y=rows.filter(r=>r.policy===b);cells($('multipath-comparison'),[label,fmt(mean(x,'forwarding_score'),2)+' → '+fmt(mean(y,'forwarding_score'),2),pct(pooled(x),3)+' → '+pct(pooled(y),3),fmt(mean(x,'overload_minutes'),2)+' → '+fmt(mean(y,'overload_minutes'),2)]);});
 $('multipath-example').textContent='Perfect-demand runs know the future. They are diagnostics, not deployable methods or guaranteed upper bounds. The replay above contains only causal methods.';
 panel.querySelector('p.meta').textContent='Forecast replacement gives small service improvements at 10 Mbps and can raise the served-weighted carbon score. This tests these existing planners, not every possible routing algorithm.';
}
function forecast(){
 $('forecast').replaceChildren();for(let h=1;h<=3;h++)$('h'+h).textContent=h*D.manifest.config.bin_seconds/60+' min';
 ['gnn','gru','persistence'].forEach(model=>{
  const rows=D.forecast.filter(r=>r.model===model),seeds=[...new Set(rows.map(r=>r.model_seed))];
  const values=seeds.map(seed=>mean(rows.filter(r=>r.model_seed===seed),'mae_mbps')),avg=values.reduce((s,v)=>s+v,0)/values.length;
  const sd=values.length>1?Math.sqrt(values.reduce((s,v)=>s+(v-avg)**2,0)/(values.length-1)):null;
  cells($('forecast'),[model.toUpperCase(),...[1,2,3].map(h=>fmt(mean(rows.filter(r=>r.horizon_bins===h),'mae_mbps'),5)),fmt(avg,5)+(sd===null?' (deterministic)':' ± '+fmt(sd,5))]);
 });
 $('forecast-verdict').textContent=active==='geant'?'Table 2: persistence has the lowest mean error. Every GNN seed is worse than persistence; graph aggregation shows no forecasting advantage here.':'Table 2: GRU has the lowest mean error. GNN improves slightly over persistence but does not beat the matched GRU.';
}
function notes(){
 const items=[`Final test dates: ${D.days[0]} to ${D.days.at(-1)}. Seven days per network; all outcomes retained.`,
  active==='geant'?'2005 traffic is paired with daily 2022 country carbon as a constructed counterfactual. Source traffic dates were anonymized; no verified historical synchronization.':'Abilene uses annual EPA eGRID2004 regional rates. Values vary geographically, not hourly.',
  '10 Mbps uses three neural seeds in the Table 3 view. Table 4 fixes seed 42 across capacities. Replay always shows the first chronological day and seed 42 for learned policies.',
  'GNN forecasting does not consistently beat simpler controls. Multipath benefits depend on network and capacity; persistence often matches or exceeds GNN routing.',
  'Current carbon is supplied by historical replay. There is no carbon prediction, packet-level emulation, or measured emissions reduction.'];
 $('notes').replaceChildren(...items.map(s=>{const li=document.createElement('li');li.textContent=s;return li;}));
 $('provenance').textContent='Source: final-validation-20261027 · audit passed · summary SHA-256 '+ALL.summary_sha256;
 $('sources').innerHTML='<a href="FINDINGS.md">Complete final findings</a> · <a href="summary.csv">All 2,058 result rows (CSV)</a> · <a href="AUDIT.json">Audit</a> · <a href="forecast_metrics.csv">Forecast results</a>';
 $('footnote').textContent='* Forwarding carbon score is served-byte-weighted hop intensity, not grams of emitted CO₂. Capacities and propagation delays are assumptions. Service pools bytes; other metrics average runs. p95 pools link/bin samples within each run. Cached decision times exclude bulk neural inference. Replay shows day 1; headline results cover all seven days. Annual US and daily European carbon use different accounting boundaries, so absolute scores should not be compared between networks.';
}
// __REPLAY_RENDER__
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));
$('scenario').addEventListener('change',choose);$('capacity').addEventListener('change',choose);
$('view').addEventListener('change',()=>{if($('view').value==='paper3')$('capacity').value='10';choose();});
$('policy').addEventListener('change',refresh);$('flow').addEventListener('change',()=>{if(selectedRun)renderReplay();});$('step').addEventListener('input',()=>{if(selectedRun)renderReplay();});
$('play').addEventListener('click',()=>{if(timer)stop();else if(selectedRun){$('play').textContent='Pause';timer=setInterval(()=>{$('step').value=(Number($('step').value)+1)%selectedRun.records.length;renderReplay();},400);}});
switchTab(location.hash==='#abilene'?'abilene':'geant');

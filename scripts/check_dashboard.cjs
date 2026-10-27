// DOM-level interaction smoke check; this does not replace visual browser QA.
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync(process.argv[2] || 'results/demo/index.html', 'utf8');
const payload = html.match(/<script id="experiment-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const source = html.split('<script>').pop().split('</script>')[0];
class Element {
  constructor(id, tag='div') { this.id=id; this.tag=tag; this.value=''; this.children=[]; this.events={}; this.dataset={}; }
  replaceChildren(...items) { this.children=items; if(this.tag==='select')this.value=items[0]?.value ?? ''; }
  append(item) { this.children.push(item); }
  setAttribute(key,value) { this[key]=value; }
  addEventListener(name,callback) { this.events[name]=callback; }
}
const elements={};
for(const match of html.matchAll(/<(select|button|input|div|span|section|tbody|svg|p|th)[^>]*\bid="([^"]+)"/g))elements[match[2]]=new Element(match[2],match[1]);
elements['experiment-data']=new Element('experiment-data');elements['experiment-data'].textContent=payload;
const tabs=[elements['tab-geant'],elements['tab-abilene']];tabs[0].dataset.tab='geant';tabs[1].dataset.tab='abilene';
const document={getElementById:id=>elements[id] ?? (elements[id]=new Element(id)),querySelectorAll:()=>tabs,createElement:tag=>new Element('',tag)};
vm.runInNewContext(source,{document,location:{hash:''},setInterval,clearInterval,console},{timeout:10000});
function check(value,message){if(!value)throw new Error(message);}
const all=JSON.parse(payload);
check(!all.followup,'retired training comparison embedded in main dashboard');
check(all.multipath && all.multipath.summary.length===462,'missing complete multipath study');
for(const [index,name,date] of [[0,'geant','2005-07-26'],[1,'abilene','2004-05-24']]){
  tabs[index].events.click();
  for(const scenario of ['normal','congested','bursty']){
    elements['multipath-scenario'].value=scenario;elements['multipath-scenario'].events.change();
    check(!elements['multipath-panel'].hidden,`${name} multipath section hidden`);
    check(elements['multipath-comparison'].children.length===11,'multipath method missing');
    check(elements['multipath-note'].textContent.includes(date),'incorrect multipath dates');
    const rows=all.multipath.summary.filter(r=>r.network===name&&r.scenario===scenario&&r.policy==='reactive_carbon');
    const score=(rows.reduce((s,r)=>s+r.forwarding_score,0)/rows.length).toFixed(1);
    const service=(100*rows.reduce((s,r)=>s+r.served_mb,0)/rows.reduce((s,r)=>s+r.offered_mb,0)).toFixed(3)+'%';
    check(elements['multipath-comparison'].children[1].children[1].textContent===score,'incorrect paired baseline score');
    check(elements['multipath-comparison'].children[1].children[2].textContent===service,'incorrect pooled service');
    const example=all.multipath.examples[name+'_'+scenario];
    if(example){
      check(elements['multipath-example'].textContent.includes(example.traffic_time.replace('T',' ')),'split example does not follow network/workload');
      check(Math.abs(example.paths.reduce((s,p)=>s+p.fraction,0)-1)<1e-5,'example path fractions do not conserve demand');
    }
  }
}
console.log('Dashboard interactions verified: both networks, three workloads, 11 multipath methods, pooled service and recorded split examples.');

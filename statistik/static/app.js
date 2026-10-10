'use strict';
const $=id=>document.getElementById(id), nf=new Intl.NumberFormat('da-DK');
let current=null, busy=false;
function localDate(d){return new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Copenhagen'}).format(d)}
function dateTime(value){if(!value)return 'ukendt';return new Intl.DateTimeFormat('da-DK',{timeZone:'Europe/Copenhagen',dateStyle:'short',timeStyle:'short'}).format(new Date(typeof value==='number'?value*1000:value))}
const today=new Date();$('end').value=localDate(today);const prior=new Date(today);prior.setDate(prior.getDate()-29);$('start').value=localDate(prior);
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}
function notice(text,error=false){$('notice').textContent=text;$('notice').classList.toggle('error',error)}
function quota(prefix,w,observed){
 const out=$(prefix+'-remaining');out.replaceChildren();
 const expired=w&&w.resets_at&&w.resets_at*1000<Date.now();
 if(!w||w.used==null||expired){out.append(el('span','—'),el('small',expired?'afventer ny måling':'ingen måling'));$(prefix+'-bar').style.width='0%';$(prefix+'-reset').textContent=expired?'Det viste vindue er udløbet. Afventer nye kontodata.':'Kontogrænsen er endnu ikke tilgængelig.';return}
 const remaining=Math.max(0,Math.min(100,100-w.used));out.append(el('span',nf.format(remaining)+' %'),el('small','tilbage'));
 $(prefix+'-bar').style.width=remaining+'%';
 $(prefix+'-reset').textContent=`${w.minutes>=1440?nf.format(w.minutes/1440)+' dage':nf.format(w.minutes/60)+' timer'} · nulstilles ${dateTime(w.resets_at)}`;
}
function ranking(target,values,showShare=false){const root=$(target);root.replaceChildren();const entries=Object.entries(values).sort((a,b)=>b[1]-a[1]);if(!entries.length){root.append(el('p','Ingen målinger i perioden.','muted'));return}const max=entries[0][1],sum=entries.reduce((n,e)=>n+e[1],0),pf=new Intl.NumberFormat('da-DK',{maximumFractionDigits:1});for(const [name,n]of entries){const row=el('div',undefined,'rank'),head=el('div',undefined,'rank-head'),track=el('div',undefined,'track'),bar=el('div'),value=showShare?`${nf.format(n)} · ${pf.format(sum?n/sum*100:0)} %`:nf.format(n);head.append(el('span',name),el('strong',value));bar.style.width=(max?n/max*100:0)+'%';track.append(bar);row.append(head,track);root.append(row)}}
function dailyChart(values,available){
 $('chart').replaceChildren();$('daily-table').replaceChildren();
 $('chart').hidden=!available;$('daily-table').parentElement.hidden=!available;
 $('empty').textContent=available?'Ingen registrerede målinger i den valgte periode.':'Ingen data fra denne kilde — forbruget er ukendt.';
 if(!available){$('empty').hidden=false;return;}
 const start=new Date($('start').value+'T12:00:00Z'),end=new Date($('end').value+'T12:00:00Z'),days=[];
 for(let d=new Date(start);d<=end&&days.length<366;d.setUTCDate(d.getUTCDate()+1))days.push(d.toISOString().slice(0,10));
 const max=Math.max(1,...Object.values(values));const sparse=days.length>15?Math.ceil(days.length/10):1;
 const table=el('table'),body=el('tbody'),tr=el('tr');tr.append(el('th','Dato'),el('th','Tokens'));table.append(tr,body);
 days.forEach((day,i)=>{const n=values[day]||0;const column=el('div',undefined,'day'),space=el('div',undefined,'bar-space'),bar=el('div',undefined,'bar');column.title=day+': '+nf.format(n)+' tokens';column.setAttribute('aria-label',column.title);bar.style.height=(n/max*100)+'%';space.append(bar);column.append(space,el('span',i%sparse===0?day.slice(8)+'/'+day.slice(5,7):''));$('chart').append(column);const row=el('tr');row.append(el('td',day),el('td',nf.format(n)));body.append(row)});
 $('daily-table').append(table);$('empty').hidden=Object.keys(values).length>0;
}
function render(data){
 current=data;const m=data.meta,lim=m.limits||{},col=m.collector||{},settings=m.settings||{};
 quota('short',(lim.windows||[]).find(w=>w.name==='primary'),lim.observed_at);quota('long',(lim.windows||[]).find(w=>w.name==='secondary'),lim.observed_at);
 $('plan').textContent=(settings.plan||lim.plan||'ukendt plan').toUpperCase();
 const formActive=$('renew-form').contains(document.activeElement);
 if(!formActive){$('renew-day').value=settings.renewal_day||'';$('monthly-price').value=settings.monthly_price??'';$('subscription-plan').value=settings.plan||'';}
 $('renew-text').textContent=settings.next_renewal?'Næste fornyelse: '+new Intl.DateTimeFormat('da-DK',{dateStyle:'long'}).format(new Date(settings.next_renewal+'T12:00:00')):'Fornyelsesdato ukendt';
 $('subscription-price').textContent=settings.monthly_price!=null?nf.format(settings.monthly_price)+' USD / måned · den '+settings.renewal_day+'. i hver måned':'';
 $('reported-plan').textContent=settings.source==='user'?'Abonnement og pris er oplyst af dig. Codex-forbindelsen rapporterer '+(lim.plan||'ukendt plan')+'.':'';
 const credit=m.credit_summary||{},cf=new Intl.NumberFormat('da-DK',{minimumFractionDigits:2,maximumFractionDigits:2});
 $('credit-remaining').textContent=credit.unlimited?'Ubegrænset':credit.remaining!=null?cf.format(Number(credit.remaining)):'—';
 $('credit-used').textContent=credit.used!=null?cf.format(Number(credit.used)):'—';
 $('credit-purchased').textContent=credit.purchased!=null?nf.format(credit.purchased):'—';
 $('credit-bar').style.width=credit.remaining!=null&&credit.purchased>0?Math.max(0,Math.min(100,Number(credit.remaining)/credit.purchased*100))+'%':'0%';
 const creditAge=credit.observed_at?Date.now()-new Date(credit.observed_at):Infinity;
 $('credit-measured').textContent='Saldo målt '+dateTime(credit.observed_at)+(creditAge>600000?' · ældre måling, afventer synkronisering':' · fra OpenAI');
 $('credit-explanation').textContent=credit.used==null&&credit.remaining!=null?'Saldoen kan ikke sammenholdes med det registrerede køb. Et nyt køb eller en korrektion kan være årsagen.':'Forbrug = dit oplyste køb minus den målte saldo. Beregningen forudsætter ingen senere køb, udløb eller korrektioner. Dette er ChatGPT/Codex-kreditter, ikke API-saldo.';

 const stale= !col.at||Date.now()-new Date(col.at)>10*60000;
 const limitStale=!lim.observed_at||Date.now()-new Date(lim.observed_at)>10*60000;
 notice(stale?'Mac-synkronisering mangler eller er over 10 minutter gammel. Åbn din Mac og forbind den til hjemmenetværket.':`Lokale målinger synkroniseret ${dateTime(col.at)}. Kontogrænser målt ${dateTime(lim.observed_at)}${limitStale?' — ældre måling; opdateres ved ny Codex-aktivitet.':'.'}`,stale||limitStale);
 const source=$('source').value,available=source==='codex'?!!col.at:source==='api_org'?m.api_status?.state==='connected'||data.tasks.length>0:data.tasks.length>0;
 for(const key of ['total','input','cached','output'])$(key).textContent=available?nf.format(data.totals[key]):'—';
 $('coverage').textContent=source==='codex'?'Lokale Codex-målinger · dage i dansk tid · cache indgår allerede i input.':source==='api_org'?'OpenAI organisationsdata · dage i UTC · tekst/modelkald og embeddings · opdateres hvert 15. minut.':'Kun programmer med installeret funktionsmåling · dage i dansk tid · vises separat fra organisationsdata.';
 ranking('models',data.models||{},true);ranking('programs',data.programs);ranking('functions',data.functions);dailyChart(data.daily,available);
 $('tasks').replaceChildren();
 for(const t of data.tasks){const row=el('tr');row.append(el('td',t.day),el('td',t.program),el('td',t.function),el('td',nf.format(t.tokens)));const cell=el('td'),btn=el('button','Navngiv');btn.onclick=()=>{$('task-id').value=t.id;$('program-name').value=t.program;$('function-name').value=t.function;$('form-error').textContent='';$('edit').showModal()};cell.append(btn);row.append(cell);$('tasks').append(row)}
 if(!data.tasks.length){const row=el('tr'),cell=el('td','Ingen opgaver registreret for dette filter.');cell.colSpan=5;row.append(cell);$('tasks').append(row)}
 $('sync-status').textContent=col.at?`${col.files} sessionsfiler. Senest synkroniseret ${dateTime(col.at)}. Synkronisering kræver, at din Mac er vågen og på netværket.`:'Afventer første synkronisering fra Mac.';
 $('api-status').textContent=m.api_status?.message||'Ikke tilsluttet — API-forbruget er ukendt.';
 $('updated').textContent='Side opdateret '+dateTime(data.server_time);
}
async function load(){if(busy)return;busy=true;$('refresh').disabled=true;try{
 if(!$('start').value||!$('end').value||$('start').value>$('end').value)throw Error('Vælg en gyldig start- og slutdato.');
 if((new Date($('end').value)-new Date($('start').value))/86400000>365)throw Error('Vælg højst 366 dage ad gangen.');
 const q=new URLSearchParams({start:$('start').value,end:$('end').value,source:$('source').value});const r=await fetch('/api/dashboard?'+q);if(!r.ok)throw Error('Kunne ikke hente statistikken.');render(await r.json());
 }catch(e){notice(e.message,true)}finally{busy=false;$('refresh').disabled=false}}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const p=await r.json();if(!r.ok)throw Error(p.error||'Kunne ikke gemme.');}
$('refresh').onclick=load;for(const id of ['start','end','source'])$(id).addEventListener('change',load);
$('cancel').onclick=()=>$('edit').close();
$('label-form').onsubmit=async e=>{e.preventDefault();try{await post('/api/label',{task:$('task-id').value,program:$('program-name').value,function:$('function-name').value});$('edit').close();await load()}catch(e){$('form-error').textContent=e.message}};
$('renew-form').onsubmit=async e=>{e.preventDefault();try{await post('/api/settings',{renewal_day:Number($('renew-day').value),monthly_price:Number($('monthly-price').value),plan:$('subscription-plan').value});await load();notice('Abonnement gemt. Næste fornyelse beregnes automatisk hver måned.')}catch(e){notice(e.message,true)}};
load();setInterval(load,60000);

const tabs=await fetch('http://127.0.0.1:9222/json').then(r=>r.json());
const tab=tabs.find(t=>t.url.includes('127.0.0.1:8000/modules/production'))||tabs.find(t=>t.url.includes('127.0.0.1:8000/'));
if(!tab)throw new Error('Authenticated ERP tab not found');
const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
let n=1;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id);}};
const send=(method,params={})=>new Promise(resolve=>{const id=n++;pending.set(id,resolve);ws.send(JSON.stringify({id,method,params}));});
await send('Page.enable');await send('Runtime.enable');await send('Page.navigate',{url:'http://127.0.0.1:8002/configuration'});
await new Promise(r=>setTimeout(r,1200));
const expression=`(() => {
 const select=document.getElementById('masterRecordType');
 const out={title:document.title,url:location.href,heading:document.querySelector('h1')?.textContent?.trim(),loginPrompt:/sign in|login/i.test(document.body.innerText),types:select?[...select.options].map(x=>x.value):[],cards:[...document.querySelectorAll('.config-card h2')].map(x=>x.textContent.trim()).filter(x=>['Yarn Counts','Fiber Types','Shade Categories'].includes(x)),buttons:[...document.querySelectorAll('.master-edit-row')].filter(x=>['YARN_COUNT','FIBER_TYPE','SHADE_CATEGORY'].includes(x.dataset.masterKind)).length,forms:document.querySelectorAll('form').length};
 for(const kind of ['YARN_COUNT','FIBER_TYPE','SHADE_CATEGORY']){
   select.value=kind;select.dispatchEvent(new Event('change'));
   out[kind+'_CREATE']=[...document.querySelectorAll('#masterGuidedFields label')].map(x=>x.textContent.trim());
   const b=document.querySelector('.master-edit-row[data-master-kind="'+kind+'"]');
   if(b){b.click();out[kind+'_EDIT']={id:document.getElementById('masterRecordId').value,fields:[...document.querySelectorAll('#masterGuidedFields label')].map(x=>x.textContent.trim()),payload:document.getElementById('masterRecordPayload').value};}
   else out[kind+'_EDIT']='NO_EXISTING_ROW';
 }
 return out;
})()`;
const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
console.log(JSON.stringify(r.result?.result?.value??r.result,null,2));ws.close();
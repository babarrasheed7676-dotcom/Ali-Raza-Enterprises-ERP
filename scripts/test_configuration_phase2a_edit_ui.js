const tabs=await fetch('http://127.0.0.1:9222/json').then(r=>r.json());
const tab=tabs.find(t=>t.url==='http://127.0.0.1:8000/configuration');
if(!tab)throw new Error('Configuration tab missing');
const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
let n=1;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id);}};
const send=(method,params={})=>new Promise(resolve=>{const id=n++;pending.set(id,resolve);ws.send(JSON.stringify({id,method,params}));});
const expression=`(() => {
 const out={};
 for(const kind of ['YARN_COUNT','FIBER_TYPE','SHADE_CATEGORY']){
  const b=document.querySelector('.master-edit-row[data-master-kind="'+kind+'"]');
  if(!b){out[kind]='NO_ROW';continue;}
  b.click();
  out[kind]={recordId:document.getElementById('masterRecordId').value,labels:[...document.querySelectorAll('#masterGuidedFields label')].map(x=>x.textContent.trim()),payload:document.getElementById('masterRecordPayload').value};
 }
 return out;
})()`;
const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
console.log(JSON.stringify(r.result?.result?.value??r.result,null,2));ws.close();
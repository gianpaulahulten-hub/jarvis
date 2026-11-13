/* Shared by the Dining and Travel mini apps (inlined at build time). */
const TZ="America/New_York",embedded=window.parent!==window;
if(embedded)document.body.classList.add("embedded");
const $=s=>document.querySelector(s),esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const EYE_ON='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>',EYE_OFF='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.9 17.9A10 10 0 0 1 12 19C5 19 1 12 1 12a18 18 0 0 1 5-5.9M9.9 4.2A9 9 0 0 1 12 4c7 0 11 7 11 7a18 18 0 0 1-2.2 3.2M1 1l22 22"/></svg>';
function setHide(v,save){document.body.classList.toggle("hide",!!v);$("#eye").innerHTML=v?EYE_OFF:EYE_ON;if(save)try{localStorage.setItem("jarvis.hide",v?"1":"0")}catch(e){}}
try{setHide(localStorage.getItem("jarvis.hide")==="1")}catch(e){setHide(false)}
$("#eye").onclick=()=>setHide(!document.body.classList.contains("hide"),true);
addEventListener("message",e=>{if(e.origin!==location.origin||e.source!==window.parent)return;const m=e.data||{};if(m.type==="jarvis:privacy")setHide(m.hidden)});
const fmt=(iso,o,tz)=>new Date(iso).toLocaleString("en-US",{timeZone:tz||TZ,...o});
const tm=(iso,tz)=>fmt(iso,{hour:"numeric",minute:"2-digit"},tz);
const isDate=s=>/^\d{4}-\d{2}-\d{2}$/.test(s||"");
const dayOf=s=>isDate(s)?new Date(s+"T12:00:00Z"):new Date(s);
const dfmt=(s,o={weekday:"short",month:"short",day:"numeric"})=>isDate(s)?new Date(s+"T12:00:00Z").toLocaleDateString("en-US",{...o,timeZone:"UTC"}):fmt(s,o);
const TZAB={"America/New_York":"ET","America/Chicago":"CT","America/Denver":"MT","America/Boise":"MT","America/Phoenix":"MST","America/Los_Angeles":"PT","Pacific/Honolulu":"HT"};
const ab=tz=>TZAB[tz]||tz||"";
const ago=iso=>{const d=Math.round((Date.now()-new Date(iso))/864e5);return d<=0?"today":d===1?"yesterday":d<30?d+" days ago":d<60?"1 month ago":Math.round(d/30)+" months ago"};
const until=s=>{const d=Math.ceil((dayOf(s)-Date.now())/864e5);return d<=0?"today":d===1?"tomorrow":"in "+d+" days"};
function updated(iso){return iso?fmt(iso,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET":"unknown"}
function post(){if(embedded)parent.postMessage({type:"jarvis:height",h:document.documentElement.scrollHeight},location.origin)}
if(embedded){new ResizeObserver(post).observe(document.body);
 ["touchstart","touchmove","touchend"].forEach(t=>addEventListener(t,e=>{const p=e.touches[0]||e.changedTouches[0];parent.postMessage({type:"jarvis:touch",phase:t,y:p?p.screenY:0},location.origin)},{passive:true}));
 parent.postMessage({type:"jarvis:hello"},location.origin)}

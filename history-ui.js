const slider = document.getElementById('yearSlider');
const baselineSelect = document.getElementById('baselineSelect');
for (let y=2015;y<=2025;y++) baselineSelect.add(new Option(String(y),String(y)));
baselineSelect.value='2015';
let playTimer=null;
function stopPlayback() {
  clearTimeout(playTimer); playTimer=null;
  document.getElementById('playButton').textContent='▶';
  document.getElementById('playButton').setAttribute('aria-label','Play years');
}
async function selectYear(year) {
  currentYear=year; slider.value=String(year);
  document.getElementById('yearLabel').textContent=year;
  await load();
}
slider.addEventListener('change',()=>{stopPlayback();selectYear(Number(slider.value));});
slider.addEventListener('input',()=>document.getElementById('yearLabel').textContent=slider.value);
document.getElementById('playButton').addEventListener('click',async()=>{
  if(playTimer!==null){stopPlayback();return;}
  document.getElementById('playButton').textContent='❚❚';
  document.getElementById('playButton').setAttribute('aria-label','Pause years');
  playTimer=0;
  async function advance(){
    if(playTimer===null)return;
    await selectYear(currentYear===2025?2015:currentYear+1);
    if(playTimer===null)return;
    if(currentYear===2025){stopPlayback();return;}
    playTimer=setTimeout(advance,1800);
  }
  advance();
});
document.getElementById('fieldSelect').addEventListener('change',e=>{
  currentField=e.target.value;
  const noun=currentField==='v'?'assessed value':'just value';
  document.querySelector('#metricSelect option[value=value]').textContent='Total '+noun;
  document.querySelector('#metricSelect option[value=per_acre]').textContent=noun[0].toUpperCase()+noun.slice(1)+' / acre';
  updateLegendVisibility();rebuildLayer();
  document.getElementById('yearDescription').textContent=viewMode==='change'
    ? `${baselineYear}–${currentYear} change. Height shows ${currentYear} value; color shows change.`
    : `${currentYear} ${currentField==='v'?'assessed value (AV_NSD)':'just value (JV)'}.`;
  if(selectedParcel)showHistory(selectedParcel);
});
document.getElementById('viewSelect').addEventListener('change',e=>{
  stopPlayback();viewMode=e.target.value;
  document.getElementById('baselineControl').hidden=viewMode!=='change';
  load();
});
baselineSelect.addEventListener('change',()=>{baselineYear=Number(baselineSelect.value);load();});
document.getElementById('closeHistory').addEventListener('click',()=>{
  selectedParcel=null;++historyVersion;document.getElementById('historyPanel').hidden=true;
});
let historyChangeField=null, historyRows=null, historyPid=null;
const HIST_COLORS={j:'#c0623a',v:'#2160a0'};
const pctChange=(cur,prev)=>prev>0?cur/prev-1:null;
const fmtPct=p=>p===null?'—':(p>0?'+':p<0?'−':'')+Math.abs(100*p).toFixed(1)+'%';
function renderHistory(){
  const rows=historyRows, body=document.getElementById('historyBody');
  if(!historyChangeField) historyChangeField=currentField==='j'?'j':'v';
  // History rows are [year, AV_NSD, JV, acres, use]. Chart both values on one scale.
  const max=Math.max(1,...rows.map(r=>Math.max(r[1],r[2])));
  const x=r=>12+(r[0]-2015)*27, yOf=val=>90-val/max*75;
  const line=(i,color)=>`<polyline fill="none" stroke="${color}" stroke-width="2" points="${rows.map(r=>`${x(r)},${yOf(r[i])}`).join(' ')}"/>`+rows.map(r=>`<circle cx="${x(r)}" cy="${yOf(r[i])}" r="3" fill="${color}"/>`).join('');
  const svg=`<svg viewBox="0 0 294 110" role="img" aria-label="Annual just and assessed value history"><line x1="12" y1="90" x2="282" y2="90" stroke="#767676"/>${line(2,HIST_COLORS.j)}${line(1,HIST_COLORS.v)}<text x="12" y="105" font-size="10" fill="#1a1a1a">2015</text><text x="255" y="105" font-size="10" fill="#1a1a1a">2025</text></svg>`;
  const byYear=new Map(rows.map(r=>[r[0],r]));
  const change=(y,i)=>{const r=byYear.get(y),p=byYear.get(y-1);return r&&p?pctChange(r[i],p[i]):null;};
  const table=Array.from({length:11},(_,k)=>2015+k).map(y=>{
    const r=byYear.get(y);
    return `<tr${y===currentYear?' style="background:#e7f0f9"':''}><td>${y}</td><td>${r?fmtMoney(r[2]):'—'}</td><td>${fmtPct(change(y,2))}</td><td>${r?fmtMoney(r[1]):'—'}</td><td>${fmtPct(change(y,1))}</td><td>${r?Math.round(100*r[1]/r[2])+'%':'—'}</td></tr>`;
  }).join('');
  // Percent change chart: one series at a time, chosen by the filter.
  const idx=historyChangeField==='v'?1:2, name=historyChangeField==='v'?'Assessed value':'Just value', color=HIST_COLORS[historyChangeField];
  const yrs=Array.from({length:10},(_,k)=>2016+k), vals=yrs.map(y=>change(y,idx));
  const ok=vals.filter(v=>v!==null), pos=Math.max(0,...ok), neg=Math.max(0,...ok.map(v=>-v));
  const scale=86/Math.max(0.01,pos+neg), zero=14+pos*scale;
  const bars=yrs.map((y,k)=>{
    const cx=12+(y-2015)*27, v=vals[k];
    const yr=`<text x="${cx}" y="118" font-size="8" text-anchor="middle" fill="#1a1a1a">'${String(y).slice(2)}</text>`;
    if(v===null) return `<text x="${cx}" y="${zero-3}" font-size="8" text-anchor="middle" fill="#1a1a1a">—</text>`+yr;
    const h=Math.abs(v)*scale, top=v>=0?zero-h:zero;
    const ly=v>=0?top-3:zero+h+9;
    return `<rect x="${cx-8}" y="${top}" width="16" height="${Math.max(h,0.5)}" fill="${color}"><title>${y}: ${fmtPct(v)}</title></rect><text x="${cx}" y="${ly}" font-size="8" text-anchor="middle" fill="#1a1a1a">${Math.round(100*v)===0?'0%':(v>0?'+':'−')+Math.abs(Math.round(100*v))+'%'}</text>`+yr;
  }).join('');
  const chg=`<svg viewBox="0 0 294 124" role="img" aria-label="${name}, percent change from the prior year, 2016 to 2025. Values are listed in the table below."><line x1="2" y1="${zero}" x2="292" y2="${zero}" stroke="#767676"/>${bars}</svg>`;
  const radio=(val,label)=>`<label><input type="radio" name="historyChangeField" value="${val}"${historyChangeField===val?' checked':''}> ${label}</label>`;
  body.innerHTML=`<p><span style="color:${HIST_COLORS.j}" aria-hidden="true">●</span> Just value (JV) &nbsp; <span style="color:${HIST_COLORS.v}" aria-hidden="true">●</span> Assessed (AV_NSD)</p>${svg}
<fieldset class="hist-filter"><legend>Yearly % change</legend>${radio('j','Just value')}${radio('v','Assessed value')}</fieldset>${chg}
<table><thead><tr><th scope="col">Year</th><th scope="col">Just value</th><th scope="col">JV chg</th><th scope="col">Assessed</th><th scope="col">AV chg</th><th scope="col">% of JV</th></tr></thead><tbody>${table}</tbody></table><p style="font-size:11px;color:#4a4a4a">Change columns compare each year with the year before. History follows matching parcel IDs. Boundaries may change. A dash means no mapped record for that year or the year before.</p>`;
}
document.getElementById('historyBody').addEventListener('change',e=>{
  if(e.target.name!=='historyChangeField')return;
  historyChangeField=e.target.value;renderHistory();
  const sel=document.querySelector(`#historyBody input[value="${historyChangeField}"]`);if(sel)sel.focus();
});
async function showHistory(pid) {
  selectedParcel=pid;
  const version=++historyVersion;
  document.getElementById('historyPanel').hidden=false;
  document.getElementById('historyTitle').textContent=`Parcel ${pid}`;
  const body=document.getElementById('historyBody');body.textContent='Loading history…';
  try {
    const shard=Number(pid.slice(0,-1))%128;
    if(!historyCache.has(shard)){
      historyCache.set(shard,await readGzip(`data/history-${shard}.json.gz`));
      if(historyCache.size>4)historyCache.delete(historyCache.keys().next().value);
    }
    if(version!==historyVersion)return;
    historyRows=historyCache.get(shard)[pid]||[];historyPid=pid;
    renderHistory();
  }catch(error){if(version===historyVersion)body.textContent=error.message;}
}

document.getElementById('changeSelect').addEventListener('change',e=>{changeUnit=e.target.value;updateLegendVisibility();rebuildLayer();});

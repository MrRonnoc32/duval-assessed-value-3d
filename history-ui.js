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
    const rows=historyCache.get(shard)[pid]||[];
    // History rows are [year, AV_NSD, JV, acres, use]. Chart both values on one scale.
    const max=Math.max(1,...rows.map(r=>Math.max(r[1],r[2])));
    const x=r=>12+(r[0]-2015)*27, yOf=val=>90-val/max*75;
    const line=(i,color)=>`<polyline fill="none" stroke="${color}" stroke-width="2" points="${rows.map(r=>`${x(r)},${yOf(r[i])}`).join(' ')}"/>`+rows.map(r=>`<circle cx="${x(r)}" cy="${yOf(r[i])}" r="3" fill="${color}"/>`).join('');
    const svg=`<svg viewBox="0 0 294 110" role="img" aria-label="Annual just and assessed value history"><line x1="12" y1="90" x2="282" y2="90" stroke="#aaa"/>${line(2,'#c0623a')}${line(1,'#2160a0')}<text x="12" y="105" font-size="10">2015</text><text x="255" y="105" font-size="10">2025</text></svg>`;
    const byYear=new Map(rows.map(r=>[r[0],r]));
    const table=Array.from({length:11},(_,i)=>2015+i).map(y=>{
      const r=byYear.get(y);
      return `<tr${y===currentYear?' style="background:#e7f0f9"':''}><td>${y}</td><td>${r?fmtMoney(r[2]):'—'}</td><td>${r?fmtMoney(r[1]):'—'}</td><td>${r?Math.round(100*r[1]/r[2])+'%':'—'}</td></tr>`;
    }).join('');
    body.innerHTML=`<p><span style="color:#c0623a">●</span> Just value (JV) &nbsp; <span style="color:#2160a0">●</span> Assessed (AV_NSD)</p>${svg}<table><thead><tr><th>Year</th><th>Just value</th><th>Assessed</th><th>% of JV</th></tr></thead><tbody>${table}</tbody></table><p style="font-size:11px;color:#666">History follows matching parcel IDs. Boundaries may change. A dash means no mapped record for that year.</p>`;
  }catch(error){if(version===historyVersion)body.textContent=error.message;}
}

document.getElementById('changeSelect').addEventListener('change',e=>{changeUnit=e.target.value;updateLegendVisibility();rebuildLayer();});

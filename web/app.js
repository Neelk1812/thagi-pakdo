(() => {
const $ = id => document.getElementById(id);
const MOCK = new URLSearchParams(location.search).has('mock');
let lang = localStorage.getItem('tp_lang') || 'en';
let imageFile = null;
let last = null;

const T = {
  en: {tag:'Check any suspicious message before you pay or click.',drop:'<strong>Drop a screenshot here</strong>, click to choose, or paste (Ctrl+V)',
    textLbl:'Or paste the SMS / WhatsApp / UPI message',ph:'Paste the message here...',check:'Check now',clear:'Clear',remove:'Remove',
    samples:'Try a sample (fake):',privacy:'Privacy: with the free Gemini tier, inputs may be used by Google to improve its products. Use only fake samples in the demo. For real messages, run locally with LLM_BACKEND=local (nothing leaves your computer).',
    red:'SCAM - DANGER',amber:'SUSPICIOUS - BE CAREFUL',green:'LOOKS SAFE',why:'Why',todo:'What to do',found:'Found in the message',
    speak:'Read aloud',stop:'Stop',loading:'Checking...',slow:'Gemma is reading the screenshot... this can take up to a minute',slowTxt:'Gemma is reading the message... this can take up to a minute',empty:'Please add a screenshot or paste a message first.',
    err:'Could not check right now. Please try again.',ai:'AI is unavailable - this result is from rule-based checks only.',
    src_gemini:'AI (Gemma)',src_local:'Offline AI',src_cache:'Cached',src_code:'Rules only',greenNote:'This still isn\'t a guarantee. If anything feels off, don\'t pay or click, and ask someone you trust.',urls:'Links',phones:'Phones',upi_ids:'UPI IDs',amounts:'Amounts',foot:'Report cyber fraud: call <b>1930</b> or visit <a href="https://cybercrime.gov.in" target="_blank" rel="noopener">cybercrime.gov.in</a>'},
  hi: {tag:'पैसे देने या क्लिक करने से पहले संदिग्ध मैसेज जाँचें।',drop:'<strong>स्क्रीनशॉट यहाँ छोड़ें</strong>, क्लिक करके चुनें, या पेस्ट करें (Ctrl+V)',
    textLbl:'या SMS / WhatsApp / UPI मैसेज पेस्ट करें',ph:'मैसेज यहाँ पेस्ट करें...',check:'जाँचें',clear:'साफ़ करें',remove:'हटाएँ',
    samples:'नमूना आज़माएँ (नकली):',privacy:'गोपनीयता: मुफ़्त Gemini टियर में आपका इनपुट Google अपने उत्पाद सुधारने में इस्तेमाल कर सकता है। डेमो में सिर्फ़ नकली नमूने इस्तेमाल करें। असली मैसेज के लिए LLM_BACKEND=local के साथ अपने कंप्यूटर पर चलाएँ (कुछ भी आपके कंप्यूटर से बाहर नहीं जाता)।',
    red:'स्कैम - ख़तरा',amber:'संदिग्ध - सावधान रहें',green:'सुरक्षित लगता है',why:'क्यों',todo:'क्या करें',found:'मैसेज में मिला',
    speak:'सुनें',stop:'रोकें',loading:'जाँच हो रही है...',slow:'Gemma स्क्रीनशॉट पढ़ रहा है... इसमें एक मिनट तक लग सकता है',slowTxt:'Gemma मैसेज पढ़ रहा है... इसमें एक मिनट तक लग सकता है',empty:'कृपया पहले स्क्रीनशॉट जोड़ें या मैसेज पेस्ट करें।',
    err:'अभी जाँच नहीं हो सकी। कृपया दोबारा कोशिश करें।',ai:'AI उपलब्ध नहीं है - यह नतीजा सिर्फ़ नियम-आधारित जाँच से है।',
    src_gemini:'AI (Gemma)',src_local:'ऑफ़लाइन AI',src_cache:'सेव किया गया',src_code:'सिर्फ़ नियम',greenNote:'यह गारंटी नहीं है। कुछ भी गड़बड़ लगे तो पैसे न दें, लिंक न खोलें, और किसी भरोसेमंद से पूछें।',urls:'लिंक',phones:'फ़ोन',upi_ids:'UPI आईडी',amounts:'रकम',foot:'साइबर ठगी की शिकायत: <b>1930</b> पर कॉल करें या <a href="https://cybercrime.gov.in" target="_blank" rel="noopener">cybercrime.gov.in</a> पर जाएँ'},
  gu: {tag:'પૈસા ચૂકવતા કે ક્લિક કરતા પહેલાં શંકાસ્પદ મેસેજ તપાસો.',drop:'<strong>સ્ક્રીનશૉટ અહીં મૂકો</strong>, ક્લિક કરીને પસંદ કરો, અથવા પેસ્ટ કરો (Ctrl+V)',
    textLbl:'અથવા SMS / WhatsApp / UPI મેસેજ પેસ્ટ કરો',ph:'મેસેજ અહીં પેસ્ટ કરો...',check:'તપાસો',clear:'સાફ કરો',remove:'કાઢી નાખો',
    samples:'નમૂનો અજમાવો (નકલી):',privacy:'ગોપનીયતા: મફત Gemini ટિયરમાં તમારું ઇનપુટ Google પોતાના ઉત્પાદનો સુધારવા વાપરી શકે છે. ડેમોમાં ફક્ત નકલી નમૂના વાપરો. અસલી મેસેજ માટે LLM_BACKEND=local સાથે તમારા કમ્પ્યુટર પર ચલાવો (કંઈ પણ તમારા કમ્પ્યુટરની બહાર જતું નથી).',
    red:'સ્કેમ - જોખમ',amber:'શંકાસ્પદ - સાવચેત રહો',green:'સુરક્ષિત લાગે છે',why:'શા માટે',todo:'શું કરવું',found:'મેસેજમાં મળ્યું',
    speak:'સાંભળો',stop:'બંધ કરો',loading:'તપાસ ચાલુ છે...',slow:'Gemma સ્ક્રીનશૉટ વાંચી રહ્યું છે... એક મિનિટ સુધી લાગી શકે',slowTxt:'Gemma મેસેજ વાંચી રહ્યું છે... એક મિનિટ સુધી લાગી શકે',empty:'કૃપા કરીને પહેલાં સ્ક્રીનશૉટ ઉમેરો અથવા મેસેજ પેસ્ટ કરો.',
    err:'હમણાં તપાસ થઈ શકી નહીં. ફરી પ્રયત્ન કરો.',ai:'AI ઉપલબ્ધ નથી - આ પરિણામ ફક્ત નિયમ-આધારિત તપાસનું છે.',
    src_gemini:'AI (Gemma)',src_local:'ઑફલાઇન AI',src_cache:'સેવ કરેલ',src_code:'ફક્ત નિયમો',greenNote:'આ ગેરંટી નથી. કંઈ પણ શંકાસ્પદ લાગે તો પૈસા ન ચૂકવો, લિંક ન ખોલો, અને કોઈ વિશ્વાસુને પૂછો.',urls:'લિંક',phones:'ફોન',upi_ids:'UPI આઈડી',amounts:'રકમ',foot:'સાયબર છેતરપિંડીની ફરિયાદ: <b>1930</b> પર કૉલ કરો અથવા <a href="https://cybercrime.gov.in" target="_blank" rel="noopener">cybercrime.gov.in</a> પર જાઓ'}
};
const SPEECH = {en:'en-IN',hi:'hi-IN',gu:'gu-IN'};
const ICON = {red:'⛔',amber:'⚠️',green:'✅'};

// Fake samples only. Each loads /samples/<id>.png (screenshot) and falls back to the same text.
const SAMPLES = [
  {id:'kyc_sms',label:{en:'Fake KYC SMS',hi:'नकली KYC SMS',gu:'નકલી KYC SMS'},
   text:'Dear Customer, your SBI account will be BLOCKED today due to incomplete KYC. Update immediately: http://bit.ly/sbi-kyc-upd8 or your account will be suspended. - SBI Support'},
  {id:'upi_refund',label:{en:'UPI refund request',hi:'UPI रिफंड रिक्वेस्ट',gu:'UPI રિફંડ રિક્વેસ્ટ'},
   text:'Hello, this is Amazon refund team. Your refund of Rs 4,999 is ready. Please approve the collect request of Rs 4,999 from refund.help@okaxis in your UPI app and enter your PIN to receive the money. Do it within 10 minutes.'},
  {id:'courier_fee',label:{en:'Courier fee WhatsApp',hi:'कूरियर फ़ीस WhatsApp',gu:'કુરિયર ફી WhatsApp'},
   text:'India Post: Your parcel #IP88213 could not be delivered due to an incomplete address. Pay a redelivery fee of Rs 25 at http://indiapost-redeliver.xyz/pay within 24 hours or the parcel will be returned. Reply YES to activate the link.'},
  {id:'lottery',label:{en:'Lottery / prize',hi:'लॉटरी / इनाम',gu:'લોટરી / ઇનામ'},
   text:'CONGRATULATIONS!! You have won Rs 25,00,000 in the KBC Lucky Draw 2026! To claim your prize, send your Aadhaar number and a processing fee of Rs 5,500 to UPI ID kbc.claim@ybl. WhatsApp +91 90000 00000 now. Offer expires today!'},
  {id:'safe_otp',label:{en:'Safe bank OTP',hi:'सुरक्षित बैंक OTP',gu:'સુરક્ષિત બેંક OTP'},
   text:'123456 is your OTP for login to Example Bank mobile app. Valid for 5 minutes. Do not share this OTP with anyone, including bank staff. Example Bank never asks for your OTP.'}
];

const MOCKS = {
  en:{verdict:'red',scam_type:'Fake KYC / phishing',reasons:['Threatens to block your account today to create panic.','Uses a shortened link (bit.ly) instead of the bank\'s real website.','Banks never ask you to update KYC through a link in an SMS.'],
    red_flags_found:['url shortener','urgency','KYC'],extracted:{urls:['http://bit.ly/sbi-kyc-upd8'],phones:['9876500011'],upi_ids:[],amounts:[]},
    advice:['Do not click the link or call the number.','Do not share OTP, PIN or card details.','Block and delete the message.','Report at 1930 or cybercrime.gov.in.']},
  hi:{verdict:'red',scam_type:'नकली KYC / फ़िशिंग',reasons:['घबराहट पैदा करने के लिए आज ही खाता बंद करने की धमकी दी गई है।','बैंक की असली वेबसाइट की जगह छोटा लिंक (bit.ly) है।','बैंक SMS के लिंक से KYC अपडेट करने को नहीं कहते।'],
    red_flags_found:[],extracted:{urls:['http://bit.ly/sbi-kyc-upd8'],phones:['9876500011'],upi_ids:[],amounts:[]},
    advice:['लिंक पर क्लिक न करें, नंबर पर कॉल न करें।','OTP, PIN या कार्ड की जानकारी साझा न करें।','मैसेज ब्लॉक करके हटा दें।','1930 या cybercrime.gov.in पर शिकायत करें।']},
  gu:{verdict:'red',scam_type:'નકલી KYC / ફિશિંગ',reasons:['ગભરાટ ફેલાવવા આજે જ ખાતું બ્લૉક કરવાની ધમકી આપી છે.','બેંકની અસલી વેબસાઇટને બદલે ટૂંકી લિંક (bit.ly) છે.','બેંક SMS ની લિંકથી KYC અપડેટ કરવા કહેતી નથી.'],
    red_flags_found:[],extracted:{urls:['http://bit.ly/sbi-kyc-upd8'],phones:['9876500011'],upi_ids:[],amounts:[]},
    advice:['લિંક પર ક્લિક ન કરો, નંબર પર કૉલ ન કરો.','OTP, PIN કે કાર્ડની વિગતો શેર ન કરો.','મેસેજ બ્લૉક કરી ડિલીટ કરો.','1930 અથવા cybercrime.gov.in પર ફરિયાદ કરો.']}
};

function applyLang(){
  const t = T[lang];
  document.documentElement.lang = lang;
  $('tagline').textContent = t.tag; $('dropText').innerHTML = t.drop; $('textLabel').textContent = t.textLbl;
  $('text').placeholder = t.ph; $('check').textContent = t.check; $('reset').textContent = t.clear;
  $('clearImg').textContent = t.remove; $('samplesLabel').textContent = t.samples; $('privacy').textContent = t.privacy;
  $('whyH').textContent = t.why; $('doH').textContent = t.todo; $('foundH').textContent = t.found;
  $('loadTxt').textContent = t.loading; document.querySelector('footer').innerHTML = t.foot;
  $('speakLbl').textContent = speechSynthesis.speaking ? t.stop : t.speak;
  document.querySelectorAll('.lang').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
  renderSamples(); updateSpeakVisibility();
}
function renderSamples(){
  const box = $('sampleBtns'); box.innerHTML = '';
  SAMPLES.forEach(s => {
    const b = document.createElement('button'); b.type='button'; b.className='sample'; b.textContent = s.label[lang];
    b.onclick = () => runSample(s); box.appendChild(b);
  });
}

// ---- image handling
function setImage(f){
  if(!f || !f.type.startsWith('image/')) return;
  imageFile = f; $('previewImg').src = URL.createObjectURL(f);
  $('preview').hidden = false; $('dropText').hidden = true;
}
function clearImage(){ imageFile = null; $('preview').hidden = true; $('dropText').hidden = false; $('file').value=''; }
const drop = $('drop');
drop.addEventListener('click', e => { if(e.target.id !== 'clearImg') $('file').click(); });
drop.addEventListener('keydown', e => { if(e.key==='Enter'||e.key===' '){ e.preventDefault(); $('file').click(); }});
$('file').addEventListener('change', e => setImage(e.target.files[0]));
['dragenter','dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave','drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => setImage(e.dataTransfer.files[0]));
$('clearImg').addEventListener('click', e => { e.stopPropagation(); clearImage(); });
document.addEventListener('paste', e => {
  for(const it of (e.clipboardData||{}).items || []) if(it.type.startsWith('image/')){ setImage(it.getAsFile()); e.preventDefault(); return; }
});

// ---- actions
$('reset').onclick = () => { $('text').value=''; clearImage(); hideAll(); stopSpeak(); };
$('check').onclick = () => check();
document.querySelectorAll('.lang').forEach(b => b.onclick = () => {
  lang = b.dataset.lang; localStorage.setItem('tp_lang', lang); stopSpeak(); applyLang();
  if(last && (imageFile || $('text').value.trim())) check(); // re-run so the result comes back in the new language
});

function hideAll(){ $('result').hidden = true; $('error').hidden = true; $('loading').hidden = true; last = null; }

async function runSample(s){
  clearImage(); $('text').value = '';
  const [img, txt] = await Promise.all([
    fetch('/samples/'+s.id+'.png').then(r => r.ok ? r.blob() : null).catch(() => null),
    fetch('/samples/'+s.id+'.txt').then(r => r.ok ? r.text() : null).catch(() => null)
  ]);
  if(img && img.type.startsWith('image/')) setImage(new File([img], s.id+'.png', {type:img.type}));
  // send image + text together (identical inputs keep the cache warm); fall back to embedded text
  $('text').value = (txt && txt.trim()) || s.text;
  check();
}

async function check(){
  const text = $('text').value.trim();
  if(!imageFile && !text){ showError(T[lang].empty); return; }
  hideAll(); $('loading').hidden = false; $('check').disabled = true; stopSpeak();
  const t0 = Date.now(); $('loadTxt').textContent = T[lang].loading;
  const tick = setInterval(() => { const s = Math.round((Date.now()-t0)/1000); if(s >= 8) $('loadTxt').textContent = (imageFile ? T[lang].slow : T[lang].slowTxt) + ' (' + s + 's)'; }, 1000);
  const ctl = new AbortController(); const to = setTimeout(() => ctl.abort(), 120000);
  try{
    let data;
    if(MOCK){ await new Promise(r=>setTimeout(r,500)); data = MOCKS[lang]; }
    else{
      const fd = new FormData();
      if(imageFile) fd.append('image', imageFile);
      if(text) fd.append('text', text);
      fd.append('lang', lang);
      const r = await fetch('/api/check', {method:'POST', body: fd, signal: ctl.signal});
      if(!r.ok) throw new Error('HTTP '+r.status);
      data = await r.json();
    }
    render(data);
  }catch(err){ console.error(err); showError(T[lang].err); }
  finally{ clearInterval(tick); clearTimeout(to); $('loading').hidden = true; $('check').disabled = false; }
}

function showError(m){ $('error').textContent = m; $('error').hidden = false; $('result').hidden = true; }
function li(parent, items){ parent.innerHTML=''; (items||[]).forEach(x => { const e=document.createElement('li'); e.textContent=x; parent.appendChild(e); }); }

function render(d){
  last = d;
  const v = ['red','amber','green'].includes(d.verdict) ? d.verdict : 'amber';
  const t = T[lang];
  $('verdict').className = 'verdict ' + v;
  $('vicon').textContent = ICON[v]; $('vlabel').textContent = t[v]; $('vtype').textContent = d.scam_type || '';
  li($('reasons'), d.reasons); li($('advice'), d.advice);
  const aiDown = d.ai_unavailable === true || d.ai_available === false;
  const sb=$('srcBadge'); const sk={gemini:'src_gemini',local:'src_local',cache:'src_cache',code:'src_code'}[d.source]; sb.hidden=!sk; if(sk) sb.textContent=t[sk];
  $('greenNote').hidden = v!=='green'; $('greenNote').textContent = t.greenNote;
  $('aiWarn').hidden = !aiDown; $('aiWarn').textContent = t.ai;
  const ex = d.extracted || {}, chips = $('extracted'); chips.innerHTML=''; let n=0;
  ['urls','phones','upi_ids','amounts'].forEach(k => (ex[k]||[]).forEach(val => {
    const c=document.createElement('span'); c.className='chip'; const b=document.createElement('b'); b.textContent=t[k]+':';
    c.appendChild(b); c.appendChild(document.createTextNode(String(val))); chips.appendChild(c); n++; }));
  $('extractedCard').hidden = n===0;
  $('result').hidden = false; $('error').hidden = true;
  updateSpeakVisibility();
  $('result').scrollIntoView({behavior:'smooth', block:'nearest'});
}

// ---- read aloud
let voices = [];
function loadVoices(){ voices = window.speechSynthesis ? speechSynthesis.getVoices() : []; updateSpeakVisibility(); }
function pickVoice(){ const tag = SPEECH[lang]; return voices.find(v=>v.lang===tag) || voices.find(v=>v.lang.replace('_','-').toLowerCase().startsWith(lang)); }
function updateSpeakVisibility(){ $('speak').hidden = !('speechSynthesis' in window) || !last || !pickVoice(); }
function stopSpeak(){ if('speechSynthesis' in window) speechSynthesis.cancel(); $('speak').classList.remove('on'); $('speakLbl').textContent = T[lang].speak; }
$('speak').onclick = () => {
  if(speechSynthesis.speaking){ stopSpeak(); return; }
  if(!last) return;
  const t = T[lang];
  const parts = [t[$('verdict').className.split(' ')[1]], last.scam_type, ...(last.reasons||[]), t.todo, ...(last.advice||[]), $('greenNote').hidden ? '' : t.greenNote].filter(Boolean);
  const u = new SpeechSynthesisUtterance(parts.join('. '));
  u.lang = SPEECH[lang]; const v = pickVoice(); if(v) u.voice = v;
  u.onend = u.onerror = () => { $('speak').classList.remove('on'); $('speakLbl').textContent = t.speak; };
  $('speak').classList.add('on'); $('speakLbl').textContent = t.stop; speechSynthesis.speak(u);
};
if('speechSynthesis' in window){ loadVoices(); speechSynthesis.onvoiceschanged = loadVoices; }

applyLang();
})();

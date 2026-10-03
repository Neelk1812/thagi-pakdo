(() => {
const $ = id => document.getElementById(id);
const MEM = {};
const area = sess => sess ? window.sessionStorage : window.localStorage; // may throw in cross-site iframes
const store = {
  get(k, sess){ try{ const v = area(sess).getItem(k); if(v !== null) return v; }catch(_){} return k in MEM ? MEM[k] : null; },
  set(k, v, sess){ MEM[k] = String(v); try{ area(sess).setItem(k, v); }catch(_){} },
  del(k, sess){ delete MEM[k]; try{ area(sess).removeItem(k); }catch(_){} }
};
const MOCK = new URLSearchParams(location.search).has('mock');
let lang = store.get('tp_lang') || 'en';
let imageFile = null;
let last = null;

const T = {
  en: {tag:'Check any suspicious message before you pay or click.',drop:'<strong>Drop a screenshot here</strong>, click to choose, or paste (Ctrl+V)',
    textLbl:'Or paste the SMS / WhatsApp / UPI message',ph:'Paste the message here...',check:'Check now',clear:'Clear',remove:'Remove',
    samples:'Try a sample (fake):',privacy:'Privacy: with the free Gemini tier, inputs may be used by Google to improve its products. Use only fake samples in the demo. For real messages, run locally with LLM_BACKEND=local (nothing leaves your computer).',
    red:'SCAM - DANGER',amber:'SUSPICIOUS - BE CAREFUL',green:'LOOKS SAFE',why:'Why',todo:'What to do',found:'Found in the message',
    speak:'Read aloud',stop:'Stop',loading:'Checking...',slow:'Gemma is reading the screenshot... this can take up to a minute',slowTxt:'Gemma is reading the message... this can take up to a minute',empty:'Please add a screenshot or paste a message first.',
    err:'Could not check right now. Please try again.',ai:'AI is unavailable - this result is from rule-based checks only.',
    src_gemini:'AI (Gemma)',src_local:'Offline AI',src_cache:'Cached',src_code:'Rules only',greenNote:'This still isn\'t a guarantee. If anything feels off, don\'t pay or click, and ask someone you trust.',camera:'Camera',gallery:'Gallery',pasteUp:'Paste / Upload',call:'Call 1930 (cyber helpline)',rep:'Report at cybercrime.gov.in',hint:'Take a photo, pick a screenshot, or drop / paste one here.',draft:'Draft complaint',dTitle:'Draft a complaint',dIntro:'All fields are optional. Skip anything you do not want to share.',fName:'Your name',fPhone:'Your phone',fAmount:'Amount lost (Rs)',fMethod:'Paid via',fWhat:'What happened',fDate:'Date & time',fTxn:'Transaction ID',more:'More details',mNone:'Select',mUpi:'UPI',mCard:'Card',mNet:'Net banking',mCash:'Cash',mOther:'Other',gen:'Generate',regen:'Generate again',gening:'Drafting...',subject:'Subject',body:'Complaint text (you can edit it)',copy:'Copy',copied:'Copied!',share:'Share',dl:'Download',openPortal:'Open cybercrime.gov.in',note:'Review before submitting. Do not include real Aadhaar, PIN or OTP.',missing:'Still to fill in:',cErr:'Could not draft the complaint. Please try again.',cTime:'Taking too long. Please try again.',aTitle:'Sign in to run live AI checks',aWhy:'Sample buttons work without signing in. Checking your own messages needs a Google sign-in and your own free Gemini key.',aOut:'Sign out',aKeyLbl:'Your Gemini API key',aShow:'Show',aHide:'Hide',aGet:'Get a free key',aRemove:'Remove key',aPriv:'Your key stays on this device and is sent only with your own checks.',eLogin:'Please sign in with Google to check your own messages. The sample buttons work without signing in.',eInvalid:'Your sign-in has expired. Please sign in with Google again.',eKey:'Please add your free Gemini API key below to check your own messages.',eKeyBad:'That Gemini API key was not accepted. Please check it or add a new one.',eRate:'Your Gemini key hit its usage limit. Please wait a minute and try again.',e413:'Image too large. Please try a smaller screenshot.',urls:'Links',phones:'Phones',upi_ids:'UPI IDs',amounts:'Amounts',foot:'Report cyber fraud: call <b>1930</b> or visit <a href="https://cybercrime.gov.in" target="_blank" rel="noopener">cybercrime.gov.in</a>'},
  hi: {tag:'पैसे देने या क्लिक करने से पहले संदिग्ध मैसेज जाँचें।',drop:'<strong>स्क्रीनशॉट यहाँ छोड़ें</strong>, क्लिक करके चुनें, या पेस्ट करें (Ctrl+V)',
    textLbl:'या SMS / WhatsApp / UPI मैसेज पेस्ट करें',ph:'मैसेज यहाँ पेस्ट करें...',check:'जाँचें',clear:'साफ़ करें',remove:'हटाएँ',
    samples:'नमूना आज़माएँ (नकली):',privacy:'गोपनीयता: मुफ़्त Gemini टियर में आपका इनपुट Google अपने उत्पाद सुधारने में इस्तेमाल कर सकता है। डेमो में सिर्फ़ नकली नमूने इस्तेमाल करें। असली मैसेज के लिए LLM_BACKEND=local के साथ अपने कंप्यूटर पर चलाएँ (कुछ भी आपके कंप्यूटर से बाहर नहीं जाता)।',
    red:'स्कैम - ख़तरा',amber:'संदिग्ध - सावधान रहें',green:'सुरक्षित लगता है',why:'क्यों',todo:'क्या करें',found:'मैसेज में मिला',
    speak:'सुनें',stop:'रोकें',loading:'जाँच हो रही है...',slow:'Gemma स्क्रीनशॉट पढ़ रहा है... इसमें एक मिनट तक लग सकता है',slowTxt:'Gemma मैसेज पढ़ रहा है... इसमें एक मिनट तक लग सकता है',empty:'कृपया पहले स्क्रीनशॉट जोड़ें या मैसेज पेस्ट करें।',
    err:'अभी जाँच नहीं हो सकी। कृपया दोबारा कोशिश करें।',ai:'AI उपलब्ध नहीं है - यह नतीजा सिर्फ़ नियम-आधारित जाँच से है।',
    src_gemini:'AI (Gemma)',src_local:'ऑफ़लाइन AI',src_cache:'सेव किया गया',src_code:'सिर्फ़ नियम',greenNote:'यह गारंटी नहीं है। कुछ भी गड़बड़ लगे तो पैसे न दें, लिंक न खोलें, और किसी भरोसेमंद से पूछें।',camera:'कैमरा',gallery:'गैलरी',pasteUp:'पेस्ट / अपलोड',call:'1930 पर कॉल करें (साइबर हेल्पलाइन)',rep:'cybercrime.gov.in पर शिकायत करें',hint:'फ़ोटो खींचें, स्क्रीनशॉट चुनें, या यहाँ छोड़ें / पेस्ट करें।',draft:'शिकायत का मसौदा बनाएँ',dTitle:'शिकायत का मसौदा',dIntro:'सभी जानकारी वैकल्पिक है। जो साझा नहीं करना चाहते उसे छोड़ दें।',fName:'आपका नाम',fPhone:'आपका फ़ोन',fAmount:'गँवाई रकम (रु)',fMethod:'भुगतान का तरीका',fWhat:'क्या हुआ',fDate:'तारीख़ और समय',fTxn:'ट्रांज़ैक्शन आईडी',more:'और जानकारी',mNone:'चुनें',mUpi:'UPI',mCard:'कार्ड',mNet:'नेट बैंकिंग',mCash:'नकद',mOther:'अन्य',gen:'बनाएँ',regen:'फिर से बनाएँ',gening:'बन रहा है...',subject:'विषय',body:'शिकायत का पाठ (आप बदल सकते हैं)',copy:'कॉपी',copied:'कॉपी हो गया!',share:'शेयर',dl:'डाउनलोड',openPortal:'cybercrime.gov.in खोलें',note:'जमा करने से पहले जाँच लें। असली आधार, PIN या OTP न लिखें।',missing:'अभी भरना बाकी:',cErr:'शिकायत का मसौदा नहीं बन सका। कृपया दोबारा कोशिश करें।',cTime:'बहुत देर लग रही है। कृपया दोबारा कोशिश करें।',aTitle:'लाइव AI जाँच के लिए साइन इन करें',aWhy:'सैंपल बटन बिना साइन इन के चलते हैं। अपने मैसेज जाँचने के लिए Google साइन-इन और आपकी अपनी मुफ़्त Gemini कुंजी चाहिए।',aOut:'साइन आउट',aKeyLbl:'आपकी Gemini API कुंजी',aShow:'दिखाएँ',aHide:'छिपाएँ',aGet:'मुफ़्त कुंजी पाएँ',aRemove:'कुंजी हटाएँ',aPriv:'आपकी कुंजी इसी डिवाइस पर रहती है और सिर्फ़ आपकी अपनी जाँच के साथ भेजी जाती है।',eLogin:'अपने मैसेज जाँचने के लिए कृपया Google से साइन इन करें। सैंपल बटन बिना साइन इन के चलते हैं।',eInvalid:'आपका साइन-इन समाप्त हो गया है। कृपया Google से दोबारा साइन इन करें।',eKey:'अपने मैसेज जाँचने के लिए कृपया नीचे अपनी मुफ़्त Gemini API कुंजी जोड़ें।',eKeyBad:'यह Gemini API कुंजी स्वीकार नहीं हुई। कृपया जाँचें या नई कुंजी जोड़ें।',eRate:'आपकी Gemini कुंजी की सीमा पूरी हो गई है। कृपया एक मिनट रुककर दोबारा कोशिश करें।',e413:'तस्वीर बहुत बड़ी है। कृपया छोटा स्क्रीनशॉट आज़माएँ।',urls:'लिंक',phones:'फ़ोन',upi_ids:'UPI आईडी',amounts:'रकम',foot:'साइबर ठगी की शिकायत: <b>1930</b> पर कॉल करें या <a href="https://cybercrime.gov.in" target="_blank" rel="noopener">cybercrime.gov.in</a> पर जाएँ'},
  gu: {tag:'પૈસા ચૂકવતા કે ક્લિક કરતા પહેલાં શંકાસ્પદ મેસેજ તપાસો.',drop:'<strong>સ્ક્રીનશૉટ અહીં મૂકો</strong>, ક્લિક કરીને પસંદ કરો, અથવા પેસ્ટ કરો (Ctrl+V)',
    textLbl:'અથવા SMS / WhatsApp / UPI મેસેજ પેસ્ટ કરો',ph:'મેસેજ અહીં પેસ્ટ કરો...',check:'તપાસો',clear:'સાફ કરો',remove:'કાઢી નાખો',
    samples:'નમૂનો અજમાવો (નકલી):',privacy:'ગોપનીયતા: મફત Gemini ટિયરમાં તમારું ઇનપુટ Google પોતાના ઉત્પાદનો સુધારવા વાપરી શકે છે. ડેમોમાં ફક્ત નકલી નમૂના વાપરો. અસલી મેસેજ માટે LLM_BACKEND=local સાથે તમારા કમ્પ્યુટર પર ચલાવો (કંઈ પણ તમારા કમ્પ્યુટરની બહાર જતું નથી).',
    red:'સ્કેમ - જોખમ',amber:'શંકાસ્પદ - સાવચેત રહો',green:'સુરક્ષિત લાગે છે',why:'શા માટે',todo:'શું કરવું',found:'મેસેજમાં મળ્યું',
    speak:'સાંભળો',stop:'બંધ કરો',loading:'તપાસ ચાલુ છે...',slow:'Gemma સ્ક્રીનશૉટ વાંચી રહ્યું છે... એક મિનિટ સુધી લાગી શકે',slowTxt:'Gemma મેસેજ વાંચી રહ્યું છે... એક મિનિટ સુધી લાગી શકે',empty:'કૃપા કરીને પહેલાં સ્ક્રીનશૉટ ઉમેરો અથવા મેસેજ પેસ્ટ કરો.',
    err:'હમણાં તપાસ થઈ શકી નહીં. ફરી પ્રયત્ન કરો.',ai:'AI ઉપલબ્ધ નથી - આ પરિણામ ફક્ત નિયમ-આધારિત તપાસનું છે.',
    src_gemini:'AI (Gemma)',src_local:'ઑફલાઇન AI',src_cache:'સેવ કરેલ',src_code:'ફક્ત નિયમો',greenNote:'આ ગેરંટી નથી. કંઈ પણ શંકાસ્પદ લાગે તો પૈસા ન ચૂકવો, લિંક ન ખોલો, અને કોઈ વિશ્વાસુને પૂછો.',camera:'કૅમેરા',gallery:'ગેલેરી',pasteUp:'પેસ્ટ / અપલોડ',call:'1930 પર કૉલ કરો (સાયબર હેલ્પલાઇન)',rep:'cybercrime.gov.in પર ફરિયાદ કરો',hint:'ફોટો લો, સ્ક્રીનશૉટ પસંદ કરો, અથવા અહીં મૂકો / પેસ્ટ કરો.',draft:'ફરિયાદનો ડ્રાફ્ટ બનાવો',dTitle:'ફરિયાદનો ડ્રાફ્ટ',dIntro:'બધી માહિતી વૈકલ્પિક છે. જે શેર ન કરવી હોય તે છોડી દો.',fName:'તમારું નામ',fPhone:'તમારો ફોન',fAmount:'ગુમાવેલી રકમ (રૂ)',fMethod:'ચુકવણીની રીત',fWhat:'શું થયું',fDate:'તારીખ અને સમય',fTxn:'ટ્રાન્ઝેક્શન આઈડી',more:'વધુ માહિતી',mNone:'પસંદ કરો',mUpi:'UPI',mCard:'કાર્ડ',mNet:'નેટ બેંકિંગ',mCash:'રોકડ',mOther:'અન્ય',gen:'બનાવો',regen:'ફરી બનાવો',gening:'બની રહ્યું છે...',subject:'વિષય',body:'ફરિયાદનો લખાણ (તમે ફેરફાર કરી શકો)',copy:'કૉપી',copied:'કૉપી થયું!',share:'શેર',dl:'ડાઉનલોડ',openPortal:'cybercrime.gov.in ખોલો',note:'સબમિટ કરતા પહેલાં તપાસી લો. અસલી આધાર, PIN કે OTP ન લખો.',missing:'હજી ભરવાનું બાકી:',cErr:'ફરિયાદનો ડ્રાફ્ટ બની શક્યો નહીં. ફરી પ્રયત્ન કરો.',cTime:'ખૂબ વાર લાગે છે. ફરી પ્રયત્ન કરો.',aTitle:'લાઇવ AI તપાસ માટે સાઇન ઇન કરો',aWhy:'સેમ્પલ બટન સાઇન ઇન વગર ચાલે છે. તમારા પોતાના મેસેજ તપાસવા Google સાઇન-ઇન અને તમારી પોતાની મફત Gemini કી જોઈએ.',aOut:'સાઇન આઉટ',aKeyLbl:'તમારી Gemini API કી',aShow:'બતાવો',aHide:'છુપાવો',aGet:'મફત કી મેળવો',aRemove:'કી કાઢી નાખો',aPriv:'તમારી કી આ ડિવાઇસ પર જ રહે છે અને ફક્ત તમારી પોતાની તપાસ સાથે મોકલાય છે.',eLogin:'તમારા મેસેજ તપાસવા કૃપા કરીને Google થી સાઇન ઇન કરો. સેમ્પલ બટન સાઇન ઇન વગર ચાલે છે.',eInvalid:'તમારું સાઇન-ઇન પૂરું થઈ ગયું છે. કૃપા કરીને Google થી ફરી સાઇન ઇન કરો.',eKey:'તમારા મેસેજ તપાસવા કૃપા કરીને નીચે તમારી મફત Gemini API કી ઉમેરો.',eKeyBad:'આ Gemini API કી સ્વીકારાઈ નથી. કૃપા કરીને તપાસો અથવા નવી કી ઉમેરો.',eRate:'તમારી Gemini કીની મર્યાદા પૂરી થઈ ગઈ છે. એક મિનિટ રાહ જોઈને ફરી પ્રયત્ન કરો.',e413:'ફોટો બહુ મોટો છે. કૃપા કરીને નાનો સ્ક્રીનશૉટ અજમાવો.',urls:'લિંક',phones:'ફોન',upi_ids:'UPI આઈડી',amounts:'રકમ',foot:'સાયબર છેતરપિંડીની ફરિયાદ: <b>1930</b> પર કૉલ કરો અથવા <a href="https://cybercrime.gov.in" target="_blank" rel="noopener">cybercrime.gov.in</a> પર જાઓ'}
};
const SPEECH = {en:'en-IN',hi:'hi-IN',gu:'gu-IN'};
const ICON = {
  red:'<svg viewBox="0 0 24 24"><path d="M12 2 1 21h22zM11 9h2v6h-2zm0 8h2v2h-2z" fill-rule="evenodd"/></svg>',
  amber:'<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1 5h2v7h-2zm0 9h2v2h-2z"/></svg>',
  green:'<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.500 14.500-4-4 1.400-1.400 2.600 2.600 5.600-5.600 1.400 1.400z"/></svg>'};

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
  $('tagline').textContent = t.tag; $('dropText').textContent = t.hint; $('textLabel').textContent = t.textLbl;
  $('text').placeholder = t.ph; $('check').textContent = t.check; $('pasteLbl').textContent = t.pasteUp; $('reset').setAttribute('aria-label', t.clear);
  $('clearImg').textContent = t.remove; $('samplesLabel').textContent = t.samples; $('privacy').textContent = t.privacy;
  $('whyH').textContent = t.why; $('doH').textContent = t.todo; $('foundH').textContent = t.found;
  $('callLbl').textContent = t.call; $('repLbl').textContent = t.rep;
  document.querySelectorAll('[data-i18n]').forEach(e => e.textContent = t[e.dataset.i18n]);
  $('genLbl').textContent = $('dout').hidden ? t.gen : t.regen; $('c_copyLbl').textContent = t.copy;
  $('sheetClose').setAttribute('aria-label', t.clear); $('c_share').hidden = false;
  if($('loading').hidden) $('loadTxt').textContent = t.loading;
  document.querySelector('footer').innerHTML = t.foot;
  $('speakLbl').textContent = ('speechSynthesis' in window && speechSynthesis.speaking) ? t.stop : t.speak;
  document.querySelectorAll('.lang').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
  if(last) render(last, true);
  if(cfg.auth_required) renderAcct();
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
  $('preview').hidden = false; $('dropEmpty').hidden = true;
}
function clearImage(){ imageFile = null; $('preview').hidden = true; $('dropEmpty').hidden = false; $('fileCam').value=''; $('file').value=''; }
const drop = $('drop');
drop.addEventListener('click', e => { if(e.target === drop || e.target.id === 'dropText' || e.target.id === 'previewImg') $('file').click(); });
drop.addEventListener('keydown', e => { if(e.key==='Enter'||e.key===' '){ e.preventDefault(); $('file').click(); }});
$('file').addEventListener('change', e => setImage(e.target.files[0]));
$('fileCam').addEventListener('change', e => setImage(e.target.files[0]));
['dragenter','dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave','drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => setImage(e.dataTransfer.files[0]));
$('clearImg').addEventListener('click', e => { e.stopPropagation(); clearImage(); });
document.addEventListener('paste', e => {
  for(const it of (e.clipboardData||{}).items || []) if(it.type.startsWith('image/')){ setImage(it.getAsFile()); e.preventDefault(); return; }
});

// ---- actions
$('reset').onclick = () => { $('text').value=''; clearImage(); hideAll(); stopSpeak(); window.scrollTo({top:0,behavior:'smooth'}); };
$('check').onclick = () => check();
$('pasteUp').onclick = async () => {
  try{
    if(navigator.clipboard && navigator.clipboard.read){
      for(const item of await navigator.clipboard.read()){
        const it = item.types.find(x => x.startsWith('image/'));
        if(it){ const bl = await item.getType(it); setImage(new File([bl], 'pasted.png', {type: it})); return; }
        if(item.types.includes('text/plain')){ const tx = await (await item.getType('text/plain')).text(); if(tx.trim()){ $('text').value = tx; return; } }
      }
    } else if(navigator.clipboard && navigator.clipboard.readText){
      const tx = await navigator.clipboard.readText(); if(tx.trim()){ $('text').value = tx; return; }
    }
  }catch(_){}
  $('file').click(); // clipboard empty or blocked: open the gallery picker
};
document.querySelectorAll('.lang').forEach(b => b.onclick = () => {
  lang = b.dataset.lang; store.set('tp_lang', lang); stopSpeak(); applyLang();
  if(last && (imageFile || $('text').value.trim())) check(); // re-run so the result comes back in the new language
});

function hideAll(){ if(typeof closeSheet==='function'){ closeSheet(); resetDraft(); } $('result').hidden = true; $('error').hidden = true; $('loading').hidden = true; last = null; }

async function runSample(s){
  clearImage(); $('text').value = '';
  const [img, txt] = await Promise.all([
    fetch('/samples/'+s.id+'.png').then(r => r.ok ? r.blob() : null).catch(() => null),
    fetch('/samples/'+s.id+'.txt').then(r => r.ok ? r.text() : null).catch(() => null)
  ]);
  if(img && img.type.startsWith('image/')){ const sf = new File([img], s.id+'.png', {type:img.type}); sf._sample = true; setImage(sf); }
  // send image + text together (identical inputs keep the cache warm); fall back to embedded text
  $('text').value = (txt && txt.trim()) || s.text;
  check();
}


// Downscale big camera photos before upload (hosting limits request size). Falls back to the original on any failure.
const SHRINK_OVER = 1.5*1024*1024, SHRINK_SIDE = 1600;
const shrinkCache = new WeakMap();
async function shrinkImage(f){
  if(!f || f._sample || f.size <= SHRINK_OVER || !/^image\//.test(f.type)) return f;
  if(shrinkCache.has(f)) return shrinkCache.get(f);
  let out = f;
  try{
    let src, w, h;
    if(window.createImageBitmap){ src = await createImageBitmap(f); w = src.width; h = src.height; }
    else{ src = await new Promise((ok, no) => { const im = new Image(); im.onload = () => ok(im); im.onerror = no; im.src = URL.createObjectURL(f); }); w = src.naturalWidth; h = src.naturalHeight; }
    const k = Math.min(1, SHRINK_SIDE / Math.max(w, h));
    const cv = document.createElement('canvas'); cv.width = Math.max(1, Math.round(w*k)); cv.height = Math.max(1, Math.round(h*k));
    const cx = cv.getContext('2d'); cx.fillStyle = '#fff'; cx.fillRect(0, 0, cv.width, cv.height); cx.drawImage(src, 0, 0, cv.width, cv.height);
    if(src.close) src.close();
    const blob = await new Promise(r => cv.toBlob(r, 'image/jpeg', 0.85));
    if(blob && blob.size && blob.size < f.size) out = new File([blob], (f.name||'photo').replace(/\.[^.]+$/, '') + '.jpg', {type:'image/jpeg'});
  }catch(_){ out = f; }
  shrinkCache.set(f, out); return out;
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
      if(imageFile) fd.append('image', await shrinkImage(imageFile));
      if(text) fd.append('text', text);
      fd.append('lang', lang);
      const r = await fetch('/api/check', {method:'POST', body: fd, headers: authHeaders(), signal: ctl.signal});
      if(!r.ok) throw await apiFail(r);
      data = await r.json();
    }
    clearInterval(tick); $('loading').hidden = true;
    render(data);
  }catch(err){ console.error(err); const m = authMsg(err) || (err && err.status === 413 ? T[lang].e413 : ''); showError(m || T[lang].err); if(m) authFocus(err); }
  finally{ clearInterval(tick); clearTimeout(to); $('loading').hidden = true; $('check').disabled = false; }
}

function showError(m){ $('error').textContent = m; $('error').hidden = false; $('result').hidden = true; }
function li(parent, items){ parent.innerHTML=''; (items||[]).forEach(x => { const e=document.createElement('li'); e.textContent=x; parent.appendChild(e); }); }

function render(d, quiet){
  last = d;
  const v = ['red','amber','green'].includes(d.verdict) ? d.verdict : 'amber';
  const t = T[lang];
  $('verdict').className = 'verdict ' + v;
  $('vicon').innerHTML = ICON[v]; $('vlabel').textContent = t[v]; $('vtype').textContent = d.scam_type || '';
  li($('reasons'), d.reasons); li($('advice'), d.advice);
  const aiDown = d.ai_unavailable === true || d.ai_available === false;
  const sb=$('srcBadge'); const sk={gemini:'src_gemini',local:'src_local',cache:'src_cache',code:'src_code'}[d.source]; sb.hidden=!sk; if(sk) sb.textContent=t[sk];
  $('draftBtn').hidden = v==='green';
  $('greenNote').hidden = v!=='green'; $('greenNote').textContent = t.greenNote;
  $('aiWarn').hidden = !aiDown; $('aiWarn').textContent = t.ai;
  const ex = d.extracted || {}, chips = $('extracted'); chips.innerHTML=''; let n=0;
  ['urls','phones','upi_ids','amounts'].forEach(k => (ex[k]||[]).forEach(val => {
    const c=document.createElement('span'); c.className='chip'; const b=document.createElement('b'); b.textContent=t[k]+':';
    c.appendChild(b); c.appendChild(document.createTextNode(String(val))); chips.appendChild(c); n++; }));
  $('extractedCard').hidden = n===0;
  $('result').hidden = false; $('error').hidden = true;
  updateSpeakVisibility();
  if(!quiet) $('result').scrollIntoView({behavior:'smooth', block:'start'});
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

// ---- optional Google sign-in + user's own Gemini key (only when the server asks for it)
let cfg = {auth_required:false, google_client_id:null}, idToken = null, profile = null, gsiReady = false;
const KEY_STORE = 'tp_gemini_key', TOK_STORE = 'tp_id_token';
function jwt(t){ try{ return JSON.parse(decodeURIComponent(escape(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))))); }catch(_){ return null; } }
function tokenValid(){ if(!idToken) return false; const p = jwt(idToken); return !!(p && p.exp && p.exp*1000 > Date.now()+30000); }
function getKey(){ return (store.get(KEY_STORE) || '').trim(); }
function authHeaders(){
  const h = {}; if(!cfg.auth_required) return h;
  if(tokenValid()) h['Authorization'] = 'Bearer ' + idToken;
  const k = getKey(); if(k) h['X-Gemini-Key'] = k;
  return h;
}
async function apiFail(r){
  let code = '', msg = '';
  try{ const j = await r.json(); code = j.error || (j.detail && j.detail.error) || ''; msg = j.message || ''; }catch(_){}
  const e = new Error('HTTP '+r.status+' '+code); e.status = r.status; e.code = code; e.serverMsg = msg; return e;
}
function authMsg(err){
  if(!err || !cfg.auth_required) return '';
  const t = T[lang], c = err.code;
  if(c === 'login_required') return t.eLogin;
  if(c === 'invalid_token') return t.eInvalid;
  if(c === 'key_required') return t.eKey;
  if(c === 'gemini_key_invalid') return t.eKeyBad;
  if(c === 'gemini_rate_limited') return t.eRate;
  return '';
}
function authFocus(err){
  const c = err.code; if(!c) return;
  if(c === 'login_required' || c === 'invalid_token'){
    if(c === 'invalid_token') signOut(true);
    $('acct').scrollIntoView({behavior:'smooth', block:'center'});
    try{ if(gsiReady && c === 'invalid_token') google.accounts.id.prompt(); }catch(_){}
  }else{ $('acct').scrollIntoView({behavior:'smooth', block:'center'}); setTimeout(() => $('gkey').focus({preventScroll:true}), 400); }
}
function renderAcct(){
  if(!cfg.auth_required){ $('acct').hidden = true; return; }
  $('acct').hidden = false;
  const signed = tokenValid() && profile;
  $('acctOut').hidden = !!signed; $('acctIn').hidden = !signed;
  if(signed){ $('acctName').textContent = profile.name || profile.email || ''; $('acctMail').textContent = profile.email || ''; if(profile.picture) $('acctPic').src = profile.picture; else $('acctPic').removeAttribute('src'); }
  const has = !!getKey(); $('keyRemove').hidden = !has; $('gkey').closest('.keybox').classList.toggle('ok', has);
  $('keyToggle').textContent = T[lang][$('gkey').type === 'password' ? 'aShow' : 'aHide'];
  drawGsi();
}
function drawGsi(){
  if(!gsiReady || $('acctOut').hidden) return;
  $('gsiBtn').innerHTML = '';
  try{ google.accounts.id.renderButton($('gsiBtn'), {type:'standard', theme:'outline', size:'large', shape:'pill', text:'signin_with', locale: lang, width: Math.min(320, $('gsiBtn').clientWidth || 300)}); }catch(e){ console.error(e); }
}
function onCredential(resp){
  idToken = resp.credential; profile = jwt(idToken);
  store.set(TOK_STORE, idToken, true);
  $('error').hidden = true; renderAcct();
}
function signOut(silent){
  idToken = null; profile = null; store.del(TOK_STORE, true);
  try{ if(!silent && window.google) google.accounts.id.disableAutoSelect(); }catch(_){}
  renderAcct();
}
$('signOut').onclick = () => signOut();
$('gkey').addEventListener('input', () => { const v = $('gkey').value.trim(); v ? store.set(KEY_STORE, v) : store.del(KEY_STORE); renderAcct(); });
$('keyToggle').onclick = () => { $('gkey').type = $('gkey').type === 'password' ? 'text' : 'password'; renderAcct(); };
$('keyRemove').onclick = () => { store.del(KEY_STORE); $('gkey').value = ''; $('gkey').type = 'password'; renderAcct(); };
async function initAuth(){
  try{
    const r = await fetch('/api/config'); if(!r.ok) return;
    const c = await r.json(); if(!c || c.auth_required !== true) return;
    cfg = {auth_required:true, google_client_id: c.google_client_id || null};
  }catch(_){ return; } // no config endpoint or offline: behave exactly as before
  try{ idToken = store.get(TOK_STORE, true); if(!tokenValid()) idToken = null; else profile = jwt(idToken); }catch(_){ idToken = null; }
  $('gkey').value = getKey();
  renderAcct();
  if(!cfg.google_client_id) return;
  const sc = document.createElement('script'); sc.src = 'https://accounts.google.com/gsi/client'; sc.async = true; sc.defer = true;
  sc.onload = () => {
    try{ google.accounts.id.initialize({client_id: cfg.google_client_id, callback: onCredential, auto_select: false, cancel_on_tap_outside: true}); gsiReady = true; renderAcct(); }catch(e){ console.error(e); }
  };
  document.head.appendChild(sc);
}
initAuth();

// ---- complaint draft
let lastEl = null, genSeq = 0;
function resetDraft(){ genSeq++; $('dout').hidden = true; $('dErr').hidden = true; $('c_body').value = ''; $('c_subject').value = ''; $('genBtn').disabled = false; $('genLbl').textContent = T[lang].gen; }
function openSheet(){
  lastEl = document.activeElement; $('backdrop').hidden = false; $('sheet').hidden = false; document.body.classList.add('sheet-open');
  setTimeout(() => $('d_name').focus({preventScroll:true}), 300);
}
function closeSheet(){
  if($('sheet').hidden) return;
  $('sheet').hidden = true; $('backdrop').hidden = true; document.body.classList.remove('sheet-open');
  if(lastEl && lastEl.focus) lastEl.focus({preventScroll:true});
}
$('draftBtn').onclick = openSheet; $('sheetClose').onclick = closeSheet; $('backdrop').onclick = closeSheet;
document.addEventListener('keydown', e => { if(e.key === 'Escape') closeSheet(); });

function paintMirror(){
  const esc = x => x.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const txt = $('c_body').value;
  const filled = new Set(['d_name','d_phone','d_amount','d_method','d_date','d_txn'].map(id => $(id).value.trim().toLowerCase()).filter(Boolean));
  const isPh = m => !filled.has(m.slice(1,-1).trim().toLowerCase());
  $('c_mirror').innerHTML = esc(txt).replace(/\[[^\[\]\n]{1,60}\]/g, m => isPh(m) ? '<mark>'+m+'</mark>' : m) + '\n';
  $('c_mirror').scrollTop = $('c_body').scrollTop;
  const found = [...new Set(txt.match(/\[[^\[\]\n]{1,60}\]/g) || [])].filter(isPh);
  const box = $('c_missing'); box.hidden = !found.length; box.innerHTML = '';
  if(found.length){ box.append(document.createTextNode(T[lang].missing + ' ')); found.forEach(f => { const b = document.createElement('b'); b.textContent = f; box.appendChild(b); }); }
}
$('c_body').addEventListener('input', paintMirror);
$('c_body').addEventListener('scroll', () => { $('c_mirror').scrollTop = $('c_body').scrollTop; });

$('dform').addEventListener('submit', async e => {
  e.preventDefault(); if(!last) return;
  const t = T[lang], btn = $('genBtn');
  const details = {};
  [['name','d_name'],['phone','d_phone'],['amount_lost','d_amount'],['payment_method','d_method'],['what_happened','d_what'],['date_time','d_date'],['transaction_id','d_txn']]
    .forEach(([k,id]) => { const v = $(id).value.trim(); if(v) details[k] = v; });
  const my = ++genSeq; btn.disabled = true; $('genLbl').textContent = t.gening; $('dErr').hidden = true;
  const ctl = new AbortController(); const to = setTimeout(() => ctl.abort(), 60000);
  try{
    let d;
    if(MOCK){ await new Promise(r => setTimeout(r, 600)); d = {subject:'Complaint: online fraud via SMS', body:'To,\nThe Officer, Cyber Crime Cell\n\nI, '+(details.name||'[Your name]')+', received a fraudulent message. Phone: '+(details.phone||'[Your phone]')+'.\nAmount lost: '+(details.amount_lost||'[Amount lost]')+'.\n\nRegards,\n'+(details.name||'[Your name]')}; }
    else{
      const r = await fetch('/api/complaint', {method:'POST', headers:{'Content-Type':'application/json', ...authHeaders()}, body: JSON.stringify({result: last, lang, details}), signal: ctl.signal});
      if(!r.ok) throw await apiFail(r);
      d = await r.json();
    }
    if(my !== genSeq) return; // a newer check/draft replaced this one
    $('c_subject').value = d.subject || ''; $('c_body').value = d.body || '';
    $('dout').hidden = false; paintMirror();
    $('dout').scrollIntoView({behavior:'smooth', block:'start'});
  }catch(err){ if(my !== genSeq) return; console.error(err); const m = authMsg(err); $('dErr').textContent = m || (err.name === 'AbortError' ? t.cTime : t.cErr); $('dErr').hidden = false; if(m){ closeSheet(); showError(m); authFocus(err); } }
  finally{ clearTimeout(to); if(my === genSeq){ btn.disabled = false; $('genLbl').textContent = $('dout').hidden ? t.gen : t.regen; } }
});

const fullText = () => ($('c_subject').value.trim() ? $('c_subject').value.trim() + '\n\n' : '') + $('c_body').value;
$('c_copy').onclick = async () => {
  const txt = fullText();
  try{ await navigator.clipboard.writeText(txt); }
  catch(_){ $('c_body').select(); document.execCommand('copy'); }
  $('c_copyLbl').textContent = T[lang].copied; setTimeout(() => $('c_copyLbl').textContent = T[lang].copy, 1800);
};
$('c_share').onclick = async () => {
  const txt = fullText();
  if(navigator.share){ try{ await navigator.share({title: $('c_subject').value, text: txt}); }catch(_){} }
  else window.open('https://wa.me/?text=' + encodeURIComponent(txt), '_blank', 'noopener'); // no native share sheet (desktop): WhatsApp link
};
$('c_dl').onclick = () => {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([fullText()], {type:'text/plain;charset=utf-8'}));
  a.download = 'cyber-crime-complaint.txt'; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};

applyLang();
})();

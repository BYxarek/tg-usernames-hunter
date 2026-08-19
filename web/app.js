(() => {
  const $ = (sel, root=document) => root.querySelector(sel);
  const app = $('#app');

  const state = {
    lang: 'ru',
    version: '',
    screen: 'loading',
    config: {},
    settings: {
      mode: 'both', min_len: 5, max_len: 12, limit: 100, delay: 1.0,
      min_score: 70, words: '', allow_digits: false, allow_underscore: false,
      bot_usernames: false,
    },
    results: [], checked: 0, total: 0, unlimited: false, availableCount: 0, skippedCount: 0,
    searchState: 'idle', lastUsername: '', error: '',
  };

  const T = {
    ru: {
      subtitle:'поиск свободных username', log:'Лог', lang:'EN',
      credK:'Подключение', credTitle:'Данные Telegram приложения', credHint:'Укажите API-данные и бота для уведомлений. Они сохраняются только в локальный config.py.',
      apiId:'API ID', apiHash:'API hash', botToken:'Bot token', notifyIds:'ID получателей', notifyHelp:'Через запятую. Каждый получатель должен сначала отправить боту /start.',
      connect:'Подключиться', connecting:'Подключение…', getApi:'Открыть my.telegram.org',
      phoneK:'Авторизация', phoneTitle:'Вход в Telegram', phoneHint:'Введите номер телефона в международном формате.', phone:'Номер телефона', sendCode:'Отправить код', sending:'Отправка…',
      codeTitle:'Код подтверждения', codeHint:'Код придёт в Telegram или по SMS.', code:'Код', confirm:'Подтвердить', checking:'Проверка…',
      passTitle:'Двухфакторная аутентификация', passHint:'Введите облачный пароль Telegram.', password:'Пароль', signIn:'Войти',
      settingsK:'Параметры', settingsTitle:'Настройка поиска', settingsHint:'Сформируйте пул кандидатов и запустите проверку через Telegram API.',
      mode:'Режим', dict:'Словарь', syllable:'Слоги', both:'Словарь + слоги', list:'Свой список', words:'Username через запятую',
      minLen:'Мин. длина', maxLen:'Макс. длина', limit:'Количество проверок', limitHelp:'0 — без ограничения: генератор продолжит работу до нажатия «Остановить».',
      delay:'Пауза, сек', score:'Мин. красота', digits:'Разрешить цифры', underscore:'Разрешить _', bots:'Username для ботов',
      botsHelp:'Только варианты, оканчивающиеся на bot; при разрешённом _ также name_bot.', start:'Начать поиск',
      resultsK:'Поиск', resultsTitle:'Проверка username', stop:'Остановить', newSearch:'Новый поиск',
      checked:'Проверено', available:'Свободно', skipped:'Пропущено', progress:'Прогресс', unlimited:'Без лимита',
      waiting:'Подготовка кандидатов…', running:'Проверяю', done:'Поиск завершён', stopped:'Поиск остановлен', failed:'Ошибка поиска',
      empty:'Результаты появятся здесь по мере проверки.', free:'свободен', taken:'занят', unavailable:'недоступен', fragment:'Fragment', skip:'пропущен', beauty:'score',
      noCandidates:'Нет кандидатов под выбранные критерии.',
    },
    en: {
      subtitle:'find available Telegram usernames', log:'Log', lang:'RU',
      credK:'Connection', credTitle:'Telegram application data', credHint:'Enter API credentials and notification bot settings. They are stored only in local config.py.',
      apiId:'API ID', apiHash:'API hash', botToken:'Bot token', notifyIds:'Recipient IDs', notifyHelp:'Comma-separated. Each recipient must send /start to the bot first.',
      connect:'Connect', connecting:'Connecting…', getApi:'Open my.telegram.org',
      phoneK:'Authorization', phoneTitle:'Sign in to Telegram', phoneHint:'Enter your phone number in international format.', phone:'Phone number', sendCode:'Send code', sending:'Sending…',
      codeTitle:'Confirmation code', codeHint:'The code will arrive in Telegram or via SMS.', code:'Code', confirm:'Confirm', checking:'Checking…',
      passTitle:'Two-factor authentication', passHint:'Enter your Telegram cloud password.', password:'Password', signIn:'Sign in',
      settingsK:'Parameters', settingsTitle:'Search setup', settingsHint:'Build a candidate pool and verify it through Telegram API.',
      mode:'Mode', dict:'Dictionary', syllable:'Syllables', both:'Dictionary + syllables', list:'Custom list', words:'Comma-separated usernames',
      minLen:'Min length', maxLen:'Max length', limit:'Checks count', limitHelp:'0 — unlimited: generation continues until you press Stop.',
      delay:'Delay, sec', score:'Min beauty', digits:'Allow digits', underscore:'Allow _', bots:'Bot usernames',
      botsHelp:'Only names ending in bot; with underscore enabled, name_bot is also mixed in.', start:'Start search',
      resultsK:'Search', resultsTitle:'Username checks', stop:'Stop', newSearch:'New search',
      checked:'Checked', available:'Available', skipped:'Skipped', progress:'Progress', unlimited:'Unlimited',
      waiting:'Preparing candidates…', running:'Checking', done:'Search completed', stopped:'Search stopped', failed:'Search failed',
      empty:'Results will appear here as usernames are checked.', free:'available', taken:'taken', unavailable:'unavailable', fragment:'Fragment', skip:'skipped', beauty:'score',
      noCandidates:'No candidates matched the selected criteria.',
    }
  };
  const t = k => T[state.lang][k] || k;
  const esc = (s='') => String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  function chrome() {
    $('#headerSubtitle').textContent = t('subtitle');
    $('#openLogBtn').textContent = t('log');
    $('#langBtn').textContent = t('lang');
    $('#versionText').textContent = state.version ? `v${state.version}` : '';
  }

  function alertHtml(message, type='danger') {
    return message ? `<div class="alert alert-${type} py-2 px-3 small mb-3">${esc(message)}</div>` : '';
  }

  function renderCredentials() {
    const c = state.config || {};
    app.innerHTML = `
      <div class="row justify-content-center"><div class="col-12 col-lg-8 col-xl-7">
        <div class="mb-4"><div class="section-kicker mb-2">${t('credK')}</div><h1 class="h3 hero-title mb-2">${t('credTitle')}</h1><p class="text-secondary mb-0">${t('credHint')}</p></div>
        <div class="panel p-3 p-md-4">
          <div id="pageError"></div>
          <form id="credentialsForm" class="row g-3">
            <div class="col-md-4"><label class="form-label small text-secondary">${t('apiId')}</label><input class="form-control" name="api_id" inputmode="numeric" value="${esc(c.TG_API_ID||'')}"></div>
            <div class="col-md-8"><label class="form-label small text-secondary">${t('apiHash')}</label><input class="form-control" name="api_hash" type="password" value="${esc(c.TG_API_HASH||'')}"></div>
            <div class="col-12"><label class="form-label small text-secondary">${t('botToken')}</label><input class="form-control" name="bot_token" type="password" value="${esc(c.TG_BOT_TOKEN||'')}"></div>
            <div class="col-12"><label class="form-label small text-secondary">${t('notifyIds')}</label><input class="form-control" name="notify_ids" value="${esc(c.TG_NOTIFY_CHAT_IDS||'')}"><div class="form-text">${t('notifyHelp')}</div></div>
            <div class="col-12 d-flex flex-column flex-sm-row gap-2 mt-4"><button class="btn btn-light flex-grow-1" id="connectBtn">${t('connect')}</button><button type="button" class="btn btn-outline-secondary" id="apiSiteBtn">${t('getApi')}</button></div>
          </form>
        </div>
      </div></div>`;
    $('#credentialsForm').addEventListener('submit', async e => {
      e.preventDefault();
      const fd = new FormData(e.currentTarget); const data = Object.fromEntries(fd.entries());
      const btn=$('#connectBtn'); btn.disabled=true; btn.textContent=t('connecting');
      const res=await window.pywebview.api.connect(data);
      if (!res.ok) { showError(res.error); btn.disabled=false; btn.textContent=t('connect'); }
    });
    $('#apiSiteBtn').onclick = () => window.pywebview.api.open_external('https://my.telegram.org');
  }

  function authView(kind) {
    const cfg = {
      phone:{title:t('phoneTitle'),hint:t('phoneHint'),label:t('phone'),type:'tel',placeholder:'+79991234567',button:t('sendCode'),method:'send_code'},
      code:{title:t('codeTitle'),hint:t('codeHint'),label:t('code'),type:'text',placeholder:'12345',button:t('confirm'),method:'confirm_code'},
      password:{title:t('passTitle'),hint:t('passHint'),label:t('password'),type:'password',placeholder:'••••••••',button:t('signIn'),method:'confirm_password'}
    }[kind];
    app.innerHTML=`<div class="row justify-content-center"><div class="col-12 col-md-8 col-lg-6">
      <div class="mb-4"><div class="section-kicker mb-2">${t('phoneK')}</div><h1 class="h3 hero-title mb-2">${cfg.title}</h1><p class="text-secondary mb-0">${cfg.hint}</p></div>
      <div class="panel p-3 p-md-4"><div id="pageError"></div><form id="authForm"><label class="form-label small text-secondary">${cfg.label}</label><input autofocus class="form-control mb-3" id="authValue" type="${cfg.type}" placeholder="${cfg.placeholder}"><button class="btn btn-light w-100" id="authBtn">${cfg.button}</button></form></div>
    </div></div>`;
    $('#authForm').onsubmit=async e=>{e.preventDefault(); const value=$('#authValue').value; const btn=$('#authBtn'); btn.disabled=true; const res=await window.pywebview.api[cfg.method](value); if(!res.ok){showError(res.error);btn.disabled=false;}};
  }

  function renderSettings() {
    const s=state.settings;
    app.innerHTML=`<div class="row justify-content-center"><div class="col-12 col-xl-10">
      <div class="mb-4"><div class="section-kicker mb-2">${t('settingsK')}</div><h1 class="h3 hero-title mb-2">${t('settingsTitle')}</h1><p class="text-secondary mb-0">${t('settingsHint')}</p></div>
      <div class="panel p-3 p-md-4"><div id="pageError"></div><form id="settingsForm" class="row g-3">
        <div class="col-md-6"><label class="form-label small text-secondary">${t('mode')}</label><select class="form-select" name="mode">
          <option value="dict" ${s.mode==='dict'?'selected':''}>${t('dict')}</option><option value="syllable" ${s.mode==='syllable'?'selected':''}>${t('syllable')}</option><option value="both" ${s.mode==='both'?'selected':''}>${t('both')}</option><option value="list" ${s.mode==='list'?'selected':''}>${t('list')}</option>
        </select></div>
        <div class="col-md-3 col-6"><label class="form-label small text-secondary">${t('minLen')}</label><input class="form-control" type="number" min="5" max="32" name="min_len" value="${s.min_len}"></div>
        <div class="col-md-3 col-6"><label class="form-label small text-secondary">${t('maxLen')}</label><input class="form-control" type="number" min="5" max="32" name="max_len" value="${s.max_len}"></div>
        <div class="col-md-4"><label class="form-label small text-secondary">${t('limit')}</label><input class="form-control" type="number" min="0" max="10000" name="limit" value="${s.limit}"><div class="form-text">${t('limitHelp')}</div></div>
        <div class="col-md-4"><label class="form-label small text-secondary">${t('delay')}</label><input class="form-control" type="number" min="0" step="0.1" name="delay" value="${s.delay}"></div>
        <div class="col-md-4"><label class="form-label small text-secondary">${t('score')}</label><input class="form-control" type="number" min="0" max="100" name="min_score" value="${s.min_score}"></div>
        <div class="col-12 ${s.mode==='list'?'':'d-none'}" id="wordsWrap"><label class="form-label small text-secondary">${t('words')}</label><textarea class="form-control" name="words" rows="3">${esc(s.words)}</textarea></div>
        <div class="col-12"><div class="panel-soft p-3"><div class="row g-3">
          <div class="col-md-4"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="allow_digits" ${s.allow_digits?'checked':''}><label class="form-check-label">${t('digits')}</label></div></div>
          <div class="col-md-4"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="allow_underscore" ${s.allow_underscore?'checked':''}><label class="form-check-label">${t('underscore')}</label></div></div>
          <div class="col-md-4"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="bot_usernames" ${s.bot_usernames?'checked':''}><label class="form-check-label">${t('bots')}</label></div><div class="form-text">${t('botsHelp')}</div></div>
        </div></div></div>
        <div class="col-12 mt-4"><button class="btn btn-light w-100 py-2" id="startBtn">${t('start')}</button></div>
      </form></div>
    </div></div>`;
    const form=$('#settingsForm');
    form.elements.mode.onchange=()=>$('#wordsWrap').classList.toggle('d-none',form.elements.mode.value!=='list');
    form.onsubmit=async e=>{e.preventDefault(); captureSettings(); const btn=$('#startBtn');btn.disabled=true; const res=await window.pywebview.api.start_search(state.settings); if(!res.ok){showError(res.error);btn.disabled=false;return;} state.screen='results';state.results=[];state.checked=0;state.total=state.settings.limit;state.unlimited=state.settings.limit===0;state.availableCount=0;state.skippedCount=0;state.searchState='waiting';state.error='';render();};
  }

  function captureSettings() {
    const f=$('#settingsForm'); if(!f)return;
    state.settings={mode:f.elements.mode.value,min_len:Number(f.elements.min_len.value),max_len:Number(f.elements.max_len.value),limit:Number(f.elements.limit.value),delay:Number(f.elements.delay.value),min_score:Number(f.elements.min_score.value),words:f.elements.words.value,allow_digits:f.elements.allow_digits.checked,allow_underscore:f.elements.allow_underscore.checked,bot_usernames:f.elements.bot_usernames.checked};
  }

  function stats() {
    return {available: state.availableCount, skipped: state.skippedCount};
  }

  function renderResults() {
    const st=stats();
    const terminal=['done','stopped','error'].includes(state.searchState);
    let status=t('waiting');
    if(state.searchState==='running') status=`${t('running')}: @${esc(state.lastUsername)}`;
    if(state.searchState==='done') status=t('done');
    if(state.searchState==='stopped') status=t('stopped');
    if(state.searchState==='error') status=t('failed');
    const pct=state.total?Math.min(100,Math.round(state.checked/state.total*100)):0;
    app.innerHTML=`<div class="row justify-content-center"><div class="col-12 col-xl-11">
      <div class="d-flex flex-column flex-sm-row align-items-sm-end justify-content-between gap-3 mb-4"><div><div class="section-kicker mb-2">${t('resultsK')}</div><h1 class="h3 hero-title mb-1">${t('resultsTitle')}</h1><div class="text-secondary small" id="searchStatus">${status}</div></div><div class="d-flex gap-2">${terminal?`<button class="btn btn-light" id="newSearchBtn">${t('newSearch')}</button>`:''}<button class="btn btn-outline-secondary" id="stopBtn" ${state.searchState==='running'||state.searchState==='waiting'?'':'disabled'}>${t('stop')}</button></div></div>
      ${alertHtml(state.error)}
      <div class="row g-2 mb-3"><div class="col-4"><div class="panel-soft metric"><div class="metric-value">${state.checked}</div><div class="metric-label">${t('checked')}</div></div></div><div class="col-4"><div class="panel-soft metric"><div class="metric-value">${st.available}</div><div class="metric-label">${t('available')}</div></div></div><div class="col-4"><div class="panel-soft metric"><div class="metric-value">${st.skipped}</div><div class="metric-label">${t('skipped')}</div></div></div></div>
      <div class="panel p-3 p-md-4"><div class="d-flex justify-content-between small mb-2"><span class="text-secondary">${t('progress')}</span><span>${state.unlimited?t('unlimited'):`${pct}%`}</span></div><div class="progress mb-4"><div class="progress-bar ${state.unlimited&&state.searchState==='running'?'progress-bar-striped progress-bar-animated':''}" style="width:${state.unlimited?'100%':pct+'%'}"></div></div>
        <div class="result-list panel-soft" id="resultList">${resultsHtml()}</div>
      </div>
    </div></div>`;
    const stop=$('#stopBtn'); if(stop) stop.onclick=async()=>{stop.disabled=true;await window.pywebview.api.stop_search();};
    const nw=$('#newSearchBtn'); if(nw) nw.onclick=()=>{state.screen='settings';state.searchState='idle';state.results=[];state.checked=0;state.total=0;state.unlimited=false;state.availableCount=0;state.skippedCount=0;state.error='';render();};
    const list=$('#resultList'); if(list) list.scrollTop=list.scrollHeight;
  }

  function resultsHtml() {
    if(!state.results.length) return `<div class="p-4 text-center text-secondary small">${t('empty')}</div>`;
    return state.results.map(singleResultHtml).join('');
  }

  function singleResultHtml(r) {
    let cls='text-bg-secondary', label=t('skip');
    if(r.available===true){cls='text-bg-success';label=t('free');}
    else if(r.available===false){cls='text-bg-dark border';label=t('taken');}
    else if(r.available==='unavailable'){cls='text-bg-secondary';label=t('unavailable');}
    else if(r.available==='fragment'){cls='text-bg-warning';label=t('fragment');}
    return `<div class="result-row d-flex align-items-center gap-3 px-3 py-2"><div class="flex-grow-1 overflow-hidden"><div class="username text-truncate">@${esc(r.username)}</div><div class="small text-secondary">${t('beauty')} ${r.score}</div></div><span class="badge rounded-pill ${cls} status-pill">${label}</span></div>`;
  }

  function updateResultsLive(r) {
    if (state.screen !== 'results') return;
    const status=$('#searchStatus'); if(status) status.innerHTML=`${t('running')}: @${esc(state.lastUsername)}`;
    const metrics=document.querySelectorAll('.metric-value');
    if(metrics.length>=3){metrics[0].textContent=state.checked;metrics[1].textContent=state.availableCount;metrics[2].textContent=state.skippedCount;}
    const pct=state.total?Math.min(100,Math.round(state.checked/state.total*100)):0;
    const bar=$('.progress-bar'); if(bar && !state.unlimited) bar.style.width=`${pct}%`;
    const progressText=$('.progress').previousElementSibling?.querySelector('span:last-child'); if(progressText && !state.unlimited) progressText.textContent=`${pct}%`;
    const list=$('#resultList');
    if(list){
      if(state.checked===1) list.innerHTML='';
      list.insertAdjacentHTML('beforeend', singleResultHtml(r));
      while(list.children.length>5000) list.removeChild(list.firstElementChild);
      list.scrollTop=list.scrollHeight;
    }
  }

  function renderLoading(){app.innerHTML='<div class="d-flex justify-content-center py-5"><div class="spinner-border text-light" role="status"></div></div>';}
  function render(){chrome(); if(state.screen==='loading')return renderLoading(); if(state.screen==='credentials')return renderCredentials(); if(['phone','code','password'].includes(state.screen))return authView(state.screen); if(state.screen==='settings')return renderSettings(); if(state.screen==='results')return renderResults();}
  function showError(msg){state.error=msg||''; const holder=$('#pageError'); if(holder)holder.innerHTML=alertHtml(state.error); else render();}

  window.dispatchBackendEvent = ev => {
    switch(ev.kind){
      case 'connect_error': state.screen='credentials';state.error=ev.message;render();break;
      case 'authorized': state.screen='settings';state.error='';render();break;
      case 'need_phone': state.screen='phone';state.error='';render();break;
      case 'phone_error': state.screen='phone';state.error=ev.message;render();break;
      case 'need_code': state.screen='code';state.error='';render();break;
      case 'code_error': state.screen='code';state.error=ev.message;render();break;
      case 'need_password': state.screen='password';state.error='';render();break;
      case 'password_error': state.screen='password';state.error=ev.message;render();break;
      case 'search_started': state.searchState='running';state.total=ev.total||0;state.unlimited=!!ev.unlimited;renderResults();break;
      case 'search_result':
        state.searchState='running';state.checked=ev.index;state.total=ev.total||state.total;state.lastUsername=ev.username;
        if(ev.available===true) state.availableCount++; if(ev.available===null) state.skippedCount++;
        state.results.push(ev); if(state.results.length>6000) state.results.splice(0,1000);
        updateResultsLive(ev);break;
      case 'search_done': state.searchState='done';state.checked=ev.checked;state.total=ev.total||state.total;renderResults();break;
      case 'search_stopped': state.searchState='stopped';state.checked=ev.checked;renderResults();break;
      case 'search_error': state.searchState='error';state.error=ev.message;renderResults();break;
      case 'bot_error': state.error=ev.message;renderResults();break;
      case 'fatal_error': state.searchState='error';state.error=ev.message;render();break;
    }
  };

  $('#langBtn').onclick=()=>{ if(state.screen==='settings')captureSettings(); state.lang=state.lang==='ru'?'en':'ru'; document.documentElement.lang=state.lang; render(); };
  $('#openLogBtn').onclick=async()=>{const res=await window.pywebview.api.open_log();if(!res.ok){state.error=res.error;render();}};
  $('#githubCredit').onclick=async e=>{e.preventDefault();await window.pywebview.api.open_external('https://github.com/BYxarek');};

  window.addEventListener('pywebviewready', async () => {
    try {
      const init=await window.pywebview.api.bootstrap();
      state.version=init.version;state.config=init.config||{};state.screen='credentials';render();
      if(init.auto_connect){
        const c=init.config;
        const res=await window.pywebview.api.connect({api_id:c.TG_API_ID,api_hash:c.TG_API_HASH,bot_token:c.TG_BOT_TOKEN,notify_ids:c.TG_NOTIFY_CHAT_IDS});
        if(res.ok){state.screen='credentials';render();}
      }
    } catch(e){state.screen='credentials';state.error=String(e);render();}
  });

  render();
})();

// 원본 앱(app/source.html)을 002book.com 용으로 바꾸는 패치 목록
// 함수 교체는 acorn으로 함수 위치를 정확히 찾아서 바꾸고, 짧은 문자열 교체는 정확히 1번만 나와야 한다.
// 원본이 바뀌어서 패치가 맞지 않으면 빌드가 실패하고 어느 패치인지 알려 준다.

export const FUNCTIONS = {
  doLogin: `async function doLogin(fd){
  const id=String(fd.get('id')||'').trim().toLowerCase();const pw=String(fd.get('pw')||'');
  if(!id||!pw){S.authErr='아이디와 비밀번호를 넣어 주세요.';return render()}
  try{
    const r=await window.__002.auth.login(id,pw);
    S.authErr='';S.authMsg='';await enter(id,r.member);
  }catch(e){S.authErr=(e&&e.code==='blocked')?'이용이 정지된 계정이에요. 관리자에게 문의해 주세요.':(e&&e.code&&e.code!=='server_error'&&e.message)?e.message:'로그인하지 못했어요. 잠시 뒤 다시 해 주세요.';render()}
}`,

  doFind: `async function doFind(fd){
  const id=String(fd.get('id')||'').trim().toLowerCase();const email=String(fd.get('email')||'').trim().toLowerCase();
  if(!id||!EMAILRE.test(email)){S.authErr='아이디와 가입한 이메일을 정확히 적어 주세요.';return render()}
  try{
    await window.__002.auth.resetPassword(id,email);
    S.authErr='';S.authTab='login';S.authMsg='아이디와 이메일이 맞으면 몇 분 안에 임시 비밀번호가 메일로 와요. 스팸함도 확인해 주세요.';render();
  }catch(e){S.authErr=(e&&e.message)||'요청하지 못했어요. 잠시 뒤 다시 해 주세요.';render()}
}`,

  doSignup: `async function doSignup(fd){
  // 오류가 나도 입력한 내용이 지워지지 않도록 화면을 다시 그리지 않고 오류 문구만 바꾼다
  const er=m=>{S.authErr=m;const e=$('#autherr');if(e){e.textContent=m;e.scrollIntoView({block:'center',behavior:'smooth'})}else render()};
  const g=k=>String(fd.get(k)||'').trim();
  const id=g('id').toLowerCase();const pw=String(fd.get('pw')||'');const nick=g('nick')||id;
  if(!/^[a-z0-9_-]{3,20}$/.test(id))return er('아이디는 영문 소문자와 숫자로 3~20자여야 해요.');
  if(pw.length<8)return er('비밀번호는 8자 이상이어야 해요.');
  if(!EMAILRE.test(g('email')))return er('이메일 주소를 정확히 적어 주세요.');
  if(!GENDERS.includes(g('gender')))return er('성별을 골라 주세요.');
  const bm=/^(\\d{4})-(\\d{2})$/.exec(g('birth'));if(!bm)return er('태어난 연도와 월을 골라 주세요.');
  const now=new Date();let age=now.getFullYear()-(+bm[1]);if(now.getMonth()+1<+bm[2])age--;
  if(age<14&&(!g('gname')||!EMAILRE.test(g('gemail'))))return er('만 14세 미만은 보호자 이름과 보호자 이메일을 적어 주세요.');
  if(!fd.get('agt')||!fd.get('agp'))return er('이용약관 동의와 개인정보 처리 안내 확인에 체크해 주세요.');
  const p={id,pw,nick,region:g('region'),grade:SCODES.includes(g('grade'))?g('grade'):'중1',gender:g('gender'),bio:g('bio').slice(0,40),buddy:g('buddy').slice(0,10)||BUDDY0,...budFields(),
    email:g('email').slice(0,120),birth:g('birth'),guardianName:g('gname'),guardianEmail:g('gemail'),agreeTerms:!!fd.get('agt'),agreePrivacy:!!fd.get('agp'),agreeMarketing:!!fd.get('agm')};
  const btn=$('form[data-form=signup] button[type=submit]');if(btn)btn.disabled=true;
  try{
    const r=await window.__002.auth.signup(p);S.bpk=null;
    if(r.pending==='guardian'){S.authErr='';S.authTab='login';S.authMsg='보호자 이메일로 동의 요청을 보냈어요. 보호자가 승인하면 바로 로그인할 수 있어요.';return render()}
    S.authErr='';await enter(id,r.member);toast('가입했어요. 환영해요, '+nick+'!');
  }catch(e){if(btn)btn.disabled=false;er((e&&e.code&&e.code!=='server_error'&&e.message)?e.message:'가입하지 못했어요. 잠시 뒤 다시 해 주세요.')}
}`,

  doWithdraw: `async function doWithdraw(fd){
  const er=m=>{const e=$('#wderr');if(e)e.textContent=m};
  if(isAdmin())return er('관리자 계정은 탈퇴할 수 없어요.');
  if(!fd.get('ok'))return er('안내를 읽고 체크해 주세요.');
  try{await window.__002.auth.withdraw(String(fd.get('pw')||''))}
  catch(e){return er(e&&e.code==='bad_password'?'비밀번호가 맞지 않아요.':'탈퇴 처리를 마치지 못했어요. 잠시 뒤 다시 해 주세요.')}
  doLogout();toast('탈퇴했어요. 모든 기록이 지워졌어요.')
}`,

  deleteMember: `async function deleteMember(id){
  await window.__002.server.adminDelete(id);
  if((S.plans.paid||{})[id])delete S.plans.paid[id];if((S.plans.blocked||{})[id])delete S.plans.blocked[id];
}`,
};

// 원래 함수 본문을 고쳐서 쓰는 패치 (원본 함수 텍스트 → 새 텍스트)
export const FUNCTION_EDITS = {
  saveProfile: [
    ['const up={nick,email,region,', "const up={pub:{bio:!!fd.get('pub_bio'),grade:!!fd.get('pub_grade'),region:!!fd.get('pub_region'),photo:!!fd.get('pub_photo')},nick,email,region,"],
    [`if(pw.length<4)return er('새 비밀번호는 4자 이상이어야 해요.');
        if(await sha(S.me.salt+cur)!==S.me.pw)return er('현재 비밀번호가 맞지 않아요.');
        up.pw=await sha(S.me.salt+pw);up.mustChange=false;`,
     `if(pw.length<8)return er('새 비밀번호는 8자 이상이어야 해요.');
        try{await window.__002.auth.changePassword(cur,pw)}catch(e){return er((e&&e.message)||'비밀번호를 바꾸지 못했어요.')}
        up.mustChange=false;`],
  ],
  doLogout: [['function doLogout(){', 'function doLogout(){window.__002.auth.logout();']],
};

// const 선언 교체
export const CONSTS = {
  pwOK: `const pwOK=async pw=>{try{await window.__002.server.call('auth.verify',{pw});return true}catch(e){return false}};`,
};

const SIGNUP_EXTRA = `<label for="su-birth">태어난 연월 <small class="hint">만 14세 미만은 보호자 동의가 필요해요</small><input id="su-birth" name="birth" type="month" min="1940-01" max="\${new Date().toISOString().slice(0,7)}" required></label>
      <fieldset style="border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:0;display:flex;flex-direction:column;gap:8px"><legend class="hint" style="padding:0 4px">만 14세 미만이면 보호자 정보도 적어 주세요</legend>
        <label for="su-gname">보호자 이름<input id="su-gname" name="gname" maxlength="30" autocomplete="off"></label>
        <label for="su-gemail">보호자 이메일 <small class="hint">이 주소로 동의 요청 메일이 가요</small><input id="su-gemail" name="gemail" type="email" autocomplete="off"></label></fieldset>
      <details style="border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:var(--field)"><summary style="cursor:pointer;font-weight:500">개인정보 처리·AI 이용 안내 (꼭 읽어 주세요)</summary>
        <ul class="hint" style="margin:6px 0 0;padding-left:18px">
          <li><b>목적</b>: 회원 관리, 학년별 책·영화 코스와 논술 AI 첨삭 제공, 친구·가족 기능</li>
          <li><b>항목</b>: 아이디, 비밀번호(암호화), 닉네임, 이메일, 거주지역, 학년, 성별, 태어난 연월, 학습 기록 (만 14세 미만은 보호자 이름·이메일)</li>
          <li><b>보유 기간</b>: 탈퇴하면 바로 삭제\${(window.__002CFG&&window.__002CFG.free)?'':' (법령상 결제 기록은 5년)'}</li>
          <li><b>생성형 AI</b>: 첨삭·추천·일기 답장은 생성형 AI(Anthropic Claude)가 만들어요. 버튼을 누를 때만 내용이 AI로 가고 AI 학습에는 쓰이지 않아요.</li>
          <li><b>국외 이전</b>: 서비스 운영을 위해 Supabase·Anthropic·Resend·GitHub(미국)에 처리를 맡겨요.</li>
          <li><b>공개 범위</b>: 다른 회원에게는 닉네임만 보여요. 나머지는 내가 공개를 켠 것만 보여요.</li>
          <li>선택 항목(소개·사진·마케팅)은 동의하지 않아도 이용에 제한이 없어요. 자세한 내용은 <a href="/privacy.html" target="_blank" rel="noopener" style="color:var(--rose-ink)">개인정보처리방침</a>을 봐 주세요.</li>
        </ul></details>
      <label style="flex-direction:row;gap:8px;align-items:center"><input type="checkbox" name="agt" required style="width:auto"> [필수] <a href="/terms.html" target="_blank" rel="noopener" style="color:var(--rose-ink)">이용약관</a>(생성형 AI 이용 고지 포함)에 동의해요</label>
      <label style="flex-direction:row;gap:8px;align-items:center"><input type="checkbox" name="agp" required style="width:auto"> [필수] 위 개인정보 처리·국외 이전 안내를 확인했어요</label>
      <label style="flex-direction:row;gap:8px;align-items:center"><input type="checkbox" name="agm" style="width:auto"> [선택] 새 소식 이메일 받기 <small class="hint">만 14세 이상만</small></label>
      `;

export const STRINGS = [
  ['free: 무료 출시 모드에서는 모두 맞춤형 사용 가능', `const isPaid=()=>paidOf(S.id);`, `const isPaid=()=>!!(window.__002CFG&&window.__002CFG.free)||paidOf(S.id);`],
  ['free: 상단 등급 표시', `<span class="bdg \${isPaid()?'paid':''}" style="flex:none">\${isAdmin()?'관리자':isPaid()?'유료회원':'무료회원'}</span>`, `<span class="bdg \${(isPaid()&&!(window.__002CFG&&window.__002CFG.free))?'paid':''}" style="flex:none">\${isAdmin()?'관리자':(window.__002CFG&&window.__002CFG.free)?'회원':isPaid()?'유료회원':'무료회원'}</span>`],
  ['free: 내 정보 등급 표시', `\${esc(S.id)} · \${isAdmin()?'관리자':isPaid()?'유료회원':'무료회원'} · 가입`, `\${esc(S.id)} · \${isAdmin()?'관리자':(window.__002CFG&&window.__002CFG.free)?'회원':isPaid()?'유료회원':'무료회원'} · 가입`],
  ['free: 내 정보 유료 안내 숨김', `function subSecHTML(){`, `function subSecHTML(){if(window.__002CFG&&window.__002CFG.free)return '';`],
  ['boot: 저장된 로그인은 서버 세션으로만', `const saved=lsGet('ppang.login');`, `const saved=(window.__002.auth.session()||{}).uid||null;`],
  ['auth: 연결 실패 안내', `'<p class="warn">이 페이지는 Claude에 로그인한 상태로 열어야 해요. 초대받은 계정으로 다시 열어 주세요.</p>'`, `'<p class="warn">서버에 연결하지 못했어요. 잠시 뒤 새로고침해 주세요.</p>'`],
  ['signup: 비밀번호 8자', `<label for="su-pw">비밀번호 <small class="hint">4자 이상</small>`, `<label for="su-pw">비밀번호 <small class="hint">8자 이상</small>`],
  ['signup: 생년월·보호자·약관 동의', `<p class="err" id="autherr">\${esc(S.authErr)}</p><button class="btn" type="submit">가입하고 시작하기</button>`,
    SIGNUP_EXTRA + `<p class="err" id="autherr">\${esc(S.authErr)}</p><button class="btn" type="submit">가입하고 시작하기</button>`],
  ['admin: 임시 비밀번호는 서버에서', `try{const salt=m.salt||hid(id+Date.now()+Math.random());await S.db.doc('members/'+id).update({salt,pw:await sha(salt+pw),mustChange:true});m.salt=salt;`,
    `try{await window.__002.server.call('admin.setPassword',{id,pw,temp:true});`],
  ['admin: 비밀번호 바꾸기는 서버에서', `try{const salt=m.salt||hid(d.id+Date.now()+Math.random());await S.db.doc('members/'+d.id).update({salt,pw:await sha(salt+v)});m.salt=salt;`,
    `try{await window.__002.server.call('admin.setPassword',{id:d.id,pw:v});`],
  ['pay: 유료회원 신청 → 토스 결제', `const rec={id:S.id,nick:S.me.nick||S.id,status:'requested',at:Date.now()};`,
    `if(window.__002.isPlayApp){toast('유료회원 신청은 002book.com 웹사이트에서 할 수 있어요.');break}location.href='/pay/checkout.html';break;const rec={id:S.id,nick:S.me.nick||S.id,status:'requested',at:Date.now()};`],
  ['head: PWA·어댑터', `<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>`,
    `<meta name="description" content="중학생을 위한 책·영화 인생교육과 논술 첨삭, 002BOOK">
<meta name="theme-color" content="#3E2F26">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/png" href="/icons/icon-192.png">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="002BOOK">
<meta property="og:title" content="002BOOK — 꿈이 이루어지는 서재"><meta property="og:description" content="한 달에 책 한 권, 영화 두 편. 읽고 보고 쓰면서 중학교 3년을 채워 가는 나만의 서재">
<meta property="og:image" content="https://002book.com/icons/og.png"><meta property="og:url" content="https://002book.com/">
<script src="/runtime/config.js"></script>
<script src="/runtime/claude-shim.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>`],
  ['profile: 공개 설정', `<div class="sec" style="margin-top:6px"><h3>비밀번호 바꾸기</h3>`, `<div class="sec" style="margin-top:6px"><h3>공개 설정</h3><p class="hint">다른 회원에게는 <b>닉네임</b>만 보여요. 아래에서 켠 정보만 함께 보여요. 이메일·성별·태어난 연월은 항상 비공개예요.</p>
      <label style="flex-direction:row;gap:8px;align-items:center"><input type="checkbox" name="pub_bio" style="width:auto" \${(m.pub||{}).bio?'checked':''}> 한 줄 소개 공개</label>
      <label style="flex-direction:row;gap:8px;align-items:center"><input type="checkbox" name="pub_grade" style="width:auto" \${(m.pub||{}).grade?'checked':''}> 학년 공개</label>
      <label style="flex-direction:row;gap:8px;align-items:center"><input type="checkbox" name="pub_region" style="width:auto" \${(m.pub||{}).region?'checked':''}> 거주지역(시·도) 공개</label>
      <label style="flex-direction:row;gap:8px;align-items:center"><input type="checkbox" name="pub_photo" style="width:auto" \${(m.pub||{}).photo?'checked':''}> 내가 올린 프로필 사진 공개 <small class="hint">끄면 다른 회원에게는 기본 캐릭터로 보여요</small></label></div>
    <div class="sec" style="margin-top:6px"><h3>비밀번호 바꾸기</h3>`],
  ['profile: 한 줄 소개 안내', `<label for="pf-bio">한 줄 소개 <small class="hint">친구들에게 보여요</small>`, `<label for="pf-bio">한 줄 소개 <small class="hint">아래 공개 설정을 켜야 다른 회원에게 보여요</small>`],
  ['profile: 새 비밀번호 8자', `<label for="pf-pw">새 비밀번호 <small class="hint">4자 이상</small>`, `<label for="pf-pw">새 비밀번호 <small class="hint">8자 이상</small>`],
  ['signup: 한 줄 소개 안내', `<small class="hint">친구들에게 보여요. 비워도 돼요</small>`, `<small class="hint">처음에는 비공개예요. 내 정보 → 공개 설정에서 켤 수 있어요. 비워도 돼요</small>`],
  ['friends: 다른 회원 아이디 숨김', "\${esc([m.id,sub(m.id)].filter(Boolean).join(' · '))}", "\${esc(sub(m.id))}"],
  ['AI 표시: 첨삭 PDF 쪽 바닥글', "첨삭 평가서 · \${nSheets+k+1} / \${all}</div>", "첨삭 평가서 · 생성형 AI(Claude)가 작성한 첨삭 · \${nSheets+k+1} / \${all}</div>"],
  ['AI 표시: 첨삭 PDF 메타데이터', "await S.downloads.save({filename:fname+'.pdf',data:pdf.output('blob')});", "pdf.setProperties({title:fname,subject:'생성형 AI(Anthropic Claude)가 작성한 첨삭 결과',creator:'002BOOK · AI 생성',keywords:'AI-generated'});await S.downloads.save({filename:fname+'.pdf',data:pdf.output('blob')});"],
  ['AI 표시: 비전보드 저장 안내', "toast('비전보드를 저장했어요.')", "toast('비전보드를 저장했어요. 문구 일부는 생성형 AI가 다듬었어요.')"],
  ['html lang', `<!doctype html><html><head>`, `<!doctype html><html lang="ko"><head>`],
  ['tail: 약관 링크·서비스워커', `\n</body></html>`, `
<div id="legal" style="text-align:center;font-size:12px;color:#6F6155;padding:18px 0 28px"><a href="/terms.html" style="color:inherit">이용약관</a> · <a href="/privacy.html" style="color:inherit"><b>개인정보처리방침</b></a> · <a href="/refund.html" style="color:inherit">환불정책</a><br>002BOOK의 첨삭·추천·피드백은 생성형 AI(Anthropic Claude)가 만들어요. 사실과 다를 수 있어요.<br>__BUSINESS_INFO__</div>
<style>#legal{max-width:1100px;margin:0 auto}@media (max-width:720px){#legal{padding-bottom:calc(96px + env(safe-area-inset-bottom,0px))!important}}</style>
<script>if('serviceWorker' in navigator)addEventListener('load',function(){navigator.serviceWorker.register('/sw.js').catch(function(){})});</script>
</body></html>`],
];

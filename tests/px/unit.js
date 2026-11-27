// 누적 오류 프로파일·공통 주제 문항 생성 계산부(app/source.html의 PX 블록) 단위 시험: node tests/px/unit.js
const fs=require('fs');const assert=require('assert');
let calls=[];
global.S={progress:{evalLog:[],evalN:0},sample:{json:async(p,o)=>{calls.push(p);return S._reply?S._reply(p):[]}}};global.saveProgress=()=>{S._saved=(S._saved||0)+1};global.esc=s=>String(s);
const store={};global.localStorage={getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v}};
const src=fs.readFileSync(require('path').join(__dirname,'../../app/source.html'),'utf8');
// PX가 쓰는 공용 도우미(본 작품만 묻기, 11-27)를 원본에서 그대로 가져온다
for(const nm of ['mvs','esIds','esLines','esCnt']){const m=src.match(new RegExp('const '+nm+'=([^\\n]*?);(?:const |\\n)'));if(m)global[nm]=eval('('+m[1]+')')}
eval(src.slice(src.indexOf('/*PX-BEGIN'),src.indexOf('/*PX-END*/'))+';global.PX=PX');
let n=0;const ok=(name,c,extra)=>{n++;if(!c){console.log('FAIL',name,extra||'');process.exitCode=1}else console.log('PASS',name)};
(async()=>{
// 1) 첫 첨삭: 오류 레코드 저장, OCR 불확실 토큰 제외
const ev1={transcript:'나는 어른이 됬다고 생각한다. 순례 씨는 수림이를 도와 줄수있다. 그래서 가족은 중요하다 왜냐하면 가족이 없으면 힘들기 때문에 가족은 소중하다. 그[?]는 좋았다.',unreadable:['그[?]는'],
 spelling:[{orig:'됬다고',fix:'되었다고',why:''},{orig:'줄수있다',fix:'줄 수 있다',why:''},{orig:'그[?]는',fix:'그는',why:''}],
 sentences:[{orig:'그래서 가족은 중요하다 왜냐하면 가족이 없으면 힘들기 때문에 가족은 소중하다.',grade:'고침',type:'긴 문장',why:'',fix:'가족은 중요하다. 가족이 없으면 힘들기 때문이다.'},{orig:'나는 어른이 됬다고 생각한다.',grade:'잘함',why:'',fix:''}],scores:{}};
const inj1=PX.persistent(S.progress.errs,1);ok('첫 첨삭은 지속 오류 없음',inj1.length===0);ok('지시문 없음',PX.p1Ask(inj1)==='');
await PX.after(ev1,{r2:false,key:'k1',inj:inj1,text:ev1.transcript});
ok('레코드 3건(불확실 토큰 제외)',S.progress.errs.length===3,JSON.stringify(S.progress.errs));
ok('유형 분류',S.progress.errs.map(e=>e.t).join()==='맞춤법,띄어쓰기,긴 문장',S.progress.errs.map(e=>e.t).join());
ok('식별자 부여',S.progress.errs.map(e=>e.id).join()==='e1,e2,e3');ok('ev.px 기록',ev1.px&&ev1.px.n===3&&ev1.px.rd===1);
S.progress.evalN=1;
// 같은 달 재시도 시 중복 저장 안 됨
await PX.after(JSON.parse(JSON.stringify(Object.assign({},ev1,{px:undefined}))),{r2:false,key:'k1',inj:[],text:''});ok('같은 회차 다시 저장해도 중복 없음',S.progress.errs.length===6-3||S.progress.errs.filter(e=>e.rd===2).length===3);
S.progress.errs=S.progress.errs.filter(e=>e.rd===1||false);if(!S.progress.errs.length){S.progress.errs=[{id:'e1',t:'맞춤법',ex:'됬다고',fx:'되었다고',rd:1,k:'k1',len:80,st:'open'},{id:'e2',t:'띄어쓰기',ex:'줄수있다',fx:'줄 수 있다',rd:1,k:'k1',len:80,st:'open'},{id:'e3',t:'긴 문장',ex:'그래서 가족은 중요하다 왜냐하면 가족이 없으면 힘들기 때문에 가족은 소중하다.',fx:'',rd:1,k:'k1',len:80,st:'open'}]}
// 2) 2차(재작성): 정렬, 이중 판정, 해소 상태 갱신
const L=PX.r2List('k1');ok('2차 대상 3건',L.length===3);
const t2='나는 어른이 되었다고 생각한다. 순례 씨는 수림이를 도와 줄수있다. 가족은 중요하다. 가족이 없으면 힘들기 때문이다.';
const r2x=PX.r2Ask(L,ev1.transcript,t2);ok('지시문에 식별자 3개',['e1','e2','e3'].every(id=>r2x.add.includes('id:'+id)));
ok('대응 문장 찾음',r2x.al.e1&&r2x.al.e1.includes('되었다고')&&r2x.al.e2&&r2x.al.e2.includes('줄수있다'),JSON.stringify(r2x.al));
// 언어모델이 e3을 빠뜨림 → 재질의
S._reply=p=>p.includes('검증에 실패')?[{id:'e3',ok:true}]:[];calls=[];
const ev2={transcript:t2,scores:{},fixed:[{id:'e1',ok:true},{id:'e2',ok:true}]};
await PX.after(ev2,{r2:true,key:'k1',r2x,text:t2});
ok('빠진 식별자 재질의 1회',calls.length===1&&calls[0].includes('e3')&&calls[0].includes('실패 사유'),String(calls.length));
const fx=Object.fromEntries(ev2.px.fix.map(x=>[x.id,x.c]));
ok('e1: 규칙·모델 모두 해소 → 해소',fx.e1==='res');ok('e2: 모델만 해소(문자열 그대로) → 부분해소',fx.e2==='part');ok('e3: 규칙 없는 유형, 모델 판정 → 해소',fx.e3==='res');
ok('통계',ev2.px.n===3&&ev2.px.res===2&&ev2.px.part===1&&ev2.px.un===0&&ev2.px.rate===83,JSON.stringify(ev2.px));
ok('오류 레코드 상태 갱신',S.progress.errs.find(e=>e.id==='e1').st==='res'&&S.progress.errs.find(e=>e.id==='e2').st==='part');ok('저장 호출',S._saved>=1);ok('임시 필드 제거',ev2.fixed===undefined);
// 3) 가중점수: 해소 감쇠, 최근성 감쇠, 길이 정규화
const w=PX.weights(S.progress.errs,2).w;ok('해소된 유형 가중치 0.3배',Math.abs(w['맞춤법']-0.3*(100/100))<1e-9&&Math.abs(w['띄어쓰기']-1)<1e-9,JSON.stringify(w));
const E2=[{id:'a',t:'맞춤법',ex:'x',rd:1,len:400,st:'open'},{id:'b',t:'맞춤법',ex:'y',rd:3,len:200,st:'open'},{id:'c',t:'근거',ex:'z',rd:3,len:200,st:'open'},{id:'d',t:'띄어쓰기',ex:'q',rd:-3,len:100,st:'open'}];
const w2=PX.weights(E2,4);ok('최근성·길이 반영',Math.abs(w2.w['맞춤법']-(0.49*0.25+1*0.5))<1e-9&&Math.abs(w2.w['근거']-0.5)<1e-9&&w2.w['띄어쓰기']===undefined,JSON.stringify(w2.w));
const per=PX.persistent(E2,4);ok('M회 이상 나온 유형만 지속 오류',per.length===1&&per[0].t==='맞춤법'&&per[0].id==='b',JSON.stringify(per));
ok('누적 1회면 조건 없이 상위 K',PX.persistent([{id:'a',t:'근거',ex:'x',rd:1,len:100,st:'open'}],2).length===1);
// 4) 다음 첨삭: 지속 오류 주입, 재발 판정, 누락 시 재질의, 재발 건수 반영
S.progress.errs=[{id:'e1',t:'띄어쓰기',ex:'줄수있다',fx:'줄 수 있다',rd:1,k:'k1',len:200,st:'open'},{id:'e4',t:'띄어쓰기',ex:'할수있다',fx:'할 수 있다',rd:2,k:'k2',len:200,st:'open'},{id:'e5',t:'근거',ex:'그냥 그렇다.',fx:'',rd:1,k:'k1',len:200,st:'open'},{id:'e6',t:'근거',ex:'좋다고 생각한다.',fx:'',rd:2,k:'k2',len:200,st:'res'}];S.progress.evalN=2;S.progress.errSeq=6;
const inj=PX.persistent(S.progress.errs,3);ok('지속 오류 2유형',inj.map(x=>x.t).join()==='띄어쓰기,근거'&&inj[0].id==='e4'&&inj[1].id==='e5',JSON.stringify(inj));
const ask=PX.p1Ask(inj);ok('지시문에 식별자·예문',ask.includes('id:e4')&&ask.includes('할수있다')&&ask.includes('recur'));
S._reply=p=>[{id:'e5',recur:true}];calls=[];
const ev3={transcript:'가'.repeat(300),spelling:[{orig:'갈수있다',fix:'갈 수 있다'}],sentences:[],recur:[{id:'e4',recur:true}],scores:{}};
await PX.after(ev3,{r2:false,key:'k3',inj,text:ev3.transcript});
ok('재발 누락 재질의',calls.length===1&&calls[0].includes('e5'));
const r3=S.progress.errs.filter(e=>e.rd===3);ok('이번 회차 2건(새 띄어쓰기 1 + 재발 근거 1)',r3.length===2&&r3[0].t==='띄어쓰기'&&r3[1].t==='근거'&&r3[1].re==='e5',JSON.stringify(r3));
ok('재발 표시',ev3.px.recur.length===2&&ev3.px.recur.every(x=>x.recur===true));ok('화면 문구',PX.html(ev3).includes('다시 나옴')&&PX.html(ev2).includes('고친 정도 83%'));
// 재질의도 실패하면 그대로 진행
S._reply=p=>{throw new Error('x')};const ev4={transcript:'나'.repeat(200),spelling:[],sentences:[],scores:{}};S.progress.evalN=3;await PX.after(ev4,{r2:false,key:'k4',inj:PX.persistent(S.progress.errs,4),text:''});ok('재질의 실패해도 진행',ev4.px&&ev4.px.recur.every(x=>x.recur===null));
// 5) 주제 게이트
ok('낙서는 걸러짐',PX.junk('아아아아아아아아아아아아아아','가족의 의미를 논하시오 순례주택'));ok('정상 글은 통과',!PX.junk('순례주택에서 가족은 서로 기대며 산다고 생각한다.','가족의 의미를 논하시오 순례주택'));ok('아주 짧은 글은 게이트 대상 아님',!PX.junk('ㅋㅋ','가족'));
// 6) 문항 생성: 서술문·엔티티·공통 주제, 근거 점수, 재생성, 교체 조건
const it={g:'중1',book:'순례주택 / 돼지꿈',m1:'인생은 아름다워',m2:'패밀리맨',topic:'가족',level:2};
S._reply=p=>p.includes('후보 주제어')?{works:[{id:'책',summary:'빌라 주인 순례 씨가 철없는 수림이 가족을 받아 주며 스스로 서는 어른의 삶을 보여 준다. 가족이 서로 기대는 방식을 묻는다.',entities:['순례 씨','수림','거북마을']},{id:'영화 ①',summary:'귀도는 수용소에서 아들 조수아를 지키려고 모든 것을 놀이라고 속인다. 가족을 위한 희생과 사랑의 의미를 보여 준다.',entities:['귀도','조수아','수용소']},{id:'영화②',summary:'투자가 잭이 가족과 함께하는 다른 삶을 살아 보며 가족의 의미를 깨닫는다.',entities:['잭','케이트']}],themes:['가족의 의미','어른의 책임','사랑과 선택']}:[{n:2,q:'「순례주택」의 수림이와 영화 「패밀리맨」의 잭이 가족의 의미를 깨닫는 과정을 비교하시오. (800자 내외)'}];calls=[];
const meta=await PX.qmeta(it);ok('작품 3개·엔티티',meta&&meta.works.length===3&&meta.works[0].title==='순례주택'&&meta.works[2].ents.join()==='잭,케이트',JSON.stringify(meta&&meta.works.map(w=>w.ents)));
ok('공통 주제 선택',meta.theme==='가족의 의미'&&!meta.fb,meta.theme);await PX.qmeta(it);ok('두 번째는 저장분 사용',calls.length===1);
ok('생성 지시에 공통 주제·요약·엔티티',PX.qAdd(meta).includes('[공통 주제] 가족의 의미')&&PX.qAdd(meta).includes('조수아'));ok('메타 없으면 빈 문자열',PX.qAdd(null)==='');
const pool=['「순례주택」의 순례 씨와 영화 「인생은 아름다워」의 귀도가 가족을 지키는 방식을 비교하고 논하시오. (800자 내외)','두 작품의 주인공이 공동체를 대하는 태도를 비교하고 더 바람직한 쪽을 논하시오. (800자 내외)','「순례주택」, 「인생은 아름다워」, 「패밀리맨」을 관통하는 가족의 의미를 논하시오. (1000자 내외)'];
const tags=[['책','영화 ①'],['책','영화 ②'],['책','영화 ①','영화 ②']];calls=[];
const gr=await PX.reground(meta,pool,tags);ok('근거 약한 2번만 재생성',calls.length===1&&calls[0].includes('2번')&&!calls[0].includes('1번 (')&&pool[1].includes('패밀리맨'),pool[1]);ok('재생성 뒤 모두 채택',gr.join()==='true,true,true',gr.join());
ok('매체가 같으면 불채택',!PX.check('「인생은 아름다워」의 귀도와 「패밀리맨」의 잭을 비교하시오.',['영화 ①','영화 ②'],meta.works).ok);
const c1=PX.replaceOK(pool[0],pool,meta.theme,2);ok('이력과 같은 문항은 교체 불가',!c1.ok&&c1.why.includes('비슷'));
const c2=PX.replaceOK('순례 씨와 귀도의 선택을 근거로 가족의 의미가 무엇인지 설명하시오. (700자 내외)',pool,meta.theme,2);ok('조건 만족 문항은 교체',c2.ok,JSON.stringify(c2));
const c3=PX.replaceOK('주인공의 선택을 평가하시오. (600자 내외)',pool,'성장과 독립',2);ok('주제가 드러나지 않으면 불가',!c3.ok&&c3.why.includes('공통 주제'));
ok('난이도 차이 초과면 불가',!PX.replaceOK('가족의 의미를 쓰시오.',[],'가족의 의미',3).ok);
console.log(process.exitCode?'SOME FAILED':'ALL PASS',n);
})();

// 도서 서지 조회 계산부 시험: ISBN 검사, KDC·부가기호 → 분야, 같은 책 고르기
// 실행: cd supabase/functions/api && FAKE_DB=1 deno run -A --unstable-sloppy-imports ../../../tests/books_unit.ts
import { isbn13, kdcAx, addInfo, toBook, pick } from '../supabase/functions/api/books.ts';
const eq=(n:string,a:unknown,b:unknown)=>{const ok=JSON.stringify(a)===JSON.stringify(b);console.log((ok?'PASS ':'FAIL ')+n+(ok?'':' — '+JSON.stringify(a)));if(!ok)Deno.exitCode=1};
eq('isbn13 정상',isbn13('978-89-364-5683-8'),null===isbn13('9788936456838')?null:isbn13('9788936456838'));
eq('isbn10→13',isbn13('0-306-40615-2'),'9780306406157');
eq('체크 숫자 틀림',isbn13('9788936433674'),null);
eq('KDC 문학',kdcAx('813.7'),0); eq('KDC 철학',kdcAx('199.1'),1); eq('KDC 사회',kdcAx('325.04'),2); eq('KDC 역사',kdcAx('911.05'),3);
eq('KDC 과학',kdcAx('440'),4); eq('KDC 컴퓨터',kdcAx('004.73'),4); eq('KDC 총류',kdcAx('030'),-1); eq('KDC 건축',kdcAx('540.9'),5); eq('KDC 예술',kdcAx('670'),5); eq('빈 값',kdcAx(''),-1);
eq('부가기호 청소년 문학',addInfo('43810'),{reader:'4',form:'3',ax:0,ref:false,comic:false,kid:false,teen:true});
eq('부가기호 만화',addInfo('07910')!.comic,true); eq('부가기호 참고서',addInfo('53410')!.ref,true);
const b=toBook({TITLE:'순례주택',AUTHOR:'유은실 지음',EA_ISBN:'9788936433673',EA_ADD_CODE:'43810',KDC:'',PUBLISHER:'비룡소',TITLE_URL:'http://x/y.jpg'});
eq('KDC 없으면 부가기호로',[b.main,b.from,b.author,b.cover,b.teen],[0,'add','유은실','https://x/y.jpg',true]);
eq('제목 고르기',pick([{TITLE:'코스모스 해설'},{TITLE:'코스모스',AUTHOR:'칼 세이건',KDC:'443'},{TITLE:'코스모스',KDC:''}],'코스모스','칼 세이건')!.KDC,'443');
eq('다른 책은 고르지 않음',pick([{TITLE:'코스모스 해설'}],'코스모스'),null);

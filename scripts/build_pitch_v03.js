// Reproducible Clinical Compass grant-preview deck. Run: node scripts/build_pitch_v03.js
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const OUTPUT = path.join(ROOT, 'docs/presentation/Clinical_Compass_v03_Grant_Preview.pptx');
const currentMetrics = path.join(ROOT, 'evaluation/results/gigachat_v1_2_medical_rc1/metrics.json');
const archivedMetrics = path.join(ROOT, 'evaluation/results/gigachat_v1_2.json');
const reviewReference = path.join(ROOT, 'docs/presentation/medical_review_metrics_reference.json');
let metrics, label, provenance;
if (fs.existsSync(currentMetrics)) {
  metrics = JSON.parse(fs.readFileSync(currentMetrics, 'utf8'));
  label = 'После медицинской сверки';
  provenance = 'Источник: evaluation/results/gigachat_v1_2_medical_rc1/metrics.json';
} else if (fs.existsSync(reviewReference)) {
  metrics = JSON.parse(fs.readFileSync(reviewReference, 'utf8'));
  label = 'После медицинской сверки · лог';
  provenance = 'Источник: лог медицинской сверки · требуется сверка JSON с текущим main';
} else {
  metrics = JSON.parse(fs.readFileSync(archivedMetrics, 'utf8'));
  label = 'Архивный прогон · до сверки';
  provenance = 'Источник: evaluation/results/gigachat_v1_2.json · обновить до финальной защиты';
}
const p = new pptxgen();
p.layout = 'LAYOUT_WIDE'; p.author = 'Clinical Compass team'; p.subject='Clinical Compass v0.3: grant preview'; p.lang='ru-RU';
p.theme = {headFontFace:'Aptos Display',bodyFontFace:'Aptos',lang:'ru-RU'};
const C = {navy:'17212B', teal:'0D5966', turquoise:'00BDB9', darkteal:'063A43', white:'FFFFFF', bg:'F6F7F9', muted:'50616F', line:'DEE4E9', soft:'E3EEF0', danger:'A42619'};
const SW=13.333, SH=7.5;
function bg(slide, n, section) {
 slide.background = {color:C.bg};
 slide.addShape(p.ShapeType.rect,{x:0,y:0,w:SW,h:.095,fill:{color:C.turquoise},line:{color:C.turquoise}});
 slide.addText('CLINICAL COMPASS', {x:.58,y:.28,w:3,h:.27,fontFace:'Aptos',fontSize:11,bold:true,color:C.teal,charSpacing:2});
 slide.addText(section.toUpperCase(),{x:8.75,y:.28,w:3.95,h:.27,fontSize:10,color:C.muted,align:'right'});
 slide.addShape(p.ShapeType.line,{x:.58,y:7.06,w:12.14,h:0,line:{color:C.line,width:1}});
 slide.addText('Рабочий прототип · демо-данные · не клиническая валидация',{x:.58,y:7.11,w:10.8,h:.18,fontSize:8.2,color:C.muted});
 slide.addText(String(n).padStart(2,'0'),{x:12.12,y:7.11,w:.57,h:.18,fontSize:9,color:C.muted,align:'right'});
}
function title(s, a, b) {
 s.addText(a,{x:.58,y:.79,w:12.15,h:.69,fontSize:31.5,bold:true,color:C.navy,margin:0,breakLine:false});
 if(b)s.addText(b,{x:.6,y:1.49,w:12.1,h:.41,fontSize:15,color:C.muted,margin:0});
}
function txt(s,t,x,y,w,h,fs=17,options={}) {s.addText(t,{x,y,w,h,fontSize:fs,color:C.navy,margin:0,breakLine:false,vertAlign:'mid',...options});}
function pill(s,t,x,y,w){s.addShape(p.ShapeType.roundRect,{x,y,w,h:.43,rectRadius:.09,line:{color:C.line},fill:{color:C.white}});txt(s,t,x+.13,y+.02,w-.26,.36,12.5,{bold:true});}
function block(s,x,y,w,h,head,body,accent=false){
 s.addShape(p.ShapeType.roundRect,{x,y,w,h,rectRadius:.13,fill:{color:accent?C.soft:C.white},line:{color:accent?C.turquoise:C.line,width:1}});
 txt(s,head,x+.22,y+.19,w-.44,.46,18,{bold:true,color:C.teal});
 txt(s,body,x+.22,y+.75,w-.44,h-.84,14.8,{color:C.muted,breakLine:false,vertAlign:'top'});
}
function photo(s,file,x,y,w,h){
 const full=path.join(ROOT,file);
 if (!fs.existsSync(full))return;
 s.addImage({path:full,x,y,w,h,sizingCrop:true});
 s.addShape(p.ShapeType.rect,{x,y,w,h,line:{color:C.line,width:1},fill:{color:C.white,transparency:100}});
}
// 1: architecture
{
 const s=p.addSlide();bg(s,1,'архитектура');title(s,'ИИ понимает текст, правила определяют действия','Чёткое разделение вероятностного извлечения и медицинской маршрутизации');
 const parts=[['Пациент','Flutter'],['Backend','FastAPI'],['AI-извлечение','GigaChat'],['Patient State','PostgreSQL'],['Правила','Rule Engine'],['Результат','Врач / пациент']];
 const y=2.63,w=1.76,gap=.3,start=.56;
 for(let i=0;i<parts.length;i++){
  let x=start+i*(w+gap);
  s.addShape(p.ShapeType.roundRect,{x,y,w,h:1.17,rectRadius:.15,fill:{color:i===2?C.soft:C.white},line:{color:i===2?C.turquoise:C.line,width:1.5}});
  txt(s,parts[i][0],x+.1,y+.2,w-.2,.33,16,{align:'center',bold:true});
  txt(s,parts[i][1],x+.1,y+.65,w-.2,.28,11.5,{align:'center',color:C.muted});
  if(i<parts.length-1) txt(s,'›',x+w+.055,y+.32,.17,.47,26,{color:C.teal,bold:true,align:'center'});
 }
 block(s,.59,4.38,5.84,1.55,'Что делает модель','Симптомы · приём препаратов · сигналы риска · упоминания анализов');
 block(s,6.61,4.38,6.10,1.55,'Чего модель НЕ делает','Не ставит диагноз, не назначает лечение, не выбирает срочность');
 txt(s,'При сбое AI ограниченный словарь проверяет часть красных флагов. Врач принимает окончательное решение.',.61,6.15,12,.55,13,{color:C.muted});
}
// 2: features
{
 const s=p.addSlide();bg(s,2,'функции пациента');title(s,'Пациент: наблюдение между визитами','Минимум действий, понятная история и мягкое вовлечение');
 photo(s,'docs/screenshots/patient-home.jpg',.58,2.12,4.07,4.65);
 block(s,4.94,2.14,3.73,1.33,'Дневник состояния','Симптомы и сообщения врачу');
 block(s,8.89,2.14,3.77,1.33,'Лечение','Отметки приёма препарата');
 block(s,4.94,3.73,3.73,1.33,'Опросники','GAD-7 и PHQ-9 по графику');
 block(s,8.89,3.73,3.77,1.33,'Безопасность','Экстренные действия по правилам');
 block(s,4.94,5.32,7.72,1.26,'Новое в v0.3 · «Мой прогресс»','Число дней с записями за неделю — без оценки «хорошего» или «плохого» состояния',true);
 txt(s,'Скриншот — предыдущая версия интерфейса. Блок прогресса внедрён в код и требует новой съёмки.',4.95,6.76,7.72,.22,9,{color:C.muted});
}
// 3: doctor
{
 const s=p.addSlide();bg(s,3,'интерфейс врача');title(s,'Врач видит, кому сейчас нужно внимание','Понятная очередь и объяснение причин каждого алерта');
 photo(s,'docs/screenshots/doctor-queue.jpg',.58,2.10,7.3,4.66);
 block(s,8.1,2.17,4.58,1.3,'01 · Рабочая очередь','Срочные события закрепляются до принятия');
 block(s,8.1,3.66,4.58,1.3,'02 · Карточка пациента','Динамика, сообщения, отметки и история');
 block(s,8.1,5.15,4.58,1.3,'03 · «Почему?»','Правило, версия, источник и исходные факты');
}
// 4: metrics
{
 const s=p.addSlide();bg(s,4,'качество извлечения');title(s,'Мы измеряем извлечение фактов, а не диагноз','Эталонные сущности сравниваются с ответом языковой модели');
 pill(s,`${metrics.dataset.messages} сообщений`,.62,2.08,2.35);
 pill(s,`${metrics.dataset.gold_entities} размеченных фактов`,3.13,2.08,3.25);
 pill(s,label,6.58,2.08,4.11);
 const vals=[['Precision',metrics.overall.precision],['Recall',metrics.overall.recall],['F1',metrics.overall.f1]];
 vals.forEach(([name,v],i)=>{
   const y=2.88+i*1.03;
   txt(s,name,.64,y,2,.40,18,{bold:true});
   s.addShape(p.ShapeType.roundRect,{x:2.58,y:y+.06,w:7.99,h:.31,rectRadius:.07,fill:{color:'E8EFF1'},line:{color:'E8EFF1'}});
   s.addShape(p.ShapeType.roundRect,{x:2.58,y:y+.06,w:7.99*v,h:.31,rectRadius:.07,fill:{color:C.turquoise},line:{color:C.turquoise}});
   txt(s,`${(v*100).toFixed(1).replace('.',',')}%`,10.79,y-.01,1.45,.48,22,{bold:true,color:C.teal,align:'right'});
 });
 txt(s,provenance,.64,6.14,11.87,.35,11,{color:C.muted});
 txt(s,'8/8 выбранных критических сценариев — отдельная техническая проверка, не 100% безопасность.',.64,6.55,12,.32,12,{bold:true,color:C.danger});
}
// 5: roadmap
{
 const s=p.addSlide();bg(s,5,'следующий этап');title(s,'От работающего MVP — к проверенному продукту','Пошаговая реализация без обещаний клинической эффективности до испытаний');
 block(s,.6,2.07,5.94,1.64,'01 · Качество и безопасность','Расширить выборку, оценить пропуски критических случаев, утвердить тексты с врачами');
 block(s,6.75,2.07,5.94,1.64,'02 · Пилот','Небольшая группа пациентов и специалистов, реальные показатели удобства и нагрузки');
 block(s,.6,4.01,5.94,1.64,'03 · Интеграция с МИС','Сначала доступ к API и тестовый контур, затем согласованный обмен с клиникой');
 block(s,6.75,4.01,5.94,1.64,'04 · Вовлечение и UX','Недельный прогресс, проще интерфейс, новые анимации и проверка доступности',true);
 txt(s,'ЕМИАС и 1С в текущем проекте: демонстрационный контур, не подтверждённая промышленная интеграция.',.62,6.3,12.0,.51,12,{color:C.muted});
}
fs.mkdirSync(path.dirname(OUTPUT),{recursive:true});
p.writeFile({fileName:OUTPUT}).then(()=>{console.log('Generated',OUTPUT);console.log(provenance)});

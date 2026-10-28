const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const pptx = new pptxgen(); pptx.layout='LAYOUT_WIDE'; pptx.author='智学研途 StudyPath AI'; pptx.subject='智慧教育作品汇报'; pptx.title='智学研途——AI个性化学习平台'; pptx.company='StudyPath AI'; pptx.lang='zh-CN';
pptx.theme={headFontFace:'Microsoft YaHei',bodyFontFace:'Microsoft YaHei',lang:'zh-CN'};
const C={navy:'24174A',purple:'7047E8',violet:'9B79F7',lav:'F1ECFF',bg:'F7F5FC',ink:'302A42',muted:'77718C',line:'E7E1F2',white:'FFFFFF',teal:'35B7A5',mint:'E7F7F3',gold:'FFB84D',pink:'F4E8FF'};
const W=13.333,H=7.5;
function rect(s,x,y,w,h,fill,rad=0.16,line=fill){s.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:rad,line:{color:line,transparency:line===fill?100:0,width:0.7},fill:{color:fill},radius:rad});}
function txt(s,t,x,y,w,h,size=16,color=C.ink,bold=false,opts={}){s.addText(t,{x,y,w,h,fontFace:'Microsoft YaHei',fontSize:size,color,bold,margin:0,breakLine:false,fit:'shrink',valign:'mid',...opts});}
function base(title,kicker,num){let s=pptx.addSlide();s.background={color:C.bg};s.addShape(pptx.ShapeType.ellipse,{x:10.5,y:-1.9,w:4.4,h:4.4,line:{color:C.bg,transparency:100},fill:{color:'EEE8FF',transparency:25}});txt(s,kicker.toUpperCase(),0.65,0.4,5,0.25,9,C.purple,true,{charSpacing:1.4});txt(s,title,0.65,0.78,11.9,0.55,27,C.navy,true);txt(s,String(num).padStart(2,'0'),12.15,7.05,0.5,0.2,9,C.muted,true,{align:'right'});txt(s,'智学研途  ·  STUDYPATH AI',0.65,7.03,3.2,0.2,8,C.muted);return s;}
function pill(s,label,x,y,w,color=C.purple){rect(s,x,y,w,0.34,color,0.1);txt(s,label,x+0.1,y+0.02,w-0.2,0.28,10,C.white,true,{align:'center'});}
function card(s,x,y,w,h,head,body,accent=C.purple){rect(s,x,y,w,h,C.white,0.13,C.line);s.addShape(pptx.ShapeType.ellipse,{x:x+0.22,y:y+0.2,w:0.32,h:0.32,line:{color:accent,transparency:100},fill:{color:accent}});txt(s,head,x+0.68,y+0.18,w-0.9,0.34,15,C.navy,true);txt(s,body,x+0.24,y+0.68,w-0.48,h-0.84,11,C.muted,false,{valign:'top',breakLine:false,paraSpaceAfterPt:5});}
function line(s,x1,y1,x2,y2,color='D7CFF0',width=1.6){s.addShape(pptx.ShapeType.line,{x:x1,y:y1,w:x2-x1,h:y2-y1,line:{color,width,beginArrowType:'none',endArrowType:'triangle'}});}
// 1 cover
{
 let s=pptx.addSlide();s.background={color:C.navy};
 s.addShape(pptx.ShapeType.ellipse,{x:8.5,y:-1.3,w:6.2,h:6.2,line:{color:C.navy,transparency:100},fill:{color:'5637A6',transparency:22}});
 s.addShape(pptx.ShapeType.ellipse,{x:9.9,y:3.4,w:4.8,h:4.8,line:{color:C.navy,transparency:100},fill:{color:'3AAFA0',transparency:70}});
 pill(s,'智慧教育与科普创作',0.8,0.85,1.9,C.purple);
 txt(s,'智学研途',0.8,1.65,6.6,0.9,42,C.white,true);
 txt(s,'AI 个性化学习平台',0.82,2.62,7.4,0.58,27,'D9CEFF',true);
 txt(s,'让每一次提问都能回到资料，让每一道错题都成为进步的起点。',0.84,3.46,7.4,0.55,16,'E4DFF3',false);
 const tags=[['RAG资料问答',0.84,4.55,1.55],['错题举一反三',2.55,4.55,1.75],['知识图谱',4.48,4.55,1.3],['用户画像与计划',5.94,4.55,1.9]];
 tags.forEach(([t,x,y,w])=>{s.addShape(pptx.ShapeType.roundRect,{x,y,w,h:0.42,rectRadius:0.1,line:{color:'8271B4',width:0.8},fill:{color:'34255F'}});txt(s,t,x+0.08,y+0.03,w-0.16,0.32,10,C.white,true,{align:'center'});});
 // motif nodes
 [[10.55,2.15,.95,'资料'],[11.75,3.0,.72,'理解'],[10.45,4.0,.82,'练习'],[9.35,3.1,.72,'画像'],[11.45,5.0,.78,'成长']].forEach(([x,y,d,t],i)=>{s.addShape(pptx.ShapeType.ellipse,{x,y,w:d,h:d,line:{color:'FFFFFF',transparency:65,width:1},fill:{color:i===2?C.teal:C.purple,transparency:8}});txt(s,t,x,y+d*.34,d,d*.3,12,C.white,true,{align:'center'});});
 line(s,11.25,2.8,11.78,3.12,'A99ADC',1.4);line(s,11.9,3.7,11.15,4.15,'A99ADC',1.4);line(s,10.6,4.1,10.1,3.55,'A99ADC',1.4);line(s,11.25,4.8,11.65,5.02,'A99ADC',1.4);
 txt(s,'作品汇报',0.84,6.73,2,0.22,10,'B6A9DE');txt(s,'StudyPath AI',10.9,6.73,1.55,0.22,10,'D4C9F2',false,{align:'right'});
}
// 2 pain points
{
 let s=base('从“能回答”走向“会学习”','学习痛点',2);
 txt(s,'学习工具很多，但学生仍常遇到四个断点',0.68,1.48,7,0.34,16,C.muted);
 const data=[['资料难找','课程文件分散，定位知识点耗时。',C.purple],['答案难核对','通用回答不一定贴合课程资料，来源不清晰。',C.teal],['错题被搁置','做完只看对错，缺少变式练习检验迁移。',C.gold],['计划不适配','学习进度与薄弱点不同，统一安排不够精准。','9071D6']];
 data.forEach((d,i)=>{let x=0.7+(i%2)*6.0,y=2.05+Math.floor(i/2)*1.75;card(s,x,y,5.55,1.42,d[0],d[1],d[2]);});
 rect(s,0.7,5.75,11.95,0.78,C.lav,0.16);txt(s,'作品目标',0.98,5.94,1.0,0.3,12,C.purple,true);txt(s,'把资料、答疑、错题、知识结构与个人学习计划连成一个持续改进的学习过程。',2.0,5.91,10.1,0.36,15,C.navy,true);
}
// 3 product loop
{
 let s=base('一条闭环：识别学情，持续改进','产品方案',3);
 const nodes=[['上传资料','个人课程内容'],['检索问答','资料依据 / 拓展'],['练习检测','掌握情况反馈'],['错题变式','举一反三训练'],['画像计划','推荐课程与节奏']];
 const xs=[0.75,3.15,5.55,7.95,10.35];
 nodes.forEach((n,i)=>{let x=xs[i];rect(s,x,2.45,2.05,1.25,i===3?C.pink:C.white,0.18,i===3?'E5D4FF':C.line);s.addShape(pptx.ShapeType.ellipse,{x:x+0.15,y:2.62,w:0.35,h:0.35,line:{color:C.purple,transparency:100},fill:{color:C.purple}});txt(s,String(i+1),x+0.15,2.67,0.35,0.18,10,C.white,true,{align:'center'});txt(s,n[0],x+0.58,2.6,1.32,0.3,14,C.navy,true);txt(s,n[1],x+0.18,3.13,1.7,0.28,10,C.muted,false,{align:'center'});if(i<4)line(s,x+2.08,3.06,xs[i+1]-0.12,3.06,'B9A7E9',1.8);});
 rect(s,1.05,4.55,11.2,1.05,C.white,0.16,C.line);txt(s,'核心逻辑',1.35,4.78,1.2,0.28,12,C.purple,true);txt(s,'学习数据 → 发现薄弱点 → 安排适合的课程与练习 → 用新的学习结果更新画像',2.75,4.72,9.1,0.43,15,C.navy,true,{align:'center'});
 txt(s,'让系统的每次推荐都能服务于下一步学习，而不只停留在一次问答。',2.3,6.12,8.8,0.3,12,C.muted,false,{align:'center'});
}
// 4 RAG
{
 let s=base('RAG：回答围绕用户自己的资料','核心能力 01 · 智能问答',4);
 const img='D:/Personal/Temp/codex-clipboard-ea76d17f-427d-4470-87f8-b3eb6cd9fd10.png';
 rect(s,0.7,1.6,6.2,4.75,C.white,0.16,C.line);s.addImage({path:img,x:0.82,y:1.73,w:5.96,h:3.47,transparency:0});txt(s,'问答界面：资料库模式可查看回答引用的原文与页码',1.0,5.43,5.6,0.4,10,C.muted,false,{align:'center'});
 const steps=[['01','用户上传','PDF / DOCX / TXT / Markdown'],['02','解析与检索','分块、向量化、召回并重排'],['03','生成回答','结合证据输出并标注来源']];
 steps.forEach((a,i)=>{let y=1.75+i*1.25;rect(s,7.35,y,5.25,0.94,C.white,0.14,C.line);pill(s,a[0],7.58,y+0.29,0.48,i===1?C.teal:C.purple);txt(s,a[1],8.28,y+0.13,1.6,0.27,14,C.navy,true);txt(s,a[2],8.28,y+0.48,3.9,0.24,10,C.muted);});
 rect(s,7.35,5.72,5.25,0.63,C.mint,0.12);txt(s,'另一模式：大模型问答，用于知识解释与拓展',7.58,5.87,4.78,0.3,11,'18776B',true);
}
// 5 mistake practice
{
 let s=base('错题不止订正：继续训练知识迁移','核心能力 02 · 重点展示',5);
 const img='D:/Personal/Temp/codex-clipboard-c41a5e28-ebf0-4d76-8792-d33363fa43d7.png';
 rect(s,0.65,1.55,7.05,4.95,C.white,0.16,C.line);s.addImage({path:img,x:0.76,y:1.68,w:6.82,h:3.96});txt(s,'举一反三练习页：围绕同一知识点生成不同情境的题目',1.0,5.88,6.4,0.34,10,C.muted,false,{align:'center'});
 txt(s,'从一道错题，走完四步',8.05,1.78,4.5,0.42,20,C.navy,true);
 const flow=[['错题归集','记录错题与所属课程'],['定位知识点','明确问题对应的概念或方法'],['生成变式','改变情境与问法，保留考查目标'],['反馈巩固','完成练习，暴露仍需加强之处']];
 flow.forEach((a,i)=>{let y=2.55+i*0.86;s.addShape(pptx.ShapeType.ellipse,{x:8.1,y:y+0.05,w:0.28,h:0.28,line:{color:C.purple,transparency:100},fill:{color:i===2?C.teal:C.purple}});txt(s,a[0],8.58,y,1.4,0.28,13,C.navy,true);txt(s,a[1],9.98,y,2.5,0.34,10,C.muted);if(i<3)s.addShape(pptx.ShapeType.line,{x:8.24,y:y+0.36,w:0,h:0.39,line:{color:'CFC4EA',width:1.2}});});
 rect(s,8.05,6.08,4.55,0.48,C.lav,0.11);txt(s,'重点：练新情境，检验是否真正掌握',8.2,6.18,4.25,0.25,11,C.purple,true,{align:'center'});
}
// 6 graph and personalization
{
 let s=base('知识图谱 × 用户画像：让学习建议有依据','核心能力 03 · 个性化学习',6);
 txt(s,'知识图谱把“知识点之间的关系”可视化',0.72,1.5,6.3,0.3,14,C.muted);
 const pts=[[2.45,2.5,'操作系统',0.95,C.purple],[1.1,3.65,'进程管理',0.8,C.teal],[3.8,3.65,'内存管理',0.8,C.teal],[2.45,5.0,'虚拟内存',0.78,'9274E8'],[5.2,2.8,'文件系统',0.78,'9274E8'],[5.2,4.55,'页面置换',0.78,'9274E8']];
 [[2.9,3.25,1.7,3.65],[3.25,3.2,4.05,3.65],[2.75,4.1,2.75,5.0],[3.4,2.95,5.15,2.95],[4.45,3.8,5.15,4.55],[2.0,4.3,2.6,5.0]].forEach(([x1,y1,x2,y2])=>line(s,x1,y1,x2,y2,'CFC5E8',1.3));
 pts.forEach(([x,y,l,d,c])=>{s.addShape(pptx.ShapeType.ellipse,{x:x-d/2,y:y-d/2,w:d,h:d,line:{color:C.white,width:1.5},fill:{color:c}});txt(s,l,x-d/2+0.04,y-0.14,d-0.08,0.28,10,C.white,true,{align:'center'});});
 rect(s,6.6,1.7,5.95,4.95,C.white,0.16,C.line);
 txt(s,'用户画像驱动个性化服务',6.95,2.0,5.1,0.4,19,C.navy,true);
 const rows=[['学习记录','进度、测验表现、错题'],['学情分析','识别薄弱知识与待复习内容'],['学习计划','结合课程关系与掌握情况安排任务'],['持续更新','新练习结果反馈到后续建议']];
 rows.forEach((a,i)=>{let y=2.85+i*0.8;rect(s,6.95,y,5.15,0.59,i===2?C.lav:C.bg,0.11,i===2?C.lav:C.bg);txt(s,a[0],7.16,y+0.12,1.15,0.3,12,C.purple,true);txt(s,a[1],8.45,y+0.12,3.45,0.3,11,C.ink);});
 txt(s,'从“推荐内容”进一步走向“适合这个学生的学习路径”。',7.03,6.15,5.0,0.32,11,C.muted,false,{align:'center'});
}
const out=path.resolve('docs/prefix_6.pptx'); (async()=>{ await pptx.writeFile({fileName:out}); })();

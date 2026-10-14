import fs from 'node:fs';
import {generateManimScript} from './vendor/Manim-Motion/services/web/src/export/manim.js';
const facts=JSON.parse(fs.readFileSync('facts.json'));
const values=['base','r1','fullnight'].map(k=>facts.test[k].subject_mf1.point);
const colors=['#B2ABFF','#51D9E8','#FFCC73'];
const objects=[];
for(let i=0;i<3;i++){
  const h=values[i]*390,x=320+i*320;
  objects.push({id:'bar'+i,type:'rectangle',x,y:580-h/2,width:160,height:h,fill:colors[i],stroke:colors[i],strokeWidth:2,opacity:1,rotation:0,enterTime:0,enterAnim:'fade'});
  objects.push({id:'label'+i,type:'text',x,y:620,width:285,height:52,content:['Base','R1','Full-night'][i]+' '+(values[i]*100).toFixed(2)+'%',fontFamily:'Monospace',fontSize:30,fill:'#EFF6FF',stroke:'#EFF6FF',strokeWidth:1,opacity:1,rotation:0,enterTime:0,enterAnim:'fade'});
}
objects.push({id:'title',type:'text',x:640,y:75,width:1100,height:65,content:'Archived test: mean-subject macro-F1',fontFamily:'Monospace',fontSize:32,fill:'#EFF6FF',stroke:'#EFF6FF',strokeWidth:1,opacity:1,rotation:0,enterTime:0,enterAnim:'fade'});
const project={name:'Sleep Stage Results - measured aggregate values',sceneDuration:3,stage:{width:1280,height:720,backgroundColor:'#081321'},objects,groups:[],tracks:[{id:'main',clips:[]}],assets:[]};
const code=generateManimScript(project);
if(!code.includes('Base 56.42%')||code.includes('Text("Text"'))throw Error('Exported evidence labels missing');
fs.writeFileSync('manim-motion-project-verified.json',JSON.stringify(project,null,2)+'\n',{flag:'wx'});
fs.writeFileSync('motion-export-verified.py',code+'\n',{flag:'wx'});
console.log('Actual Manim-Motion exporter generated motion-export-verified.py and verified editable project JSON.');

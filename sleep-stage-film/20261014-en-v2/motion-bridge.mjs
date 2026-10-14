import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {generateManimScript} from '../20261013-v1/vendor/Manim-Motion/services/web/src/export/manim.js';
const root=path.dirname(fileURLToPath(import.meta.url)),facts=JSON.parse(fs.readFileSync(path.join(root,'facts.json')));
const colors=['#B9ADFF','#58DFEE','#FFD08A'],labels=['Base','R1','Full-night'];
const objects=[];
for(let i=0;i<3;i++){
  const value=facts.test[['base','r1','fullnight'][i]].subject_mf1.point,h=value*430,x=310+i*330;
  objects.push({id:'bar'+i,type:'rectangle',x,y:580-h/2,width:150,height:h,fill:colors[i],stroke:colors[i],strokeWidth:1,opacity:1,rotation:0,enterTime:0,enterAnim:'fade'});
  objects.push({id:'label'+i,type:'text',x,y:620,width:285,height:52,content:labels[i]+' '+(100*value).toFixed(2)+'%',fontFamily:'Monospace',fontSize:27,fill:'#F1F5FC',stroke:'#F1F5FC',strokeWidth:1,opacity:1,rotation:0,enterTime:0,enterAnim:'fade'});
}
for(const [id,y,content,size] of [['title',75,'Archived subject-mean macro-F1',30],['caveat',140,'R1: post-hoc and transductive. Not paper replication.',19]])objects.push({id,type:'text',x:640,y,width:1150,height:45,content,fontFamily:'Monospace',fontSize:size,fill:'#ABB9CC',stroke:'#ABB9CC',strokeWidth:1,opacity:1,rotation:0,enterTime:0,enterAnim:'fade'});
const project={name:'English Sleep Stage Evidence',sceneDuration:6,stage:{width:1280,height:720,backgroundColor:'#080F1C'},objects,groups:[],tracks:[{id:'main',clips:[]}],assets:[]};
const code=generateManimScript(project);
for(const s of ['Base 56.42%','R1 74.86%','Full-night 71.84%','post-hoc'])if(!code.includes(s))throw Error('Exporter missing label '+s);
fs.writeFileSync(path.join(root,'manim-motion-project.json'),JSON.stringify(project,null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(root,'motion-export.py'),code+'\n',{flag:'wx'});
console.log('Manim-Motion actual exporter passed: editable English project and renderable Python.');

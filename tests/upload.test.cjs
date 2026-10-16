const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function setup() {
  const elements = {};
  for (const id of ['upload-form','upload-file','drop-zone','choose-file','upload-status']) {
    elements[id] = {listeners:{},files:[],value:'',hidden:true,disabled:false,textContent:'',
      classList:{add(){},remove(){}},contains(){return false},setAttribute(){},
      addEventListener(type,fn){this.listeners[type]=fn},click(){this.clicked=true}};
  }
  let submissions=0;
  elements['upload-form'].requestSubmit = () => {
    submissions++;
    elements['upload-form'].listeners.submit();
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../labtranslator/static/upload.js'),'utf8'),{
    document:{getElementById:id=>elements[id],addEventListener(){}}
  });
  return {elements,count:()=>submissions};
}
test('picker button opens the real input and selection submits the PDF',()=>{
  const {elements:e,count}=setup();
  e['choose-file'].listeners.click();
  assert.equal(e['upload-file'].clicked,true);
  e['upload-file'].files=[{name:'report.PDF',size:100}];
  e['upload-file'].listeners.change();
  assert.equal(count(),1);
  assert.equal(e['choose-file'].disabled,true);
});
test('drop attaches the file and submits exactly once',()=>{
  const {elements:e,count}=setup();
  const files=[{name:'report.pdf',size:100}];
  let prevented=false;
  e['drop-zone'].listeners.drop({preventDefault(){prevented=true},dataTransfer:{files}});
  assert.equal(prevented,true);
  assert.equal(e['upload-file'].files,files);
  assert.equal(count(),1);
  e['upload-file'].listeners.change();
  assert.equal(count(),1);
});
for(const files of [[{name:'report.csv',size:10}],[{name:'big.pdf',size:21*1024*1024}],[],[{name:'a.pdf',size:1},{name:'b.pdf',size:1}]]) {
  test('rejects invalid, oversized or multiple dropped files: '+JSON.stringify(files),()=>{
    const {elements:e,count}=setup();
    e['drop-zone'].listeners.drop({preventDefault(){},dataTransfer:{files}});
    assert.equal(count(),0);
    assert.ok(e['upload-status'].textContent);
    assert.equal(e['choose-file'].disabled,false);
  });
}

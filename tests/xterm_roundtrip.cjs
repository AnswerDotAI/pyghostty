const {Terminal} = require(process.env.PYGHOSTTY_XTERM_MODULE);
const assert = require('node:assert/strict');
const cases = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const write = (t,b) => new Promise(resolve=>t.write(Buffer.from(b,'base64'),resolve));
function state(t) {
 const b=t.buffer.active, lines=[];
 for(let y=0;y<b.length;y++) {
   const line=b.getLine(y),cells=[];
   for(let x=0;x<20;x++) {
     const c=line.getCell(x);
     cells.push([c.getChars().trimEnd(),c.getWidth(),c.getFgColor(),c.getBgColor(),c.isBold(),c.isItalic(),c.isUnderline()]);
   }
   lines.push([line.isWrapped,cells]);
 }
 return {cursor:[b.cursorX,b.cursorY],base:b.baseY,type:b.type,lines};
}
(async()=>{
 for(const c of cases) {
  const a=new Terminal({cols:20,rows:5,allowProposedApi:true}),b=new Terminal({cols:20,rows:5,allowProposedApi:true});
  await write(a,c.data);await write(b,c.snapshot);
  assert.deepEqual(state(b),state(a),c.label+' snapshot');
  await write(a,c.suffix);await write(b,c.suffix);
  assert.deepEqual(state(b),state(a),c.label+' continuation');
  a.dispose();b.dispose();console.log('PASS '+c.label);
 }
})().catch(e=>{console.error(e);process.exitCode=1});

const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../professional.js'),'utf8');
const login=source.slice(source.indexOf('async function login()'),source.indexOf('async function logout()'));
test('login preserves password exactly and shows rejected login persistently',async()=>{
  const hint={textContent:'',setAttribute(name,value){this[name]=value;}};
  let sent;
  const context=vm.createContext({$:selector=>selector==='#f_password'?{value:' fixture password '}:hint,
    val:()=> 'fixture@example.invalid',api:async(_path,body)=>{sent=body;throw Error('Credenciais inválidas.');},toast(){}});
  vm.runInContext(login,context);await context.login();
  assert.equal(sent.password,' fixture password ');
  assert.equal(hint.textContent,'Credenciais inválidas.');assert.equal(hint.role,'alert');
});

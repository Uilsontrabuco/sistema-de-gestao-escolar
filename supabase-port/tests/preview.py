"""Prévia isolada de QA. Sem SDK remoto, credenciais ou acesso ao Supabase."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
ledger=json.loads((ROOT/'private/teaching-cost-2027.json').read_text(encoding='utf-8'))
rooms=[]
for i,r in enumerate(ledger['classes']):
    serie,turma=r['class_name'].rsplit(' ',1)
    rooms.append(dict(id=f'id-{i}',serie=serie,turma=turma,capacidade=30,matriculados=10))
mock='''<script>
const testProfile={id:'test-user',nome:'QA isolado',email:'qa@example.invalid',role:'master',ativo:true};
const testClient={auth:{getSession:async()=>({data:{session:{user:{id:'test-user'}}}}),getUser:async()=>({data:{user:{id:'test-user'}}}),signOut:async()=>({})},from(table){const q={select(){return q},eq(){return q},order(){return q},limit(){return q},range:async()=>({data:await fetch('/fixture-rooms').then(r=>r.json())}),single:async()=>({data:testProfile}),maybeSingle:async()=>table==='teaching_cost_snapshots'?{data:{version:1,payload:await fetch('/fixture-ledger').then(r=>r.json())}}:{data:null}};return q;}};
window.seven7Supabase=testClient;
window.SEVEN7_CONFIG={supabaseUrl:'',supabaseAnonKey:''};
window.initSeven7Supabase=()=>false;
</script>'''
html=(ROOT/'index.html').read_text(encoding='utf-8')
html=re.sub(r'<script[^>]*src="https://[^>]*></script>','',html)
html=re.sub(r'<script>\s*window.SEVEN7_CONFIG.*?</script>',lambda _:mock,html,count=1,flags=re.S)
html=html.replace('<body>','<body><div style="background:#ffe181;padding:8px">AMBIENTE DE TESTE ISOLADO — SEM DADOS OPERACIONAIS</div>')
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/':data=html.encode();kind='text/html'
        elif self.path=='/fixture-ledger':data=json.dumps(ledger).encode();kind='application/json'
        elif self.path=='/fixture-rooms':data=json.dumps(rooms).encode();kind='application/json'
        elif self.path in ['/finance-2027.js','/finance-2027-ui.js']:data=(ROOT/self.path[1:]).read_bytes();kind='text/javascript'
        elif self.path=='/favicon.ico':self.send_response(204);self.end_headers();return
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
if __name__=='__main__':
    print('QA somente local: http://127.0.0.1:8878',flush=True)
    HTTPServer(('127.0.0.1',8878),Handler).serve_forever()

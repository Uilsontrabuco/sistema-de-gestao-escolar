"""Entrada Vercel; usa o mesmo domínio e as mesmas validações do servidor local."""
import base64
import io
import json
import gzip
import os
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from cloud_store import CloudStore
from server import Handler, require


class CloudHandler(Handler):
    @property
    def store(self):
        if not hasattr(self, '_cloud_store'):
            self._cloud_store = CloudStore()
        return self._cloud_store

    def body(self):
        if int(self.headers.get('Content-Length', 0)) > 4 * 1024 * 1024:
            raise ValueError('Requisição excede o limite de 4 MB do serviço publicado.')
        return super().body()

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == '/admin/private-runtime':
                user = self.current()
                if not user.get('isAdmin'):
                    raise PermissionError()
                return self.binary(Path(__file__).with_name('private_runtime_import.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/auth/recovery':
                return self.binary(Path(__file__).with_name('password_recovery.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/health':
                self._health_stage = 'database'
                self.store
                self._health_stage = 'authentication'
                auth = self.store.auth_request('admin/users?page=1&per_page=1')
                if not isinstance(auth.get('users'), list):
                    raise RuntimeError('Serviço de autenticação não validado.')
                return self.respond(200, {'available':True, 'configured':True,
                    'persistence':'postgres', 'authentication':'supabase',
                    'backendRevision':'seven7-recovery-625-v1',
                    'commit':next((value for value in (
                        os.environ.get('VERCEL_GIT_COMMIT_SHA',''),
                        os.environ.get('APP_COMMIT',''),
                    ) if re.fullmatch(r'[0-9a-f]{40}', value)), None)})
            if path == '/api/events':
                try:
                    self.current()
                    _, version = self.store.state()
                    content = ('retry: 10000\nevent: changed\ndata: ' + json.dumps({'version':version}) + '\n\n').encode()
                except PermissionError:
                    content = b'event: revoked\ndata: {}\n\n'
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.send_header('Cache-Control','no-store')
                self.send_header('Content-Length',str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            if path in ('/api/teaching-load/costs','/api/financial/teaching-integration','/api/break-even/integrated'):
                require(self.current(), 'financial', 'view')
                state, version = self.store.state()
                result = self.store.documentary_costs(state['classes'])
                if path != '/api/teaching-load/costs':
                    from financial_integration import integration_snapshot
                    year = int(parse_qs(urlparse(self.path).query).get('year',[state.get('activeAcademicYear',2027)])[0])
                    result = integration_snapshot(state,result,year)
                result['state_version'] = version
                return self.respond(200,result)
            if path == '/api/logo':
                self.current()
                with self.store.db() as db:
                    row = db.execute("SELECT content FROM assets WHERE id='logo'").fetchone()
                return self.binary(bytes(row['content']), 'image/png') if row else self.respond(404, {'error':'Logo institucional ainda não fornecida.'})
            return super().do_GET()
        except PermissionError:
            return self.respond(401, {'error':'Entre com um perfil autorizado.'})
        except Exception as error:
            response = {'error':'Serviço indisponível. A base não foi substituída nem reinicializada.'}
            if path == '/api/health':
                known = {
                    'Conexão de servidor ainda não configurada.':'missing_configuration',
                    'Projeto Supabase diferente do projeto recuperado.':'unexpected_project',
                    'Conexão Postgres inválida.':'invalid_postgres_configuration',
                    'Identidade do banco não corresponde à recuperação aprovada.':'unexpected_database',
                    'Base recuperada não instalada. Inicialização automática bloqueada.':'recovery_not_installed',
                    'Schema privado exposto; inicialização bloqueada.':'private_schema_exposed',
                }
                code = known.get(str(error), 'dependency_missing' if isinstance(error,ModuleNotFoundError) else 'runtime_error')
                db_code = getattr(error,'diagnostic_code','')
                if re.fullmatch(r'postgres_(?:[A-Z0-9]{5}|connection|authentication|tenant|network|dns|timeout|format|tls|closed)',db_code):
                    code = db_code
                response.update(stage=getattr(self,'_health_stage','initialization'),code=code)
            return self.respond(503, response)

    def do_POST(self):
        path = urlparse(self.path).path
        if path in ('/api/private-runtime/preview', '/api/private-runtime/confirm'):
            try:
                origin = self.headers.get('Origin')
                if not origin or urlparse(origin).netloc != self.headers.get('Host'):
                    raise PermissionError()
                user = self.current(True)
                from private_runtime_import import process_import
                result = process_import(self.store, self.body(), user, confirm=path.endswith('/confirm'))
                return self.respond(200, result)
            except PermissionError:
                return self.respond(403, {'error':'Acesso administrativo autorizado necessário.'})
            except (ValueError, KeyError, TypeError):
                return self.respond(409, {'error':'Pacote, prévia ou dados divergentes. Nenhuma alteração aplicada.'})
            except Exception:
                return self.respond(503, {'error':'Configuração indisponível. Nenhuma alteração parcial aplicada.'})
        if path == '/api/recovery/complete':
            try:
                origin = self.headers.get('Origin')
                if not origin or urlparse(origin).netloc != self.headers.get('Host'):
                    raise PermissionError('Origem não autorizada.')
                body = self.body()
                self.store.recover_master_password(body.get('token'), body.get('password'))
                return self.respond(200, {'ok':True})
            except PermissionError:
                return self.respond(403, {'error':'Link inválido, expirado ou perfil não autorizado. Solicite outro link de recuperação.'})
            except ValueError:
                return self.respond(400, {'error':'Use uma senha com pelo menos 12 caracteres.'})
            except Exception:
                return self.respond(503, {'error':'Não foi possível concluir a recuperação. Tente novamente.'})
        # Login local já foi substituído por CloudStore.login. Cookies de produção
        # sempre Secure, sem depender de configuração adicional no painel.
        if path == '/api/migrate':
            return self.respond(403, {'error':'Migração inicial encerrada. A base recuperada está preservada.'})
        if path == '/api/logo':
            try:
                origin = self.headers.get('Origin')
                if origin and urlparse(origin).netloc != self.headers.get('Host'):
                    raise PermissionError()
                require(self.current(True), 'users', 'edit')
                from PIL import Image
                content = base64.b64decode(self.body()['content'], validate=True)
                if len(content) > 2 * 1024 * 1024:
                    raise ValueError('Logo excede 2 MB.')
                image = Image.open(io.BytesIO(content))
                image.verify()
                image = Image.open(io.BytesIO(content))
                image.thumbnail((1600,1600))
                output = io.BytesIO()
                image.save(output, 'PNG')
                with self.store.db() as db:
                    db.execute("INSERT INTO assets VALUES('logo',?) ON CONFLICT(id) DO UPDATE SET content=EXCLUDED.content", (output.getvalue(),))
                return self.respond(200, {'ok':True})
            except PermissionError:
                return self.respond(403, {'error':'Operação não autorizada.'})
            except Exception:
                return self.respond(400, {'error':'Não foi possível salvar a imagem.'})
        return super().do_POST()

    def respond(self, status, data, headers=None):
        headers = dict(headers or {})
        if 'Set-Cookie' in headers and '; Secure' not in headers['Set-Cookie']:
            headers['Set-Cookie'] += '; Secure'
        content = json.dumps(data, ensure_ascii=False).encode()
        if len(content) > 512 * 1024 and 'gzip' in self.headers.get('Accept-Encoding', ''):
            content = gzip.compress(content)
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Encoding','gzip')
            self.send_header('Vary','Accept-Encoding')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            for key,value in headers.items():
                self.send_header(key,value)
            self.send_header('Content-Length',str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        return super().respond(status, data, headers)

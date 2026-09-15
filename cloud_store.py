"""Persistência Postgres para o domínio existente; autenticação Supabase.

Não inicializa schema, não cria dados e nunca usa SQLite em produção.
Credenciais são lidas exclusivamente do ambiente do servidor.
"""
import hashlib
import json
import os
import re
import secrets
import threading
import time
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from server import Store, MODULES, allowed, fold, require

PROJECT = 'pvsdlqspxfbfeepylfxc'
SOURCE_HASH = '199b5c813e50988bbb2f6eb8e8d2771a97a9c62a117277a12678f1ae0beb20c9'
PROMOTORA = {
    'dashboard': ['view'], 'classes': ['view'],
    'enrollments': ['view', 'create', 'edit'],
    'benefits': ['view', 'create', 'edit'],
    'requests': ['view', 'create', 'edit'],
}


def configuration(environ=None):
    env = os.environ if environ is None else environ
    direct = any(name in env for name in ('SEVEN7_DATABASE_URL', 'SEVEN7_SUPABASE_SECRET_KEY', 'SEVEN7_SUPABASE_URL'))
    dsn = env.get('SEVEN7_DATABASE_URL') if direct else env.get('POSTGRES_URL') or env.get('DATABASE_URL')
    key = env.get('SEVEN7_SUPABASE_SECRET_KEY') if direct else env.get('SUPABASE_SECRET_KEY')
    if not dsn or not key:
        raise RuntimeError('Conexão de servidor ainda não configurada.')
    url = (env.get('SEVEN7_SUPABASE_URL') or f'https://{PROJECT}.supabase.co') if direct else (env.get('SUPABASE_URL') or env.get('NEXT_PUBLIC_SUPABASE_URL') or f'https://{PROJECT}.supabase.co')
    if url.rstrip('/') != f'https://{PROJECT}.supabase.co':
        raise RuntimeError('Projeto Supabase diferente do projeto recuperado.')
    parsed = urlparse(dsn)
    if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname:
        raise RuntimeError('Conexão Postgres inválida.')
    # A identidade definitiva também é verificada dentro do banco. Proxies
    # podem ter hostname genérico, portanto não inferimos identidade pelo host.
    return dsn, url.rstrip('/'), key


def translate(statement):
    """Compatibilidade restrita para consultas parametrizadas do Store existente."""
    if 'INSERT OR REPLACE INTO failures' in statement:
        statement = statement.replace('INSERT OR REPLACE', 'INSERT')
        statement += ' ON CONFLICT (key) DO UPDATE SET count=EXCLUDED.count,last=EXCLUDED.last'
    elif 'INSERT OR IGNORE INTO outbox' in statement:
        statement = statement.replace('INSERT OR IGNORE', 'INSERT') + ' ON CONFLICT (id) DO NOTHING'
    if re.search(r'\b(?:PRAGMA|REPLACE|AUTOINCREMENT)\b', statement, re.I):
        raise ValueError('Consulta não suportada na persistência de produção.')
    return statement.replace('?', '%s')


class Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, params=()):
        from psycopg.pq import TransactionStatus
        if self.connection.info.transaction_status == TransactionStatus.IDLE:
            self.connection.execute('SET LOCAL search_path = seven7_app, pg_catalog')
            self.connection.execute("SET LOCAL lock_timeout = '8s'")
            self.connection.execute("SET LOCAL statement_timeout = '20s'")
            self.connection.execute('SELECT pg_advisory_xact_lock(772027, 625)')
        return self.connection.execute(translate(statement), params)

    def commit(self):
        self.connection.commit()


class CloudStore(Store):
    def __init__(self, environ=None):
        self.dsn, self.auth_url, self.auth_key = configuration(environ)
        self.lock = threading.RLock()
        self._transaction = threading.local()
        # Apenas relatórios temporários usam este caminho; dados vêm do Postgres.
        self.path = '/tmp/seven7-runtime/unused.sqlite3'
        with self.db() as db:
            marker = db.execute('SELECT project_ref,source_sha256 FROM metadata WHERE id=1').fetchone()
            if not marker or marker['project_ref'] != PROJECT or marker['source_sha256'] != SOURCE_HASH:
                raise RuntimeError('Identidade do banco não corresponde à recuperação aprovada.')
            if not db.execute('SELECT id FROM state WHERE id=1').fetchone():
                raise RuntimeError('Base recuperada não instalada. Inicialização automática bloqueada.')
            exposure = db.execute("SELECT has_schema_privilege('anon','seven7_app','USAGE') OR has_schema_privilege('authenticated','seven7_app','USAGE') AS exposed").fetchone()
            if exposure['exposed']:
                raise RuntimeError('Schema privado exposto; inicialização bloqueada.')

    @contextmanager
    def db(self):
        current = getattr(self._transaction, 'connection', None)
        if current is not None:
            yield current
            return
        import psycopg
        from psycopg.rows import dict_row
        # Transaction pooler: não usar prepared statements ou pool persistente.
        try:
            with psycopg.connect(self.dsn, connect_timeout=10, sslmode='require',
                                 prepare_threshold=None, row_factory=dict_row) as conn:
                self._transaction.connection = Connection(conn)
                try:
                    yield self._transaction.connection
                finally:
                    self._transaction.connection = None
        except psycopg.Error as error:
            failure = RuntimeError('Persistência indisponível; nenhuma alteração parcial foi confirmada.')
            category = error.sqlstate or 'connection'
            if not error.sqlstate:
                message = str(error).lower()
                for needle, safe_code in (
                    ('password authentication failed', 'authentication'),
                    ('tenant or user not found', 'tenant'),
                    ('network is unreachable', 'network'),
                    ('cannot assign requested address', 'network'),
                    ('connection refused', 'network'),
                    ('could not translate host name', 'dns'),
                    ('failed to resolve host', 'dns'),
                    ('name or service not known', 'dns'),
                    ('timeout expired', 'timeout'),
                    ('connection timed out', 'timeout'),
                    ('invalid percent-encoded token', 'format'),
                    ('invalid integer value', 'format'),
                    ('invalid connection option', 'format'),
                    ('missing "="', 'format'),
                    ('ssl', 'tls'),
                    ('certificate', 'tls'),
                    ('authentication', 'authentication'),
                    ('server closed the connection', 'closed'),
                    ('circuit breaker', 'tenant'),
                ):
                    if needle in message:
                        category = safe_code
                        break
            failure.diagnostic_code = 'postgres_' + category
            raise failure from None

    def auth_request(self, path, payload=None, method=None):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {'apikey': self.auth_key, 'Content-Type': 'application/json'}
        if self.auth_key.startswith('eyJ'):
            headers['Authorization'] = 'Bearer ' + self.auth_key
        request = Request(self.auth_url + '/auth/v1/' + path, data=body,
                          method=method or ('POST' if body is not None else 'GET'),
                          headers=headers)
        try:
            with urlopen(request, timeout=15) as response:
                return json.load(response)
        except HTTPError:
            raise PermissionError('Operação de autenticação não autorizada.') from None
        except (URLError, TimeoutError):
            raise RuntimeError('Autenticação temporariamente indisponível.') from None

    def users(self, db=None):
        if db is None:
            with self.db() as connection:
                return self.users(connection)
        rows = db.execute('SELECT p.id,p.nome,p.email,p.role,p.ativo,u.payload FROM public.profiles p LEFT JOIN user_permissions u ON u.id=p.id')
        result = []
        for row in rows:
            extra = json.loads(row['payload']) if row['payload'] else {}
            access = extra.get('access', PROMOTORA if row['role'] == 'promotora' else {})
            result.append(dict(id=str(row['id']), name=row['nome'], email=row['email'] or '',
                               active=row['ativo'], isAdmin=row['role'] == 'master',
                               access=access, phone=extra.get('phone', ''), deleted=extra.get('deleted', False)))
        return result

    def login(self, email, password, remote):
        failkey = hashlib.sha256((remote + '|' + fold(email)).encode()).hexdigest()
        with self.db() as db:
            failure = db.execute('SELECT * FROM failures WHERE key=?', (failkey,)).fetchone()
            if failure and failure['count'] >= 8 and time.time() - failure['last'] < 900:
                raise PermissionError('Aguarde antes de tentar novamente.')
        try:
            auth = self.auth_request('token?grant_type=password', {'email': email, 'password': password})
            uid = auth.get('user', {}).get('id')
            with self.db() as db:
                user = next((u for u in self.users(db) if u['id'] == uid and u['active'] and not u['deleted']), None)
                if not user:
                    raise PermissionError('Credenciais inválidas ou usuário inativo.')
                token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
                # Limita a sessão local à validade da autenticação Supabase.
                expires = time.time() + min(int(auth.get('expires_in', 3600)), 3600)
                db.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                           (hashlib.sha256(token.encode()).hexdigest(), uid, csrf, expires))
                db.execute('DELETE FROM failures WHERE key=?', (failkey,))
                self.audit(db, user, 'users', 'login', 'session')
                return token, csrf, user
        except PermissionError:
            with self.db() as db:
                db.execute('INSERT INTO failures VALUES(?,?,?) ON CONFLICT (key) DO UPDATE SET count=failures.count+1,last=EXCLUDED.last',
                           (failkey, 1, time.time()))
            raise PermissionError('Credenciais inválidas ou usuário inativo.') from None

    def session(self, token):
        if not token:
            return None, None
        with self.db() as db:
            row = db.execute('SELECT * FROM sessions WHERE token=? AND expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
            if not row:
                return None, None
            user = next((u for u in self.users(db) if u['id'] == str(row['user_id']) and u['active'] and not u['deleted']), None)
            return (user, row['csrf']) if user else (None, None)

    def snapshot(self, user):
        result = super().snapshot(user)
        # Dashboard não concede acesso aos detalhes financeiros ou de outros módulos.
        if not user.get('isAdmin'):
            state = result['state']
            legacy = state.get('recoveredLegacy', {})
            visible_legacy = {}
            if allowed(user, 'benefits'):
                visible_legacy['benefits'] = legacy.get('benefits', [])
            if allowed(user, 'requests'):
                visible_legacy['requests'] = [r for r in legacy.get('requests', []) if fold(r.get('requester','')) == fold(user.get('name',''))]
            for key, module, empty in [('budget','budget',[]), ('imports','budget',[]),
                    ('benefits','benefits',[]), ('guardians','guardians',[]),
                    ('breakEven','financial',{'plans':[]}), ('revenuePlanning','financial',{'years':{}}),
                    ('teachingLoad','financial',{'versions':[]})]:
                if not allowed(user, module):
                    state[key] = empty
            state['recoveredLegacy'] = visible_legacy
        return result

    def patch(self, user, changes, version, module, action='edit', confirmation=None):
        with self.lock, self.db() as db:
            current = next((p for p in self.users(db) if p['id']==user['id'] and p['active'] and not p['deleted']), None)
            if not current:
                raise PermissionError('Usuário inativo ou sessão encerrada.')
            result = super().patch(current, changes, version, module, action, confirmation)
            if 'classes' in changes or 'enrollments' in changes:
                state, _ = self.state(db)
                for room in state['classes']:
                    parts = room['name'].rsplit(' ',1)
                    serie, turma = parts if len(parts)==2 else (parts[0],'')
                    matches = list(db.execute('SELECT id FROM public.turmas WHERE serie=? AND turma=?', (serie,turma)))
                    if len(matches)>1:
                        raise ValueError('Turma ambígua no cadastro persistente; alteração cancelada.')
                    if matches:
                        db.execute('UPDATE public.turmas SET capacidade=?,matriculados=? WHERE id=?',
                                   (room['capacity'],room['students'],matches[0]['id']))
                    else:
                        db.execute('INSERT INTO public.turmas(serie,turma,capacidade,matriculados) VALUES(?,?,?,?)',
                                   (serie,turma,room['capacity'],room['students']))
            return result

    def user_action(self, actor, payload, action):
        require(actor, 'users', action)
        if not actor.get('isAdmin'):
            raise PermissionError('Somente administradores gerenciam usuários.')
        with self.lock, self.db() as db:
            people = self.users(db)
            old = next((u for u in people if u['id'] == payload.get('id')), None)
            if action not in ('create', 'edit', 'delete') or (action != 'create' and not old):
                raise ValueError('Operação de usuário inválida.')
            if action == 'delete':
                user = dict(old, active=False, deleted=True)
            else:
                user = {k:payload.get(k) for k in ('name','email','phone','active','isAdmin')}
                user.update(id=old['id'] if old else None, access=payload.get('access', {}), deleted=False)
                if not str(user['name'] or '').strip() or '@' not in str(user['email']):
                    raise ValueError('Nome e e-mail válidos são obrigatórios.')
                if any(u['id'] != user['id'] and fold(u['email']) == fold(user['email']) for u in people):
                    raise ValueError('E-mail já cadastrado.')
                if not isinstance(user['access'], dict) or any(k not in MODULES or not isinstance(v,list) or any(a not in ['view','create','edit','delete','approve'] for a in v) for k,v in user['access'].items()):
                    raise ValueError('Permissões inválidas.')
                password = payload.get('password')
                if (not old and not password) or (password and len(password) < 12):
                    raise ValueError('Senha inicial deve ter pelo menos 12 caracteres.')
            if old and old['isAdmin'] and (not user['active'] or not user['isAdmin']) and not any(u['id'] != old['id'] and u['isAdmin'] and u['active'] for u in people):
                raise ValueError('Mantenha pelo menos um administrador ativo.')
            if action != 'delete':
                auth_payload = {'email':user['email']}
                if payload.get('password'):
                    auth_payload['password'] = payload['password']
                response = self.auth_request('admin/users' + ('/' + old['id'] if old else ''), auth_payload, 'PUT' if old else 'POST')
                user['id'] = old['id'] if old else response['id']
            role = 'master' if user['isAdmin'] else ('promotora' if old and old.get('access') == PROMOTORA else 'comum')
            db.execute('INSERT INTO public.profiles(id,nome,email,role,ativo) VALUES(?,?,?,?::public.user_role,?) ON CONFLICT(id) DO UPDATE SET nome=EXCLUDED.nome,email=EXCLUDED.email,role=EXCLUDED.role,ativo=EXCLUDED.ativo',
                       (user['id'],user['name'],user['email'],role,bool(user['active'])))
            db.execute('INSERT INTO user_permissions VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=EXCLUDED.payload',
                       (user['id'],json.dumps({k:user.get(k) for k in ('access','phone','deleted')})))
            db.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
            self.audit(db, actor, 'users', action, user['id'], old, user)
            db.execute('UPDATE state SET version=version+1 WHERE id=1')
            return user

    def documentary_costs(self, classes):
        with self.db() as db:
            row = db.execute("SELECT payload,source_sha256 FROM public.teaching_cost_snapshots WHERE year=2027 AND version=1 AND status='approved'").fetchone()
            if not row or row['source_sha256'] != SOURCE_HASH:
                raise RuntimeError('Snapshot docente aprovado indisponível.')
            return row['payload'] if isinstance(row['payload'],dict) else json.loads(row['payload'])

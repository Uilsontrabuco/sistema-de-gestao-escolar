"""Static parsing only: never connects to a database or executes SQL."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(os.environ['TEMP']) / 'seven7-sql-parser'))
from pglast import parse_sql, parse_plpgsql

BASE = Path(__file__).resolve().parents[1]
MAIN = (BASE / 'private/FINAL-SNAPSHOT-2027.sql').read_bytes().decode('utf-8')
STRUCTURE = (BASE / 'review/FINAL-ESTRUTURA.sql').read_text(encoding='utf-8')
TEMPLATE = (BASE / 'review/final-administrative.template.sql').read_text(encoding='utf-8')
ROLLBACK = (BASE / 'review/FINAL-ROLLBACK.sql').read_text(encoding='utf-8')
VERIFY = (BASE / 'review/FINAL-VALIDAR.sql').read_text(encoding='utf-8')


class FinalSQL(unittest.TestCase):
    def test_structure_postgres_and_plpgsql_syntax(self):
        self.assertTrue(parse_sql(STRUCTURE))
        self.assertTrue(parse_plpgsql(STRUCTURE))

    def test_split_has_only_intended_operations(self):
        structure = re.sub(r'--[^\n]*', '', STRUCTURE)
        snapshot = re.sub(r'--[^\n]*', '', MAIN.replace(MAIN.split('$validated_ledger$')[1], '{}'))
        self.assertNotIn('$validated_ledger$', structure)
        self.assertNotRegex(structure, r'(?i)\b(INSERT|UPDATE|DELETE)\s+(INTO|FROM|public\.)')
        self.assertNotRegex(snapshot, r'(?i)\b(CREATE|ALTER|GRANT|REVOKE|DROP|TRUNCATE)\b')
        self.assertEqual(re.findall(r'(?i)INSERT\s+INTO\s+([\w.]+)', snapshot), ['public.teaching_cost_snapshots'])
        self.assertIn('existing_snapshot.payload IS DISTINCT FROM ledger', snapshot)
        self.assertIn('pg_advisory_xact_lock(772027, 1)', snapshot)
        self.assertLess(len(STRUCTURE.encode()), 20000)

    def test_monthly_salary_remains_null(self):
        values = []
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == 'monthly_salary':
                        values.append(child)
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(json.loads(MAIN.split('$validated_ledger$')[1]))
        self.assertTrue(values)
        self.assertTrue(all(value is None for value in values))

    def test_main_postgres_and_plpgsql_syntax(self):
        self.assertTrue(parse_sql(MAIN))
        self.assertTrue(parse_plpgsql(MAIN))

    def test_rollback_postgres_and_plpgsql_syntax(self):
        self.assertTrue(parse_sql(ROLLBACK))
        self.assertTrue(parse_plpgsql(ROLLBACK))

    def test_verification_read_only_ast(self):
        statements = parse_sql(VERIFY)
        self.assertTrue(statements)
        self.assertTrue(all(type(s.stmt).__name__ in ('SelectStmt', 'TransactionStmt') for s in statements))
        self.assertIn('BEGIN TRANSACTION READ ONLY;', VERIFY)

    def test_payload_exact_private_source(self):
        source = (BASE / 'private/teaching-cost-2027.json').read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        self.assertEqual(digest, '199b5c813e50988bbb2f6eb8e8d2771a97a9c62a117277a12678f1ae0beb20c9')
        embedded = MAIN.split('$validated_ledger$')[1]
        self.assertEqual(embedded.encode('utf-8'), source)
        self.assertIn(digest, MAIN)
        self.assertNotIn('__VALIDATED_LEDGER_', MAIN)
        ledger = json.loads(embedded)
        self.assertEqual(ledger['validated_cost_cents'], 2567735)
        self.assertEqual(len(ledger['classes']), 41)
        self.assertEqual(ledger['summary']['reconciled_professors'], 50)

    def test_only_intended_mutations(self):
        code = re.sub(r'--[^\n]*', '', TEMPLATE)
        self.assertNotRegex(code, r'(?i)\b(?:DROP|TRUNCATE|DELETE|UPDATE)\s+(?:TABLE|FROM|public\.)')
        self.assertNotRegex(code, r'(?i)ALTER\s+(?:TABLE\s+public\.profiles|POLICY|ROLE)|CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION')
        self.assertEqual(re.findall(r'(?i)INSERT\s+INTO\s+([\w.]+)', code), ['public.teaching_cost_snapshots'])
        self.assertEqual(re.findall(r'(?i)ALTER\s+FUNCTION\s+([\w.]+)', code), ['public.is_master', 'public.is_master'])
        self.assertNotRegex(code, r'(?i)(GRANT|REVOKE).*ON\s+FUNCTION')
        self.assertNotRegex(code, r'(?i)GRANT\s+(?:ALL|INSERT|UPDATE|DELETE)\b')
        self.assertLess(code.index('Owner nao consegue'), code.index('ALTER FUNCTION'))
        self.assertIn('existing_snapshot.payload IS DISTINCT FROM ledger', code)
        self.assertIn('obj_description(object_id', code)

    def test_rollback_preserves_all_data(self):
        code = re.sub(r'--[^\n]*', '', ROLLBACK)
        self.assertNotRegex(code, r'(?i)\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|CREATE|GRANT|REVOKE)\b')
        self.assertIn('SECURITY INVOKER;', code)
        self.assertIn('RESET search_path;', code)


if __name__ == '__main__':
    unittest.main(verbosity=1)

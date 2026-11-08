"""Synthetic controls for acquisition errors and scientific-summary selection."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO
from release_queries import reproduce as r

spec = importlib.util.spec_from_file_location('fetch_inputs', r.ROOT/'data/fetch_inputs.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class DataRoute(unittest.TestCase):
    def test_optional_identity_records_actual_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'record.json').write_text('{"x": 1}\n')
            manifest = {'files': [{'path': 'record.json', 'bytes': 1, 'sha256': '0'*64}]}
            record = r.verify_inputs(root, manifest)[0]
            self.assertFalse(record['matches_recorded_version'])
            self.assertNotEqual(record['sha256'], record['recorded_sha256'])
            with self.assertRaisesRegex(ValueError, 'version mismatch'):
                r.verify_inputs(root, manifest, exact=True)

    def test_failed_api_response_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            record = {'role': 'ili_training', 'path': 'lag00.json', 'url': 'https://example.invalid'}
            for body in [b'{"result":-2,"epidata":[]}', b'<html>error</html>']:
                with patch.object(f.urllib.request, 'urlopen', return_value=BytesIO(body)):
                    with self.assertRaises(ValueError):
                        f.fetch(record, Path(directory))
                self.assertFalse((Path(directory)/'lag00.json').exists())

    def test_existing_input_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'lag00.json'
            target.write_bytes(b'keep')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                f.fetch({'role': 'ili_training', 'path': 'lag00.json'}, Path(directory))
            self.assertEqual(target.read_bytes(), b'keep')

    def test_scientific_summary_excludes_query_inputs(self):
        model = {'reused': 1, 'wrong_reuses': 0, 'family_covered': True}
        value = {'demo': {'eligible_pool': 2, 'test_families': 1,
                         'cases': [{'input_queries': [17, 19], 'target_queries': [23, 29],
                                    'models': {'fit': model}}]}}
        result = r.adverse_summary(value)
        self.assertEqual(result['demo']['query_answers'], 2)
        self.assertEqual(result['demo']['models']['fit']['reused'], 1)
        text = json.dumps(result)
        self.assertNotIn('input_queries', text)
        self.assertNotIn('target_queries', text)
        self.assertNotIn('17', text)

    def test_summary_tolerance_keeps_counts_exact(self):
        r.compare({'effect': 0.0050000000001, 'count': 12}, {'effect': 0.005, 'count': 12})
        for actual in [{'effect': 0.005, 'count': 13}, {'effect': 0.006, 'count': 12}]:
            with self.assertRaises(ValueError):
                r.compare(actual, {'effect': 0.005, 'count': 12})

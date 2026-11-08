"""Small exact-byte controls for retained input preparation."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile, ZipInfo
from release_queries.reproduce import unpack_inputs


class InputPreparation(unittest.TestCase):
    def manifest(self, body=b'a'):
        return {'files': [{'path': 'nested/input', 'bytes': 1,
                           'sha256': hashlib.sha256(body).hexdigest()}]}

    def test_validate_before_writing_and_preserve_existing_destination(self):
        with TemporaryDirectory() as name:
            root = Path(name); archive = root/'inputs.zip'; target = root/'new'
            with ZipFile(archive, 'w') as stream:
                stream.writestr('nested/input', b'a')
            self.assertEqual(unpack_inputs(archive, target, self.manifest())['verified_input_files'], 1)
            with self.assertRaises(ValueError):
                unpack_inputs(archive, target, self.manifest())
            self.assertEqual((target/'nested/input').read_bytes(), b'a')

    def test_wrong_version_never_creates_output(self):
        with TemporaryDirectory() as name:
            root = Path(name); archive = root/'inputs.zip'; target = root/'new'
            with ZipFile(archive, 'w') as stream:
                stream.writestr('nested/input', b'b')
            with self.assertRaises(ValueError):
                unpack_inputs(archive, target, self.manifest())
            self.assertFalse(target.exists())

    def test_symlink_member_is_rejected(self):
        with TemporaryDirectory() as name:
            root = Path(name); archive = root/'inputs.zip'; info = ZipInfo('nested/input')
            info.create_system = 3; info.external_attr = 0o120777 << 16
            with ZipFile(archive, 'w') as stream:
                stream.writestr(info, b'a')
            with self.assertRaises(ValueError):
                unpack_inputs(archive, root/'new', self.manifest())
            self.assertFalse((root/'new').exists())


if __name__ == '__main__':
    unittest.main()

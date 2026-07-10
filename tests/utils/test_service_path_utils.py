import unittest
import os
import tempfile

os.chdir(os.getcwd().replace('/tests/utils', ''))

from src.utils import service_path_utils


class TestResolveTarget(unittest.TestCase):

    def test_directory_resolves_to_itself_with_no_highlight(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(service_path_utils.resolve_target(d), (d, None))

    def test_file_resolves_to_parent_folder_with_filename_highlight(self):
        with tempfile.TemporaryDirectory() as d:
            file_path = os.path.join(d, 'notes.txt')
            with open(file_path, 'w'):
                pass
            self.assertEqual(
                service_path_utils.resolve_target(file_path),
                (d, 'notes.txt'))

    def test_nonexistent_path_resolves_to_none(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, 'does_not_exist')
            self.assertIsNone(service_path_utils.resolve_target(missing))

    def test_trailing_slash_on_directory_is_normalized(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                service_path_utils.resolve_target(d + '/'),
                (d, None))


if __name__ == '__main__':
    unittest.main()

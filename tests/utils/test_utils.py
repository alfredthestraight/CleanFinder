import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
os.chdir(os.getcwd().replace('/tests/utils', ''))

from src.utils import os_utils
import pandas as pd
from pathlib import Path



class TestOsUtils(unittest.TestCase):

    # @patch('os_utils.Image.open')
    # @patch('os_utils.Image.save')
    # def test_resize_and_save_png_file(self, mock_save, mock_open):
    #     mock_image = MagicMock()
    #     mock_open.return_value = mock_image
    #     os_utils.resize_and_save_png_file('test.png', 30, 30)
    #     mock_open.assert_called_once_with('test.png')
    #     mock_image.resize.assert_called_once_with((30, 30))
    #     mock_image.save.assert_called_once_with('test.png', quality=95)

    # @patch('builtins.open', new_callable=mock_open)
    # @patch('os.utime')
    # def test_create_empty_file(self, mock_utime, mock_open):
    #     os_utils.create_empty_file('test.txt')
    #     mock_open.assert_called_once_with('test.txt', 'a')
    #     mock_utime.assert_called_once_with('test.txt', None)

    def test_is_dir(self):
        with patch('os_utils.Path.is_dir', return_value=True):
            self.assertTrue(os_utils.is_dir('test_dir'))

    def test_dir_(self):
        obj = MagicMock()
        obj.a = 1
        obj.b = 2
        result = os_utils.dir_(obj, 'a')
        self.assertIn('a', result)
        self.assertNotIn('b', result)

    def test_get_root_dir(self):
        self.assertEqual(os_utils.get_root_dir(), os.path.abspath(os.sep))

    def test_is_root(self):
        self.assertTrue(os_utils.is_root(os_utils.get_root_dir()))

    @patch('os.scandir')
    def test_folder_size(self, mock_scandir):
        mock_entry = MagicMock()
        mock_entry.is_file.return_value = True
        mock_entry.stat.return_value.st_size = 100
        mock_scandir.return_value = [mock_entry]
        self.assertEqual(os_utils.folder_size('test_dir'), 100)

    def test_get_item_size_pretty(self):
        self.assertEqual(os_utils.get_item_size_pretty(1023), (1023, "bytes", "1023 bytes"))
        self.assertEqual(os_utils.get_item_size_pretty(1024), (1.0, "KB", "1 KB"))

    @patch('os.scandir')
    def test_get_folder_size_bytes(self, mock_scandir):
        mock_entry = MagicMock()
        mock_entry.is_file.return_value = True
        mock_entry.path = 'test_file'
        mock_entry.stat.return_value.st_size = 100
        mock_scandir.return_value = [mock_entry]
        self.assertEqual(os_utils.get_folder_size_bytes('test_dir'), 100)

    @patch('os_utils.Path.iterdir')
    def test_get_all_item_names_in_directory(self, mock_iterdir):
        mock_path = MagicMock()
        mock_path.name = 'test_file'
        mock_iterdir.return_value = [mock_path]
        self.assertEqual(os_utils.get_all_item_names_in_directory('test_dir'), ['test_file'])

    def test_size_bytes_to_string(self):
        self.assertEqual(os_utils.size_bytes_to_string(1023), "1023 bytes")
        self.assertEqual(os_utils.size_bytes_to_string(1024), "1 KB")

    def test_size_string_to_bytes(self):
        self.assertEqual(os_utils.size_string_to_bytes("1 KB"), 1024)
        self.assertEqual(os_utils.size_string_to_bytes("1 MB"), 1024**2)

    def test_extract_extension_from_path(self):
        self.assertEqual(os_utils.extract_extension_from_path('test.txt'), 'txt')
        self.assertEqual(os_utils.extract_extension_from_path('test'), '')

    def test_extract_filename_from_path(self):
        self.assertEqual(os_utils.extract_filename_from_path('path/to/test.txt'), 'test.txt')
        self.assertEqual(os_utils.extract_filename_from_path('path/to/test.txt', include_extension=False), 'test')

    def test_extract_parent_path_from_path(self):
        self.assertEqual(os_utils.extract_parent_path_from_path('path/to/test.txt'), 'path/to')

    def test_get_type_as_icon_string(self):
        with patch('os_utils.Path.is_dir', return_value=True):
            self.assertEqual(os_utils.get_type_as_icon_string('test_dir'), 'folder_icon')
        with patch('os_utils.Path.is_dir', return_value=False):
            self.assertEqual(os_utils.get_type_as_icon_string('test.txt'), 'file_icon')

    @patch('os_utils.os.path.getctime', return_value=1609459200)
    def test_get_item_date_modified(self, mock_getctime):
        self.assertEqual(os_utils.get_item_date_modified('test.txt'), '2021-01-01 00:00:00')

    @patch('os.path.exists', return_value=True)
    @patch('os.path.iterdir')
    def test_get_dataframe_of_file_names_in_directory(self, mock_iterdir, mock_exists):
        mock_path = MagicMock()
        mock_path.name = 'test_file'
        mock_path.is_dir.return_value = False
        mock_iterdir.return_value = [mock_path]
        df = os_utils.get_dataframe_of_file_names_in_directory('test_dir')
        self.assertIn('test_file', df['Filename'].values)

    # @patch('os_utils.shutil.move')
    # @patch('os_utils.os.path.exists', side_effect=[True, True])
    # def test_move_item_from_dir1_to_dir2(self, mock_exists, mock_move):
    #     self.assertEqual(os_utils.move_item_from_dir1_to_dir2('test_file', 'dir1', 'dir2'), 1)
    #     mock_move.assert_called_once_with('dir1/test_file', 'dir2/test_file')
    #
    # @patch('os_utils.shutil.rmtree')
    # @patch('os_utils.os.path.exists', return_value=True)
    # def test_delete_item(self, mock_exists, mock_rmtree):
    #     self.assertEqual(os_utils.delete_item('test_dir'), 1)
    #     mock_rmtree.assert_called_once_with('test_dir')
    #
    # @patch('os_utils.shutil.copy')
    # @patch('os_utils.os.path.exists', return_value=True)
    # def test_copy_item_to_dir(self, mock_exists, mock_copy):
    #     self.assertEqual(os_utils.copy_item_to_dir('test_file', 'test_dir'), 1)
    #     mock_copy.assert_called_once_with('test_file', 'test_dir/test_file')
    #
    # @patch('os_utils.subprocess.run')
    # def test_open_application(self, mock_run):
    #     mock_run.return_value.returncode = 0
    #     self.assertEqual(os_utils.open_application('/Applications/Safari.app'), 1)
    #     mock_run.assert_called_once_with(['open', '/Applications/Safari.app'], check=True)

if __name__ == '__main__':
    unittest.main()
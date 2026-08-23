import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import shutil
import stat
import tempfile
os.chdir(os.getcwd().replace('/tests/utils', ''))

from src.utils import os_utils
from src.utils import utils
import pandas as pd
from pathlib import Path


class TestTypeAheadBuffer(unittest.TestCase):

    def test_appends_within_timeout(self):
        self.assertEqual(
            utils.update_type_ahead_buffer('r', 'e', elapsed_seconds=0.2, timeout=0.7),
            're')

    def test_resets_after_timeout(self):
        self.assertEqual(
            utils.update_type_ahead_buffer('r', 'e', elapsed_seconds=1.5, timeout=0.7),
            'e')

    def test_empty_previous_buffer_starts_fresh(self):
        self.assertEqual(
            utils.update_type_ahead_buffer('', 'r', elapsed_seconds=0.1, timeout=0.7),
            'r')


class TestComputeTypeAheadTarget(unittest.TestCase):

    def setUp(self):
        self.names = ['report.txt', 'resume.pdf', 'essay.doc', 'Run.sh', 'zebra.png']

    def test_prefix_match_returns_first_match_from_top(self):
        # 're' is not a repeated single letter -> prefix mode, first match wins
        self.assertEqual(utils.compute_type_ahead_target(self.names, 're', current_row=3), 0)

    def test_is_case_insensitive(self):
        self.assertEqual(utils.compute_type_ahead_target(self.names, 'run', current_row=None), 3)

    def test_single_letter_cycles_to_next_match_after_current(self):
        # current on row 0 (report), pressing 'r' should advance to resume (row 1)
        self.assertEqual(utils.compute_type_ahead_target(self.names, 'r', current_row=0), 1)

    def test_repeated_letter_keeps_cycling(self):
        # 'rr' is a repeated single letter -> still cycle mode from current
        self.assertEqual(utils.compute_type_ahead_target(self.names, 'rr', current_row=1), 3)

    def test_cycle_wraps_around(self):
        # current on last r-match (Run, row 3), pressing 'r' wraps back to report (row 0)
        self.assertEqual(utils.compute_type_ahead_target(self.names, 'r', current_row=3), 0)

    def test_no_match_returns_none(self):
        self.assertIsNone(utils.compute_type_ahead_target(self.names, 'q', current_row=None))

    def test_empty_names_returns_none(self):
        self.assertIsNone(utils.compute_type_ahead_target([], 'r', current_row=None))


class TestResolveTypeAhead(unittest.TestCase):

    def setUp(self):
        self.names = ['report.txt', 'resume.pdf', 'essay.doc', 'Run.sh', 'zebra.png']

    def test_matching_buffer_is_kept_as_is(self):
        # 're' matches report.txt -> no fallback, buffer untouched
        self.assertEqual(utils.resolve_type_ahead(self.names, 're', current_row=3),
                         (0, 're'))

    def test_unmatched_buffer_falls_back_to_last_character(self):
        # nothing starts with 'rz', so the 'z' keystroke acts on its own -> zebra.png
        self.assertEqual(utils.resolve_type_ahead(self.names, 'rz', current_row=0),
                         (4, 'z'))

    def test_fallback_buffer_is_the_single_character(self):
        # the returned buffer must be 'z', so a following 'e' searches 'ze', not 'rze'
        _, buffer = utils.resolve_type_ahead(self.names, 'rz', current_row=0)
        self.assertEqual(utils.update_type_ahead_buffer(buffer, 'e', elapsed_seconds=0.2),
                         'ze')

    def test_fallback_uses_cycle_mode_like_a_standalone_keypress(self):
        # 'rx' misses -> retries 'x'... which also misses, so nothing is selected
        self.assertEqual(utils.resolve_type_ahead(self.names, 'rx', current_row=0),
                         (None, 'x'))

    def test_fallback_matches_a_standalone_press_of_that_key(self):
        # falling back to 'r' from row 0 must behave exactly like pressing 'r' there
        row, _ = utils.resolve_type_ahead(self.names, 'qr', current_row=0)
        self.assertEqual(row, utils.compute_type_ahead_target(self.names, 'r', current_row=0))

    def test_single_character_buffer_has_nothing_to_fall_back_to(self):
        self.assertEqual(utils.resolve_type_ahead(self.names, 'q', current_row=None),
                         (None, 'q'))

    def test_empty_buffer_is_a_no_op(self):
        self.assertEqual(utils.resolve_type_ahead(self.names, '', current_row=None),
                         (None, ''))


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

    @patch('os_utils.os.path.getmtime', return_value=1609459200)
    def test_get_item_date_modified(self, mock_getmtime):
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

class TestCopyPrimitives(unittest.TestCase):
    """
    count_tree / copy_tree_with_progress back the pasting thread. They exist so a paste can be
    stopped part-way and can report progress - shutil.copytree can do neither.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.src = os.path.join(self.base, 'src')
        os.makedirs(os.path.join(self.src, 'sub', 'deeper'))
        for i in range(5):
            with open(os.path.join(self.src, f'f{i}.txt'), 'w') as f:
                f.write('x' * 10)
        for i in range(3):
            with open(os.path.join(self.src, 'sub', f'g{i}.txt'), 'w') as f:
                f.write('y' * 20)
        with open(os.path.join(self.src, 'sub', 'deeper', 'h.txt'), 'w') as f:
            f.write('z' * 30)
        # 5*10 + 3*20 + 30 = 140 bytes across 9 files

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_count_tree_counts_files_and_bytes_recursively(self):
        self.assertEqual(os_utils.count_tree(self.src), (9, 140))

    def test_count_tree_of_a_single_file(self):
        self.assertEqual(os_utils.count_tree(os.path.join(self.src, 'f0.txt')), (1, 10))

    def test_copy_reproduces_the_whole_tree(self):
        dest = os.path.join(self.base, 'dest')
        self.assertEqual(os_utils.copy_tree_with_progress(self.src, dest), 1)
        self.assertTrue(os.path.exists(os.path.join(dest, 'sub', 'deeper', 'h.txt')))
        self.assertEqual(os_utils.count_tree(dest), (9, 140))

    def test_copy_reports_every_file_it_copied(self):
        dest = os.path.join(self.base, 'dest')
        reported = []
        os_utils.copy_tree_with_progress(self.src, dest, on_file_done=reported.append)
        self.assertEqual(len(reported), 9)
        self.assertEqual(sum(reported), 140)

    def test_copy_of_a_single_file(self):
        dest = os.path.join(self.base, 'one.txt')
        self.assertEqual(
            os_utils.copy_tree_with_progress(os.path.join(self.src, 'f0.txt'), dest), 1)
        self.assertTrue(os.path.exists(dest))

    def test_abort_mid_tree_removes_the_partial_destination(self):
        dest = os.path.join(self.base, 'dest')
        calls = {'n': 0}

        def should_stop():
            calls['n'] += 1
            return calls['n'] > 2

        self.assertEqual(
            os_utils.copy_tree_with_progress(self.src, dest, should_stop=should_stop), -2)
        self.assertFalse(os.path.exists(dest),
                         'a cancelled copy must not leave half a folder behind')

    def test_abort_before_the_first_file_still_aborts(self):
        dest = os.path.join(self.base, 'dest')
        self.assertEqual(
            os_utils.copy_tree_with_progress(self.src, dest, should_stop=lambda: True), -2)

    def test_missing_source_is_an_error(self):
        self.assertEqual(
            os_utils.copy_tree_with_progress(os.path.join(self.base, 'nope'),
                                             os.path.join(self.base, 'dest')), -1)

    def test_identical_source_and_destination_does_nothing(self):
        self.assertEqual(os_utils.copy_tree_with_progress(self.src, self.src), 0)

    def test_unreadable_file_reports_an_error_without_raising(self):
        unreadable = os.path.join(self.src, 'f0.txt')
        os.chmod(unreadable, 0o000)
        try:
            dest = os.path.join(self.base, 'dest')
            self.assertEqual(os_utils.copy_tree_with_progress(self.src, dest), -1)
        finally:
            os.chmod(unreadable, 0o644)


class TestIsHiddenFromStat(unittest.TestCase):
    """
    is_hidden_from_stat replaces a Launch Services round trip per item when listing a directory,
    so it has to agree with the NSURL-based is_hidden it stands in for.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_dotfile_is_hidden(self):
        path = os.path.join(self.base, '.hidden')
        with open(path, 'w') as f:
            f.write('x')
        self.assertTrue(os_utils.is_hidden_from_stat('.hidden', os.stat(path)))
        self.assertEqual(bool(os_utils.is_hidden(path)),
                         os_utils.is_hidden_from_stat('.hidden', os.stat(path)))

    def test_ordinary_file_is_not_hidden(self):
        path = os.path.join(self.base, 'visible.txt')
        with open(path, 'w') as f:
            f.write('x')
        self.assertFalse(os_utils.is_hidden_from_stat('visible.txt', os.stat(path)))
        self.assertEqual(bool(os_utils.is_hidden(path)),
                         os_utils.is_hidden_from_stat('visible.txt', os.stat(path)))

    def test_uf_hidden_flag_is_honoured(self):
        path = os.path.join(self.base, 'flagged.txt')
        with open(path, 'w') as f:
            f.write('x')
        os.chflags(path, stat.UF_HIDDEN)
        try:
            self.assertTrue(os_utils.is_hidden_from_stat('flagged.txt', os.stat(path)))
            self.assertEqual(bool(os_utils.is_hidden(path)),
                             os_utils.is_hidden_from_stat('flagged.txt', os.stat(path)))
        finally:
            os.chflags(path, 0)


class TestExtractExtensionFromName(unittest.TestCase):

    def test_matches_extract_extension_from_path_for_files(self):
        for name in ['notes.txt', 'archive.tar.gz', 'noextension', '.bashrc']:
            self.assertEqual(os_utils.extract_extension_from_name(name),
                             os_utils.extract_extension_from_path(name),
                             f'disagreed on {name}')

    def test_no_dot_means_no_extension(self):
        self.assertEqual(os_utils.extract_extension_from_name('README'), '')


if __name__ == '__main__':
    unittest.main()
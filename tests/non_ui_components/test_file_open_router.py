import unittest
import os
import tempfile

os.chdir(os.getcwd().replace('/tests/non_ui_components', ''))

from src.non_ui_components.file_open_router import FileOpenRouter


class RecordingManager:
    def __init__(self):
        self.calls = []

    def open_service_target(self, folder, filename_to_highlight=None):
        self.calls.append((folder, filename_to_highlight))


class TestFileOpenRouter(unittest.TestCase):

    def test_routes_directory_to_manager_after_set(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = RecordingManager()
            router = FileOpenRouter()
            router.set_manager(mgr)
            router.handle_path(d)
            self.assertEqual(mgr.calls, [(d, None)])
            self.assertEqual(router.opened_count, 1)

    def test_routes_file_to_parent_with_highlight(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'notes.txt')
            open(f, 'w').close()
            mgr = RecordingManager()
            router = FileOpenRouter()
            router.set_manager(mgr)
            router.handle_path(f)
            self.assertEqual(mgr.calls, [(d, 'notes.txt')])

    def test_queues_paths_until_manager_set_then_flushes_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            sub1 = os.path.join(d, 'one'); os.mkdir(sub1)
            sub2 = os.path.join(d, 'two'); os.mkdir(sub2)
            mgr = RecordingManager()
            router = FileOpenRouter()
            # Paths arrive before the UI/manager exists (as at cold launch).
            router.handle_path(sub1)
            router.handle_path(sub2)
            self.assertEqual(mgr.calls, [])
            self.assertEqual(router.opened_count, 0)
            router.set_manager(mgr)
            self.assertEqual(mgr.calls, [(sub1, None), (sub2, None)])
            self.assertEqual(router.opened_count, 2)

    def test_skips_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = RecordingManager()
            router = FileOpenRouter()
            router.set_manager(mgr)
            router.handle_path(os.path.join(d, 'missing'))
            self.assertEqual(mgr.calls, [])
            self.assertEqual(router.opened_count, 0)


if __name__ == '__main__':
    unittest.main()

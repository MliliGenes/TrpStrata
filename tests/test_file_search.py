from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from trp_strata.file_search import FileSearchModel, scan_files, search_files


class FileSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content")
        return str(path)

    def model(self, **kwargs):
        model = FileSearchModel(str(self.root), **kwargs)
        def cleanup():
            model.close()
            model.thread.join(2)
        self.addCleanup(cleanup)
        return model

    def ready(self, model):
        with model.condition:
            self.assertTrue(model.condition.wait_for(lambda: not model.busy, timeout=3))

    def test_exact_abbreviations_typos_and_unicode(self):
        report = self.file("Projects/report.txt")
        other = self.file("report-summary.txt")
        resume = self.file("Résumé.pdf")
        index, capped = scan_files(str(self.root))
        self.assertFalse(capped)
        self.assertEqual(search_files(index, "report.txt")[0], report)
        self.assertIn(report, search_files(index, "rpt"))
        self.assertIn(report, search_files(index, "reprot"))
        self.assertEqual(search_files(index, "RESUME"), (resume,))
        self.assertEqual(search_files(index, "projects rpt"), (report,))
        self.assertEqual(search_files(index, ""), ())
        self.assertEqual(search_files(index, "zzzzzz"), ())
        self.assertIn(other, search_files(index, "report"))

    def test_scan_excludes_hidden_generated_and_symlink_trees_and_is_bounded(self):
        visible = self.file("Documents/visible.txt")
        for name in (".secret.txt", ".private/hidden.txt", "node_modules/dependency.txt", "build/output.txt"):
            self.file(name)
        (self.root / "linked").symlink_to(self.root / ".private", target_is_directory=True)
        (self.root / "loop").symlink_to(self.root, target_is_directory=True)
        index, _ = scan_files(str(self.root))
        self.assertEqual([entry[0] for entry in index], [visible])
        self.file("another.txt")
        index, capped = scan_files(str(self.root), limit=1)
        self.assertTrue(capped)
        self.assertEqual(len(index), 1)
        self.assertEqual(scan_files(str(self.root), cancelled=lambda: True), ((), False))

    def test_refresh_picks_up_files_and_open_errors_are_visible(self):
        opener = Mock(side_effect=RuntimeError("No default application"))
        model = self.model(opener=opener)
        model.set_query("new-file")
        self.ready(model)
        self.assertEqual(model.view()[0], ())
        path = self.file("new-file.txt")
        model.refresh()
        self.ready(model)
        self.assertEqual(model.view()[0], (path,))
        model.launch(path)
        opener.assert_called_once_with(path)
        self.assertIn("No default application", model.view()[1])

    def test_query_changed_during_indexing_never_publishes_stale_results(self):
        first = self.file("first.txt")
        second = self.file("second.txt")
        started, release = threading.Event(), threading.Event()
        def scanner(root, cancelled):
            started.set()
            release.wait(2)
            return scan_files(root, cancelled)
        model = self.model(scanner=scanner)
        try:
            self.assertTrue(started.wait(2))
            model.set_query("first")
            model.set_query("second")
        finally:
            release.set()
        self.ready(model)
        self.assertEqual(model.view()[0], (second,))
        self.assertNotIn(first, model.view()[0])

    def test_root_changes_rebuild_and_missing_roots_report_errors(self):
        self.file("one/first.txt")
        second = self.file("two/second.txt")
        model = self.model()
        model.configure(str(self.root / "two"))
        model.set_query("txt")
        self.ready(model)
        self.assertEqual(model.view()[0], (second,))
        model.configure(str(self.root / "missing"))
        self.ready(model)
        self.assertIn("Cannot search this folder", model.view()[1])
        self.assertEqual(model.view()[0], ())

    def test_close_wakes_idle_worker(self):
        model = self.model()
        self.ready(model)
        model.close()
        model.thread.join(2)
        self.assertFalse(model.thread.is_alive())


if __name__ == "__main__":
    unittest.main()

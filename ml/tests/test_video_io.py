import csv
import tempfile
import unittest
from pathlib import Path

from ml.src.video_io import evenly_spaced_indices, read_manifest


class VideoIOTests(unittest.TestCase):
    def test_indices_span_clip_and_repeat_short_clips(self):
        self.assertEqual(evenly_spaced_indices(5, 3), [0, 2, 4])
        self.assertEqual(evenly_spaced_indices(1, 3), [0, 0, 0])
        self.assertEqual(evenly_spaced_indices(9, 1), [4])
        for frames, n in ((0, 1), (1, 0), (-1, 2)):
            with self.assertRaises(ValueError): evenly_spaced_indices(frames, n)

    def test_manifest_explicit_group_and_resolved_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.csv"
            rows = [{"clip_id":"a", "group_id":"cow1", "path":"clips/a.mp4", "label":"0", "split":"train"},
                    {"clip_id":"b", "group_id":"cow2", "path":"clips/b.mp4", "label":"1", "split":"validation"}]
            def write():
                with path.open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader(); writer.writerows(rows)
            write()
            records = read_manifest(path)
            self.assertEqual(records[0]["path"], str((path.parent / "clips/a.mp4").resolve()))
            rows[1]["group_id"] = "cow1"
            write()
            with self.assertRaisesRegex(ValueError, "group appears"): read_manifest(path)
            rows[1]["group_id"] = "cow2"
            rows[1]["path"] = "clips/a.mp4"
            write()
            with self.assertRaisesRegex(ValueError, "same clip path"): read_manifest(path)

    def test_no_implicit_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.csv"
            path.write_text("clip_id,group_id,path,label,split\na,cow1,lame/a.mp4,,train\n")
            with self.assertRaisesRegex(ValueError, "missing required"): read_manifest(path)


if __name__ == "__main__": unittest.main()

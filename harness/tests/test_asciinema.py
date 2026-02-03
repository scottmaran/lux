import json
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from asciinema import build_header, decode_bytes, format_event


class TestAsciinema(unittest.TestCase):
    def test_build_header_includes_required_fields(self) -> None:
        header = build_header(
            width=120,
            height=40,
            timestamp=1700000000,
            command="bash -l",
            title="test run",
            env={"TERM": "xterm-256color"},
        )

        self.assertEqual(header["version"], 2)
        self.assertEqual(header["width"], 120)
        self.assertEqual(header["height"], 40)
        self.assertEqual(header["timestamp"], 1700000000)
        self.assertEqual(header["command"], "bash -l")
        self.assertEqual(header["title"], "test run")
        self.assertEqual(header["env"]["TERM"], "xterm-256color")

    def test_decode_bytes_replaces_invalid_utf8(self) -> None:
        raw = b"\xff\xfehi"
        decoded = decode_bytes(raw)
        self.assertIn("hi", decoded)

    def test_format_event_rounds_timestamp(self) -> None:
        line = format_event(0.12345678, "o", "hello")
        data = json.loads(line)
        self.assertEqual(data[0], 0.123457)
        self.assertEqual(data[1], "o")
        self.assertEqual(data[2], "hello")


if __name__ == "__main__":
    unittest.main()

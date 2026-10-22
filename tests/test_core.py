import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gotchi_chain
import gotchi_memory
import gotchi_query


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "chain.json"
        self.patches = [
            patch.object(gotchi_chain, "CHAIN_FILE", self.path),
            patch.object(gotchi_chain, "sign_file", return_value=True),
            patch.object(gotchi_chain, "verify_signature", return_value=True),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_genesis_append_and_validation(self):
        gotchi_chain.append_to_chain("Checked SSH", 10)
        chain = gotchi_chain.load_chain()
        self.assertEqual(len(chain), 2)
        self.assertTrue(gotchi_chain.validate_chain())

    def test_tampered_genesis(self):
        chain = gotchi_chain.load_chain()
        chain[0]["action"] = "tampered"
        self.assertFalse(gotchi_chain.validate_blocks(chain))

    def test_invalid_prev_hash(self):
        gotchi_chain.append_to_chain("checked", 1)
        chain = gotchi_chain.load_chain()
        chain[1]["prev_hash"] = "forged"
        chain[1]["hash"] = gotchi_chain.hash_block(chain[1])
        self.assertFalse(gotchi_chain.validate_blocks(chain))

    def test_refuses_tampered_chain(self):
        chain = gotchi_chain.load_chain()
        chain[0]["action"] = "tampered"
        self.path.write_text(json.dumps(chain), encoding="utf-8")
        with self.assertRaises(ValueError):
            gotchi_chain.append_to_chain("nope", 10)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.brain = Path(self.tmp.name) / "brain.json"
        self.log = Path(self.tmp.name) / "activity.txt"
        self.brain.write_text(json.dumps({"xp": 0, "memory_log": []}), encoding="utf-8")
        self.patches = [
            patch.object(gotchi_memory, "brain_path", self.brain),
            patch.object(gotchi_memory, "changelog_path", self.log),
            patch.object(gotchi_memory, "append_to_chain"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_memory_xp(self):
        with patch.dict("sys.modules", {"gotchi_vector": None}):
            result = gotchi_memory.add_memory("Audit completed", 120)
        self.assertEqual(result["xp"], 120)
        self.assertEqual(result["level"], 2)
        self.assertIn("Audit completed", self.log.read_text())

    def test_negative_xp_rejected(self):
        with self.assertRaises(ValueError):
            gotchi_memory.add_memory("oops", -10)


class QueryTests(unittest.TestCase):
    def test_pagination(self):
        with patch.object(gotchi_query, "search_memory", return_value=list("abcdef")) as search:
            self.assertEqual(gotchi_query.get_results("audit", page=2, results_per_page=3), list("def"))
            search.assert_called_once_with("audit", n=6)


if __name__ == "__main__":
    unittest.main()

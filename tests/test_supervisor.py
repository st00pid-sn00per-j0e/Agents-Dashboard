import asyncio
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rich.console import Console


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "supervisor_under_test", PROJECT_ROOT / "src" / "Supervisor.py"
)
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


class SupervisorTests(unittest.TestCase):
    def test_extract_json_handles_prose_and_multiple_objects(self):
        self.assertEqual(
            supervisor._extract_json('Note: {"mode":"direct","answer":"ok"} End.'),
            {"mode": "direct", "answer": "ok"},
        )
        self.assertEqual(
            supervisor._extract_json('ignore {"first":true} then {"second":true}'),
            {"first": True},
        )

    def test_extract_json_rejects_non_object(self):
        with self.assertRaises(ValueError):
            supervisor._extract_json('["not", "an object"]')

    def test_legacy_database_is_migrated_and_storable(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "state.db"
            con = sqlite3.connect(db_path)
            con.execute(
                "CREATE TABLE sessions(id INTEGER PRIMARY KEY, uuid TEXT, task TEXT, output TEXT, status TEXT, created TEXT)"
            )
            con.close()

            with patch.object(supervisor, "STATE_DB", db_path):
                supervisor.init_state_db()
                uid = supervisor.store_session("task", "direct", None, "answer", {})

            con = sqlite3.connect(db_path)
            columns = {row[1] for row in con.execute("PRAGMA table_info(sessions)")}
            row = con.execute(
                "SELECT uuid, mode, distribution, output FROM sessions WHERE uuid = ?", (uid,)
            ).fetchone()
            con.close()

            self.assertTrue({"mode", "distribution"} <= columns)
            self.assertEqual(row, (uid, "direct", "", "answer"))

    def test_reasoning_validation_filters_unknown_and_invalid_assignments(self):
        async def fake_think(*_args, **_kwargs):
            return '''{"mode":"dispatch","distribution":"shared","plan":{"Agent_1":"  inspect  ","Unknown":"ignore","Agent_2":3,"Agent_3":""}}'''

        with patch.object(supervisor, "think", fake_think):
            decision = asyncio.run(
                supervisor.reason_about_task("test", ["Agent_1", "Agent_2", "Agent_3"])
            )
        self.assertEqual(decision["plan"], {"Agent_1": "inspect"})

    def test_direct_answer_requires_text(self):
        async def fake_think(*_args, **_kwargs):
            return '{"mode":"direct","answer":null}'

        with patch.object(supervisor, "think", fake_think):
            with self.assertRaises(ValueError):
                asyncio.run(supervisor.reason_about_task("test", ["Agent_1"]))

    def test_plain_text_reasoning_response_becomes_direct_answer(self):
        async def fake_think(*_args, **_kwargs):
            return "I’m sorry, but I can’t help with that."

        with patch.object(supervisor, "think", fake_think):
            decision = asyncio.run(supervisor.reason_about_task("test", ["Agent_1"]))
        self.assertEqual(
            decision,
            {"mode": "direct", "answer": "I’m sorry, but I can’t help with that."},
        )

    def test_merge_compacts_verbose_agent_logs(self):
        captured = {}

        async def fake_think(prompt, *_args, **_kwargs):
            captured["prompt"] = prompt
            return "merged"

        output = "start\n" + ("x" * 40_000) + "\nfinal result"
        with patch.object(supervisor, "think", fake_think):
            result = asyncio.run(
                supervisor.merge_outputs("task", "split", {"Agent_1": output})
            )

        self.assertEqual(result, "merged")
        self.assertLess(len(captured["prompt"]), 26_000)
        self.assertIn("verbose worker logs omitted", captured["prompt"])
        self.assertIn("start", captured["prompt"])
        self.assertIn("final result", captured["prompt"])

    def test_no_agent_fallback_does_not_return_invalid_direct_answer(self):
        async def fake_think(*_args, **_kwargs):
            return '{"mode":"direct","answer":null}'

        with patch.object(supervisor, "think", fake_think):
            decision = asyncio.run(supervisor.reason_about_task("test", []))
        self.assertEqual(decision, {"mode": "direct", "answer": '{"mode":"direct","answer":null}'})

    def test_worker_exit_status_and_empty_output_are_handled(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "Agent_1.py").write_text(
                "import sys\nprint('worker failure', file=sys.stderr)\nsys.exit(7)\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "exited with code 7: worker failure"):
                asyncio.run(supervisor.run_agent("test", folder, "task"))

            (folder / "Agent_1.py").write_text("", encoding="utf-8")
            self.assertEqual(
                asyncio.run(supervisor.run_agent("test", folder, "task")),
                "test completed without output",
            )

            (folder / "Agent_1.py").write_text(
                "import os\nassert os.environ['PYTHONIOENCODING'] == 'utf-8'\nprint('unicode: non-breaking hyphen ‑')\n",
                encoding="utf-8",
            )
            self.assertEqual(
                asyncio.run(supervisor.run_agent("test", folder, "task")),
                "unicode: non-breaking hyphen ‑",
            )

    def test_worker_rejects_invalid_task_before_spawning(self):
        with self.assertRaises(ValueError):
            asyncio.run(supervisor.run_agent("test", Path("."), "  "))

    def test_agent_responses_are_rendered_in_the_cli(self):
        rendered_console = Console(record=True, force_terminal=False, width=100)
        outputs = {"Agent_1": "completed research", "Agent_2": "ERROR worker timeout"}

        with patch.object(supervisor, "console", rendered_console):
            supervisor.show_agent_responses(outputs)

        rendered = rendered_console.export_text()
        self.assertIn("AGENT RESPONSE · Agent_1", rendered)
        self.assertIn("completed research", rendered)
        self.assertIn("AGENT RESPONSE · Agent_2", rendered)
        self.assertIn("ERROR worker timeout", rendered)


if __name__ == "__main__":
    unittest.main()

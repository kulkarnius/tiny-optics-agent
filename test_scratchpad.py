"""
Tests for the Python scratchpad Docker backend and result versioning.

Docker tests require Docker to be available. Versioning tests are pure
filesystem and run without Docker.
"""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scratchpad.docker_backend import DockerScratchpad, ExecutionResult
from scratchpad import versioning


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def scratchpad(event_loop, tmp_path_factory):
    """Build image, start container, yield backend, stop on teardown."""
    shared = tmp_path_factory.mktemp("shared")
    sp = DockerScratchpad(
        container_name="scratchpad-test",
        shared_dir=shared,
        timeout=30,
        memory_limit="512m",
        cpu_limit=1.0,
    )
    event_loop.run_until_complete(sp.build_image())
    event_loop.run_until_complete(sp.ensure_running())
    yield sp
    event_loop.run_until_complete(sp.stop())


@pytest.fixture(autouse=True)
def reset_before_test(scratchpad, event_loop):
    """Reset session before each test for isolation."""
    event_loop.run_until_complete(scratchpad.reset_session())


def run(event_loop, coro):
    """Helper: run a coroutine on the module event loop."""
    return event_loop.run_until_complete(coro)


# ==========================================
# Numerics
# ==========================================

class TestNumerics:
    def test_basic_arithmetic(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute("print(2 + 3)"))
        assert result.success
        assert "5" in result.stdout

    def test_numpy_operations(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "import numpy as np\n"
            "a = np.array([1, 2, 3])\n"
            "print(a.mean())"
        ))
        assert result.success
        assert "2.0" in result.stdout

    def test_scipy_integration(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "from scipy import integrate\n"
            "val, err = integrate.quad(lambda x: x**2, 0, 1)\n"
            "print(f'{val:.6f}')"
        ))
        assert result.success
        assert "0.333333" in result.stdout


# ==========================================
# Symbolics
# ==========================================

class TestSymbolics:
    def test_sympy_solve(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "from sympy import symbols, solve\n"
            "x = symbols('x')\n"
            "print(solve(x**2 - 4, x))"
        ))
        assert result.success
        assert "-2" in result.stdout
        assert "2" in result.stdout

    def test_sympy_differentiate(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "from sympy import symbols, sin, diff\n"
            "x = symbols('x')\n"
            "print(diff(sin(x), x))"
        ))
        assert result.success
        assert "cos(x)" in result.stdout

    def test_sympy_integrate(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "from sympy import symbols, integrate\n"
            "x = symbols('x')\n"
            "print(integrate(x**2, x))"
        ))
        assert result.success
        assert "x**3/3" in result.stdout


# ==========================================
# Stateful Execution
# ==========================================

class TestStateful:
    def test_variable_persistence(self, scratchpad, event_loop):
        r1 = run(event_loop, scratchpad.execute("x = 42"))
        assert r1.success

        r2 = run(event_loop, scratchpad.execute("print(x)"))
        assert r2.success
        assert "42" in r2.stdout

    def test_function_persistence(self, scratchpad, event_loop):
        r1 = run(event_loop, scratchpad.execute(
            "def greet(name): return f'Hello {name}'"
        ))
        assert r1.success

        r2 = run(event_loop, scratchpad.execute("print(greet('World'))"))
        assert r2.success
        assert "Hello World" in r2.stdout


# ==========================================
# Plots
# ==========================================

class TestPlots:
    def test_auto_save_figure(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "import matplotlib.pyplot as plt\n"
            "plt.plot([1, 2, 3], [1, 4, 9])\n"
            "plt.title('Test Plot')"
        ))
        assert result.success
        assert len(result.figures) > 0
        # figures now contain full /shared/ paths
        fig_name = Path(result.figures[0]).name
        fig_path = scratchpad.shared_dir / fig_name
        assert fig_path.exists()
        assert fig_path.stat().st_size > 0

    def test_explicit_savefig(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "import matplotlib.pyplot as plt\n"
            "plt.plot([1, 2, 3])\n"
            "plt.savefig('/shared/my_plot.png')\n"
            "plt.close()"
        ))
        assert result.success
        assert (scratchpad.shared_dir / "my_plot.png").exists()

    def test_opencv_imwrite(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "import numpy as np\n"
            "import cv2\n"
            "img = np.zeros((100, 100, 3), dtype=np.uint8)\n"
            "cv2.imwrite('/shared/test_cv.png', img)"
        ))
        assert result.success
        assert (scratchpad.shared_dir / "test_cv.png").exists()


# ==========================================
# Security
# ==========================================

class TestSecurity:
    def test_timeout_enforcement(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "import time\ntime.sleep(60)",
            timeout=5,
        ))
        assert not result.success
        assert result.error is not None
        assert "timed out" in result.error.lower() or "timeout" in result.error.lower()

    def test_no_network(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "import urllib.request\n"
            "urllib.request.urlopen('http://example.com')"
        ))
        assert not result.success
        assert result.error is not None

    def test_read_only_filesystem(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "open('/etc/test_readonly', 'w').write('should fail')"
        ))
        assert not result.success
        assert result.error is not None

    def test_shared_dir_writable(self, scratchpad, event_loop):
        result = run(event_loop, scratchpad.execute(
            "with open('/shared/test_write.txt', 'w') as f:\n"
            "    f.write('hello')\n"
            "print('write ok')"
        ))
        assert result.success
        assert "write ok" in result.stdout


# ==========================================
# Session Management
# ==========================================

class TestSession:
    def test_reset_clears_state(self, scratchpad, event_loop):
        r1 = run(event_loop, scratchpad.execute("x = 42"))
        assert r1.success

        event_loop.run_until_complete(scratchpad.reset_session())

        r2 = run(event_loop, scratchpad.execute("print(x)"))
        assert not r2.success
        assert "NameError" in r2.error


# ==========================================
# Result Versioning (no Docker required)
# ==========================================

def _make_result(**kwargs) -> ExecutionResult:
    """Build an ExecutionResult with sensible defaults."""
    defaults = dict(stdout="hello", stderr="", error=None, figures=[], success=True)
    defaults.update(kwargs)
    return ExecutionResult(**defaults)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestVersioningRecord:
    def test_record_json_created(self, tmp_path):
        result = _make_result(stdout="42")
        run_id = versioning.record_run(tmp_path / "results", "sess-1", "print(42)", result, tmp_path / "shared")
        record_path = tmp_path / "results" / run_id / "record.json"
        assert record_path.exists()

    def test_record_fields(self, tmp_path):
        result = _make_result(stdout="out", stderr="err", error=None, success=True)
        run_id = versioning.record_run(tmp_path / "results", "sess-abc", "x=1", result, tmp_path / "shared")
        record = json.loads((tmp_path / "results" / run_id / "record.json").read_text())

        assert record["schema_version"] == "1.0"
        assert record["run_id"] == run_id
        assert record["session_id"] == "sess-abc"
        assert record["code"] == "x=1"
        assert record["stdout"] == "out"
        assert record["stderr"] == "err"
        assert record["error"] is None
        assert record["success"] is True
        assert "timestamp" in record
        assert "content_hash" in record

    def test_failed_run_recorded(self, tmp_path):
        result = _make_result(stdout="", stderr="", error="SyntaxError: invalid syntax", success=False)
        run_id = versioning.record_run(tmp_path / "results", "sess-1", "def bad(:", result, tmp_path / "shared")
        record = json.loads((tmp_path / "results" / run_id / "record.json").read_text())
        assert record["success"] is False
        assert record["error"] == "SyntaxError: invalid syntax"


class TestVersioningFigures:
    def test_figure_copied_to_run_dir(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        fig_data = b"\x89PNG fake image bytes"
        (shared / "plot.png").write_bytes(fig_data)

        result = _make_result(figures=["plot.png"])
        run_id = versioning.record_run(tmp_path / "results", "sess-1", "plt.plot()", result, shared)

        copied = tmp_path / "results" / run_id / "plot.png"
        assert copied.exists()
        assert copied.read_bytes() == fig_data

    def test_figure_sha256_in_record(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        fig_data = b"\x89PNG real content"
        (shared / "fig.png").write_bytes(fig_data)

        result = _make_result(figures=["fig.png"])
        run_id = versioning.record_run(tmp_path / "results", "sess-1", "plt.plot()", result, shared)

        record = json.loads((tmp_path / "results" / run_id / "record.json").read_text())
        assert len(record["figures"]) == 1
        assert record["figures"][0]["filename"] == "fig.png"
        assert record["figures"][0]["sha256"] == _sha256_bytes(fig_data)
        assert record["figures"][0]["size_bytes"] == len(fig_data)

    def test_missing_figure_skipped_gracefully(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        # figure listed in result but not present on disk
        result = _make_result(figures=["ghost.png"])
        run_id = versioning.record_run(tmp_path / "results", "sess-1", "code", result, shared)
        record = json.loads((tmp_path / "results" / run_id / "record.json").read_text())
        assert record["figures"] == []


class TestVersioningIndex:
    def test_index_created_on_first_run(self, tmp_path):
        result = _make_result()
        versioning.record_run(tmp_path / "results", "sess-1", "pass", result, tmp_path / "shared")
        assert (tmp_path / "results" / "index.json").exists()

    def test_index_contains_summary(self, tmp_path):
        result = _make_result(success=True)
        run_id = versioning.record_run(tmp_path / "results", "sess-1", "pass", result, tmp_path / "shared")
        index = json.loads((tmp_path / "results" / "index.json").read_text())
        assert len(index) == 1
        entry = index[0]
        assert entry["run_id"] == run_id
        assert entry["session_id"] == "sess-1"
        assert entry["success"] is True
        assert "timestamp" in entry
        assert "content_hash" in entry

    def test_index_newest_first(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        results_dir = tmp_path / "results"
        id1 = versioning.record_run(results_dir, "s", "print(1)", _make_result(stdout="1"), shared)
        id2 = versioning.record_run(results_dir, "s", "print(2)", _make_result(stdout="2"), shared)
        id3 = versioning.record_run(results_dir, "s", "print(3)", _make_result(stdout="3"), shared)
        index = json.loads((results_dir / "index.json").read_text())
        assert [e["run_id"] for e in index] == [id3, id2, id1]

    def test_multiple_runs_accumulate_in_index(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        results_dir = tmp_path / "results"
        for i in range(5):
            versioning.record_run(results_dir, "s", f"print({i})", _make_result(stdout=str(i)), shared)
        index = json.loads((results_dir / "index.json").read_text())
        assert len(index) == 5


class TestVersioningDeduplication:
    def test_identical_run_returns_same_id(self, tmp_path):
        result = _make_result(stdout="42")
        id1 = versioning.record_run(tmp_path / "results", "s", "print(42)", result, tmp_path / "shared")
        id2 = versioning.record_run(tmp_path / "results", "s", "print(42)", result, tmp_path / "shared")
        assert id1 == id2

    def test_duplicate_does_not_grow_index(self, tmp_path):
        results_dir = tmp_path / "results"
        result = _make_result(stdout="42")
        versioning.record_run(results_dir, "s", "print(42)", result, tmp_path / "shared")
        versioning.record_run(results_dir, "s", "print(42)", result, tmp_path / "shared")
        index = json.loads((results_dir / "index.json").read_text())
        assert len(index) == 1

    def test_different_stdout_is_new_record(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        results_dir = tmp_path / "results"
        id1 = versioning.record_run(results_dir, "s", "print(42)", _make_result(stdout="42"), shared)
        id2 = versioning.record_run(results_dir, "s", "print(42)", _make_result(stdout="43"), shared)
        assert id1 != id2
        assert len(json.loads((results_dir / "index.json").read_text())) == 2

    def test_different_code_is_new_record(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        results_dir = tmp_path / "results"
        id1 = versioning.record_run(results_dir, "s", "print(1)", _make_result(stdout="1"), shared)
        id2 = versioning.record_run(results_dir, "s", "print(2)", _make_result(stdout="1"), shared)
        assert id1 != id2


class TestVersioningSessionGrouping:
    def test_session_id_stored_in_record(self, tmp_path):
        result = _make_result()
        run_id = versioning.record_run(tmp_path / "results", "my-session", "pass", result, tmp_path / "shared")
        record = json.loads((tmp_path / "results" / run_id / "record.json").read_text())
        assert record["session_id"] == "my-session"

    def test_different_sessions_tracked_separately(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        results_dir = tmp_path / "results"
        versioning.record_run(results_dir, "sess-A", "print(1)", _make_result(stdout="1"), shared)
        versioning.record_run(results_dir, "sess-B", "print(2)", _make_result(stdout="2"), shared)
        index = json.loads((results_dir / "index.json").read_text())
        sessions = {e["session_id"] for e in index}
        assert sessions == {"sess-A", "sess-B"}


# ==========================================
# TC-1-xx: File output path documentation and error handling
# ==========================================

class TestFileOutputPath:
    def test_savefig_wrong_path_raises_helpful_error(self, scratchpad, event_loop):
        """TC-1-02: plt.savefig to unsupported path raises FileNotFoundError mentioning /shared/."""
        result = run(event_loop, scratchpad.execute(
            "plt.savefig('/home/claude/test.png')"
        ))
        assert not result.success
        assert result.error is not None
        assert "/shared/" in result.error


# ==========================================
# TC-2-xx: figures_saved in run_code result envelope
# ==========================================

class TestFiguresSavedInResult:
    def test_autosave_path_in_result(self, scratchpad, event_loop):
        """TC-2-01: Auto-named figure path is included in result.figures with full /shared/ prefix."""
        result = run(event_loop, scratchpad.execute(
            "plt.plot([1, 2, 3])\n"
            "plt.show()"
        ))
        assert result.success
        assert len(result.figures) > 0
        assert all(f.startswith("/shared/") for f in result.figures)

    def test_named_savefig_path_in_result(self, scratchpad, event_loop):
        """TC-2-02: Explicit plt.savefig path is echoed in result.figures; no list_figures call needed."""
        result = run(event_loop, scratchpad.execute(
            "plt.savefig('/shared/named.png')\n"
            "plt.close()"
        ))
        assert result.success
        assert "/shared/named.png" in result.figures

    def test_multiple_figures_in_one_call(self, scratchpad, event_loop):
        """TC-2-03: Two figures created in one execution produce two entries in result.figures."""
        result = run(event_loop, scratchpad.execute(
            "import matplotlib.pyplot as plt\n"
            "fig1 = plt.figure()\n"
            "plt.plot([1, 2])\n"
            "fig2 = plt.figure()\n"
            "plt.plot([3, 4])\n"
        ))
        assert result.success
        assert len(result.figures) == 2
        assert all(f.startswith("/shared/") for f in result.figures)

    def test_cv2_imwrite_path_in_result(self, scratchpad, event_loop):
        """TC-2-04: cv2.imwrite path appears in result.figures."""
        result = run(event_loop, scratchpad.execute(
            "import numpy as np\n"
            "import cv2\n"
            "arr = np.zeros((50, 50, 3), dtype=np.uint8)\n"
            "cv2.imwrite('/shared/cv_out.png', arr)"
        ))
        assert result.success
        assert "/shared/cv_out.png" in result.figures

    def test_no_figures_returns_empty_list(self, scratchpad, event_loop):
        """TC-2-06: Code with no plot or imwrite calls produces an empty figures list, not None."""
        result = run(event_loop, scratchpad.execute("x = 1 + 1"))
        assert result.success
        assert result.figures == []


# ==========================================
# TC-4-xx: Session persistence semantics
# ==========================================

class TestSessionPersistence:
    def test_import_persists_across_calls(self, scratchpad, event_loop):
        """TC-4-02: An import in call 1 is available in call 2."""
        r1 = run(event_loop, scratchpad.execute("import numpy as np"))
        assert r1.success

        r2 = run(event_loop, scratchpad.execute("print(np.pi)"))
        assert r2.success
        assert "3.14159" in r2.stdout

    def test_exception_does_not_clear_prior_names(self, scratchpad, event_loop):
        """TC-4-03: An exception in call 2 does not wipe names defined in call 1."""
        r1 = run(event_loop, scratchpad.execute("y = 99"))
        assert r1.success

        r2 = run(event_loop, scratchpad.execute("raise ValueError('oops')"))
        assert not r2.success

        r3 = run(event_loop, scratchpad.execute("print(y)"))
        assert r3.success
        assert "99" in r3.stdout

    def test_partial_execution_retains_pre_error_names(self, scratchpad, event_loop):
        """TC-4-04: Names bound before the failing line are retained; names after are not."""
        r1 = run(event_loop, scratchpad.execute(
            "a = 1\n"
            "b = 2\n"
            "raise RuntimeError('stop here')\n"
            "c = 3\n"
        ))
        assert not r1.success

        r2 = run(event_loop, scratchpad.execute("print(a + b)"))
        assert r2.success
        assert "3" in r2.stdout

        r3 = run(event_loop, scratchpad.execute("print(c)"))
        assert not r3.success
        assert "NameError" in r3.error


# ==========================================
# copy_file_to_scratchpad (no Docker required)
# ==========================================

class TestCopyFileToScratchpad:
    def test_copies_file_to_shared_dir(self, tmp_path, monkeypatch):
        import scratchpad_server
        monkeypatch.setattr(scratchpad_server, "SHARED_DIR", tmp_path / "shared")

        src = tmp_path / "capture.jpg"
        src.write_bytes(b"fake jpeg data")

        result = asyncio.run(scratchpad_server.copy_file_to_scratchpad(str(src)))

        dest = tmp_path / "shared" / "capture.jpg"
        assert dest.exists()
        assert dest.read_bytes() == b"fake jpeg data"
        assert "/shared/capture.jpg" in result

    def test_custom_dest_filename(self, tmp_path, monkeypatch):
        import scratchpad_server
        monkeypatch.setattr(scratchpad_server, "SHARED_DIR", tmp_path / "shared")

        src = tmp_path / "capture_001.jpg"
        src.write_bytes(b"image data")

        result = asyncio.run(scratchpad_server.copy_file_to_scratchpad(str(src), "renamed.jpg"))

        assert (tmp_path / "shared" / "renamed.jpg").exists()
        assert not (tmp_path / "shared" / "capture_001.jpg").exists()
        assert "/shared/renamed.jpg" in result

    def test_source_not_found_returns_error(self, tmp_path, monkeypatch):
        import scratchpad_server
        monkeypatch.setattr(scratchpad_server, "SHARED_DIR", tmp_path / "shared")

        result = asyncio.run(scratchpad_server.copy_file_to_scratchpad("/nonexistent/file.jpg"))

        assert result.startswith("Error:")
        assert "not found" in result

    def test_source_is_directory_returns_error(self, tmp_path, monkeypatch):
        import scratchpad_server
        monkeypatch.setattr(scratchpad_server, "SHARED_DIR", tmp_path / "shared")

        result = asyncio.run(scratchpad_server.copy_file_to_scratchpad(str(tmp_path)))

        assert result.startswith("Error:")
        assert "not a file" in result

    def test_creates_shared_dir_if_missing(self, tmp_path, monkeypatch):
        import scratchpad_server
        shared = tmp_path / "shared"
        monkeypatch.setattr(scratchpad_server, "SHARED_DIR", shared)
        assert not shared.exists()

        src = tmp_path / "data.npy"
        src.write_bytes(b"\x93NUMPY fake")

        asyncio.run(scratchpad_server.copy_file_to_scratchpad(str(src)))

        assert shared.exists()
        assert (shared / "data.npy").exists()

"""
Tests for the Python scratchpad Docker backend.

Requires Docker to be available. Tests build the image, start a container,
and exercise numeric, symbolic, plotting, stateful, and security scenarios.
"""

import asyncio
import pytest

from scratchpad.docker_backend import DockerScratchpad


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
        fig_path = scratchpad.shared_dir / result.figures[0]
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

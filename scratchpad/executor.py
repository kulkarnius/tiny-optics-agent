"""
Persistent Python REPL server that runs inside the Docker container.

Reads JSON-line commands from stdin, executes code in a persistent namespace,
and writes JSON-line responses to stdout. All debug output goes to stderr.
"""

import json
import os
import signal
import sys
import traceback
from io import StringIO


def _init_namespace():
    """Create the initial namespace with convenience imports."""
    ns = {}
    exec(
        "import numpy as np\n"
        "import scipy\n"
        "import sympy\n"
        "import cv2\n"
        "import matplotlib\n"
        "import matplotlib.pyplot as plt\n",
        ns,
    )

    return ns


def _get_shared_images():
    """Return set of full /shared/ paths for image files currently in /shared."""
    exts = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}
    try:
        return {
            f"/shared/{f}" for f in os.listdir("/shared")
            if os.path.splitext(f)[1].lower() in exts
        }
    except OSError:
        return set()


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Execution timed out")


def execute(code, namespace, timeout):
    """Execute code in namespace with timeout, return result dict."""
    stdout_capture = StringIO()
    stderr_capture = StringIO()

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    images_before = _get_shared_images()

    error = None
    success = True

    # Set timeout
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        exec(code, namespace)
    except TimeoutError as e:
        error = str(e)
        success = False
    except Exception:
        error = traceback.format_exc()
        # Augment FileNotFoundError on non-/shared/ paths with actionable guidance
        if "FileNotFoundError" in error and "/shared/" not in error:
            import re as _re
            m = _re.search(r"No such file or directory: '([^']+)'", error)
            if m and not m.group(1).startswith("/shared/"):
                error += (
                    "\nNote: the scratchpad sandbox only allows writing to /shared/. "
                    "Use plt.savefig('/shared/name.png') or cv2.imwrite('/shared/name.png', img)."
                )
        success = False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    # Auto-save any unsaved matplotlib figures
    figures_saved = []
    try:
        plt = namespace.get("plt")
        if plt and plt.get_fignums():
            import time
            ts = int(time.time() * 1000)
            for i, num in enumerate(plt.get_fignums()):
                fig = plt.figure(num)
                fname = f"figure_{ts}_{i + 1}.png"
                fpath = f"/shared/{fname}"
                fig.savefig(fpath, dpi=150, bbox_inches="tight")
                figures_saved.append(fpath)
            plt.close("all")
    except Exception as e:
        print(f"Warning: failed to auto-save figures: {e}", file=sys.stderr)

    # Detect any new image files written directly (e.g. cv2.imwrite)
    images_after = _get_shared_images()
    new_images = images_after - images_before
    for img in sorted(new_images):
        if img not in figures_saved:
            figures_saved.append(img)

    return {
        "stdout": stdout_capture.getvalue(),
        "stderr": stderr_capture.getvalue(),
        "error": error,
        "figures": figures_saved,
        "success": success,
    }


def main():
    """Main REPL loop: read JSON lines from stdin, write JSON lines to stdout."""
    # All debug output to stderr
    print("executor: starting persistent session", file=sys.stderr)

    namespace = _init_namespace()

    print("executor: namespace initialized, ready for commands", file=sys.stderr)
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            result = {
                "stdout": "",
                "stderr": "",
                "error": f"Invalid JSON: {e}",
                "figures": [],
                "success": False,
            }
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.flush()
            continue

        code = request.get("code", "")
        timeout = request.get("timeout", 30)

        result = execute(code, namespace, timeout)
        sys.stdout.write(json.dumps(result) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

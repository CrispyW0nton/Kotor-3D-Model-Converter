"""Shared utilities for test profiling, benchmarking, and timeout management.

This module provides cross-platform test timeout and profiling infrastructure
using multiprocessing instead of threading for proper isolation.
"""

from __future__ import annotations

import cProfile
import os
import pstats
import re
import time

from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator


def get_profile_threshold_ms() -> int:
    """Get the profiling threshold from environment variable.

    Returns:
        Threshold in milliseconds. 0 means profiling is disabled.
    """
    raw = os.environ.get("PYKOTOR_PROFILE_SLOW_MS", "0").strip()
    try:
        return int(raw)
    except ValueError:
        return 0


def get_test_timeout_seconds() -> int:
    """Get the per-test timeout from environment variable.

    Returns:
        Timeout in seconds. 0 means no timeout enforcement (relies on pytest-timeout).
    """
    raw = os.environ.get("PYKOTOR_TEST_TIMEOUT_SECONDS", "0").strip()
    try:
        return int(raw)
    except ValueError:
        return 0


def safe_nodeid_to_filename(nodeid: str) -> str:
    """Convert a pytest nodeid to a safe filename.

    Args:
        nodeid: The pytest node ID (e.g., "test_foo.py::TestClass::test_method")

    Returns:
        A sanitized filename string.
    """
    s = nodeid.replace("::", "__")
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
    return s[:180]


def get_profiling_output_dir() -> Path:
    """Get the directory for profiling outputs.

    Returns:
        Path to the profiling directory (creates if needed).
    """
    # Assumes this file is at Libraries/PyKotor/tests/test_helpers/
    out_dir = Path(__file__).resolve().parents[4] / "profiling"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def dump_profile_stats(
    profiler: cProfile.Profile,
    nodeid: str,
    duration_ms: int | None = None,
    phase: str = "call",
) -> None:
    """Dump profiling statistics to disk.

    Args:
        profiler: The cProfile.Profile instance with collected data.
        nodeid: The pytest node ID.
        duration_ms: Optional duration in milliseconds.
        phase: Test phase ("call", "setup", "teardown").
    """
    out_dir = get_profiling_output_dir()
    base = safe_nodeid_to_filename(nodeid)

    suffix = f"__{phase}" if phase != "call" else ""
    pstat_path = out_dir / f"{base}{suffix}.pstat"
    txt_path = out_dir / f"{base}{suffix}.txt"

    profiler.dump_stats(str(pstat_path))
    with txt_path.open("w", encoding="utf-8") as f:
        stats = pstats.Stats(profiler, stream=f)
        stats.strip_dirs()
        stats.sort_stats("cumulative")
        f.write(f"nodeid: {nodeid}\n")
        f.write(f"phase: {phase}\n")
        f.write(f"threshold_ms: {get_profile_threshold_ms()}\n")
        if duration_ms is not None:
            f.write(f"duration_ms: {duration_ms}\n")
        f.write("\n")
        stats.print_stats(80)
        f.write("\n\n---- callers (top 40) ----\n")
        stats.print_callers(40)


@contextmanager
def profile_if_enabled(nodeid: str, phase: str = "call") -> Iterator[None]:
    """Context manager to profile code if profiling is enabled.

    Args:
        nodeid: The pytest node ID.
        phase: Test phase ("call", "setup", "teardown").

    Yields:
        None
    """
    threshold = get_profile_threshold_ms()
    if threshold <= 0:
        yield
        return

    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.enable()
    try:
        yield
    finally:
        profiler.disable()
        dur_ms = int((time.perf_counter() - start) * 1000)

        if dur_ms >= threshold:
            dump_profile_stats(profiler, nodeid, dur_ms, phase)


def _run_test_with_timeout_worker(
    test_callable: Callable[[], Any],
    timeout_seconds: int,
) -> tuple[bool, Any, str]:
    """Worker function to run a test with timeout in a separate process.

    NOTE: This approach doesn't work well with Qt tests because Qt objects
    cannot be pickled for inter-process communication. For Qt tests, rely
    on pytest-timeout configured in pyproject.toml instead.

    Args:
        test_callable: The test function to execute.
        timeout_seconds: Maximum execution time in seconds.

    Returns:
        Tuple of (success: bool, result: Any, error_message: str)
    """
    try:
        result = test_callable()
        return True, result, ""
    except Exception as e:
        import traceback

        return False, None, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"


def run_test_with_timeout(
    test_callable: Callable[[], Any],
    timeout_seconds: int | None = None,
    test_name: str = "unknown",
) -> Any:
    """Run a test function with a timeout using multiprocessing.

    WARNING: This approach does NOT work with Qt tests because Qt objects cannot
    be pickled for inter-process communication. For Qt tests, configure pytest-timeout
    in pyproject.toml instead:

        [tool.pytest.ini_options]
        timeout = 120
        timeout_method = "thread"

    This function is provided for non-Qt tests that need explicit timeout control.

    Args:
        test_callable: The test function to execute.
        timeout_seconds: Maximum execution time. Uses PYKOTOR_TEST_TIMEOUT_SECONDS if None.
        test_name: Name of the test for error messages.

    Returns:
        The result of the test function.

    Raises:
        TimeoutError: If the test exceeds the timeout.
        Exception: Any exception raised by the test function.
    """
    if timeout_seconds is None:
        timeout_seconds = get_test_timeout_seconds()

    if timeout_seconds <= 0:
        # No timeout enforcement - rely on pytest-timeout
        return test_callable()

    # Use ProcessPoolExecutor for cross-platform timeout support
    # NOTE: This will NOT work with Qt objects!
    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_test_with_timeout_worker, test_callable, timeout_seconds)
        try:
            success, result, error_msg = future.result(timeout=timeout_seconds)
            if not success:
                raise RuntimeError(f"Test failed in subprocess:\n{error_msg}")
            return result
        except FuturesTimeoutError as e:
            msg = f"Test '{test_name}' exceeded timeout of {timeout_seconds} seconds"
            raise TimeoutError(msg) from e


# Pytest integration note:
# The profile_if_enabled context manager should be used directly in conftest.py
# pytest hooks (pytest_runtest_call, pytest_runtest_setup, pytest_runtest_makereport)
# to enable profiling for slow tests.

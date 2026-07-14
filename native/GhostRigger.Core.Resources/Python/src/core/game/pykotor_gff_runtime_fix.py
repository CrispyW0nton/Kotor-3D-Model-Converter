"""Quiet the known PyKotor 2.3.1 ``GFFStruct.acquire`` debug build.

Some released PyKotor 2.3.1 wheels contain a stray ``print`` in
``GFFStruct.acquire``.  Stock-module hydration calls that method for thousands
of fields, so the debug output both floods GhostStudio's terminal and adds a
measurable import stall.

This module never modifies site-packages.  It applies a process-local method
replacement only when the executable body exactly matches the known noisy
implementation.  Clean/upstream implementations are left untouched.
"""

from __future__ import annotations

import ast
import dis
import inspect
import logging
import textwrap
import threading
from functools import lru_cache, wraps
from typing import Any


log = logging.getLogger(__name__)

_EXPECTED_PARAMETERS = ("self", "label", "default", "object_type")
_PATCH_MARKER = "__ghostrigger_quiet_gff_acquire__"
_lock = threading.RLock()

_last_status: dict[str, Any] = {
    "checked": False,
    "status": "not_checked",
    "applied": False,
    "changed": False,
    "detail": "",
    "implementation_module": "",
}

# The body below is the exact executable body shipped by the noisy PyKotor
# 2.3.1 builds.  Comparing an AST (rather than a version string) keeps the guard
# narrow while tolerating harmless whitespace and annotation formatting.
_KNOWN_NOISY_BODY_SOURCE = """
def acquire(self, label, default, object_type=None):
    default_cls = default.__class__
    assert isinstance(default, object), f"{default_cls.__name__}: {default}"
    value: T = default
    if object_type is None:
        object_type = default_cls
    if self.exists(label) and object_type is not None:
        value = self[label]
        try:
            print(f"value: {value} cls: {value.__class__} (isinstance? {isinstance(value, object_type)} {object_type})")
        except Exception:
            ...
    if object_type is bool and issubclass(value.__class__, int):
        value = bool(value)
    return value
"""


def _known_noisy_reference(self, label, default, object_type=None):
    """Bytecode oracle used only when source inspection is unavailable."""
    default_cls = default.__class__
    assert isinstance(default, object), f"{default_cls.__name__}: {default}"
    value: Any = default
    if object_type is None:
        object_type = default_cls
    if self.exists(label) and object_type is not None:
        value = self[label]
        try:
            print(f"value: {value} cls: {value.__class__} (isinstance? {isinstance(value, object_type)} {object_type})")
        except Exception:
            ...
    if object_type is bool and issubclass(value.__class__, int):
        value = bool(value)
    return value


@lru_cache(maxsize=1)
def _known_noisy_ast() -> str:
    tree = ast.parse(textwrap.dedent(_KNOWN_NOISY_BODY_SOURCE))
    function = tree.body[0]
    assert isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
    return ast.dump(ast.Module(body=function.body, type_ignores=[]), include_attributes=False)


def _method_body_ast(method: Any) -> str | None:
    try:
        source = textwrap.dedent(inspect.getsource(method))
        tree = ast.parse(source)
    except (IndentationError, OSError, SyntaxError, TypeError):
        return None
    function = next(
        (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))),
        None,
    )
    if function is None:
        return None
    body = list(function.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    return ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)


def _instruction_fingerprint(method: Any) -> tuple[tuple[str, Any], ...] | None:
    try:
        return tuple((instruction.opname, instruction.argval) for instruction in dis.get_instructions(method))
    except (TypeError, ValueError):
        return None


def _is_known_noisy_acquire(method: Any) -> bool:
    try:
        parameters = tuple(inspect.signature(method).parameters)
    except (TypeError, ValueError):
        return False
    if parameters != _EXPECTED_PARAMETERS:
        return False

    body_ast = _method_body_ast(method)
    if body_ast is not None:
        return body_ast == _known_noisy_ast()

    # Embedded/frozen environments may not retain source.  The comparison is
    # still exact because both functions are compiled by the running Python.
    return _instruction_fingerprint(method) == _instruction_fingerprint(_known_noisy_reference)


def _quiet_acquire_for(original: Any):
    @wraps(original)
    def acquire(self, label, default, object_type=None):
        # Semantics-equivalent to the known PyKotor implementation, excluding
        # only its diagnostic print/exception wrapper.
        default_cls = default.__class__
        assert isinstance(default, object), f"{default_cls.__name__}: {default}"
        value = default
        if object_type is None:
            object_type = default_cls
        if self.exists(label) and object_type is not None:
            value = self[label]
        if object_type is bool and issubclass(value.__class__, int):
            value = bool(value)
        return value

    setattr(acquire, _PATCH_MARKER, True)
    return acquire


def _record_status(**values: Any) -> dict[str, Any]:
    _last_status.clear()
    _last_status.update(values)
    return dict(_last_status)


def ensure_pykotor_gff_acquire_quiet(gff_struct_class: type | None = None) -> dict[str, Any]:
    """Apply the exact PyKotor 2.3.1 quiet-acquire compatibility guard.

    Passing ``gff_struct_class`` is supported for focused compatibility tests.
    Normal callers omit it and the installed PyKotor ``GFFStruct`` is resolved
    lazily.  The returned dictionary is suitable for startup diagnostics.
    """
    with _lock:
        if gff_struct_class is None:
            try:
                from pykotor.resource.formats.gff.gff_data import GFFStruct
            except Exception as exc:
                return _record_status(
                    checked=True,
                    status="pykotor_unavailable",
                    applied=False,
                    changed=False,
                    detail=str(exc),
                    implementation_module="",
                )
            gff_struct_class = GFFStruct

        method = getattr(gff_struct_class, "acquire", None)
        module_name = str(getattr(method, "__module__", ""))
        if method is None:
            return _record_status(
                checked=True,
                status="unsupported",
                applied=False,
                changed=False,
                detail="GFFStruct.acquire is missing",
                implementation_module=module_name,
            )

        if bool(getattr(method, _PATCH_MARKER, False)):
            return _record_status(
                checked=True,
                status="already_patched",
                applied=True,
                changed=False,
                detail="",
                implementation_module=module_name,
            )

        if not _is_known_noisy_acquire(method):
            return _record_status(
                checked=True,
                status="upstream_clean",
                applied=False,
                changed=False,
                detail="Known PyKotor 2.3.1 debug implementation was not detected",
                implementation_module=module_name,
            )

        replacement = _quiet_acquire_for(method)
        try:
            setattr(gff_struct_class, "acquire", replacement)
        except Exception as exc:
            log.warning("Could not quiet PyKotor GFFStruct.acquire: %s", exc)
            return _record_status(
                checked=True,
                status="patch_failed",
                applied=False,
                changed=False,
                detail=str(exc),
                implementation_module=module_name,
            )

        log.debug("Applied process-local quiet guard to PyKotor GFFStruct.acquire")
        return _record_status(
            checked=True,
            status="patched",
            applied=True,
            changed=True,
            detail="",
            implementation_module=module_name,
        )


def pykotor_gff_runtime_fix_status() -> dict[str, Any]:
    """Return a copy of the most recent compatibility-check status."""
    with _lock:
        return dict(_last_status)


__all__ = ["ensure_pykotor_gff_acquire_quiet", "pykotor_gff_runtime_fix_status"]

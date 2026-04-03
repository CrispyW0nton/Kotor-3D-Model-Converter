"""Format conversion command implementations for Pykotorcli.

This module provides CLI commands for converting between different file formats
(GFF<->XML, TLK<->XML, SSF<->XML, 2DA<->CSV, etc.) using PyKotor utilities.
"""

from __future__ import annotations

import pathlib

from typing import TYPE_CHECKING, Callable

from pykotor.tools.conversions import (
    convert_2da_to_csv,
    convert_csv_to_2da,
    convert_gff_to_json,
    convert_gff_to_xml,
    convert_json_to_gff,
    convert_ssf_to_xml,
    convert_tlk_to_json,
    convert_tlk_to_xml,
    convert_xml_to_gff,
    convert_xml_to_ssf,
    convert_xml_to_tlk,
)

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger as Logger


def _run_conversion(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    conversion_func: Callable,
    logger: Logger,
    **kwargs,
) -> int:
    """Execute a format conversion with consistent error handling and logging.

    Args:
    ----
        input_path: Source file path
        output_path: Destination file path
        conversion_func: The conversion function to call
        logger: Logger instance for messages
        **kwargs: Additional arguments to pass to conversion_func

    Returns:
    -------
        0 on success, 1 on failure
    """
    try:
        conversion_func(input_path, output_path, **kwargs)
        logger.info(f"Converted {input_path.name} to {output_path.name}")  # noqa: G004
    except Exception:
        logger.exception(f"Failed to convert {input_path}")  # noqa: G004
        return 1
    return 0


def cmd_gff2xml(args: Namespace, logger: Logger) -> int:
    """Convert GFF file to XML format.

    References:
    ----------
        KotOR I (swkotor.exe) / KotOR II (swkotor2.exe):
            - GFF structures are loaded via CResGFF class throughout the engine
            - See individual resource format files (uti.py, utc.py, utp.py, dlg/base.py, etc.) for specific GFF field references
    """
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".xml")
    return _run_conversion(input_path, output_path, convert_gff_to_xml, logger)


def cmd_xml2gff(args: Namespace, logger: Logger) -> int:
    """Convert XML file to GFF format.

    References:
    ----------
        KotOR I (swkotor.exe) / KotOR II (swkotor2.exe):
            - GFF structures are loaded via CResGFF class throughout the engine
            - See individual resource format files (uti.py, utc.py, utp.py, dlg/base.py, etc.) for specific GFF field references
    """
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".gff")
    kwargs = {"gff_content_type": args.type} if hasattr(args, "type") else {}
    return _run_conversion(input_path, output_path, convert_xml_to_gff, logger, **kwargs)


def cmd_tlk2xml(args: Namespace, logger: Logger) -> int:
    """Convert TLK file to XML format.

    References:
    ----------
        KotOR I (swkotor.exe) / KotOR II (swkotor2.exe):
            - GFF structures are loaded via CResGFF class throughout the engine
            - See individual resource format files (uti.py, utc.py, utp.py, dlg/base.py, etc.) for specific GFF field references
    """
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".xml")
    return _run_conversion(input_path, output_path, convert_tlk_to_xml, logger)


def cmd_xml2tlk(args: Namespace, logger: Logger) -> int:
    """Convert XML file to TLK format.

    References:
    ----------
        KotOR I (swkotor.exe) / KotOR II (swkotor2.exe):
            - GFF structures are loaded via CResGFF class throughout the engine
            - See individual resource format files (uti.py, utc.py, utp.py, dlg/base.py, etc.) for specific GFF field references
    """
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".tlk")
    return _run_conversion(input_path, output_path, convert_xml_to_tlk, logger)


def cmd_ssf2xml(args: Namespace, logger: Logger) -> int:
    """Convert SSF file to XML format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".xml")
    return _run_conversion(input_path, output_path, convert_ssf_to_xml, logger)


def cmd_xml2ssf(args: Namespace, logger: Logger) -> int:
    """Convert XML file to SSF format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".ssf")
    return _run_conversion(input_path, output_path, convert_xml_to_ssf, logger)


def cmd_2da2csv(args: Namespace, logger: Logger) -> int:
    """Convert 2DA file to CSV format.

    References:
    ----------
        KotOR I (swkotor.exe) / KotOR II (swkotor2.exe):
            - 2DA structures loaded via C2DA class
            - See individual resource format files (uti.py, utc.py, utp.py, dlg/base.py, etc.) for specific GFF field references
    """
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".csv")
    delimiter = args.delimiter if hasattr(args, "delimiter") else ","
    return _run_conversion(input_path, output_path, convert_2da_to_csv, logger, delimiter=delimiter)


def cmd_csv22da(args: Namespace, logger: Logger) -> int:
    """Convert CSV file to 2DA format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".2da")
    delimiter = args.delimiter if hasattr(args, "delimiter") else ","
    return _run_conversion(input_path, output_path, convert_csv_to_2da, logger, delimiter=delimiter)


def cmd_gff2json(args: Namespace, logger: Logger) -> int:
    """Convert GFF file to JSON format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".json")
    return _run_conversion(input_path, output_path, convert_gff_to_json, logger)


def cmd_json2gff(args: Namespace, logger: Logger) -> int:
    """Convert JSON file to GFF format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".gff")
    kwargs = {"gff_content_type": args.type} if hasattr(args, "type") else {}
    return _run_conversion(input_path, output_path, convert_json_to_gff, logger, **kwargs)


def cmd_tlk2json(args: Namespace, logger: Logger) -> int:
    """Convert TLK file to JSON format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".json")
    return _run_conversion(input_path, output_path, convert_tlk_to_json, logger)

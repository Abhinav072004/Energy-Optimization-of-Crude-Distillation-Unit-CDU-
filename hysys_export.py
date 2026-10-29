#!/usr/bin/env python3
"""Export an already-open HYSYS case on Windows for portable pinch analysis."""

import argparse
import csv
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import sys
import tempfile

from cdu.hysys import export_case


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", dest="mapping_path", required=True, type=Path, help="JSON mapping of sensible inlet/outlet stream pairs")
    parser.add_argument("--output", type=Path, default=Path("outputs/hysys_streams.csv"), help="CSV for cdu_pinch_analysis.py")
    parser.add_argument("--metadata", type=Path, default=Path("outputs/hysys_export.json"), help="JSON source measurements and provenance")
    args = parser.parse_args(argv)
    temporary_paths = []
    try:
        if len({path.resolve() for path in (args.mapping_path, args.output, args.metadata)}) != 3:
            raise ValueError("Mapping, CSV output and metadata output must use different paths")
        mapping = json.loads(args.mapping_path.read_text(encoding="utf-8-sig"))
        streams, metadata = export_case(mapping)
        csv_buffer = io.StringIO(newline="")
        writer = csv.DictWriter(csv_buffer, fieldnames=("name", "kind", "supply_c", "target_c", "cp_kw_per_k"))
        writer.writeheader()
        writer.writerows(asdict(stream) for stream in streams)
        contents = ((args.output, csv_buffer.getvalue()),
                    (args.metadata, json.dumps(metadata, indent=2, allow_nan=False) + "\n"))
        # Complete extraction and serialization before creating output files.
        for destination, content in contents:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", prefix=".hysys-export-", dir=destination.parent, delete=False) as handle:
                temporary = Path(handle.name)
                temporary_paths.append(temporary)
                handle.write(content)
        for temporary, (destination, _) in zip(temporary_paths, contents):
            os.replace(temporary, destination)
        print(f"Exported {len(streams)} sensible segments from {metadata['case_title']}")
        print(f"CSV: {args.output}\nMetadata: {args.metadata}")
        print("Case convergence and sensible-only behavior are user-confirmed, not verified by this exporter.")
        return 0
    except (OSError, ValueError, OverflowError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        for temporary in temporary_paths:
            if temporary.exists():
                temporary.unlink()


if __name__ == "__main__":
    raise SystemExit(main())

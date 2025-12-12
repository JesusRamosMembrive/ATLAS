#!/usr/bin/env python3
"""Validate JSON output schema from similarity detector."""
import json
import subprocess
import sys


def validate_schema(data: dict) -> list[str]:
    """Validate the JSON output schema and return any errors."""
    errors = []

    # Required top-level keys
    required_keys = ["clones", "hotspots", "metrics", "summary", "timing"]
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    # Validate summary
    if "summary" in data:
        summary = data["summary"]
        summary_keys = [
            "analysis_time_ms",
            "clone_pairs_found",
            "estimated_duplication",
            "files_analyzed",
            "total_lines",
        ]
        for key in summary_keys:
            if key not in summary:
                errors.append(f"summary missing key: {key}")

        # Type checks
        if "analysis_time_ms" in summary and not isinstance(
            summary["analysis_time_ms"], int
        ):
            errors.append("summary.analysis_time_ms should be int")
        if "clone_pairs_found" in summary and not isinstance(
            summary["clone_pairs_found"], int
        ):
            errors.append("summary.clone_pairs_found should be int")
        if "files_analyzed" in summary and not isinstance(
            summary["files_analyzed"], int
        ):
            errors.append("summary.files_analyzed should be int")
        if "total_lines" in summary and not isinstance(summary["total_lines"], int):
            errors.append("summary.total_lines should be int")
        if "estimated_duplication" in summary and not isinstance(
            summary["estimated_duplication"], str
        ):
            errors.append("summary.estimated_duplication should be string")

    # Validate timing
    if "timing" in data:
        timing = data["timing"]
        timing_keys = ["hash_ms", "match_ms", "tokenize_ms", "total_ms"]
        for key in timing_keys:
            if key not in timing:
                errors.append(f"timing missing key: {key}")
            elif not isinstance(timing[key], int):
                errors.append(f"timing.{key} should be int")

    # Validate metrics
    if "metrics" in data:
        metrics = data["metrics"]
        if "by_language" not in metrics:
            errors.append("metrics missing by_language")
        if "by_type" not in metrics:
            errors.append("metrics missing by_type")

    # Validate clones array
    if "clones" in data:
        if not isinstance(data["clones"], list):
            errors.append("clones should be array")
        else:
            for i, clone in enumerate(data["clones"]):
                clone_keys = ["id", "locations", "recommendation", "similarity", "type"]
                for key in clone_keys:
                    if key not in clone:
                        errors.append(f"clones[{i}] missing key: {key}")

                if "locations" in clone:
                    if (
                        not isinstance(clone["locations"], list)
                        or len(clone["locations"]) < 2
                    ):
                        errors.append(
                            f"clones[{i}].locations should have at least 2 locations"
                        )
                    else:
                        for j, loc in enumerate(clone["locations"]):
                            loc_keys = [
                                "end_line",
                                "file",
                                "snippet_preview",
                                "start_line",
                            ]
                            for key in loc_keys:
                                if key not in loc:
                                    errors.append(
                                        f"clones[{i}].locations[{j}] missing key: {key}"
                                    )

                if "similarity" in clone:
                    if not isinstance(clone["similarity"], (int, float)):
                        errors.append(f"clones[{i}].similarity should be number")
                    elif not (0.0 <= clone["similarity"] <= 1.0):
                        errors.append(
                            f"clones[{i}].similarity should be between 0 and 1"
                        )

    # Validate hotspots array
    if "hotspots" in data:
        if not isinstance(data["hotspots"], list):
            errors.append("hotspots should be array")
        else:
            for i, hotspot in enumerate(data["hotspots"]):
                hotspot_keys = [
                    "clone_count",
                    "duplication_score",
                    "file",
                    "recommendation",
                ]
                for key in hotspot_keys:
                    if key not in hotspot:
                        errors.append(f"hotspots[{i}] missing key: {key}")

    return errors


def main():
    # Run the detector and capture output
    result = subprocess.run(
        ["./static_analysis_motor", "--root", "../tests/fixtures", "--ext", ".py"],
        capture_output=True,
        text=True,
        cwd="/home/jesusramos/Workspace/AEGIS/cpp/build",
    )

    if result.returncode != 0:
        print(f"ERROR: Detector failed with code {result.returncode}")
        print(result.stderr)
        sys.exit(1)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON output: {e}")
        sys.exit(1)

    # Validate schema
    errors = validate_schema(data)

    if errors:
        print("SCHEMA VALIDATION FAILED:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print("SCHEMA VALIDATION PASSED")
    print(f"  - {len(data['clones'])} clones validated")
    print(f"  - {len(data['hotspots'])} hotspots validated")
    print("  - All required fields present and correctly typed")

    # Additional checks
    print("\nSample clone entry:")
    if data["clones"]:
        print(json.dumps(data["clones"][0], indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())

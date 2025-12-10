#!/usr/bin/env python3
"""
Precision verification for Code Similarity Detector.
Tests for false positives and false negatives.
"""

import json
import subprocess
import sys
from pathlib import Path

def run_detector(fixture_path: str) -> dict:
    """Run the detector on a fixture path."""
    cmd = [
        "./static_analysis_motor",
        "--root", fixture_path,
        "--ext", ".py"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent / "build")
    return json.loads(result.stdout)

def verify_true_positives():
    """Verify that true duplicates are detected."""
    print("=" * 60)
    print("TEST: True Positives (should be detected)")
    print("=" * 60)

    fixture_path = str(Path(__file__).parent / "fixtures" / "precision")
    result = run_detector(fixture_path)

    clones = result.get("clones", [])

    # Expected true positives in true_positives.py
    expected_cases = [
        ("calculate_total_a", "calculate_total_b"),  # CASE 1
        ("process_user_data", "process_customer_data"),  # CASE 2
        ("format_output_v1", "format_output_v2"),  # CASE 3
        ("validate_input_a", "validate_input_b"),  # CASE 4
        ("ProcessorA.run", "ProcessorB.execute"),  # CASE 5
    ]

    detected_in_true_positives = []
    for clone in clones:
        locations = clone.get("locations", [])
        for loc in locations:
            if "true_positives.py" in loc.get("file", ""):
                detected_in_true_positives.append(clone)
                break

    print(f"\nExpected duplicates: {len(expected_cases)} cases")
    print(f"Detected clones in true_positives.py: {len(detected_in_true_positives)}")

    if detected_in_true_positives:
        print("\n✅ Detected clones:")
        for i, clone in enumerate(detected_in_true_positives, 1):
            locs = clone.get("locations", [])
            lines = [f"  lines {l['start_line']}-{l['end_line']}" for l in locs if "true_positives.py" in l.get("file", "")]
            print(f"  {i}. Type: {clone.get('type')}, Similarity: {clone.get('similarity')}")
            print(f"     Locations: {', '.join(lines)}")

    # We should detect at least some of the expected cases
    success = len(detected_in_true_positives) >= 3  # At least 3 of 5 cases
    print(f"\n{'✅ PASS' if success else '❌ FAIL'}: True positive detection")
    return success, len(detected_in_true_positives)

def verify_true_negatives():
    """Verify that non-duplicates are NOT detected as clones."""
    print("\n" + "=" * 60)
    print("TEST: True Negatives (should NOT be detected as clones)")
    print("=" * 60)

    fixture_path = str(Path(__file__).parent / "fixtures" / "precision")
    result = run_detector(fixture_path)

    clones = result.get("clones", [])

    # Check for false positives in true_negatives.py
    false_positives = []
    for clone in clones:
        locations = clone.get("locations", [])
        files_in_clone = [loc.get("file", "") for loc in locations]

        # A false positive would be a clone ONLY in true_negatives.py
        # (not cross-file clones with true_positives.py)
        if all("true_negatives.py" in f for f in files_in_clone):
            false_positives.append(clone)

    print(f"\nFalse positives found (clones only in true_negatives.py): {len(false_positives)}")

    if false_positives:
        print("\n⚠️ Potential false positives:")
        for i, clone in enumerate(false_positives, 1):
            locs = clone.get("locations", [])
            lines = [f"lines {l['start_line']}-{l['end_line']}" for l in locs]
            print(f"  {i}. Type: {clone.get('type')}, Lines: {', '.join(lines)}")

    # We should have zero or very few false positives in true_negatives.py
    success = len(false_positives) == 0
    print(f"\n{'✅ PASS' if success else '⚠️ WARNING'}: True negative verification")
    return success, len(false_positives)

def verify_cross_file_precision():
    """Verify that we don't get spurious cross-file matches."""
    print("\n" + "=" * 60)
    print("TEST: Cross-file Precision")
    print("=" * 60)

    fixture_path = str(Path(__file__).parent / "fixtures" / "precision")
    result = run_detector(fixture_path)

    clones = result.get("clones", [])

    # Check for clones between true_positives and true_negatives
    cross_matches = []
    for clone in clones:
        locations = clone.get("locations", [])
        files_in_clone = [loc.get("file", "") for loc in locations]

        has_positive = any("true_positives.py" in f for f in files_in_clone)
        has_negative = any("true_negatives.py" in f for f in files_in_clone)

        if has_positive and has_negative:
            cross_matches.append(clone)

    print(f"\nCross-file matches (positive <-> negative): {len(cross_matches)}")

    if cross_matches:
        print("\n⚠️ Cross-file clones found:")
        for i, clone in enumerate(cross_matches, 1):
            locs = clone.get("locations", [])
            print(f"  {i}. Type: {clone.get('type')}")
            for loc in locs:
                print(f"     - {Path(loc['file']).name}:{loc['start_line']}-{loc['end_line']}")

    # Some cross-matches might be legitimate (common patterns)
    # but we should have very few
    success = len(cross_matches) <= 2
    print(f"\n{'✅ PASS' if success else '⚠️ WARNING'}: Cross-file precision")
    return success, len(cross_matches)

def main():
    print("\n" + "=" * 60)
    print("CODE SIMILARITY DETECTOR - PRECISION VERIFICATION")
    print("=" * 60 + "\n")

    tp_success, tp_count = verify_true_positives()
    tn_success, tn_count = verify_true_negatives()
    cf_success, cf_count = verify_cross_file_precision()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\n  True Positives Detected: {tp_count} (expected: 3-5)")
    print(f"  False Positives:         {tn_count} (expected: 0)")
    print(f"  Cross-file Matches:      {cf_count} (expected: ≤2)")

    all_pass = tp_success and tn_success and cf_success

    print(f"\n{'✅ ALL PRECISION TESTS PASSED' if all_pass else '⚠️ SOME TESTS NEED REVIEW'}\n")

    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())

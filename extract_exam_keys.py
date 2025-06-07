#!/usr/bin/env python3
"""
Script to extract and deduplicate keys from physical_exam and lab_test 
across all cases in the case-data directory.
"""

import os
import json
import glob
from typing import Set, Dict, Any

def extract_keys_from_case(case_path: str) -> tuple[Set[str], Set[str]]:
    """
    Extract keys from physical_exam and lab_test from a single case.
    
    Args:
        case_path: Path to the case directory
        
    Returns:
        Tuple of (physical_exam_keys, lab_test_keys)
    """
    physical_exam_keys = set()
    lab_test_keys = set()
    
    test_exam_file = os.path.join(case_path, 'test_exam_data.json')
    
    if not os.path.exists(test_exam_file):
        print(f"Warning: test_exam_data.json not found in {case_path}")
        return physical_exam_keys, lab_test_keys
    
    try:
        with open(test_exam_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract physical_exam keys
        if 'physical_exam' in data and isinstance(data['physical_exam'], dict):
            physical_exam_keys.update(data['physical_exam'].keys())
        
        # Extract lab_test keys
        if 'lab_test' in data and isinstance(data['lab_test'], dict):
            lab_test_keys.update(data['lab_test'].keys())
            
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in {test_exam_file}: {e}")
    except Exception as e:
        print(f"Error processing {test_exam_file}: {e}")
    
    return physical_exam_keys, lab_test_keys

def deduplicate_case_insensitive(keys_set: Set[str]) -> list[str]:
    """
    Deduplicate keys ignoring case, preserving the first occurrence's format.
    
    Args:
        keys_set: Set of keys to deduplicate
        
    Returns:
        List of deduplicated keys with original case preserved
    """
    seen_lowercase = {}
    
    for key in keys_set:
        key_lower = key.lower()
        if key_lower not in seen_lowercase:
            seen_lowercase[key_lower] = key
    
    return sorted(list(seen_lowercase.values()), key=str.lower)

def main():
    """Main function to process all cases and extract keys."""
    
    # Set the case-data directory path
    case_data_dir = "case-data"
    
    if not os.path.exists(case_data_dir):
        print(f"Error: {case_data_dir} directory not found!")
        return
    
    # Initialize sets to store all unique keys
    all_physical_exam_keys = set()
    all_lab_test_keys = set()
    
    # Find all case directories
    case_patterns = [
        os.path.join(case_data_dir, "case*"),
        os.path.join(case_data_dir, "server-cases")
    ]
    
    case_dirs = []
    for pattern in case_patterns:
        case_dirs.extend(glob.glob(pattern))
    
    # Filter to only include directories
    case_dirs = [d for d in case_dirs if os.path.isdir(d)]
    
    print(f"Found {len(case_dirs)} case directories to process...")
    
    processed_cases = 0
    
    # Process each case directory
    for case_dir in sorted(case_dirs):
        case_name = os.path.basename(case_dir)
        print(f"Processing {case_name}...")
        
        physical_exam_keys, lab_test_keys = extract_keys_from_case(case_dir)
        
        if physical_exam_keys or lab_test_keys:
            processed_cases += 1
            all_physical_exam_keys.update(physical_exam_keys)
            all_lab_test_keys.update(lab_test_keys)
            
            print(f"  - Found {len(physical_exam_keys)} physical exam keys")
            print(f"  - Found {len(lab_test_keys)} lab test keys")
    
    # Deduplicate with case-insensitive comparison
    deduplicated_physical_exams = deduplicate_case_insensitive(all_physical_exam_keys)
    deduplicated_lab_tests = deduplicate_case_insensitive(all_lab_test_keys)
    
    # Create the final JSON structure
    result = {
        "metadata": {
            "total_cases_processed": processed_cases,
            "total_case_directories_found": len(case_dirs),
            "unique_physical_exam_keys_count": len(deduplicated_physical_exams),
            "unique_lab_test_keys_count": len(deduplicated_lab_tests),
            "original_physical_exam_keys_count": len(all_physical_exam_keys),
            "original_lab_test_keys_count": len(all_lab_test_keys)
        },
        "physical_exams": deduplicated_physical_exams,
        "lab_tests": deduplicated_lab_tests
    }
    
    # Write the result to a JSON file
    output_file = "extracted_exam_lab_keys.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== Summary ===")
    print(f"Cases processed: {processed_cases}")
    print(f"Original physical exam keys: {len(all_physical_exam_keys)}")
    print(f"Deduplicated physical exam keys (case-insensitive): {len(deduplicated_physical_exams)}")
    print(f"Original lab test keys: {len(all_lab_test_keys)}")
    print(f"Deduplicated lab test keys (case-insensitive): {len(deduplicated_lab_tests)}")
    print(f"Output saved to: {output_file}")
    
    # Print the keys for immediate viewing
    print(f"\n=== Physical Exam Keys (Case-Insensitive Deduplicated) ===")
    for key in deduplicated_physical_exams:
        print(f"  - {key}")
    
    print(f"\n=== Lab Test Keys (Case-Insensitive Deduplicated) ===")
    for key in deduplicated_lab_tests:
        print(f"  - {key}")

if __name__ == "__main__":
    main() 
from pathlib import Path
import re

def get_next_case_id() -> str:
    """Get the next available case ID by finding the highest existing case number and adding 1."""
    base_path = Path("case-data")
    if not base_path.exists():
        return "1"
    
    # Find all case directories and extract their numeric IDs
    case_ids = []
    for d in base_path.iterdir():
        if d.is_dir() and d.name.startswith("case"):
            # Extract the numeric part after "case"
            match = re.match(r"case(\d+)", d.name)
            if match:
                case_ids.append(int(match.group(1)))
    
    # If no cases exist, start with 1
    if not case_ids:
        return "1"
    
    # Return the next available ID (highest + 1)
    return str(max(case_ids) + 1) 
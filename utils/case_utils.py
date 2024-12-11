from pathlib import Path

def get_next_case_id() -> str:
    """Get the next available case ID by counting existing case directories."""
    base_path = Path("case-data")
    if not base_path.exists():
        return "1"
    
    existing_cases = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith("case")]
    return str(len(existing_cases) + 1) 
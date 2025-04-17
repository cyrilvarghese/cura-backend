import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Literal

class SessionManager:
    def __init__(self, base_dir: str = "session-data"):
        """Initialize the session manager with a base directory for storing session files."""
        self.base_dir = base_dir
        # Create the base directory if it doesn't exist
        Path(base_dir).mkdir(parents=True, exist_ok=True)

    def _get_session_file_path(self, student_id: str, case_id: str) -> str:
        """Generate the file path for a session file."""
        return os.path.join(self.base_dir, f"{student_id}_case{case_id}_session.json")

    def create_or_load_session(self, student_id: str, case_id: str) -> Dict[str, Any]:
        """Create a new session file or load an existing one."""
        file_path = self._get_session_file_path(student_id, case_id)
        
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        
        # Create new session data
        session_data = {
            "student_id": student_id,
            "case_id": case_id,
            "session_start": datetime.now().isoformat(),
            "interactions": {
                "history_taking": [],
                "physical_examinations": [],
                "tests_ordered": [],
                "diagnosis_submission": None,
                "pre_treatment_checks": [],
                "treatment_plan": None,
                "post_treatment_monitoring": []
            }
        }
        
        # Save the new session
        self._save_session(file_path, session_data)
        return session_data

    def clear_session(self, student_id: str, case_id: str) -> Dict[str, Any]:
        """Clear and reinitialize a session for a student-case combination."""
        file_path = self._get_session_file_path(student_id, case_id)
        
        # Create fresh session data
        session_data = {
            "student_id": student_id,
            "case_id": case_id,
            "session_start": datetime.now().isoformat(),
            "interactions": {
                "history_taking": [],
                "physical_examinations": [],
                "tests_ordered": [],
                "diagnosis_submission": None,
                "pre_treatment_checks": [],
                "treatment_plan": None,
                "post_treatment_monitoring": []
            }
        }
        
        # Save the fresh session
        self._save_session(file_path, session_data)
        print(f"[{datetime.now()}] 🔄 Cleared session for student {student_id} on case {case_id}")
        return session_data

    def add_history_question(self, student_id: str, case_id: str, question: str, response: str) -> Dict[str, Any]:
        """Add a history-taking question and response to the session."""
        file_path = self._get_session_file_path(student_id, case_id)
        session_data = self.create_or_load_session(student_id, case_id)
        
        # Add the new question and response
        interaction_entry = {
            "question": question,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        session_data["interactions"]["history_taking"].append(interaction_entry)
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_test_order(self, student_id: str, case_id: str, test_type: Literal["physical_exam", "lab_test"], 
                      test_name: str) -> Dict[str, Any]:
        """Add a test order to the session."""
        file_path = self._get_session_file_path(student_id, case_id)
        session_data = self.create_or_load_session(student_id, case_id)
        
        # Create test order entry
        test_entry = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to appropriate list based on test type
        if test_type == "physical_exam":
            session_data["interactions"]["physical_examinations"].append(test_entry)
        else:  # lab_test
            session_data["interactions"]["tests_ordered"].append(test_entry)
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def _save_session(self, file_path: str, session_data: Dict[str, Any]) -> None:
        """Save the session data to file."""
        with open(file_path, 'w') as f:
            json.dump(session_data, f, indent=2)

    def get_session(self, student_id: str, case_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a session if it exists."""
        file_path = self._get_session_file_path(student_id, case_id)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return None 
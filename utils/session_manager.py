import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Literal, List

class SessionManager:
    def __init__(self, base_dir: str = "session-data"):
        """Initialize the session manager with a base directory for storing session files."""
        self.base_dir = base_dir
        # Create the base directory if it doesn't exist
        Path(base_dir).mkdir(parents=True, exist_ok=True)

    def _get_session_file_path(self, student_id: str, case_id: str = None) -> str:
        """Generate the file path for a session file."""
        return os.path.join(self.base_dir, f"{student_id}_case_session.json")

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
                "final_diagnosis": None,
                "pre_treatment_checks": [],
                "treatment_plan": None,
                "post_treatment_monitoring": [],
                "clinical_findings": []
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
            "current_step": "History Taking",
            "interactions": {
                "history_taking": [],
                "physical_examinations": [],
                "tests_ordered": [],
                "diagnosis_submission": None,
                "final_diagnosis": None,
                "pre_treatment_checks": [],
                "treatment_plan": None,
                "post_treatment_monitoring": [],
                "clinical_findings": [],
                "feedback": {}

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

    def add_clinical_finding(self, student_id: str, case_id: str, finding: str) -> Dict[str, Any]:
        """Add a clinical finding to the session.
        
        Args:
            student_id (str): The ID of the student
            case_id (str): The ID of the case
            finding (str): The clinical finding to add
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id, case_id)
        session_data = self.create_or_load_session(student_id, case_id)
        
        # Add the finding directly to the array
        session_data["interactions"]["clinical_findings"].append(finding)
        session_data["current_step"] = "Clinical Findings"
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_diagnosis_submission(self, student_id: str, case_id: str, diagnosis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a diagnosis submission to the session.
        
        Args:
            student_id (str): The ID of the student
            case_id (str): The ID of the case
            diagnosis_data (Dict[str, Any]): The diagnosis submission data
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id, case_id)
        session_data = self.create_or_load_session(student_id, case_id)
        
        # Update the diagnosis submission
        session_data["interactions"]["diagnosis_submission"] = diagnosis_data
        session_data["current_step"] = "Primary Diagnosis"
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_final_diagnosis(self, student_id: str, case_id: str, final_diagnosis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a final diagnosis submission to the session.
        
        Args:
            student_id (str): The ID of the student
            case_id (str): The ID of the case
            final_diagnosis_data (Dict[str, Any]): The final diagnosis submission data
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id, case_id)
        session_data = self.create_or_load_session(student_id, case_id)
        
        # Update the final diagnosis submission
        session_data["interactions"]["final_diagnosis"] = final_diagnosis_data
        session_data["current_step"] = "Final Diagnosis"
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_treatment_monitoring_data(self, student_id: str, case_id: str, pre_treatment_checks: List[str], post_treatment_monitoring: List[str]) -> Dict[str, Any]:
        """Add pre-treatment checks and post-treatment monitoring data to the session.
        
        Args:
            student_id (str): The ID of the student
            case_id (str): The ID of the case
            pre_treatment_checks (List[str]): List of pre-treatment checks
            post_treatment_monitoring (List[str]): List of post-treatment monitoring parameters
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id, case_id)
        session_data = self.create_or_load_session(student_id, case_id)
        
        # Create monitoring data structure with timestamp
        monitoring_data = {
            "pre_treatment_checks": pre_treatment_checks,
            "post_treatment_monitoring": post_treatment_monitoring,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update both pre-treatment checks and post-treatment monitoring
        session_data["interactions"]["pre_treatment_checks"] = pre_treatment_checks
        session_data["interactions"]["post_treatment_monitoring"] = post_treatment_monitoring
        session_data["current_step"] = "Treatment Monitoring"
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_treatment_plan(self, student_id: str, case_id: str, treatment_plan: List[str]) -> Dict[str, Any]:
        """Add treatment plan to the session.
        
        Args:
            student_id (str): The ID of the student
            case_id (str): The ID of the case
            treatment_plan (List[str]): List of treatment steps/medications
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id, case_id)
        session_data = self.create_or_load_session(student_id, case_id)
        
        # Create treatment plan data structure with timestamp
        plan_data = {
            "treatment_steps": treatment_plan,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update the treatment plan
        session_data["interactions"]["treatment_plan"] = plan_data
        session_data["current_step"] = "Treatment Plan"
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_history_feedback(self, student_id: str, analysis_result: Dict[str, Any], domain_feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Add history taking feedback results to the session.
        
        Args:
            student_id (str): The ID of the student
            analysis_result (Dict[str, Any]): Results from the analysis step
            domain_feedback (Dict[str, Any]): Results from the domain feedback step
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id)
        session_data = self.get_session(student_id)
        
        if not session_data:
            raise ValueError("No active session found")
        
        # Add feedback data to the session
        if "feedback" not in session_data["interactions"]:
            session_data["interactions"]["feedback"] = {}
            
        session_data["interactions"]["feedback"]["history_taking"] = {
            "analysis": analysis_result,
            "domain_feedback": domain_feedback,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_history_analysis(self, student_id: str, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Add history taking analysis results to the session.
        
        Args:
            student_id (str): The ID of the student
            analysis_result (Dict[str, Any]): The analysis results to store
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id)
        session_data = self.get_session(student_id)
        
        if not session_data:
            raise ValueError("No active session found")
        
        # Initialize feedback structure if it doesn't exist
        if "feedback" not in session_data["interactions"]:
            session_data["interactions"]["feedback"] = {}
            
        if "history_taking" not in session_data["interactions"]["feedback"]:
            session_data["interactions"]["feedback"]["history_taking"] = {}
            
        # Store the analysis results
        session_data["interactions"]["feedback"]["history_taking"]["analysis"] = analysis_result
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_diagnosis_feedback(self, student_id: str, feedback_result: Dict[str, Any]) -> Dict[str, Any]:
        """Add diagnosis feedback results to the session.
        
        Args:
            student_id (str): The ID of the student
            feedback_result (Dict[str, Any]): The feedback results to store
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id)
        session_data = self.get_session(student_id)
        
        if not session_data:
            raise ValueError("No active session found")
        
        # Initialize feedback structure if it doesn't exist
        if "feedback" not in session_data["interactions"]:
            session_data["interactions"]["feedback"] = {}
            
        # Store the feedback results
        session_data["interactions"]["feedback"]["diagnosis"] = {
            "feedback": feedback_result,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def add_osce_score(self, student_id: str, case_id: str, osce_score_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add OSCE score data to the session feedback.
        
        Args:
            student_id (str): The ID of the student
            case_id (str): The ID of the case
            osce_score_data (Dict[str, Any]): The OSCE score data including overall performance and by question type
            
        Returns:
            Dict[str, Any]: The updated session data
        """
        file_path = self._get_session_file_path(student_id, case_id)
        session_data = self.create_or_load_session(student_id, case_id)
        
        # Ensure feedback object exists
        if "feedback" not in session_data["interactions"]:
            session_data["interactions"]["feedback"] = {}
        
        # Add OSCE score to feedback
        session_data["interactions"]["feedback"]["osce_score"] = osce_score_data
        session_data["current_step"] = "OSCE Evaluation"
        
        # Save the updated session
        self._save_session(file_path, session_data)
        return session_data

    def _save_session(self, file_path: str, session_data: Dict[str, Any]) -> None:
        """Save the session data to file."""
        with open(file_path, 'w') as f:
            json.dump(session_data, f, indent=2)

    def get_session(self, student_id: str, case_id: str = None) -> Optional[Dict[str, Any]]:
        """Retrieve a session if it exists."""
        file_path = self._get_session_file_path(student_id, case_id)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return None 
import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException
from supabase import create_client, Client

# Set environment variables or hardcode for testing
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_supabase_client() -> Client:
    """Get a Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[SUPABASE] Error: Missing environment variables - SUPABASE_URL: {'Set' if SUPABASE_URL else 'Not set'}, SUPABASE_KEY: {'Set' if SUPABASE_KEY else 'Not set'}")
        raise ValueError("Supabase URL and Key must be set in environment variables")
    print(f"[SUPABASE] Client initialized with URL: {SUPABASE_URL[:20]}...")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_rubric_scores(interactions: Dict[str, Any]) -> Dict[str, Any]:
    """Extract rubric scores from session interactions."""
    feedback = interactions.get("feedback", {})
    diagnosis = feedback.get("diagnosis", {}).get("feedback", {}).get("evaluationSummary", {})
    history_score = feedback.get("history_taking", {}).get("analysis", {}).get("summary_feedback", {}).get("cumulative_score", 0)
    
    scores = {
        "history_taking": history_score,
        "physical_exams": diagnosis.get("physicalExamPerformance", 0),
        "test_ordering": diagnosis.get("testOrderingPerformance", 0),
        "diagnosis_accuracy": diagnosis.get("primaryDiagnosisAccuracy", 0),
        "reasoning": diagnosis.get("reasoningQuality", 0),
        "differentials": diagnosis.get("differentialListMatch", 0)
    }
    
    print(f"[SUPABASE] Extracted rubric scores: {json.dumps(scores, indent=2)}")
    return scores

async def submit_session_to_supabase(session_data: Dict[str, Any], department: str) -> Dict[str, Any]:
    """Submit complete session data to Supabase after OSCE score is recorded."""
    try:
        print(f"[SUPABASE] Beginning session submission process...")
        print(f"[SUPABASE] Session data contains keys: {', '.join(session_data.keys())}")
        
        supabase = get_supabase_client()
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        student_id = session_data.get("student_id")
        case_id = session_data.get("case_id")
        session_start = session_data.get("session_start")
        interactions = session_data.get("interactions", {})
        
        print(f"[SUPABASE] Processing session for student_id: {student_id}, case_id: {case_id}")
        print(f"[SUPABASE] Session started at: {session_start}")
        print(f"[SUPABASE] Interactions contains keys: {', '.join(interactions.keys())}")
        
        # Extract structured data from the session
        print(f"[SUPABASE] Extracting rubric scores...")
        rubric_scores = extract_rubric_scores(interactions)
        
        print(f"[SUPABASE] Extracting final diagnosis...")
        final_diagnosis = interactions.get("final_diagnosis", {})
        print(f"[SUPABASE] Final diagnosis: {json.dumps(final_diagnosis, indent=2)}")
        
        print(f"[SUPABASE] Extracting OSCE summary...")
        osce_summary = interactions.get("feedback", {}).get("osce_score", {}).get("overallPerformance", {})
        print(f"[SUPABASE] OSCE summary: {json.dumps(osce_summary, indent=2)}")
        
        print(f"[SUPABASE] Extracting feedback summary...")
        # Get diagnosis accuracy and reasoning quality information
        diagnosis_accuracy = interactions.get("feedback", {}).get("diagnosis", {}).get("feedback", {}).get("evaluationSummary", {}).get("diagnosisAccuracy", {})
        reasoning_quality = interactions.get("feedback", {}).get("diagnosis", {}).get("feedback", {}).get("evaluationSummary", {}).get("reasoningQuality", {})
        
        # Combine the explanations from both components
        diagnosis_explanation = diagnosis_accuracy.get("explanation", "") if isinstance(diagnosis_accuracy, dict) else ""
        reasoning_explanation = reasoning_quality.get("explanation", "") if isinstance(reasoning_quality, dict) else ""
        
        feedback_summary = f"Diagnosis: {diagnosis_explanation} Reasoning: {reasoning_explanation}".strip()
        if not feedback_summary:
            # Fallback to original key_weakness if the new approach yields empty results
            feedback_summary = interactions.get("feedback", {}).get("history_taking", {}).get("analysis", {}).get("summary_feedback", {}).get("key_weakness", "")
        
        print(f"[SUPABASE] Feedback summary: {feedback_summary}")
        
        # Prepare payload for insertion
        insertion_payload = {
            "id": session_id,
            "student_id": student_id,
            "case_id": case_id,
            "session_start": session_start,
            "session_end": now,
            "interactions": interactions,
            "rubric_scores": rubric_scores,
            "final_diagnosis": final_diagnosis,
            "osce_score_summary": osce_summary,
            "feedback_summary": feedback_summary,
            "inserted_at": now,
            "department": department.lower() if department else None
        }
        
        # Print size of payload for debugging
        payload_size = len(json.dumps(insertion_payload))
        print(f"[SUPABASE] Insertion payload size: {payload_size} bytes")
        
        # Log truncated version of payload
        truncated_payload = {k: v if k != "interactions" else "..." for k, v in insertion_payload.items()}
        print(f"[SUPABASE] Insertion payload (truncated): {json.dumps(truncated_payload, indent=2)}")
        
        print(f"[SUPABASE] Executing insert to 'student_case_sessions' table...")
        
        # Insert into Supabase
        result = supabase.table("student_case_sessions").insert(insertion_payload).execute()
        
        print(f"[SUPABASE] Insert successful! Session ID: {session_id}")
        print(f"[SUPABASE] Supabase response: {result}")
        
        return {"status": "success", "session_id": session_id}
        
    except Exception as e:
        error_msg = str(e)
        print(f"[SUPABASE] ERROR: Failed to submit session to Supabase")
        print(f"[SUPABASE] ERROR details: {error_msg}")
        print(f"[SUPABASE] ERROR type: {type(e).__name__}")
        
        if hasattr(e, '__traceback__'):
            import traceback
            tb_str = ''.join(traceback.format_tb(e.__traceback__))
            print(f"[SUPABASE] ERROR traceback: \n{tb_str}")
            
        raise HTTPException(status_code=500, detail=f"Error submitting session to Supabase: {error_msg}") 
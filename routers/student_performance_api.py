from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from utils.supabase_session import get_supabase_client
from auth.auth_api import get_user, is_admin
from datetime import datetime
import json
import os
from pathlib import Path

# Use a prefix for better organization of routes
performance_router = APIRouter()

class StudentCaseComparison(BaseModel):
    student_id: str
    case_id: str
    primary_diagnosis: Optional[str] = None
    student_history: Optional[float] = None
    student_physicals: Optional[float] = None
    student_tests: Optional[float] = None
    student_diagnosis: Optional[float] = None
    student_reasoning: Optional[float] = None
    student_differentials: Optional[float] = None
    avg_history: Optional[float] = None
    max_history: Optional[float] = None
    avg_physicals: Optional[float] = None
    max_physicals: Optional[float] = None
    avg_tests: Optional[float] = None
    max_tests: Optional[float] = None
    avg_diagnosis: Optional[float] = None
    max_diagnosis: Optional[float] = None
    avg_reasoning: Optional[float] = None
    max_reasoning: Optional[float] = None
    avg_differentials: Optional[float] = None
    max_differentials: Optional[float] = None

class StudentSessionSummary(BaseModel):
    id: str
    student_id: str
    case_id: str
    session_start: str
    session_end: str
    rubric_scores: Dict[str, Any]
    osce_score_summary: Optional[Dict[str, Any]] = None
    feedback_summary: Optional[str] = None
    inserted_at: str

class DepartmentSessionData(BaseModel):
    session_id: str
    student_id: str
    student_name: str
    department: str
    case_id: str
    session_start: str
    session_end: str
    primary_diagnosis: Optional[str] = None
    history_taking: Optional[float] = None
    physical_exams: Optional[float] = None
    test_ordering: Optional[float] = None
    diagnosis_accuracy: Optional[float] = None
    reasoning: Optional[float] = None
    differentials: Optional[float] = None

def get_primary_diagnosis(case_id: str) -> str:
    """Get the primary diagnosis for a case from its diagnosis_context.json file."""
    try:
        diagnosis_file_path = Path(f"case-data/case{case_id}/diagnosis_context.json")
        if not diagnosis_file_path.exists():
            print(f"[PERFORMANCE_API] ⚠️ Diagnosis context file not found for case ID: {case_id}")
            return "Not available"
        
        with open(diagnosis_file_path, 'r') as f:
            diagnosis_data = json.load(f)
            primary_diagnosis = diagnosis_data.get("primaryDiagnosis", "Not specified")
            print(f"[PERFORMANCE_API] 📋 Found primary diagnosis for case {case_id}: {primary_diagnosis}")
            return primary_diagnosis
    except Exception as e:
        print(f"[PERFORMANCE_API] ⚠️ Error reading diagnosis context file for case {case_id}: {str(e)}")
        return "Error reading diagnosis"

# Add a direct alias route for 'comparison' that the frontend is trying to access
@performance_router.get("/comparison", response_model=List[StudentCaseComparison])
async def get_comparison():
    """
    Alias for the student case comparison endpoint.
    """
    print(f"[PERFORMANCE_API] 📊 Using comparison alias endpoint")
    return await get_student_case_comparison()

# You may also want to add a single case alias to match the frontend's expectations
@performance_router.get("/comparison/{case_id}", response_model=StudentCaseComparison)
async def get_comparison_by_case(case_id: str):
    """
    Alias for the student case comparison by case endpoint.
    """
    print(f"[PERFORMANCE_API] 📊 Using comparison by case alias endpoint")
    return await get_student_case_comparison_by_case(case_id)

@performance_router.get("/student-performance/comparison", response_model=List[StudentCaseComparison])
async def get_student_case_comparison():
    """
    Get performance comparison data for the authenticated student across all cases,
    including their scores and group averages/maximums.
    Includes the primary diagnosis for each case.
    """
    print(f"[PERFORMANCE_API] 📊 Getting student case comparison data...")
    
    # First authenticate the user
    try:
        print(f"[PERFORMANCE_API] 🔐 Authenticating user...")
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PERFORMANCE_API] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[PERFORMANCE_API] ✅ User authenticated successfully. Student ID: {student_id}")
    except HTTPException as auth_error:
        print(f"[PERFORMANCE_API] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PERFORMANCE_API] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Query the view for the authenticated student
        print(f"[PERFORMANCE_API] 🔍 Querying student_case_comparison_view for student ID: {student_id}")
        result = supabase.table("student_case_comparison_view").select("*").eq("student_id", student_id).execute()
        
        if not result.data:
            print(f"[PERFORMANCE_API] ℹ️ No comparison data found for student ID: {student_id}")
            return []
        
        print(f"[PERFORMANCE_API] ✅ Retrieved {len(result.data)} comparison records")
        
        # Format and return the data
        comparison_data = []
        for row in result.data:
            # Convert string scores to appropriate types
            for score_field in ['student_history', 'student_physicals', 'student_tests', 
                               'student_diagnosis', 'student_reasoning', 'student_differentials']:
                if row.get(score_field) is not None:
                    try:
                        # Simply convert to float
                        row[score_field] = float(row[score_field])
                    except (ValueError, TypeError):
                        pass  # Keep as is if conversion fails
            
            # Add primary diagnosis for the case
            row['primary_diagnosis'] = get_primary_diagnosis(row['case_id'])
            
            comparison_data.append(StudentCaseComparison(**row))
        
        print(f"[PERFORMANCE_API] 🏁 Successfully processed comparison data with primary diagnoses")
        return comparison_data
        
    except Exception as e:
        error_msg = str(e)
        print(f"[PERFORMANCE_API] ❌ Error retrieving student case comparison data: {error_msg}")
        print(f"[PERFORMANCE_API] Error type: {type(e).__name__}")
        if hasattr(e, '__traceback__'):
            import traceback
            tb_str = ''.join(traceback.format_tb(e.__traceback__))
            print(f"[PERFORMANCE_API] Error traceback: \n{tb_str}")
        raise HTTPException(status_code=500, detail=f"Error retrieving student case comparison data: {error_msg}")

@performance_router.get("/student-performance/comparison/{case_id}", response_model=StudentCaseComparison)
async def get_student_case_comparison_by_case(case_id: str):
    """
    Get performance comparison data for the authenticated student for a specific case,
    including their scores and group averages/maximums.
    Includes the primary diagnosis for the case.
    """
    print(f"[PERFORMANCE_API] 📊 Getting student case comparison data for case ID: {case_id}")
    
    # First authenticate the user
    try:
        print(f"[PERFORMANCE_API] 🔐 Authenticating user...")
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PERFORMANCE_API] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[PERFORMANCE_API] ✅ User authenticated successfully. Student ID: {student_id}")
    except HTTPException as auth_error:
        print(f"[PERFORMANCE_API] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PERFORMANCE_API] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Query the view for the authenticated student and specific case
        print(f"[PERFORMANCE_API] 🔍 Querying student_case_comparison_view for student ID: {student_id}, case ID: {case_id}")
        result = supabase.table("student_case_comparison_view") \
            .select("*") \
            .eq("student_id", student_id) \
            .eq("case_id", case_id) \
            .execute()
        
        if not result.data:
            print(f"[PERFORMANCE_API] ❌ No comparison data found for student ID: {student_id}, case ID: {case_id}")
            raise HTTPException(status_code=404, detail=f"No comparison data found for case {case_id}")
        
        # Format and return the data
        row = result.data[0]
        
        # Convert string scores to appropriate types
        for score_field in ['student_history', 'student_physicals', 'student_tests', 
                          'student_diagnosis', 'student_reasoning', 'student_differentials']:
            if row.get(score_field) is not None:
                try:
                    # Simply convert to float
                    row[score_field] = float(row[score_field])
                except (ValueError, TypeError):
                    pass  # Keep as is if conversion fails
        
        # Add primary diagnosis for the case
        row['primary_diagnosis'] = get_primary_diagnosis(case_id)
        
        print(f"[PERFORMANCE_API] 🏁 Successfully retrieved comparison data for case: {case_id}")
        return StudentCaseComparison(**row)
        
    except HTTPException as http_error:
        print(f"[PERFORMANCE_API] ❌ HTTP exception: {str(http_error)}")
        raise http_error
    except Exception as e:
        error_msg = str(e)
        print(f"[PERFORMANCE_API] ❌ Error retrieving student case comparison data: {error_msg}")
        print(f"[PERFORMANCE_API] Error type: {type(e).__name__}")
        if hasattr(e, '__traceback__'):
            import traceback
            tb_str = ''.join(traceback.format_tb(e.__traceback__))
            print(f"[PERFORMANCE_API] Error traceback: \n{tb_str}")
        raise HTTPException(status_code=500, detail=f"Error retrieving student case comparison data: {error_msg}")

@performance_router.get("/sessions/{case_id}", response_model=List[StudentSessionSummary])
async def get_sessions_for_case(
    case_id: str, 
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Alias for the case-sessions endpoint.
    """
    print(f"[PERFORMANCE_API] 📊 Using sessions alias endpoint")
    return await get_all_student_sessions_for_case(case_id, limit, offset)

@performance_router.get("/case-sessions/{case_id}", response_model=List[StudentSessionSummary])
async def get_all_student_sessions_for_case(
    case_id: str, 
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get all student sessions for a specific case.
    This endpoint provides a summary of each student's performance on the case.
    """
    print(f"[PERFORMANCE_API] 📊 Getting all student sessions for case ID: {case_id}")
    
    # First authenticate the user (just to ensure they're logged in)
    try:
        print(f"[PERFORMANCE_API] 🔐 Authenticating user...")
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PERFORMANCE_API] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[PERFORMANCE_API] ✅ User authenticated successfully. Student ID: {student_id}")
    except HTTPException as auth_error:
        print(f"[PERFORMANCE_API] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PERFORMANCE_API] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Query for all student sessions for the case
        print(f"[PERFORMANCE_API] 🔍 Querying student_case_sessions for case ID: {case_id}")
        result = supabase.table("student_case_sessions") \
            .select("id, student_id, case_id, session_start, session_end, rubric_scores, osce_score_summary, feedback_summary, inserted_at") \
            .eq("case_id", case_id) \
            .order("inserted_at", desc=True) \
            .limit(limit) \
            .offset(offset) \
            .execute()
        
        if not result.data:
            print(f"[PERFORMANCE_API] ℹ️ No sessions found for case ID: {case_id}")
            return []
        
        print(f"[PERFORMANCE_API] ✅ Retrieved {len(result.data)} student sessions for case ID: {case_id}")
        
        # Convert data to model
        sessions = [StudentSessionSummary(**session) for session in result.data]
        
        print(f"[PERFORMANCE_API] 🏁 Successfully processed student session data")
        return sessions
        
    except Exception as e:
        error_msg = str(e)
        print(f"[PERFORMANCE_API] ❌ Error retrieving student sessions: {error_msg}")
        print(f"[PERFORMANCE_API] Error type: {type(e).__name__}")
        if hasattr(e, '__traceback__'):
            import traceback
            tb_str = ''.join(traceback.format_tb(e.__traceback__))
            print(f"[PERFORMANCE_API] Error traceback: \n{tb_str}")
        raise HTTPException(status_code=500, detail=f"Error retrieving student sessions: {error_msg}")

# Add shorter route alias for department sessions
@performance_router.get("/teaching", response_model=List[DepartmentSessionData])
async def get_teaching_data(
    department: str = Query(..., description="Department to filter by"),
    case_id: Optional[str] = Query(None, description="Optional case ID to filter by"),
    student_id: Optional[str] = Query(None, description="Optional student ID to filter by")
):
    """
    Alias for the department-sessions endpoint.
    """
    print(f"[PERFORMANCE_API] 📊 Using teaching alias endpoint for department: {department}")
    return await get_department_sessions(department, case_id, student_id)

@performance_router.get("/department-sessions", response_model=List[DepartmentSessionData])
async def get_department_sessions(
    department: str = Query(..., description="Department to filter by"),
    case_id: Optional[str] = Query(None, description="Optional case ID to filter by"),
    student_id: Optional[str] = Query(None, description="Optional student ID to filter by")
):
    """
    Get session data for a specific department, optionally filtered by case or student.
    This endpoint is designed for teachers to view student performance across sessions.
    """
    print(f"[PERFORMANCE_API] 📊 Getting department sessions for department: {department}")
    if case_id:
        print(f"[PERFORMANCE_API] Filtering by case_id: {case_id}")
    if student_id:
        print(f"[PERFORMANCE_API] Filtering by student_id: {student_id}")
    
    # First authenticate the user and check if they are a teacher or admin
    try:
        print(f"[PERFORMANCE_API] 🔐 Authenticating user...")
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PERFORMANCE_API] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        user_role = user_response["user"].get("role", "")
        
        # Check if user is admin or teacher
        if user_role not in ["admin", "teacher"]:
            print(f"[PERFORMANCE_API] ❌ Access denied: User role '{user_role}' is not authorized")
            raise HTTPException(status_code=403, detail="Only teachers and admins can access department data")
            
        print(f"[PERFORMANCE_API] ✅ User authenticated successfully. User ID: {user_id}, Role: {user_role}")
    except HTTPException as auth_error:
        print(f"[PERFORMANCE_API] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PERFORMANCE_API] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Build the query
        query = supabase.table("teacher_department_sessions_view").select("*").eq("department", department)
        
        # Add optional filters if provided
        if case_id:
            query = query.eq("case_id", case_id)
        if student_id:
            query = query.eq("student_id", student_id)
            
        # Execute the query
        print(f"[PERFORMANCE_API] 🔍 Querying teacher_department_sessions_view")
        result = query.execute()
        
        if not result.data:
            print(f"[PERFORMANCE_API] ℹ️ No sessions found for department: {department}")
            return []
        
        print(f"[PERFORMANCE_API] ✅ Retrieved {len(result.data)} session records")
        
        # Create a cache for diagnoses to avoid reading the same file multiple times
        diagnosis_cache = {}
        
        # Convert data to model instances
        sessions = []
        for row in result.data:
            # Handle potential None values in numeric fields
            for field in ['history_taking', 'physical_exams', 'test_ordering', 
                          'diagnosis_accuracy', 'reasoning', 'differentials']:
                if row.get(field) is not None:
                    try:
                        row[field] = float(row[field])
                    except (ValueError, TypeError):
                        row[field] = None
            
            # Add primary diagnosis for each case
            case_id = row['case_id']
            if case_id not in diagnosis_cache:
                diagnosis_cache[case_id] = get_primary_diagnosis(case_id)
            
            row['primary_diagnosis'] = diagnosis_cache[case_id]
            print(f"[PERFORMANCE_API] Added primary diagnosis for case {case_id}: {row['primary_diagnosis']}")
            
            sessions.append(DepartmentSessionData(**row))
        
        print(f"[PERFORMANCE_API] 🏁 Successfully processed department session data with primary diagnoses")
        return sessions
        
    except Exception as e:
        error_msg = str(e)
        print(f"[PERFORMANCE_API] ❌ Error retrieving department sessions: {error_msg}")
        print(f"[PERFORMANCE_API] Error type: {type(e).__name__}")
        if hasattr(e, '__traceback__'):
            import traceback
            tb_str = ''.join(traceback.format_tb(e.__traceback__))
            print(f"[PERFORMANCE_API] Error traceback: \n{tb_str}")
        raise HTTPException(status_code=500, detail=f"Error retrieving department sessions: {error_msg}") 
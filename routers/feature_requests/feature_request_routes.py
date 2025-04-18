from fastapi import APIRouter, HTTPException
from datetime import datetime
from auth.auth_api import get_authenticated_client, get_user

feature_router = APIRouter()

@feature_router.get("/request-access")
async def request_feature_access(title: str):
    """Handle feature access request"""
    try:
        # First check authentication - keep this outside the main try block
        user_response = await get_user()
        if not user_response["success"]:
            # Explicitly handle auth failure
            error_message = user_response.get("error", "Authentication required")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        
        try:
            # Get authenticated client and perform database operations
            supabase = get_authenticated_client()
            
            # First, try to get existing request count
            existing_request = supabase.table('feature_requests')\
                .select('request_count')\
                .match({'feature_name': title, 'student_id': student_id})\
                .execute()
            
            new_count = 1
            if existing_request.data:
                new_count = existing_request.data[0]['request_count'] + 1
            
            # Now upsert with the correct count
            result = supabase.table('feature_requests')\
                .upsert({
                    'feature_name': title,
                    'student_id': student_id,
                    'request_count': new_count,
                    'updated_at': datetime.now().isoformat()
                }, on_conflict='feature_name,student_id')\
                .execute()

            return {
                "success": True,
                "message": "Feature request recorded successfully",
                "data": {
                    "feature_name": title,
                    "student_id": student_id,
                    "request_count": new_count
                }
            }

        except Exception as db_error:
            # Handle database-related errors
            print(f"Database error: {str(db_error)}")
            raise HTTPException(status_code=500, detail=str(db_error))
            
    except HTTPException as http_error:
        # Re-raise HTTP exceptions with their original status codes
        raise http_error
    except Exception as e:
        # Handle any other unexpected errors
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred") 
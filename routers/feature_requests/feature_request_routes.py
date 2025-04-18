from fastapi import APIRouter, HTTPException
from datetime import datetime
from auth.auth_api import get_authenticated_client, get_user

feature_router = APIRouter()

@feature_router.get("/request-access")
async def request_feature_access(title: str):
    """Handle feature access request"""
    try:
        # Get authenticated user using auth_api
        user_response = await get_user()
        if not user_response["success"]:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        student_id = user_response["user"]["id"]
        
        # Get authenticated client
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

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"General error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
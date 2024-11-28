from fastapi import APIRouter

user_router = APIRouter(
    prefix="/users",
    tags=["users"]
)

@user_router.get("/")
async def get_users():
    return {"message": "List of users", "users": ["user1", "user2", "user3"]}

@user_router.get("/{user_id}")
async def get_user(user_id: str):
    return {"message": f"User details for {user_id}", "user_id": user_id} 
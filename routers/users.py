from fastapi import APIRouter
from pydantic import BaseModel

# Add User model for request validation
class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str | None = None

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

@user_router.post("/")
async def create_user(user: UserCreate):
    # In a real application, you would save this to a database
    return {
        "message": "User created successfully",
        "user": {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name
        }
    } 
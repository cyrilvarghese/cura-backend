
from fastapi import APIRouter
from .users import user_router
from .products import product_router

api_router = APIRouter()

# Add your routes here
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

# Include the other routers
api_router.include_router(user_router)
api_router.include_router(product_router) 
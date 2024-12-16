from fastapi import APIRouter

product_router = APIRouter(
    prefix="/products",
    tags=["products"]
)

@product_router.get("/")
async def get_products():
    return {"message": "List of products", "products": ["product1", "product2", "product3"]}

@product_router.get("/{product_id}")
async def get_product(product_id: str):
    return {"message": f"Product details for {product_id}", "product_id": product_id} 
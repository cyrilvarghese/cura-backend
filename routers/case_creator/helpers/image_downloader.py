# components/image_downloader.py
import aiohttp
import aiofiles
import os
from fastapi import HTTPException
from typing import Optional

async def download_image(image_url: str, save_path: str) -> Optional[str]:
    """
    Downloads an image from a URL and saves it to the specified path
    
    Args:
        image_url: The URL of the image to download
        save_path: The path where the image should be saved
        
    Returns:
        str: Path where the image was saved
        
    Raises:
        HTTPException: If download fails
    """
    chunk_size = 1024  # 1KB chunks for memory efficiency
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Failed to download image from {image_url}"
                    )
                
                # Open file for writing in binary mode
                async with aiofiles.open(save_path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(chunk_size)
                        if not chunk:
                            break
                        await f.write(chunk)
                        
        return save_path

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading image: {str(e)}"
        )
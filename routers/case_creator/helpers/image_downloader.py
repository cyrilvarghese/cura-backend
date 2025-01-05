# components/image_downloader.py
import aiohttp
import aiofiles
import os
from fastapi import HTTPException
from typing import Optional, Tuple

async def download_image(image_url: str, save_path: str) -> Tuple[str, int]:
    """
    Downloads an image from a URL and saves it to the specified path
    Returns a tuple of (path, status_code)
    """
    chunk_size = 1024
    headers = {
        # Essential headers to mimic a browser request
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": image_url,  # Many sites check referrer
        "Connection": "keep-alive"
    }
    
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(image_url, allow_redirects=True) as response:
                if response.status == 403:
                    return image_url, 403
                elif response.status != 200:
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Failed to download image from {image_url}"
                    )
                
                async with aiofiles.open(save_path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(chunk_size)
                        if not chunk:
                            break
                        await f.write(chunk)
                        
        return save_path, 200

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading image: {str(e)}"
        )
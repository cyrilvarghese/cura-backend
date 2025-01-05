import aiohttp
import os
import aiofiles
import asyncio
from fastapi import HTTPException
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime

# paid image extractor api ----- 
# https://extract.pics/

# Load environment variables
load_dotenv()

# Get API key from environment
API_KEY = os.getenv("EXTRACTIMAGES_API_KEY")

def log(msg: str):
    """Simple timestamp logger"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

async def check_status(session: aiohttp.ClientSession, extraction_id: str, attempt: int = 1) -> Optional[dict]:
    """Recursively check extraction status until done or error"""
    try:
        async with session.get(
            f"https://api.extract.pics/v0/extractions/{extraction_id}",
            headers={"Authorization": f"Bearer {API_KEY}"}
        ) as response:
            data = await response.json()
            status = data.get('data', {}).get('status')
            log(f"Attempt {attempt}: Status = {status}")
            
            if status == 'error':
                log(f"Extraction failed after {attempt} attempts")
                return None
            elif status == 'done':
                log("Final data received:")
                log(f"Images found: {len(data.get('data', {}).get('images', []))}")
                return data.get('data')
                
            await asyncio.sleep(1)
            return await check_status(session, extraction_id, attempt + 1)

    except Exception as e:
        log(f"Status check error on attempt {attempt}: {str(e)}")
        return None

async def extract_and_save(url: str, save_path: str) -> Optional[str]:
    """
    Extracts first image from a URL and saves it to the specified path
    
    Args:
        url (str): The URL to extract image from
        save_path (str): Path to save the extracted image
        
    Returns:
        Optional[str]: Path where the image was saved, or None if failed
    """
    log(f"Starting extraction for URL: {url}")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    download_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.extract.pics/v0/extractions",
                headers=headers,
                json={"url": url}
            ) as response:
                log(f"Initial response status: {response.status}")
                
                if response.status == 201:
                    data = await response.json()
                    extraction_id = data.get('data', {}).get('id')
                    if not extraction_id:
                        log("Error: No extraction ID in response")
                        return None
                    
                    log(f"Starting status checks for ID: {extraction_id}")
                    extraction_data = await check_status(session, extraction_id)
                    if not extraction_data:
                        return None
                    images = extraction_data.get('images', [])
                    log(f"Status checks complete. Found {len(images)} images")
                elif response.status == 200:
                    data = await response.json()
                    images = data.get('data', {}).get('images', [])
                    log(f"Immediate success. Found {len(images)} images")
                else:
                    log(f"Error: Unexpected status code {response.status}")
                    return None

                if not images or not (image_url := images[0].get("url")):
                    log("Error: No valid images found")
                    return None

                log(f"Selected image URL: {image_url[:60]}...")
                ext = images[0].get("mimeType", "image/jpg").split("/")[-1]
                final_save_path = f"{os.path.splitext(save_path)[0]}.{ext}"
                
                os.makedirs(os.path.dirname(final_save_path), exist_ok=True)
                async with session.get(image_url, headers=download_headers) as img_response:
                    if img_response.status != 200:
                        log(f"Error: Image download failed with status {img_response.status}")
                        return None
                    
                    async with aiofiles.open(final_save_path, 'wb') as f:
                        await f.write(await img_response.read())
                
                log(f"Success: Image saved to {final_save_path}")
                return final_save_path

    except Exception as e:
        log(f"Error: Extraction failed - {str(e)}")
        return None 
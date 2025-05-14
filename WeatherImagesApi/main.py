from fastapi import FastAPI, File, UploadFile, HTTPException, Security, Depends, Form
from fastapi.responses import JSONResponse, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from PIL import Image
from dotenv import load_dotenv
import io
import os
import uuid
import json
from starlette.status import HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST
from typing import Optional

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

UPLOAD_DIR = "uploaded_images"
PROJECT_IMAGES_DIR = "images"
METADATA_FILE = "images_metadata.json"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Security settings
API_KEY = os.getenv("API_KEY", "thisisapikey")  # Default for development
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not api_key_header:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="No API key provided"
        )
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Invalid API key"
        )
    return api_key_header

# Mount static directories
app.mount("/images", StaticFiles(directory=PROJECT_IMAGES_DIR), name="project_images")
app.mount("/uploaded", StaticFiles(directory=UPLOAD_DIR), name="uploaded_images")

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_metadata(metadata):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

def get_image_info(filepath):
    try:
        with Image.open(filepath) as img:
            size_bytes = os.path.getsize(filepath)
            return {
                "dimensions": {"width": img.width, "height": img.height},
                "format": img.format,
                "mode": img.mode,
                "size_bytes": size_bytes,
                "size_kb": round(size_bytes / 1024, 2)
            }
    except Exception as e:
        print(f"Error getting image info for {filepath}: {str(e)}")
        return None

# Initialize metadata for project images if not exists
metadata = load_metadata()
if not metadata:
    print("Initializing metadata for project images...")
    for filename in os.listdir(PROJECT_IMAGES_DIR):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            image_id = str(uuid.uuid4())
            filepath = os.path.join(PROJECT_IMAGES_DIR, filename)
            image_info = get_image_info(filepath)
            if image_info:
                metadata[image_id] = {
                    "id": image_id,
                    "filename": filename,
                    "url": f"/images/{filename}",
                    "source": "project",
                    **image_info
                }
    save_metadata(metadata)

@app.get("/api/images")
async def list_images():
    try:
        return list(metadata.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/images/{image_id}")
async def get_image(image_id: str):
    try:
        if image_id not in metadata:
            raise HTTPException(status_code=404, detail="Image not found")
        
        image_data = metadata[image_id]
        filepath = os.path.join(
            UPLOAD_DIR if image_data["source"] == "uploaded" else PROJECT_IMAGES_DIR,
            image_data["filename"]
        )
        
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="Image file not found")
            
        with open(filepath, 'rb') as f:
            return Response(
                content=f.read(),
                media_type=f"image/{image_data['format'].lower()}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/images/{image_id}")
async def delete_image(
    image_id: str,
    api_key: str = Depends(get_api_key)
):
    try:
        if image_id not in metadata:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        image_data = metadata[image_id]
        
        # Prevent deletion of project images
        if image_data["source"] == "project":
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="Cannot delete project images"
            )
        
        # Delete the physical file
        filepath = os.path.join(UPLOAD_DIR, image_data["filename"])
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Remove from metadata
        del metadata[image_id]
        save_metadata(metadata)
        
        return {
            "message": "Image deleted successfully",
            "id": image_id,
            "filename": image_data["filename"]
        }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/images")
async def upload_image(
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None),
    api_key: str = Depends(get_api_key)
):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        resized_image = image.resize((100, 100))

        # Generate unique ID
        image_id = str(uuid.uuid4())
        
        # Handle filename
        if filename:
            # Ensure filename has an extension
            if not any(filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Filename must have a valid image extension (.png, .jpg, .jpeg, .gif, .bmp)"
                )
            
            # Check if filename already exists
            if any(img["filename"] == filename for img in metadata.values()):
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail=f"An image with filename '{filename}' already exists"
                )
            
            unique_filename = filename
        else:
            # Use default UUID-based filename
            file_ext = file.filename.split(".")[-1]
            unique_filename = f"{image_id}.{file_ext}"
        
        # Save the image
        path = os.path.join(UPLOAD_DIR, unique_filename)
        resized_image.save(path)
        
        # Get image info and update metadata
        image_info = get_image_info(path)
        if not image_info:
            # Clean up the file if metadata generation fails
            if os.path.exists(path):
                os.remove(path)
            raise HTTPException(status_code=500, detail="Failed to process uploaded image")
            
        metadata[image_id] = {
            "id": image_id,
            "filename": unique_filename,
            "url": f"/uploaded/{unique_filename}",
            "source": "uploaded",
            **image_info,
            "original_dimensions": {"width": image.width, "height": image.height}
        }
        save_metadata(metadata)
        
        return metadata[image_id]

    except HTTPException:
        raise
    except Exception as e:
        # Clean up any created file in case of error
        if 'path' in locals() and os.path.exists(path):
            os.remove(path)
        raise HTTPException(status_code=500, detail=str(e)) 
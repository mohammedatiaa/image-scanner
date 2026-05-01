from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from PIL import UnidentifiedImageError
import os
import uuid
from app.utils import scan_document, convert_to_pdf, extract_text
import asyncio

app = FastAPI()

# Ensure the uploads directory exists
UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.post("/upload")
async def upload_image(file: UploadFile = File(...), effect: str = Form("magic")):
    try:
        # Generate a unique filename
        file_extension = os.path.splitext(file.filename)[1] or ".png"
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        original_path = os.path.join(UPLOADS_DIR, unique_filename)

        # Save the uploaded file asynchronously
        with open(original_path, "wb") as buffer:
            buffer.write(await file.read())

        # Validate effect parameter
        valid_effects = ["magic", "enhanced", "bw", "original"]
        if effect not in valid_effects:
            effect = "magic"

        # Process the image
        scanned_filename = f"scanned_{unique_filename}"
        scanned_path = os.path.join(UPLOADS_DIR, scanned_filename)
        try:
            await asyncio.to_thread(scan_document, original_path, scanned_path, effect)
        except UnidentifiedImageError:
            if os.path.exists(original_path):
                os.remove(original_path)
            raise HTTPException(status_code=400, detail="File is not an image.")

        return JSONResponse(content={
            "message": "Image processed successfully",
            "scanned_image_url": f"/uploads/{scanned_filename}",
            "original_image_url": f"/uploads/{unique_filename}",
            "effect": effect
        })
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"An error occurred: {str(e)}"})

@app.post("/rescan")
async def rescan_image(data: dict):
    """Re-apply a different scan effect to an already-uploaded original image."""
    try:
        original_url = data.get("original_image_url")
        effect = data.get("effect", "magic")
        if not original_url:
            raise HTTPException(status_code=400, detail="Original image URL is required.")

        base_filename = os.path.basename(original_url)
        original_path = os.path.join(UPLOADS_DIR, base_filename)

        if not os.path.exists(original_path):
            raise HTTPException(status_code=404, detail="Original image not found on server.")

        valid_effects = ["magic", "enhanced", "bw", "original"]
        if effect not in valid_effects:
            effect = "magic"

        scanned_filename = f"scanned_{base_filename}"
        scanned_path = os.path.join(UPLOADS_DIR, scanned_filename)
        await asyncio.to_thread(scan_document, original_path, scanned_path, effect)

        return JSONResponse(content={
            "message": "Image re-processed successfully",
            "scanned_image_url": f"/uploads/{scanned_filename}",
            "effect": effect
        })
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"An error occurred: {str(e)}"})

@app.post("/convert")
async def convert_image_to_pdf(data: dict):
    try:
        scanned_image_path = data.get("scanned_image_path")
        if not scanned_image_path:
            raise HTTPException(status_code=400, detail="Scanned image path is required.")

        # Construct the full path on the server
        base_filename = os.path.basename(scanned_image_path)
        server_image_path = os.path.join(UPLOADS_DIR, base_filename)

        if not os.path.exists(server_image_path):
            raise HTTPException(status_code=404, detail="Scanned image not found on server.")

        # Convert to PDF
        pdf_filename = f"{os.path.splitext(base_filename)[0]}.pdf"
        pdf_path = os.path.join(UPLOADS_DIR, pdf_filename)
        await asyncio.to_thread(convert_to_pdf, server_image_path, pdf_path)

        return JSONResponse(content={
            "message": "PDF created successfully",
            "pdf_url": f"/uploads/{pdf_filename}"
        })
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"An error occurred: {str(e)}"})

@app.post("/ocr")
async def ocr_image(data: dict):
    try:
        scanned_image_path = data.get("scanned_image_path")
        if not scanned_image_path:
            raise HTTPException(status_code=400, detail="Scanned image path is required.")

        lang = data.get("lang") or "eng"
        base_filename = os.path.basename(scanned_image_path)
        server_image_path = os.path.join(UPLOADS_DIR, base_filename)

        if not os.path.exists(server_image_path):
            raise HTTPException(status_code=404, detail="Scanned image not found on server.")

        text = await asyncio.to_thread(extract_text, server_image_path, lang)
        return JSONResponse(content={
            "message": "Text extracted successfully",
            "text": text
        })
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"An error occurred: {str(e)}"})

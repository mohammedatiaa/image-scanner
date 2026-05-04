from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import os
import uuid
import asyncio
from app.utils import scan_document

app = FastAPI()

UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    try:
        ext = os.path.splitext(file.filename)[1] or ".png"
        uid = f"{uuid.uuid4()}{ext}"
        original_path = os.path.join(UPLOADS_DIR, uid)

        with open(original_path, "wb") as f:
            f.write(await file.read())

        scanned_name = f"scanned_{uid}"
        scanned_path = os.path.join(UPLOADS_DIR, scanned_name)
        await asyncio.to_thread(scan_document, original_path, scanned_path)

        return JSONResponse(content={
            "message": "Image processed successfully",
            "scanned_image_url": f"/uploads/{scanned_name}",
            "original_image_url": f"/uploads/{uid}",
        })
    except ValueError:
        raise HTTPException(status_code=400, detail="File is not a valid image.")
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Error: {str(e)}"})

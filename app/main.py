from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import os
import uuid
import asyncio
from app.utils import scan_document, generate_filtered_images, get_filter_names

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
async def upload_image(file: UploadFile = File(...), effect: str = Form("original")):
    try:
        ext = os.path.splitext(file.filename)[1] or ".png"
        uid = f"{uuid.uuid4()}{ext}"
        original_path = os.path.join(UPLOADS_DIR, uid)

        with open(original_path, "wb") as f:
            f.write(await file.read())

        filter_names = get_filter_names()
        output_paths = {
            name: os.path.join(UPLOADS_DIR, f"{name}_{uid}")
            for name in filter_names
        }
        await asyncio.to_thread(generate_filtered_images, original_path, output_paths)

        filtered_images = {
            name: f"/uploads/{os.path.basename(path)}"
            for name, path in output_paths.items()
        }
        selected_effect = effect if effect in filtered_images else "original"

        return JSONResponse(content={
            "message": "Image processed successfully",
            "original_image_url": f"/uploads/{uid}",
            "filtered_images": filtered_images,
            "filters": filter_names,
            "selected_effect": selected_effect,
        })
    except ValueError:
        raise HTTPException(status_code=400, detail="File is not a valid image.")
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Error: {str(e)}"})


@app.post("/rescan")
async def rescan_image(original_image_url: str = Form(...), effect: str = Form(...)):
    try:
        if effect not in get_filter_names():
            raise HTTPException(status_code=400, detail="Unknown effect.")

        filename = os.path.basename(original_image_url)
        if not filename:
            raise HTTPException(status_code=400, detail="Invalid image path.")

        original_path = os.path.join(UPLOADS_DIR, filename)
        if not os.path.exists(original_path):
            raise HTTPException(status_code=404, detail="Original image not found.")

        scanned_name = f"{effect}_{filename}"
        scanned_path = os.path.join(UPLOADS_DIR, scanned_name)
        await asyncio.to_thread(scan_document, original_path, scanned_path, effect)

        return JSONResponse(content={
            "message": "Image processed successfully",
            "scanned_image_url": f"/uploads/{scanned_name}",
            "effect": effect,
        })
    except ValueError:
        raise HTTPException(status_code=400, detail="File is not a valid image.")
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Error: {str(e)}"})

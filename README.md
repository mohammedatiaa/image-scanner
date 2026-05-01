# Image Scanner Pro

A high-performance document scanner web application with professional-quality image processing, OCR text extraction, and PDF conversion.

## Features

- **Multiple Scan Effects**:
  - ✨ **Magic** — Professional document scan with background normalization, gamma correction, and sharpening for clean white backgrounds.
  - 🎨 **Enhanced** — Color-preserving enhancement with CLAHE contrast and denoising. Great for colorful documents and receipts.
  - 📝 **B&W** — Adaptive thresholding for crisp black & white output. Best for text-heavy documents.
  - 📷 **Original** — Crops and straightens the document without applying any filter.
- **Automatic Document Detection** — Detects and crops document edges using contour detection, color segmentation, and threshold analysis.
- **Re-scan** — Apply a different effect to an already-uploaded image without re-uploading.
- **PDF Conversion** — Convert any scanned image to a downloadable PDF.
- **OCR Text Extraction** — Extract text from scanned documents using Tesseract OCR (supports English, Arabic, and Arabic+English).
- **Modern UI** — Glassmorphism design with dark/light mode, smooth animations, and responsive layout.
- **Multiple Upload Methods** — Drag & drop, click to browse, or paste from clipboard (Ctrl+V).

## Project Structure

```
image_scanner_pro/
├── app/
│   ├── __init__.py     # Package marker
│   ├── main.py         # FastAPI routes (upload, rescan, convert, OCR)
│   └── utils.py        # Image processing & document detection logic
├── static/
│   ├── css/style.css   # Custom styles, animations & themes
│   └── js/script.js    # Frontend logic
├── templates/
│   └── index.html      # Main HTML layout
├── uploads/            # Temporary storage for uploaded & processed files
├── requirements.txt    # Python dependencies
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Setup and Run

### 1. Create a Virtual Environment

**On Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. (Optional) Install Tesseract for OCR

If you want to use the OCR text extraction feature, install Tesseract OCR:

- **Windows**: Download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) and install to the default path.
- **macOS**: `brew install tesseract`
- **Linux**: `sudo apt install tesseract-ocr`

### 4. Run the Application

```bash
uvicorn app.main:app --reload
```

### 5. Open in Browser

Navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## How to Use

1. **Select a Scan Effect** — Choose from Magic, Enhanced, B&W, or Original.
2. **Upload an Image** — Drag & drop, click to browse, or paste (Ctrl+V).
3. **View Results** — Compare original vs scanned side by side.
4. **Re-scan** — Switch effects without re-uploading.
5. **Download** — Save the scanned image, generate a PDF, or extract text via OCR.

## Technologies

- **Backend**: Python, FastAPI, OpenCV, NumPy, Pillow, ReportLab, Pytesseract
- **Frontend**: HTML5, Vanilla CSS, Vanilla JavaScript
- **Server**: Uvicorn (ASGI)

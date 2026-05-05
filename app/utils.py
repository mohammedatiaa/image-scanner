import cv2
import pytesseract

# Required for pytesseract to work on Windows if not in PATH
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def load_image(path):
    """
    Reads an image from the given path.
    Raises ValueError if the image is not found or cannot be read.
    """
    img = cv2.imread(path)
    if img is None:
        raise ValueError("Image not found")
    return img

def scan_bw(img):
    """
    Converts the image to a black and white document using Adaptive Thresholding.
    This effectively creates a clean, scanned appearance.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 10
    )

def scan_enhanced(img):
    """
    Enhances image contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    in the LAB color space, preserving natural colors while revealing more detail.
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(3.0, (8, 8))
    l = clahe.apply(l)

    lab = cv2.merge((l, a, b))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

# 🎯 OCR and highlight specific words on the original image
def extract_specific_words(original_img, ocr_img, target_words):
    """
    Runs Tesseract OCR on the binary image (ocr_img) to detect text.
    If any target words are found, it draws a bounding box and text label 
    on the original colored image (original_img).
    """
    data = pytesseract.image_to_data(ocr_img, output_type=pytesseract.Output.DICT)

    full_text = []

    for i in range(len(data["text"])):
        word = data["text"][i].strip()
        word_lower = word.lower()

        if word != "":
            full_text.append(word)

        if word_lower in target_words:
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]

            # 🟡 Draw bounding box on the original image
            cv2.rectangle(original_img, (x, y), (x + w, y + h), (0, 255, 255), 2)

            cv2.putText(original_img, word, (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    return original_img, " ".join(full_text)

# --- Integration with FastAPI backend ---
def get_filter_names() -> list[str]:
    # Returning the exact options available in this new logic
    return [
        "bw", "enhanced", "ocr_highlight", 
        "rgb", "low_contrast", "high_contrast", "average"
    ]

def scan_document(image_path: str, output_path: str, effect: str = "bw") -> None:
    img = load_image(image_path)
    
    if effect == "bw":
        res = scan_bw(img)
        cv2.imwrite(output_path, res)
    elif effect == "enhanced":
        res = scan_enhanced(img)
        cv2.imwrite(output_path, res)
    elif effect == "ocr_highlight":
        bw = scan_bw(img)
        targets = ["name", "date", "total", "score", "formula", "policy"]
        ocr_image, _ = extract_specific_words(img.copy(), bw, targets)
        cv2.imwrite(output_path, ocr_image)
    elif effect == "rgb":
        cv2.imwrite(output_path, cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    elif effect == "low_contrast":
        cv2.imwrite(output_path, cv2.convertScaleAbs(img, alpha=0.3, beta=50))
    elif effect == "high_contrast":
        cv2.imwrite(output_path, cv2.convertScaleAbs(img, alpha=2.5, beta=-30))
    elif effect == "average":
        cv2.imwrite(output_path, cv2.blur(img, (15, 15)))
    else:
        # Fallback to original
        cv2.imwrite(output_path, img)

def generate_filtered_images(image_path: str, outputs: dict[str, str]) -> None:
    img = load_image(image_path)
    bw = scan_bw(img)
    
    if "bw" in outputs:
        cv2.imwrite(outputs["bw"], bw)
        
    if "enhanced" in outputs:
        enhanced = scan_enhanced(img)
        cv2.imwrite(outputs["enhanced"], enhanced)
        
    if "ocr_highlight" in outputs:
        targets = ["name", "date", "total", "score", "formula", "policy"]
        ocr_image, _ = extract_specific_words(img.copy(), bw, targets)
        cv2.imwrite(outputs["ocr_highlight"], ocr_image)
        
    if "rgb" in outputs:
        cv2.imwrite(outputs["rgb"], cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        
    if "low_contrast" in outputs:
        cv2.imwrite(outputs["low_contrast"], cv2.convertScaleAbs(img, alpha=0.3, beta=50))
        
    if "high_contrast" in outputs:
        cv2.imwrite(outputs["high_contrast"], cv2.convertScaleAbs(img, alpha=2.5, beta=-30))
        
    if "average" in outputs:
        cv2.imwrite(outputs["average"], cv2.blur(img, (15, 15)))



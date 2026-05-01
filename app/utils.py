from PIL import Image, UnidentifiedImageError
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import cv2
import numpy as np
import pytesseract
from pytesseract import TesseractNotFoundError
import os

MAX_SCAN_HEIGHT = 1200
MIN_DOC_AREA_RATIO = 0.1

def configure_tesseract():
    custom_cmd = os.environ.get("TESSERACT_CMD")
    if custom_cmd and os.path.exists(custom_cmd):
        pytesseract.pytesseract.tesseract_cmd = custom_cmd
        return

    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return



def order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")

    s = points.sum(axis=1)
    rect[0] = points[np.argmin(s)]
    rect[2] = points[np.argmax(s)]

    diff = np.diff(points, axis=1)
    rect[1] = points[np.argmin(diff)]
    rect[3] = points[np.argmax(diff)]
    return rect

def four_point_transform(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    rect = order_points(points)
    (tl, tr, br, bl) = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = int(max(height_a, height_b))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")

    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))

def resize_for_processing(image: np.ndarray) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    scale = 1.0
    if height > MAX_SCAN_HEIGHT:
        scale = MAX_SCAN_HEIGHT / float(height)
        image = cv2.resize(image, (int(width * scale), int(height * scale)))
    return image, scale

def find_document_contour(edged: np.ndarray, resized: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    image_area = edged.shape[0] * edged.shape[1]

    for contour in contours[:8]:
        if cv2.contourArea(contour) < image_area * MIN_DOC_AREA_RATIO:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            area = cv2.contourArea(approx)
            if area > image_area * 0.95:
                continue
            x, y, w, h = cv2.boundingRect(approx)
            if x <= 5 or y <= 5 or (x + w) >= edged.shape[1] - 5 or (y + h) >= edged.shape[0] - 5:
                continue
            return approx

    largest = contours[0]
    area = cv2.contourArea(largest)
    if area < image_area * MIN_DOC_AREA_RATIO or area > image_area * 0.95:
        return None

    rect = cv2.minAreaRect(largest)
    box = cv2.boxPoints(rect)
    x, y, w, h = cv2.boundingRect(box.astype(np.int32))
    if x <= 5 or y <= 5 or (x + w) >= edged.shape[1] - 5 or (y + h) >= edged.shape[0] - 5:
        return None
    return box.astype("float32")

def find_document_contour_by_color(resized: np.ndarray) -> np.ndarray | None:
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 0, 160], dtype=np.uint8)
    upper = np.array([179, 80, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    mask = cv2.medianBlur(mask, 7)
    close_kernel = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return None

    height, width = mask.shape[:2]
    image_area = height * width
    best_contour = None
    best_ratio = 0.0

    for label in range(1, num_labels):
        x, y, w, h, area = stats[label]
        ratio = area / image_area
        if ratio < MIN_DOC_AREA_RATIO or ratio > 0.95:
            continue
        touches_left = x <= 1
        touches_top = y <= 1
        touches_right = (x + w) >= (width - 2)
        touches_bottom = (y + h) >= (height - 2)
        touches_count = sum([touches_left, touches_top, touches_right, touches_bottom])
        if touches_count >= 3:
            continue
        if ratio <= best_ratio:
            continue

        component = (labels == label).astype("uint8") * 255
        component = cv2.morphologyEx(component, cv2.MORPH_CLOSE, close_kernel, iterations=1)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        best_ratio = ratio
        best_contour = contour

    if best_contour is None:
        return None

    rect = cv2.minAreaRect(best_contour)
    box = cv2.boxPoints(rect)
    return box.astype("float32")

def find_document_contour_by_threshold(resized: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates = [mask, cv2.bitwise_not(mask)]
    best_contour = None
    best_ratio = 0.0
    image_area = resized.shape[0] * resized.shape[1]
    height, width = resized.shape[:2]

    for candidate in candidates:
        candidate = cv2.medianBlur(candidate, 9)
        kernel = np.ones((5, 5), np.uint8)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, kernel, iterations=1)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, connectivity=8)
        if num_labels <= 1:
            continue

        for label in range(1, num_labels):
            x, y, w, h, area = stats[label]
            ratio = area / image_area
            if ratio < MIN_DOC_AREA_RATIO or ratio > 0.95:
                continue
            touches_left = x <= 1
            touches_top = y <= 1
            touches_right = (x + w) >= (width - 2)
            touches_bottom = (y + h) >= (height - 2)
            touches_count = sum([touches_left, touches_top, touches_right, touches_bottom])
            if touches_count >= 2:
                continue
            if ratio <= best_ratio:
                continue

            component = (labels == label).astype("uint8") * 255
            component = cv2.morphologyEx(component, cv2.MORPH_CLOSE, kernel, iterations=1)
            contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            contour = max(contours, key=cv2.contourArea)
            best_ratio = ratio
            best_contour = contour

    if best_contour is None:
        return None

    rect = cv2.minAreaRect(best_contour)
    box = cv2.boxPoints(rect)
    return box.astype("float32")


def magic_scan_effect(warped: np.ndarray) -> np.ndarray:
    """
    High-quality document scan effect that matches onlinephotoscanner.com quality.
    Uses multi-pass background normalization + gamma correction for a clean,
    professional scanned-document look with bright white backgrounds.
    """
    # Step 1: Convert to grayscale
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    # Step 2: Bilateral filter to reduce noise while preserving edges
    gray = cv2.bilateralFilter(gray, 11, 75, 75)

    # Step 3: Multi-scale background estimation and normalization
    # Use a large morphological closing to estimate the background
    h, w = gray.shape[:2]
    # Primary background estimation with large kernel
    bg_kernel_size = max(51, (min(h, w) // 5) | 1)  # ensure odd, large kernel
    bg_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bg_kernel_size, bg_kernel_size))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, bg_kernel)

    # Also use large median blur for secondary estimation
    med_kernel = max(51, (min(h, w) // 6) | 1)
    background2 = cv2.medianBlur(gray, med_kernel)

    # Take the maximum of both estimates (brighter = more background)
    background = np.maximum(background, background2)

    # Smooth the background estimate
    background = cv2.GaussianBlur(background, (0, 0), bg_kernel_size // 3)

    # Divide by background to normalize uneven lighting
    bg_float = background.astype(np.float32)
    bg_float[bg_float < 1] = 1
    normalized = (gray.astype(np.float32) / bg_float * 255.0)
    normalized = np.clip(normalized, 0, 255).astype(np.uint8)

    # Step 4: Aggressive gamma correction to push whites whiter
    gamma = 2.2
    inv_gamma = 1.0 / gamma
    table = np.array([
        ((i / 255.0) ** inv_gamma) * 255
        for i in np.arange(0, 256)
    ]).astype("uint8")
    normalized = cv2.LUT(normalized, table)

    # Step 5: Contrast stretching - clip aggressively to whiten background
    min_val = np.percentile(normalized, 1)
    max_val = np.percentile(normalized, 95)  # clip higher to push more to white
    if max_val - min_val > 0:
        stretched = np.clip(
            (normalized.astype(np.float32) - min_val) * 255.0 / (max_val - min_val),
            0, 255
        ).astype(np.uint8)
    else:
        stretched = normalized

    # Step 6: Second pass gamma to further brighten background
    gamma2 = 1.4
    inv_gamma2 = 1.0 / gamma2
    table2 = np.array([
        ((i / 255.0) ** inv_gamma2) * 255
        for i in np.arange(0, 256)
    ]).astype("uint8")
    stretched = cv2.LUT(stretched, table2)

    # Step 7: CLAHE for local contrast (make text pop)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(stretched)

    # Step 8: Blend CLAHE result with stretched to avoid over-darkening
    result = cv2.addWeighted(enhanced, 0.4, stretched, 0.6, 0)

    # Step 9: Unsharp masking for crispness
    blurred = cv2.GaussianBlur(result, (0, 0), 2)
    sharpened = cv2.addWeighted(result, 1.5, blurred, -0.5, 0)

    # Step 10: Final denoise
    result = cv2.fastNlMeansDenoising(sharpened, h=10, templateWindowSize=7, searchWindowSize=21)

    # Step 11: Final white balance - ensure background is truly white
    # Pixels that are light enough should be pushed to pure white
    _, white_mask = cv2.threshold(result, 200, 255, cv2.THRESH_BINARY)
    result = np.where(white_mask == 255, 255, result).astype(np.uint8)

    return result


def enhanced_scan_effect(warped: np.ndarray) -> np.ndarray:
    """
    Enhanced color scan - keeps colors but improves contrast and sharpness.
    Good for colorful documents, receipts with logos, etc.
    """
    # CLAHE on L channel in LAB space
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a_channel, b_channel))
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # Background normalization on luminance only
    gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY).astype(np.float32)
    bg_kernel = max(35, (min(gray.shape[:2]) // 8) | 1)
    background = cv2.medianBlur(gray.astype(np.uint8), bg_kernel).astype(np.float32)
    background[background == 0] = 1
    ratio = 255.0 / background

    # Apply normalization to each channel
    result = enhanced.astype(np.float32)
    for c in range(3):
        result[:, :, c] = np.clip(result[:, :, c] * ratio, 0, 255)
    result = result.astype(np.uint8)

    # Sharpen
    blurred = cv2.GaussianBlur(result, (0, 0), 2)
    result = cv2.addWeighted(result, 1.4, blurred, -0.4, 0)

    # Denoise lightly
    result = cv2.fastNlMeansDenoisingColored(result, None, 6, 6, 7, 21)
    return result


def bw_scan_effect(warped: np.ndarray) -> np.ndarray:
    """
    High-quality black & white effect using adaptive thresholding.
    Best for text-heavy documents.
    """
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    bg_kernel = max(35, (min(gray.shape[:2]) // 8) | 1)
    background = cv2.medianBlur(gray, bg_kernel)
    normalized = cv2.divide(gray, background, scale=255)

    blurred = cv2.GaussianBlur(normalized, (0, 0), 3)
    sharp = cv2.addWeighted(normalized, 1.5, blurred, -0.5, 0)

    # Adaptive threshold for clean B&W
    scanned = cv2.adaptiveThreshold(
        sharp, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        35, 12
    )

    # Clean small noise
    kernel = np.ones((2, 2), np.uint8)
    scanned = cv2.morphologyEx(scanned, cv2.MORPH_OPEN, kernel, iterations=1)
    return scanned


SCAN_EFFECTS = {
    "magic": magic_scan_effect,
    "enhanced": enhanced_scan_effect,
    "bw": bw_scan_effect,
}


def scan_document(image_path: str, output_path: str, effect: str = "magic"):
    image = cv2.imread(image_path)
    if image is None:
        raise UnidentifiedImageError("Unable to read image.")

    original = image.copy()
    resized, scale = resize_for_processing(image)

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    edged = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=1)
    edged = cv2.erode(edged, np.ones((3, 3), np.uint8), iterations=1)

    screen_contour = find_document_contour(edged, resized)
    if screen_contour is None:
        screen_contour = find_document_contour_by_color(resized)
    if screen_contour is None:
        screen_contour = find_document_contour_by_threshold(resized)
    if screen_contour is not None:
        ratio = 1 / scale
        points = screen_contour.reshape(4, 2) * ratio
        warped = four_point_transform(original, points)
    else:
        warped = original

    # Apply the selected scan effect
    if effect == "original":
        # Save the warped (cropped) original as-is
        cv2.imwrite(output_path, warped)
    else:
        effect_fn = SCAN_EFFECTS.get(effect, magic_scan_effect)
        scanned = effect_fn(warped)
        cv2.imwrite(output_path, scanned)

def extract_text(image_path: str, lang: str) -> str:
    configure_tesseract()
    try:
        pytesseract.get_tesseract_version()
    except TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR is not installed. Install it and set TESSERACT_CMD if needed."
        ) from exc

    image = cv2.imread(image_path)
    if image is None:
        raise UnidentifiedImageError("Unable to read image.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    background = cv2.medianBlur(gray, 35)
    normalized = cv2.divide(gray, background, scale=255)
    processed = cv2.adaptiveThreshold(
        normalized,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10
    )

    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(processed, lang=lang, config=config)

def convert_to_pdf(image_path: str, pdf_path: str):
    """
    Converts an image to a PDF.
    """
    with Image.open(image_path) as img:
        img_width, img_height = img.size
        
    c = canvas.Canvas(pdf_path, pagesize=(img_width, img_height))
    c.drawImage(ImageReader(image_path), 0, 0, width=img_width, height=img_height)
    c.save()

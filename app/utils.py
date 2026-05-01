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
    Clean Document scan — produces a professional grayscale scan with
    pure white background and crisp dark text/ink. The go-to mode for
    most documents, notes, and forms.
    """
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    # Step 1: Denoise while preserving edges
    denoised = cv2.bilateralFilter(gray, 9, 50, 50)

    # Step 2: Multi-scale background estimation
    k1 = max(51, (min(h, w) // 4) | 1)
    bg_morph = cv2.morphologyEx(
        denoised, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k1, k1))
    )
    k2 = max(51, (min(h, w) // 5) | 1)
    bg_median = cv2.medianBlur(denoised, k2)
    background = np.maximum(bg_morph, bg_median).astype(np.float32)
    background = cv2.GaussianBlur(background, (0, 0), k1 // 3)
    background[background < 1] = 1

    # Step 3: Normalize — divide by background so lighting is even
    norm = (denoised.astype(np.float32) / background * 255.0)
    norm = np.clip(norm, 0, 255).astype(np.uint8)

    # Step 4: Contrast stretch to push background → white, ink → dark
    lo = np.percentile(norm, 2)
    hi = np.percentile(norm, 98)
    if hi - lo > 10:
        norm = np.clip((norm.astype(np.float32) - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8)

    # Step 5: Gamma curve — brighten midtones/background, keep darks dark
    gamma_table = np.array([
        np.clip(((i / 255.0) ** 0.55) * 255, 0, 255)
        for i in range(256)
    ], dtype=np.uint8)
    norm = cv2.LUT(norm, gamma_table)

    # Step 6: Sharpen for crisp edges
    blurred = cv2.GaussianBlur(norm, (0, 0), 1.5)
    sharp = cv2.addWeighted(norm, 1.6, blurred, -0.6, 0)

    # Step 7: Push near-white pixels to pure 255
    sharp = np.where(sharp >= 210, 255, sharp).astype(np.uint8)

    # Step 8: Boost text darkness — pixels darker than midpoint get darker
    dark_mask = sharp < 140
    sharp = np.where(dark_mask, np.clip(sharp.astype(np.float32) * 0.7, 0, 255), sharp).astype(np.uint8)

    return sharp


def enhanced_scan_effect(warped: np.ndarray) -> np.ndarray:
    """
    Enhanced color scan — keeps colors but improves contrast, sharpness,
    and whitens the background. Good for colorful documents, receipts, etc.
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


def _sauvola_threshold(gray: np.ndarray, window_size: int = 25, k: float = 0.15,
                       r: float = 128.0) -> np.ndarray:
    """
    Sauvola local thresholding — produces cleaner results than OpenCV's
    adaptive threshold for document scanning. For each pixel:
        T(x,y) = mean(x,y) * (1 + k * (std(x,y) / r - 1))
    Pixels >= T are white, below are black.
    """
    gray_f = gray.astype(np.float64)
    # Integral-image based local mean & variance (very fast)
    mean = cv2.blur(gray_f, (window_size, window_size))
    mean_sq = cv2.blur(gray_f * gray_f, (window_size, window_size))
    std = np.sqrt(np.clip(mean_sq - mean * mean, 0, None))
    threshold = mean * (1.0 + k * (std / r - 1.0))
    return np.where(gray_f >= threshold, 255, 0).astype(np.uint8)


def bw_scan_effect(warped: np.ndarray) -> np.ndarray:
    """
    Professional-quality black & white document scan matching
    onlinephotoscanner.com output. Uses multi-scale background
    normalization + Sauvola local thresholding for clean, crisp results
    even on photos of handwritten notes or unevenly-lit pages.
    """
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    # Step 1: Light denoise — bilateral preserves edges
    denoised = cv2.bilateralFilter(gray, 7, 40, 40)

    # Step 2: Background estimation (morphological close + median, blended)
    k1 = max(51, (min(h, w) // 4) | 1)
    bg_morph = cv2.morphologyEx(
        denoised, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k1, k1))
    )
    k2 = max(51, (min(h, w) // 5) | 1)
    bg_median = cv2.medianBlur(denoised, k2)
    background = np.maximum(bg_morph, bg_median).astype(np.float32)
    background = cv2.GaussianBlur(background, (0, 0), k1 // 3)
    background[background < 1] = 1

    # Step 3: Divide to remove uneven lighting
    normalized = np.clip(
        denoised.astype(np.float32) / background * 255.0, 0, 255
    ).astype(np.uint8)

    # Step 4: Contrast stretch
    lo = np.percentile(normalized, 1)
    hi = np.percentile(normalized, 99)
    if hi - lo > 10:
        normalized = np.clip(
            (normalized.astype(np.float32) - lo) * 255.0 / (hi - lo),
            0, 255
        ).astype(np.uint8)

    # Step 5: Sharpen before thresholding to make ink edges crisp
    blurred = cv2.GaussianBlur(normalized, (0, 0), 1.2)
    sharp = cv2.addWeighted(normalized, 1.5, blurred, -0.5, 0)

    # Step 6: Sauvola thresholding — adapts locally, handles gradients well
    win = max(25, (min(h, w) // 30) | 1)
    if win % 2 == 0:
        win += 1
    bw = _sauvola_threshold(sharp, window_size=win, k=0.12, r=128)

    # Step 7: Clean up — remove tiny noise specks
    # Small open to remove salt noise
    kernel_small = np.ones((2, 2), np.uint8)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel_small, iterations=1)

    # Remove tiny connected components (noise dots)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        cv2.bitwise_not(bw), connectivity=8
    )
    min_area = max(4, int(h * w * 0.000015))
    for label_id in range(1, num_labels):
        if stats[label_id, cv2.CC_STAT_AREA] < min_area:
            bw[labels == label_id] = 255

    return bw


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

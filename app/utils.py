import cv2
import imutils
from imutils.perspective import four_point_transform

FILTERS = {
    "rgb": lambda img: cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
    "low_contrast": lambda img: cv2.convertScaleAbs(img, alpha=0.3, beta=50),
    "high_contrast": lambda img: cv2.convertScaleAbs(img, alpha=2.5, beta=-30),
    "median": lambda img: cv2.medianBlur(img, 15),
    "average": lambda img: cv2.blur(img, (15, 15)),
    "black_white": lambda img: cv2.adaptiveThreshold(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10),
}
IDENTITY = lambda img: img


def get_filter_names() -> list[str]:
    return list(FILTERS.keys())


def apply_filter(effect: str, image):
    return FILTERS.get(effect, IDENTITY)(image)


def prepare_image(image_path: str):
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Unable to read image.")

    ratio = image.shape[0] / 500.0
    resized = imutils.resize(image, height=500)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 200)

    cnts = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]

    doc = None
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            doc = approx
            break

    return four_point_transform(image, doc.reshape(4, 2) * ratio) if doc is not None else image


def scan_document(image_path: str, output_path: str, effect: str = "original") -> None:
    base = prepare_image(image_path)
    cv2.imwrite(output_path, apply_filter(effect, base))


def generate_filtered_images(image_path: str, outputs: dict[str, str]) -> None:
    base = prepare_image(image_path)
    for effect, output_path in outputs.items():
        cv2.imwrite(output_path, apply_filter(effect, base))

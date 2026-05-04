import cv2
import numpy as np
import imutils
from imutils.perspective import four_point_transform
from skimage.filters import threshold_sauvola


def scan_document(image_path: str, output_path: str) -> None:
    """Detect a document, correct perspective, and produce a clean B&W scan."""
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

    warped = four_point_transform(image, doc.reshape(4, 2) * ratio) if doc is not None else image
    gray_w = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    thresh = threshold_sauvola(gray_w, window_size=25)
    binary = ((gray_w > thresh) * 255).astype(np.uint8)
    cv2.imwrite(output_path, binary)

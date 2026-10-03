import os
import glob
import cv2
import sys
import numpy as np
from skimage.filters import threshold_sauvola
import importlib

rs = importlib.import_module("NisabaـOCRـfunctions")
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "0-raw photo")
OUTPUT_DIR = os.path.join(BASE_DIR, "1-cleaned photo")


def fix_inverted_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    corners = [
        gray[0:10, 0:10],
        gray[0:10, w - 10:w],
        gray[h - 10:h, 0:10],
        gray[h - 10:h, w - 10:w]
    ]
    corner_brightness = np.mean([np.mean(c) for c in corners])

    otsu_val, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark_pixels = gray[gray <= otsu_val]
    light_pixels = gray[gray > otsu_val]

    strong_black_ref = float(dark_pixels.mean()) if dark_pixels.size > 0 else 0.0
    strong_white_ref = float(light_pixels.mean()) if light_pixels.size > 0 else 255.0

    dist_to_black = abs(corner_brightness - strong_black_ref)
    dist_to_white = abs(corner_brightness - strong_white_ref)

    if dist_to_black < dist_to_white:
        return cv2.bitwise_not(image)
    return image


def deskew_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bit_not = cv2.bitwise_not(gray)

    thresh = cv2.threshold(bit_not, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    coords = np.column_stack(np.where(dilated > 0))
    if coords.size == 0:
        return image

    angle = cv2.minAreaRect(coords)[-1]

    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle
    else:
        angle = -angle

    if abs(angle) < 0.1:
        return image

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    rotated = cv2.warpAffine(
        image,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )

    return rotated


def upscale_image(image, factor=None):
    if factor is None:
        factor = rs.get_setting("cleaning.upscale_factor", 5)
    width = int(image.shape[1] * factor)
    height = int(image.shape[0] * factor)
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_LANCZOS4)


def binarize_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    return cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)


def remove_noise_components(binary_image, min_area_ratio=0.0000015, max_area_ratio=0.03):
    h_img, w_img = binary_image.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cv2.bitwise_not(binary_image), 8)

    page_area = h_img * w_img
    min_area = max(30, page_area * min_area_ratio)
    max_area = page_area * max_area_ratio

    good = (
        (stats[:, 4] > min_area) & (stats[:, 4] < max_area) &
        (stats[:, 0] > 0) & (stats[:, 1] > 0) &
        (stats[:, 0] + stats[:, 2] < w_img - 1) &
        (stats[:, 1] + stats[:, 3] < h_img - 1)
    )
    good[0] = False

    return cv2.bitwise_not(np.isin(labels, np.nonzero(good)[0]).astype(np.uint8) * 255)


def close_gaps(binary_image):
    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
    result = cv2.morphologyEx(binary_image, cv2.MORPH_CLOSE, k1)
    result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, k2)
    return result


def crop_to_content(binary_image, edge_ratio=0.01):
    hs = np.sum(binary_image == 0, axis=1) / binary_image.shape[1]
    top = np.argmax(hs < edge_ratio) if np.any(hs < edge_ratio) else 0
    bot = (binary_image.shape[0] - np.argmax(hs[::-1] < edge_ratio)
           if np.any(hs[::-1] < edge_ratio) else binary_image.shape[0])
    cropped = binary_image[top:bot, :]

    vs = np.sum(cropped == 0, axis=0) / cropped.shape[0]
    left = np.argmax(vs < edge_ratio) if np.any(vs < edge_ratio) else 0
    right = (cropped.shape[1] - np.argmax(vs[::-1] < edge_ratio)
             if np.any(vs[::-1] < edge_ratio) else cropped.shape[1])
    cropped = cropped[:, left:right]

    return cropped


def clean_image(image):
    image = fix_inverted_image(image)
    image = deskew_image(image)
    upscaled = upscale_image(image, factor=5)
    binary = binarize_image(upscaled)
    binary = remove_noise_components(binary)
    binary = close_gaps(binary)
    binary = crop_to_content(binary)
    return binary


def get_input_images():
    supported_extensions = ["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp"]
    images = []
    for ext in supported_extensions:
        images.extend(glob.glob(os.path.join(INPUT_DIR, ext)))
    return images


def process():
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    input_images = get_input_images()
    if not input_images:
        raise FileNotFoundError(f"Input folder is empty! Place an image inside: {INPUT_DIR}")

    input_path = input_images[0]

    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Could not read the image from: {input_path}")

    final_result = clean_image(img)

    file_name = os.path.basename(input_path)
    output_path = os.path.join(OUTPUT_DIR, f"cleaned_{file_name}")
    cv2.imwrite(output_path, final_result)


if __name__ == "__main__":
    process()
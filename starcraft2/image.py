import cv2, re, pytesseract
import numpy as np
from constants import template, anchor_roi
import pytesseract

def is_end_screen(frame, threshold=0.8):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    max_val = np.max(res)
    #print(f"Match score: {max_val:.3f}")
    return np.max(res) > threshold

def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return thresh

def ocr_number(img):
    processed = preprocess(img)
    config = '--psm 7 -c tessedit_char_whitelist=0123456789+-'
    text = pytesseract.image_to_string(processed, config=config)
    nums = re.findall(r'[+-]?\d+', text)
    return int(nums[0]) if nums else None

def crop(img, roi):
    x, y, w, h = roi
    return img[y:y+h, x:x+w]


def draw_rois(frame, rois, anchor_roi=anchor_roi):
    debug = frame.copy()

    if anchor_roi:
        x, y, w, h = anchor_roi
        cv2.rectangle(debug, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.putText(debug, "ANCHOR", (x, y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    for name, (x, y, w, h) in rois.items():
        cv2.rectangle(debug, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(debug, name, (x, y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)


    cv2.waitKey(1)

def is_loading_screen(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    mean = np.mean(gray)
    std = np.std(gray)
    #print(f"Loading screen: (mean, std) = ({mean:.1f}, {std:.1f})")

    # Tuned for your screenshots
    return (mean < 40) and (std < 40)

def is_anchor_detected(frame, threshold=0.7):

    x, y, w, h = anchor_roi
    crop = frame[y:y+h, x:x+w]

    # Example: use template matching with a stored anchor template
    # You can save your anchor template separately
    anchor_template = template

    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(crop_gray, anchor_template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)

    return max_val >= threshold
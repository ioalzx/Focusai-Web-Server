import base64
import json
from io import BytesIO
from typing import Union, Tuple

import cv2
import numpy as np
from PIL import Image

from focusai_utils.redis_helper import redisClient
import imagehash


def data_uri_to_str(uri):
    try:
        if type(uri) == bytes:
            uri = uri.decode('utf-8')
        uri_list = uri.split(',')
        encoded_data = uri_list[1] if len(uri_list) > 1 else uri_list[0]
        return encoded_data
    except:
        return None


def data_uri_to_cv2_img(uri, cv2_opt=cv2.IMREAD_COLOR):
    try:
        encoded_data = data_uri_to_str(uri)
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        img = cv2.imdecode(nparr, cv2_opt)
        return img
    except:
        return None


def img_to_data_uri(img, cv2_opt=None):
    try:
        if cv2_opt is None:
            _, buffer = cv2.imencode('.png', img)
        else:
            _, buffer = cv2.imencode('.png', cv2.cvtColor(img, cv2_opt))

        image_base64 = base64.b64encode(buffer).decode('utf-8')
        image_base64 = "data:image/png;base64," + image_base64
        return image_base64.encode('utf-8')
    except:
        return None


def get_dhash_and_image(uri, max_size: int = float("inf")) -> Union[None, Tuple[str, bytes]]:
    try:
        img = data_uri_to_cv2_img(uri)

        if img.shape[0] > img.shape[1]:
            if img.shape[0] > max_size:
                factor = max_size / img.shape[0]
                new_side = img.shape[1] * factor
                img = cv2.resize(img, (int(new_side), int(max_size)), interpolation=cv2.INTER_CUBIC)
        else:
            if img.shape[1] > max_size:
                factor = max_size / img.shape[1]
                new_side = img.shape[0] * factor
                img = cv2.resize(img, (int(max_size), int(new_side)), interpolation=cv2.INTER_CUBIC)

        img_uri = img_to_data_uri(img)
        img_str = data_uri_to_str(img_uri)

        return str(imagehash.dhash(Image.open(BytesIO(base64.b64decode(img_str))))), img_str.encode("utf8")

    except Exception as e:
        return None


def get_img_from_redis(key: dict, cv2_opt=cv2.IMREAD_COLOR):
    image_base64 = redisClient.get(json.dumps(key))
    if image_base64 is None:
        return None

    image = data_uri_to_cv2_img(image_base64, cv2_opt)
    return image

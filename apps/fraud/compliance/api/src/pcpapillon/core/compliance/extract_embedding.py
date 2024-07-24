import contextlib
import io

import numpy as np
import requests
from PIL import Image


def extract_embedding(data, params, prepoc_models):
    """
    Extract embedding with pretrained models
    Two types available:
    - image :
        - Input: list of urls
    - text  :
        - Input: list of string
    Params template:
    [
        {"name": "offer_name", "type": "text"},
        {"name": "offer_description", "type": "text"},
        {"name": "image_url", "type": "image"},
    ]
    """
    for feature in params:
        if feature["type"] == "image":
            model = prepoc_models[feature["type"]]
            url = data[feature["name"]]
            data["image_embedding"] = _encode_img_from_url(model, url)
            with contextlib.suppress(KeyError):
                del data[feature["name"]]
        if feature["type"] == "text":
            model = prepoc_models[feature["type"]]
            embedding = model.encode(data[feature["name"]])
            data[f"""{feature["name"]}_embedding"""] = embedding

    return data


def _encode_img_from_url(model, url):
    """
    Encode image with pre-trained model from url

    inputs:
        - model : HugginFaces pre-trained model using Sentence-Transformers
        - url : string of image url
    """
    offer_img_embs = []
    try:
        img_emb = model.encode(Image.open(io.BytesIO(requests.get(url).content)))
        offer_img_embs = img_emb
    except Exception:
        offer_img_embs = np.array([0] * 512)
    return offer_img_embs

import json
import logging

import cv2
from django.shortcuts import render
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
import random
import time
import base64
import focusai_utils.img_utils as imgu

from focusai_utils.redis_helper import get_next_id, get_next_session, redisClient, send_and_wait

log = logging.getLogger("focusai_webserver")


def construct_task(sessionID: str = "", dhash: str= "", depth: float = 0., dof: float = 1., blurness: float = 0.,
                   aperture: str = "circle", grey: bool = False,
                   motion: bool = False, defocus: bool = False, noise: bool = False):
    msg = {"requestID": get_next_id(), "timestamp": str(int(time.time())), "type": "focusaiTask"}
    msg_data = {"sessionID": str(sessionID), "dhash": str(dhash), "depth": depth, "dof": dof, "blurness": blurness,
                "aperture": str(aperture)}
    visual_effect = {"grey": grey}
    restoration = {"motion": motion, "defocus": defocus, "noise": noise}

    msg_data["visual_effect"] = visual_effect
    msg_data["restoration"] = restoration
    msg["data"] = msg_data

    return msg


@api_view(['GET'])
def create_session(request):
    log.info("Received create_session request, {}".format(request.META))
    return Response(data={"statusCode": 0, "sessionId": get_next_session(), "message": "success"})


@api_view(['POST'])
def upload_image(request: Request):
    log.info("Received upload_image image request, {}".format(request.META))

    try:
        img_dhash = imgu.get_dhash_and_image(request.data["imgData"], 1500)
    except Exception as e:
        img_dhash = True
        log.error("Exception: ", exc_info=True)

    if img_dhash is None:
        log.error("Error occurred when parsing uploaded image")
        return Response(data={"statusCode": -1, "dhash": None, "depth": None,
                              "message": "Failed to parse uploaded image"})

    task = construct_task(sessionID=request.data["sessionID"], dhash=img_dhash[0])
    image_key = {"sessionID": str(request.data["sessionID"]), "dhash": img_dhash[0]}
    redisClient.set(json.dumps(image_key), img_dhash[1], ex=86400)

    log.debug("Sending msg ({}) to kafka".format(task["requestID"]))
    res = send_and_wait(task)

    if res is None:
        log.error("Failed to get result from backend")
        return Response(data={"statusCode": -1, "dhash": None, "depth": None,
                              "message": "Failed to get result from backend"})

    if res["statueCode"] != 0:
        log.warning("Backend failed to process image, {}".format(res["message"]))
        return Response(data={"statusCode": -1, "dhash": None, "depth": None,
                              "message": "Backend failed to process image, {}".format(res["message"])})

    depth_key = {"sessionID": request.data["sessionID"], "dhash": img_dhash[0], "type": "depth", "restoration": task["data"]["restoration"]}

    depth = imgu.get_img_from_redis(depth_key, cv2.IMREAD_GRAYSCALE)
    depth = imgu.data_uri_to_str(imgu.img_to_data_uri(depth))

    return Response(data={"statusCode": 0, "dhash": img_dhash[0], "depth": depth, "message": "success"})


@api_view(['POST'])
def edit_image(request):
    log.info("Received edit_image request, {}".format(request.META))

    task = construct_task(sessionID=request.data["sessionID"], dhash=request.data["dhash"], depth=request.data["depth"],
                          dof=request.data["dof"], blurness=request.data["blurness"], aperture=request.data["aperture"],
                          grey=request.data["visualEffect"]["grey"], motion=request.data["restoration"]["motion"],
                          defocus=request.data["restoration"]["defocus"], noise=request.data["restoration"]["noise"])

    log.debug("Sending msg ({}) to kafka".format(task["requestID"]))

    res = send_and_wait(task)

    if res is None:
        log.error("Failed to get result from backend")
        return Response(data={"statusCode": -1, "result": None, "depth": None,
                              "message": "Failed to get result from backend"})

    if res["statueCode"] != 0:
        log.warning("Backend failed to process image, {}".format(res["message"]))
        return Response(data={"statusCode": -1, "result": None, "depth": None,
                              "message": "Backend failed to process image, {}".format(res["message"])})

    depth_key = {"sessionID": request.data["sessionID"], "dhash": task["data"]["dhash"], "type": "depth",
                 "restoration": task["data"]["restoration"]}
    final_result_key = {"sessionID": request.data["sessionID"], "dhash": task["data"]["dhash"],
                        "type": "result", "data": task["data"]}

    depth = imgu.get_img_from_redis(depth_key, cv2.IMREAD_GRAYSCALE)
    depth = imgu.data_uri_to_str(imgu.img_to_data_uri(depth))

    result = imgu.get_img_from_redis(final_result_key)
    result = imgu.data_uri_to_str(imgu.img_to_data_uri(result))

    return Response(data={"statusCode": 0, "result": result, "depth": depth, "message": "success"})

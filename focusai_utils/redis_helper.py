import logging
import queue
from concurrent.futures import ThreadPoolExecutor

import redis
from kafka import KafkaProducer

from config.configer import configs
import cv2
import numpy as np
import base64
import json

pool = redis.ConnectionPool(host=configs["redis"]["address"], port=configs["redis"]["port"],
                            password=configs["redis"]["password"], decode_responses=True)
redisClient = redis.Redis(connection_pool=pool)

id_key = configs["redis"]["id_key"]
session_key = configs["redis"]["session_key"]

redis_listener_thread_pool = ThreadPoolExecutor()
redis_response_queue = dict()

log = logging.getLogger("focusai_webserver")


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


def listen_on_redis():
    log.info("Started listening on Redis")
    ps = redisClient.pubsub()
    ps.subscribe(configs["redis"]["topic"])
    while True:
        for m in ps.listen():
            try:
                if m is not None and isinstance(m, dict) and m["type"] == "message":
                    res = json.loads(m["data"])
                    q = redis_response_queue[res["requestID"]]
                    del redis_response_queue[res["requestID"]]
                    q.put(res)
            except:
                continue


redis_listener_thread_pool.submit(listen_on_redis)


def send_and_wait(task):
    q = queue.Queue()
    redis_response_queue[task["requestID"]] = q

    producer = KafkaProducer(bootstrap_servers=[configs["kafka"]["address"]])
    future = producer.send(topic=configs["kafka"]["topic"], value=json.dumps(task).encode('utf-8'))
    result = future.get(timeout=10)

    try:
        res = q.get(timeout=6)
        return res
    except:
        return None


def get_next_id():
    if redisClient.exists(id_key) == 0:
        redisClient.set(id_key, 0)
        return 0
    else:
        redisClient.incr(id_key)
        return redisClient.get(id_key)


def get_next_session():
    if redisClient.exists(session_key) == 0:
        redisClient.set(session_key, 0)
        return 0
    else:
        redisClient.incr(session_key)
        return redisClient.get(session_key)


def save_image(key: dict, img: np.ndarray):
    result_image_base64 = img_to_data_uri(img)
    redisClient.set(json.dumps(key), result_image_base64, ex=86400)

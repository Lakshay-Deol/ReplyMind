import logging


def get_logger(name: str = __name__):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    fmt = logging.Formatter('{"ts":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","msg":%(message)s}')
    handler.setFormatter(fmt)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger

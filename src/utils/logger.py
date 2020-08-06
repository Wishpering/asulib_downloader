from logging import StreamHandler, getLogger, Formatter, DEBUG
from sys import stdout

class Logger:
    format = Formatter("%(levelname)s — %(message)s")

    @classmethod
    def get(cls, name):
        console_handler = StreamHandler(stdout)
        console_handler.setFormatter(Logger.format)

        logger = getLogger(name)
        logger.addHandler(console_handler)
        logger.setLevel(DEBUG)

        return logger
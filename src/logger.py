from logging import StreamHandler, getLogger, Formatter, DEBUG
from sys import stdout

class Logger:
    format = Formatter("%(levelname)s — %(message)s")

    def __init__(self):
        self.console_handler = StreamHandler(stdout)
        self.console_handler.setFormatter(Logger.format)

    def get(self):
        logger = getLogger('asulib_downloader')
        logger.addHandler(self.console_handler)
        logger.setLevel(DEBUG)

        return logger
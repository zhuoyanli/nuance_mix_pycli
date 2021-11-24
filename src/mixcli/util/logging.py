import logging
from typing import Union, Optional, TypeVar

SUPPORTED_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = '[%(name)s - %(levelname)s %(asctime)s] %(message)s'

T = TypeVar('T')


def get_logger(bearer: Union[str, T], log_level: Union[int, str] = None) -> logging.Logger:
    """
    Get a _logger for a module or ID
    :param bearer: A Python module or string ID
    :param log_level: The log_level to start with
    :return: The logging.Logger instance
    """
    if isinstance(bearer, str):
        _logger = logging.getLogger(bearer)
    else:
        _logger = logging.getLogger(bearer.__name__)
    if log_level is None:
        log_level = DEFAULT_LOG_LEVEL
    # the underlying _logger should always be on DEBUG
    _logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    # the logging level should be set on channel handlers
    ch.setLevel(log_level)
    # create formatter
    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, datefmt='%m-%d %H:%M')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to _logger
    _logger.addHandler(ch)
    return _logger


class Loggable:
    """
    Functional class to make other classes accessible to logging functions
    """
    def __init__(self, bearer: Optional[Union[str, T]] = None, log_level: Optional[Union[int, str]] = None):
        self._log_lvl = log_level
        if not self._log_lvl:
            self._log_lvl = DEFAULT_LOG_LEVEL
        if not bearer:
            self._logger = get_logger(self, log_level=self._log_lvl)
        elif isinstance(bearer, str):
            self._logger = get_logger(bearer, log_level=self._log_lvl)
        else:
            self._logger = get_logger(bearer.__name__, log_level=self._log_lvl)

    @property
    def logger(self):
        return self._logger

    def set_level(self, new_level: Union[str, int]):
        """
        Set the logging level for this loggable instance
        :param new_level:
        :return:
        """
        # Please note we only modify the logging levels on the channel handlers, not the root logger!
        for ch in self._logger.handlers:
            ch.setLevel(new_level)

    def log(self, log_msg: str, log_level: Optional[Union[int, str]] = None):
        """
        Log the message with given logging levels
        :param log_msg: log message
        :param log_level: The specific log level to use
        :return: None
        """
        _log_lvl = log_level
        if not _log_lvl:
            _log_lvl = self._log_lvl
        self._logger.log(level=_log_lvl, msg=log_msg)
        for hdlr in self._logger.handlers:
            hdlr.flush()

    def error(self, err_msg: str):
        """
        Log message as error
        :param err_msg:
        :return: None
        """
        self.log(err_msg, logging.ERROR)

    def info(self, info_msg: str):
        """
        Log message as information
        :param info_msg:
        :return: None
        """
        self.log(info_msg, logging.INFO)

    def debug(self, debug_msg: str):
        """
        Log message as debugging
        :param debug_msg:
        :return: None
        """
        self.log(debug_msg, logging.DEBUG)

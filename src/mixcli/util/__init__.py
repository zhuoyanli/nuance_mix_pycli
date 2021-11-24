"""
Utility package for various processing in other commands
"""
import json
from contextlib import contextmanager
from functools import reduce
import copy
import os
import os.path
import zipfile
from subprocess import Popen
import sys
import codecs
from typing import Optional, Union, Type, Dict
from logging import Logger
from .logging import Loggable, get_logger as create_logger, DEFAULT_LOG_LEVEL


SKIPPED_PLACEHOLDER = '........'


def truncate_long_str(string: str) -> str:
    if len(string) <= 128:
        return string
    return string[0:128-len(SKIPPED_PLACEHOLDER)] + SKIPPED_PLACEHOLDER


class _UtilLogger(Loggable):
    def __init__(self, bearer: Union[str, Type], log_level: Optional[Union[str, int]] = None):
        Loggable.__init__(self, bearer, log_level=log_level)
        self._logger = create_logger(__name__)

    @property
    def logger(self) -> Logger:
        return self._logger

    def set_level(self, new_level: Union[int, str]):
        """
        Set logging level on this Loggable
        :return: None
        """
        for ch in self._logger.handlers:
            ch.setLevel(new_level)

    def log(self, msg: str, log_lvl: Optional[Union[int, str]] = None):
        self._logger.log(msg=msg, level=log_lvl)

    def debug(self, msg: str):
        self._logger.debug(msg)

    def info(self, msg: str):
        self._logger.info(msg)

    def error(self, msg: str):
        self._logger.error(msg)


_util_logger = _UtilLogger(__name__, log_level=DEFAULT_LOG_LEVEL)


def get_logger() -> Loggable:
    return _util_logger


def count_notnone(*args, exact_none: bool = False):
    """
    Count the elements in cmd_args that are not None
    :param exact_none: If True, objects that are NOT None type will be counted. If False, other types that result
    in logical/conditional False, will not be counted as not-None, such as False, empty list, empty string, and etc.
    :param args: list, variables to be checked if not None
    :return: int, count of variables in cmd_args that are not None
    """
    def not_none(o):
        if exact_none:
            return o is not None
        else:
            return True if o else False
    return reduce(lambda base, o: base+1 if not_none(o) else base, args, 0)


def _copy_kwargs(orig_kwargs):
    """
    Make copy of keyword cmd_args
    :param orig_kwargs:
    :return:
    """
    return copy.copy(orig_kwargs)


def _extend_kwargs(orig_kwargs, new_entry=None, do_copy=True):
    result_kwargs = orig_kwargs
    if do_copy is True:
        result_kwargs = _copy_kwargs(orig_kwargs)
    if new_entry:
        for k, v in new_entry.items():
            result_kwargs[k] = v
    return result_kwargs


def _set_kwargs_quiet(kwargs, quiet=True):
    """
    Enable quiet switch in keyword cmd_args
    :param kwargs:
    :param quiet:
    :return:
    """
    kwargs['quiet'] = quiet
    return kwargs


def _is_kwargs_quiet(kwargs):
    """
    Check if there is quiet switch in keyword cmd_args
    :param kwargs:
    :return:
    """
    if 'quiet' in kwargs:
        if kwargs['quiet'] is True:
            return True
        elif str(kwargs['quiet']).lower() == 'true':
            return True
        else:
            return False
    else:
        return False


def extract_mix_exported_zip(path_zip, path_outdir='', reduce_single_childdir=True,
                             logger: Optional[Loggable] = None):
    """This method extracts the content from an Mix exported ZIP archive to an specified directory.
    If there is only one single immediate child directory in the ZIP archive, we move everything
    under that single child directory to the top-level of output directory"""
    _logger = logger
    if not _logger:
        _logger = _util_logger
    realpath_outzip = os.path.realpath(path_zip)
    with zipfile.ZipFile(realpath_outzip, 'r') as zipout:
        if not path_outdir:
            # by default we extract to $PWD/exported_quicknlp_project
            outdir_qnlpproj = 'exported_quicknlp_project'
            path_outdir = os.path.join(os.getcwd(), outdir_qnlpproj)
        else:
            path_outdir = os.path.realpath(path_outdir)
        # make sure it exists
        if os.path.isdir(path_outdir) is False:
            os.makedirs(path_outdir, exist_ok=True)
        zipout.extractall(path_outdir)
        _logger.info(f"Successfully extract all content from archive {path_zip} to "
                     f"QuickNLP project dir {path_outdir}")
        # we get a set of immediate child dir(s) under path_outdir
        set_top_childdir = {item.split('/')[0] for item in zipout.namelist()}
        # if
        if reduce_single_childdir and len(set_top_childdir) == 1:
            top_childdir = next(iter(set_top_childdir))
            _logger.debug(f"Now trying to move all content from [{path_outdir}/{top_childdir}] to top level")
            mv_qnlp_cmd = """echo '{echo_fwd}' Starting sub-shell to try tp move files around
            pushd {out_dir} &> /dev/null
            echo Now in {out_dir}
            mv {top_subdir}/* .
            if (($?)); then echo '{echo_bkwd}' Exiting sub-shell ; exit 1 ; fi
            rmdir {top_subdir}
            echo '{echo_bkwd}' Exiting sub-shell
            """.format(echo_fwd='>' * 8,
                       echo_bkwd='<' * 8,
                       out_dir=path_outdir,
                       top_subdir=top_childdir)
            proc = Popen(mv_qnlp_cmd, shell=True)
            proc.wait()
            if proc.returncode != 0:
                _logger.error(f"Failed to move all content from {path_outdir}/{top_childdir} to top level")
                _logger.error(f"Extracted content can be found at [{path_outdir}/{top_childdir}]")
            else:
                _logger.info(f"Successfully move all content from {path_outdir}/{top_childdir} to top level")
                _logger.info(f"Extracted content can be found at [{path_outdir}]")


class Counter:
    """
    Utility class to serve as counter
    """
    def __init__(self, base=0):
        self._base = base

    def add_one(self):
        """
        Add one on counter
        :return: integer, new count
        """
        self._base += 1
        return self._base

    @property
    def count(self):
        """
        Get the count
        :return: integer, count
        """
        return self._base


class OutWriter:
    """
    Utility class for writing output to a
    """
    FN_STDOUT = '-'

    def __init__(self, out_handle):
        self._outhdl = out_handle

    def write(self, s, eofl=None):
        self._outhdl.write(s)
        if eofl:
            self._outhdl.write(eofl)

    @classmethod
    @contextmanager
    def open(cls, out_file):
        if out_file == cls.FN_STDOUT:
            yield OutWriter(sys.stdout)
        else:
            with codecs.open(out_file, 'w', 'utf-8') as fho:
                yield OutWriter(fho)


def is_iterable(obj):
    try:
        iter(obj)
        return True
    # noinspection PyBroadException
    except:
        return False


def assert_json_field_and_type(jsobj: Dict, field_name: str, field_type=None):
    if field_name not in jsobj:
        raise AssertionError(f'Field {field_name} not in Json: {json.dumps(jsobj)}')
    if not field_type:
        return
    if not isinstance(jsobj[field_name], field_type):
        raise AssertionError('Field {f} (type {tf}) not as expected {et} in Json: {j}'.format(
            f=field_name,
            tf=repr(type(jsobj[field_name])),
            et=repr(field_type),
            j=json.dumps(jsobj, ensure_ascii=False)
        ))

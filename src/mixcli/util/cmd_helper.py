import codecs
import json
import re
from typing import Union, Optional, Awaitable, TypeVar, Dict, List, Any
import asyncio
import os.path
import datetime
from .logging import Loggable
from . import truncate_long_str


class MixLocale:
    """
    Utility class to process locale code for Mix.
    """
    LOCALE_PTN = re.compile(r'([a-z]{2})[_-]([A-Z]{2})')
    SUPPORTED_LANG = ['en', 'es']
    SUPPORTED_COUNTRY = ['US']

    def __init__(self, language: str, country: str):
        #if language not in self.SUPPORTED_LANG:
        #    raise RuntimeError(f'Language not supported: {language} for {self._repr(language, country)}')
        #elif country not in self.SUPPORTED_COUNTRY:
        #    raise RuntimeError(f'Country not supported: {country} for {self._repr(language, country)}')
        self._lang: str = language
        self._cnty: str = country

    @classmethod
    def _repr(cls, lang: str, cnty: str):
        return f'{lang}_{cnty}'

    @property
    def mix_locale(self) -> str:
        """
        Get the Mix compliant representation of this locale as string

        :return: A locale code compliant with Mix in string
        """
        return self._repr(self._lang, self._cnty)

    @classmethod
    def to_mix(cls, loc_str) -> str:
        """
        Convert a Locale string to Mix compliant locale code string

        :param loc_str: A locale code in one of supported formats
        :return:
        """
        return MixLocale.parse(loc_str).mix_locale

    @classmethod
    def parse(cls, loc_str: str) -> 'MixLocale':
        """
        Parse a locale code in string in one of supported formats and generate a corresponding MixLocale instance.
        If code is in unsupported formats raise RuntimeException

        :param loc_str: The locale code to be parsed
        :return: The corresponding MixLocale instance.
        """
        m = cls.LOCALE_PTN.match(loc_str)
        if not m:
            raise RuntimeError(f'Invalid Locale string: {loc_str}')
        return MixLocale(language=m.group(1), country=m.group(2))


_T = TypeVar('_T')


def run_coro_sync(coro: Awaitable[_T]) -> _T:
    """
    Run an asynchronous coroutine in synchronous way
    :param coro: An asynchronous coroutine
    :return:
    """
    return asyncio.get_event_loop().run_until_complete(coro)


def assert_id_int(id_str: Optional[Union[int, str]], id_name: str = None) -> int:
    """
    assert the argument for an ID is either an int or a str that reads as valid integer
    :param id_str:
    :param id_name: Name of the ID, such as project, job, configuration, etc
    :return: The integer instance
    """
    try:
        if isinstance(id_str, int):
            return id_str
        return int(id_str)
    except Exception as ex:
        name_part = ''
        if id_name:
            name_part = f'{id_name} '
        raise ValueError(f'{name_part}ID must be valid integer (string)') from ex


def write_result_outfile(content: Union[str, Dict, List[Dict], List[str]],
                         out_file: str, force: bool = True, is_json: bool = True, logger: Loggable = None):
    rp_outfile = os.path.realpath(out_file)
    if os.path.isfile(rp_outfile):
        if not force:
            raise IOError(f"Output file already existed: {rp_outfile}")
    with codecs.open(rp_outfile, 'w', 'utf-8') as fho:
        if not is_json:
            fho.write(content)
            fho.write('\n')
            if logger:
                logger.log(log_msg=f'Content successfully written to {rp_outfile}: {truncate_long_str(content)}')
        else:
            jsonstr = json.dumps(content)
            fho.write(jsonstr)
            if logger:
                logger.log(log_msg=f'Content successfully written to {rp_outfile}: {truncate_long_str(jsonstr)}')


def project_name_from_meta(project_meta_json: Dict[str, Union[str, Any]]) -> str:
    """
    Get project name from project meta JSON

    :param project_meta_json:
    :return:
    """
    if 'name' in project_meta_json:
        return project_meta_json['name']
    raise ValueError(f'Not a valid Mix project meta: {json.dumps(project_meta_json)}')


def project_id_from_meta(project_meta_json: Dict[str, Union[str, Any]]) -> int:
    """
    Get project ID from project meta JSON

    :param project_meta_json:
    :return:
    """
    if 'id' in project_meta_json:
        return int(project_meta_json['id'])
    raise ValueError(f'Not a valid Mix project meta: {json.dumps(project_meta_json)}')


PROJ_ID_FILE_SPEC_PROJ_ID = '%ID%'
"""Specifier for project ID, used in file name template for get_project_id_file function"""
PROJ_ID_FILE_SPEC_PROJ_NAME = '%NAME%'
"""Specifier for project name, used in file name template for get_project_id_file function"""
PROJ_ID_FILE_SPEC_MODEL_NAME = '%MODEL%'
"""Specifier for model (ASR/NLU/Dialog) name, used in file name template for get_project_id_file function"""
PROJ_ID_FILE_SPEC_TIMESTAMP = '%TIME%'
"""Specifier for time stamp, used in file name template for get_project_id_file function"""
PROJ_ID_FILE_TIMESTAMP_DT_SPEC = '%Y%m%dT%H%M%S'
"""Timestamp specifier, for generating the timestamp if specified in template for get_project_id_file function"""
DEF_PROJ_ID_FILE_TMPLT = '%ID%__%NAME%__%MODEL%__%TIME%'


def get_project_id_file(project_id: int, project_meta: Dict, model: Optional[str] = None,
                        fn_tmplt: Optional[str] = None, time_fmt: Optional[str] = None,
                        ext: Optional[str] = None) -> str:
    """
    Get an ID-like string based on project id, model name (NLU/DIALOG/etc), and timestamp. The following specifiers
    can be used in tmplt: %ID% for project ID, %NAME% for project name, %MODEL% for *model_name* argument,
    %TIME% for time stamp which should be datetime formatter string and by default '%Y%m%dT%H%M%S'.
    :param time_fmt: datetime formatter string for generating timestamp. If None the default
    :param project_id: Project ID for the file
    :param project_meta: Project meta info in JSON
    :param model: Name of model relevant with this file.
    :param fn_tmplt: Template string for the file name to be generated, could include aforementioned specifier(s).
    :param ext: Extension for the file name. IMPORTANT: Users need to include '.' themselves if expected.
    :return:
    """
    proj_name = project_name_from_meta(project_meta_json=project_meta)
    if not model:
        model = ''
    timestamp = ''
    if not fn_tmplt:
        fn_tmplt = DEF_PROJ_ID_FILE_TMPLT
    if PROJ_ID_FILE_SPEC_TIMESTAMP in fn_tmplt:
        dt = datetime.datetime.now()
        if time_fmt:
            try:
                timestamp = dt.strftime(time_fmt)
            except Exception as ex:
                raise RuntimeError(f'Error parsing time_fmt as datetime format: {time_fmt}') from ex
        else:
            timestamp = dt.strftime(PROJ_ID_FILE_TIMESTAMP_DT_SPEC)
    if not fn_tmplt:
        fn_tmplt = DEF_PROJ_ID_FILE_TMPLT
    id_fn = fn_tmplt.replace(PROJ_ID_FILE_SPEC_PROJ_ID, str(project_id)).replace(
        PROJ_ID_FILE_SPEC_PROJ_NAME, proj_name).replace(
        PROJ_ID_FILE_SPEC_MODEL_NAME, model).replace(
        PROJ_ID_FILE_SPEC_TIMESTAMP, timestamp)
    if ext:
        id_fn += ext
    return id_fn

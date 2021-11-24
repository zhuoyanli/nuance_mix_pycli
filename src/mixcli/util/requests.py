"""
Classes on handling HTTP requests towards Mix API endpoints
"""
from abc import ABCMeta, abstractmethod
import copy
import json
from typing import Optional, Union, List, Dict, Callable, Any, Tuple
import requests
import re
from io import BytesIO

from requests import Response

from .logging import Loggable
from .auth import MixApiAuthToken, MixApiAuthHandler, MixApiAuthTokenExpirationError
from . import truncate_long_str

DEFAULT_API_HOST = 'https://mix.nuance.com'
DEFAULT_API_PATH_PREFIX = '/v3'
URL_PATH_SEP = '/'
"""Default Mix production server for API requests"""
GET_METHOD = "GET"
POST_METHOD = "POST"
DELETE_METHOD = "DELETE"
PUT_METHOD = 'PUT'
SUPPORTED_HTTP_METHODS = {GET_METHOD, POST_METHOD, DELETE_METHOD, PUT_METHOD}
DEFAULT_API_REQUEST_HEADERS = {'accept': 'application/json', 'Connection': 'keep-alive',
                               'Authorization': 'Bearer {token}'}
_PTN_HEADER_VALUE_AUTH_TOKEN = re.compile(r'^Bearer\s+')

API_RESP_DATA_FIELD = 'data'


# typing hint alias
RequestResult = Union[bool, str, int, bytes, Dict, Response]


def get_api_resp_payload_data(payload_json: Dict, reduce_list: bool = True) -> Optional[Union[Dict, List]]:
    """
    Get the 'data' field from API response payload

    :param payload_json:
    :param reduce_list: Reduce the list from data field if there is only one element
    :return:
    """
    if API_RESP_DATA_FIELD not in payload_json:
        return payload_json
    payload_json_data: Union[Dict, str] = payload_json[API_RESP_DATA_FIELD]
    if isinstance(payload_json_data, list):
        if not payload_json_data:
            return None
        if len(payload_json_data) > 1:
            return payload_json_data
        if reduce_list:
            return payload_json_data[0]
        else:
            return payload_json_data
    else:
        return payload_json_data


def proc_headers_token_for_log(headers: Optional[Dict[str, Union[str, Any]]],
                               no_token: Optional[bool] = True) -> str:
    """
    Produce a representive string on HTTP headers, optionally removing auth token
    :param headers: HTTP headers
    :param no_token: whether or not token should be remove from Authorization header
    :return: A representive string for display purpose
    """
    if not headers:
        return '{}'
    headers_repr = dict()
    for k, v in headers.items():
        if no_token and k == 'Authorization' \
                and isinstance(v, str) and _PTN_HEADER_VALUE_AUTH_TOKEN.search(v):
            headers_repr[k] = 'Bearer ...'
        else:
            headers_repr[k] = v
    return json.dumps(headers_repr)


# noinspection PyUnusedLocal
def default_token_expire_action(auth_token: Optional[MixApiAuthToken] = None):
    """
    Default action when
    :return: None
    """
    raise MixApiAuthTokenExpirationError("Mix auth token has expired")


def chk_err_in_payload(json_payload, exc: bool = True):
    """
    Check if there are error(s) indicated in response.

    :param json_payload:
    :param exc: Should raise exception if error found.
    """
    err_fields = {'error', 'errors'}
    for errf in err_fields:
        if errf in json_payload and json_payload[errf]:
            if exc:
                raise RuntimeError(f'Response marked with {errf}: {json.dumps(json_payload[errf])}')
            else:
                return True


def validate_mix_resp_error(mix_json_resp: Dict):
    """
    Check Mix response with preset error field presences
    :param mix_json_resp: Json object of Mix response on API requests
    :return: None
    """
    chk_err_in_payload(mix_json_resp)


def validate_resp_json_payload(resp_payload: Union[str, Dict],
                               token_exp_action: Optional[Callable] = None, check_err: bool = True) -> Dict:
    """
    Validate HTTP response payload
    :param check_err:
    :param resp_payload: HTTP response payload, either a literal string of Json or Json object
    :param token_exp_action: A function which would be called when auth token is found expired
    :return: A Json object
    """
    if not resp_payload:
        # CURL does not return anything
        return json.loads('{}')
    try:
        if isinstance(resp_payload, str):
            json_result = json.loads(resp_payload)
        else:
            json_result = resp_payload
    except Exception as ex:
        raise RuntimeError(f"HTTP requests succeeded but returned invalid JSON: {resp_payload}") from ex

    orig_json_result = json_result
    if 'status' in json_result and json_result['status'] == 'error':
        raise RuntimeError(f"Error detected fro request: {resp_payload}")
    if check_err:
        chk_err_in_payload(json_result)
    if 'data' in json_result and json_result['data']:
        json_result = json_result['data']
        if isinstance(json_result, list):
            json_result = json_result[0]
        if 'error' in json_result:
            if 'status' in json_result['error'] and json_result['error']['status'].lower() == 'unauthorized':
                # we know the token has expired
                if not token_exp_action:
                    token_exp_action = default_token_expire_action
                token_exp_action()
            elif check_err:
                chk_err_in_payload(json_result)
        elif 'response' in json_result:
            validate_mix_resp_error(json_result['response'])
        elif check_err:
            chk_err_in_payload(json_result)
    else:
        ...
    return orig_json_result


class HTTPRequestHandler(Loggable, metaclass=ABCMeta):
    """
    Abstract class on handlers for HTTP Requests used in MixCli
    """
    def __init__(self, auth_handler: MixApiAuthHandler, name: Optional[str] = None,
                 log_level: Optional[Union[int, str]] = None, no_token_log: bool = True):
        """
        Constructor
        :param auth_handler: A MixApiAuthHandler instance from which auth tokens can be requested
        :param name: Name of the specific HTTPRequestHandler instance used in logging
        :param log_level: Default logging level for the instance
        :param no_token_log: Specification on whether or not auth tokens should be removed from logging
        """
        self._auth_hdlr = auth_handler
        if name:
            Loggable.__init__(self, bearer=name, log_level=log_level)
        else:
            Loggable.__init__(self, bearer=self, log_level=log_level)
        self._no_token_log = no_token_log

    @property
    def name(self):
        return 'HTTPReqHdlr'

    @property
    def no_token_log(self) -> bool:
        return self._no_token_log

    @no_token_log.setter
    def no_token_log(self, new_val: bool):
        self._no_token_log = new_val

    def get_default_headers(self, auth_token: Optional[str] = None) -> Dict:
        """
        Get the default headers for Mix3 API calls.
        :return: Json object of default headers to run Curl for Mix API endpoints
        """
        headers_copy = copy.copy(DEFAULT_API_REQUEST_HEADERS)
        if not auth_token:
            self.debug('requesting token from auth handler')
            auth_token = self._auth_hdlr.token
        headers_copy['Authorization'] = (headers_copy['Authorization']).format(token=auth_token)
        return headers_copy

    @abstractmethod
    def request(self, url: str, method: Optional[str] = None, headers: Optional[Dict] = None,
                data: Optional[Union[str, Dict]] = None, default_headers: bool = False, data_as_str: bool = True,
                url_fq: bool = False, no_output: bool = False, stream: bool = False, out_file: Optional[str] = None,
                json_resp: bool = False, validate_json: bool = True, check_error: bool = True,
                need_status: bool = False, byte_resp: bool = False,
                **kwargs) -> Optional[Union[RequestResult, Tuple[RequestResult, int]]]:
        """
        Send request

        :param need_status: Also need status code
        :param validate_json: When expecting JSON response, validate the JSON
        :param byte_resp: Function should return bytestring as response
        :param out_file: Response payload should be directed to an output file
        :param stream: Response payload is expected to be returned progressively and should be retrieved as stream.
        :param url: Target API endpoint or URL
        :param method: HTTP method to use for sending the request
        :param headers: HTTP headers used in request
        :param data: Payload data used in request
        :param default_headers: If should use default HTTP headers for Mix API requests
        :param data_as_str: Data should be treated as string
        :param url_fq: If function parameter "url" is a fully-qualified URL
        :param no_output: Do not expect any output in response
        :param json_resp: The response payload is expected to be a valid Json object, array, or value.
        :param check_error: If function should perform error-checking on response payload.
        :param kwargs:
        :return:
        """
        ...

    @abstractmethod
    def is_http_method_supported(self, method: str) -> bool:
        """
        Check if a HTTP method is supported
        :param method: Name of HTTP method
        :return: True if this HTTP method is
        """
        ...

    @property
    @abstractmethod
    def host(self):
        ...

    @property
    @abstractmethod
    def endpoint_prefix(self):
        ...


class PyRequestsRunner(HTTPRequestHandler):
    """
    Implementation class to query HTTP/HTTPS APIs with "requests" package
    """
    def __init__(self, auth_handler: MixApiAuthHandler,
                 host: Optional[str], log_level: Optional[Union[str, int]] = None,
                 no_token_log: Optional[bool] = True):
        """
        Constructor

        :param auth_handler: The MixApiAuthHandler instance used to generate auth token info for request headers
        :param host: Host name to send HTTP/HTTPS requests
        :param log_level: Log level used in this instance
        :param no_token_log: Suppress auth toke from logging messages.
        """
        HTTPRequestHandler.__init__(self, auth_handler, self.name, log_level=log_level, no_token_log=no_token_log)
        if host:
            self._host = host
        else:
            self._host = DEFAULT_API_HOST
        # hostname must not end with '/'
        if self._host.endswith(URL_PATH_SEP):
            self._host = self._host[:-1]
        # endpoint path prefix should start with '/'
        self._endpt_prefix = DEFAULT_API_PATH_PREFIX
        if not self._endpt_prefix.startswith(URL_PATH_SEP):
            self._endpt_prefix = URL_PATH_SEP + self._endpt_prefix

    @property
    def name(self) -> str:
        return 'PyReqRunner'

    @classmethod
    def requests_method(cls, method: str) -> str:
        return method

    @property
    def host(self) -> str:
        return self._host

    @property
    def endpoint_prefix(self) -> str:
        return self._endpt_prefix

    def endpoint_url(self, endpoint: str, need_prefix: bool = True) -> str:
        if not endpoint.startswith(URL_PATH_SEP):
            endpoint = URL_PATH_SEP + endpoint
        prefix = self.host
        if need_prefix:
            prefix += self.endpoint_prefix
        return prefix + endpoint

    def request(self, url: str, method: Optional[str] = None, headers: Optional[Dict] = None,
                data: Optional[Union[str, Dict]] = None, default_headers: bool = False, data_as_str: bool = True,
                url_fq: bool = False, stream=False, outfile=None, no_output: bool = False,
                json_resp: bool = False, validate_json: bool = True, check_error: bool = True,
                byte_resp: bool = False, need_status: bool = False,
                **kwargs) -> Optional[Union[RequestResult, Tuple[RequestResult, int]]]:
        if json_resp and byte_resp:
            raise RuntimeError('Argument json_resp and byte_resp can NOT be both True')
        if byte_resp:
            stream = True
        if not method:
            req_method = GET_METHOD
        else:
            if not self.is_http_method_supported(method):
                raise ValueError(f'Given requests HTTP method not supported: {method}')
            req_method = self.requests_method(method)
        url = url
        if not url_fq:
            url = self.endpoint_url(url)
        if not headers:
            if default_headers:
                headers = self.get_default_headers()
        if data:
            if isinstance(data, str):
                try:
                    self.debug(f'data being string: {truncate_long_str(data)}')
                    if not data_as_str:
                        data = json.loads(data)
                except Exception as ex:
                    raise ValueError(f'"data" sent to RequestRunner.request is not a valid Json') from ex
            else:
                data_str = json.dumps(data)
                self.debug(f'data being json: {data_str}')
                if data_as_str:
                    data = data_str
                    self.debug('data will be sent as string in request')
        try:
            headers_repr = proc_headers_token_for_log(headers, self.no_token_log)
            self.debug(f'Running requests with method {req_method} url {url}, headers {headers_repr}')
            if not stream:
                resp_obj: Response = requests.request(url=url, method=req_method, headers=headers, data=data, **kwargs)
                if outfile:
                    self.debug(f'Writing response payload to file: {outfile}')
                    with open(outfile, 'wb') as fho:
                        fho.write(resp_obj.raw)
            else:
                self.debug('Need to stream response payload')
                with requests.request(method=req_method, url=url,
                                      headers=headers, data=data, stream=True, **kwargs) as resp_mgr_obj:
                    resp_obj = resp_mgr_obj
                    self.debug('Start to stream response payload')
                    with BytesIO() as ram_buffer:
                        for chunk in resp_obj.iter_content(chunk_size=1024):
                            if chunk:
                                ram_buffer.write(chunk)
                        self.debug(f'Bytes length read: {ram_buffer.getbuffer().nbytes}')
                        if outfile:
                            self.debug(f'Writing response payload to file: {outfile}')
                            with open(outfile, 'wb') as fho:
                                fho.write(ram_buffer.getvalue())
                        if byte_resp:
                            resp_bytes = ram_buffer.getvalue()
                        else:
                            resp_text = ram_buffer.getvalue().decode('utf-8')

        except Exception as ex:
            raise RuntimeError('Failed to run requests with given arguments') from ex
        resp_obj.raise_for_status()
        status_code = resp_obj.status_code

        def get_result(r):
            if need_status:
                return r, status_code
            else:
                return r
        if not resp_obj or not resp_obj.raw:
            self.debug('requests returned no result')
            return get_result(None)
        if no_output:
            self.debug('requests.request completed, no output expected, returning')
            return get_result(True)

        # should we return bytestring as response
        if byte_resp:
            # result saved in resp_bytes
            return get_result(resp_bytes)
        if not json_resp:
            # response payload is expected to be treated as textual data
            # self.debug(f'API HTTP resp as text: {resp.text}')
            self.debug(f'Treat API HTTP resp as text')
            if stream:
                # response payload has been retrieved as streaming and saved in resp_text
                return get_result(resp_text)
            else:
                return get_result(resp_obj.text)
        # response payload is expected to be Json
        self.debug(f'Validating requests response Json payload')
        if stream:
            # response payload has been retrieved as streaming and saved in resp_text
            resp_json = json.loads(resp_text)
        else:
            # no response payload is with resp_obj
            try:
                resp_json: Dict = resp_obj.json()
            except Exception as ex:
                raise ValueError(f'Mix API response not in expected JSON: {resp_obj.text}') from ex

        _ = validate_resp_json_payload(resp_json, check_err=check_error)
        jsonstr_resp = truncate_long_str(json.dumps(resp_json))
        self.debug(f'Validation succeeded on requests response Json payload: {jsonstr_resp}')
        return get_result(resp_json)

    def is_http_method_supported(self, method: str) -> bool:
        """
        Check if a HTTP method is supported
        :param method: Name of HTTP method
        :return: True if this HTTP method is
        """
        return method in SUPPORTED_HTTP_METHODS

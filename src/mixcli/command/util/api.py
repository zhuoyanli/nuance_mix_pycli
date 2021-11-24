"""
Mix **util** command group **api** command.

This command is useful to directly query APIs, either endpoints with default prefixes or FQ urls, and and display
responses, for design, testing, and debugging purposes.
"""
# the name of the actual register function can be whatever
import json
from argparse import ArgumentParser
from typing import Optional

from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD, POST_METHOD, DELETE_METHOD, PUT_METHOD

HTTP_METHODS = {'get': GET_METHOD, 'post': POST_METHOD, 'delete': DELETE_METHOD, 'put': PUT_METHOD}
HTTP_METHOD_LSTSTR = '[{s}]'.format(s=','.join([k for k in HTTP_METHODS.keys()]))


def pyreq_query_mixapi(httpreq_hander: HTTPRequestHandler, api_endpoint: Optional[str], fq_url: Optional[str],
                       http_method: Optional[str] = None, data: Optional[str] = None, json_data: bool = False,
                       auth_header: bool = True):
    """
    Send requests as specified to APIs and return response payloads.

    :param httpreq_hander: HTTPRequestHandler instance to send requests to APIs
    :param api_endpoint: API endpoint that would be prefixed by httpreq_hander.api_endpoint_prefix, mutually exclusive
    with fq_url
    :param fq_url: Fully-qualified URL as API url
    :param http_method: HTTP method to use for request
    :param data: Data in request
    :param json_data: True if data should be send as JSON object not string content
    :param auth_header: Include Mix authorization token info in request headers.
    :return: The response payload
    """
    if not api_endpoint and not fq_url:
        raise RuntimeError('Must specify either (prefixed) API endpoint or fully-qualified url!')
    elif api_endpoint and fq_url:
        raise RuntimeError('Can only specify either (prefixed) API endpoint or fully-qualified url!')
    api_url = api_endpoint
    url_fq = False
    if fq_url:
        api_url = fq_url
        url_fq = True
    dat = '{}'
    data_as_str = True
    if data:
        dat = data
    if json_data:
        dat = json.loads(data)
        data_as_str = False
    headers = {}
    if auth_header:
        headers = httpreq_hander.get_default_headers()
    method = GET_METHOD
    if http_method:
        method = http_method
    resp = httpreq_hander.request(url=api_url, url_fq=url_fq, method=method, data=dat, headers=headers,
                                  data_as_str=data_as_str)
    return resp


def query_mixapi(mixcli: MixCli, api_endpoint: Optional[str], fq_url: Optional[str],
                 http_method: Optional[str] = None, data: Optional[str] = None,
                 json_data: bool = False, auth_header: bool = True):
    """
    Send requests as specified to APIs and return response payloads.

    :param mixcli: MixCli instance to send requests to APIs
    :param api_endpoint: API endpoint that would be prefixed by httpreq_hander.api_endpoint_prefix, mutually exclusive
    with fq_url
    :param fq_url: Fully-qualified URL as API url
    :param http_method: HTTP method to use for request
    :param data: Data in request
    :param json_data: True if data should be send as JSON object not string content
    :param auth_header: Include Mix authorization token info in request headers.
    :return: The response payload
    """
    return pyreq_query_mixapi(mixcli.httpreq_handler, api_endpoint=api_endpoint, fq_url=fq_url,
                              http_method=http_method, data=data, json_data=json_data, auth_header=auth_header)


def cmd_api_query(mixcli: MixCli, **kwargs):
    """
    Default function when util api command is called.

    :param mixcli:
    :param kwargs:
    :return:
    """
    endp = kwargs['endpoint']
    fq_url = kwargs['url']
    datstr = kwargs['data']
    data_as_json = kwargs['json_data']
    http_method = kwargs['method']
    if http_method:
        method = HTTP_METHODS.get(http_method)
        if not method:
            raise RuntimeError(f'Unknown HTTP method: {http_method}')
        http_method = method
    resp = query_mixapi(mixcli, api_endpoint=endp, fq_url=fq_url, http_method=http_method, data=datstr,
                        json_data=data_as_json)
    print(resp)


@cmd_regcfg_func('util', 'api', 'Query API endpoint directly', cmd_api_query)
def config_argparser(cmd_argparser: ArgumentParser):
    mutexgrp_url = cmd_argparser.add_mutually_exclusive_group(required=True)
    mutexgrp_url.add_argument('-e', '--endpoint', metavar='API_ENDPOINT', help='Mix API endpoint')
    mutexgrp_url.add_argument('-u', '--url', metavar='FULLYQUALIFIED_URL', help='Fully qualified URL for API')
    cmd_argparser.add_argument('-m', '--method', required=False, metavar='HTTP_METHOD',
                               help=f'HTTP method to use for sending request: {HTTP_METHOD_LSTSTR}')
    cmd_argparser.add_argument('-d', '--data', required=False, metavar='REQUEST_DATA',
                               help='Data as string in request payload')
    cmd_argparser.add_argument('-j', '--json-data', action='store_true', help='Data used as JSON object')

"""
MixCli **ns** command group **search** command

This command would search meta info for a given namespace.

Please note this command would search for arbitrary namespace, not only those namespaces of which the represented
user account is a member. That being said, this command is effectively an extended version of ns list command.

Lookup in this command is accomplished in two phases: The first phase is to search the given namespace name from
the namespaces affiliated with the represented user account, actually done by calling the implementation in
ns list command.

If no affiliated namespace is of name that matches the given name, this command will execute a global search:
search the given namespace name from all namespaces in Mix platform. Please note that although such 'global search'
has only been tested with an account with global PS privilege. it is believed that this global search would also
work for regular accounts.

This command is not really intended to be used by users. Instead the implementation of this command is used by
'ns' command groups. For example, 'ns new-deployment' command needs such to create deployment configs for arbitrary
namespaces: Creating deployment configs in namespaces would require Mix IDs of namespaces in API requests' payloads.
That being said, when users use namespace names as arguments in 'ns new-deployment' command, that command needs
processes to lookup namespace IDs with the names.
"""
import json
import os
import os.path
import datetime
from argparse import ArgumentParser
from typing import Union, Dict, Optional, Tuple, List
from mixcli import MixCli
from ..ns.list import pyreq_list_affiliated_ns
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD
from mixcli.util.cmd_helper import write_result_outfile

__ERR_MSG_NS_NOTFOUND = 'Namespace with name {ns_name} not found in Mix'
"""
Template message used when namespace with given name not found.
"""


def pyreq_ns_search(httpreq_handler: HTTPRequestHandler, namespace: str,
                    json_resp: bool = False, need_global_lookup_result: bool = False,
                    glblsrch_totmp: bool = False, ) -> Optional[Union[Dict, str, Tuple[Dict, Dict]]]:
    """
    Search meta info for given name of namespace by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        GET /bolt/namespaces
        GET /bolt/applications

    :param glblsrch_totmp: If generated temp file should be kept
    :param httpreq_handler: A HTTPRequestHandler instance
    :param namespace: the name of namespace to look up for ID
    :param json_resp: should return Json of lookup result, if found, instead of just the ID
    :param need_global_lookup_result: should return the response from global lookup attempt if do so
    :return: None if namespace of given name not found, Json object if found and
    json_resp is True, namespace ID as str otherwise.
    """
    result: List[Dict] = pyreq_list_affiliated_ns(httpreq_handler)
    for ns_meta in result:
        if ns_meta['name'] == namespace:
            httpreq_handler.debug(f'Found member namespace that matches {namespace}: ' + json.dumps(ns_meta))
            if json_resp:
                return ns_meta
            else:
                return ns_meta['id']
    httpreq_handler.debug(f'Target namespace {namespace} not found in affiliated results, need global search.')
    httpreq_handler.debug(f'Look up on overall nuance.com namespace. We redirect network payloads to a file')
    # this request would return a huge payload containing exhaustive info for all application configurations
    # for all users and namespaces. Therefore we rather ask curl to save the output to a file instead of
    # trying to receive that from stdout piping
    endpoint = '/bolt/applications'
    tmp_outfile = None
    if glblsrch_totmp:
        timestamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        tmp_outfile = os.path.join(os.getcwd(),
                                   f'tmp_app_config_lookup_{timestamp}.json')
        httpreq_handler.debug(f'Temp file for redirected CURL output: {tmp_outfile}')
    resp: Dict = httpreq_handler.request(url=endpoint, method=GET_METHOD, default_headers=True,
                                         stream=True, outfile=tmp_outfile, json_resp=True)
    for app_conf_grp in resp['data']:
        if app_conf_grp['namespace_name'] != namespace:
            continue
        ns_search_result = dict()
        ns_search_result['name'] = namespace
        ns_search_result['id'] = app_conf_grp['namespace_id']
        ns_search_result['is_member'] = False
        if need_global_lookup_result:
            httpreq_handler.debug(f'Retruning global lookup resp and result: {json.dumps(ns_search_result)}')
            return ns_search_result, resp
        else:
            httpreq_handler.debug(f'Retruning result: {json.dumps(ns_search_result)}')
            return ns_search_result
    raise ValueError(__ERR_MSG_NS_NOTFOUND.format(ns_name=namespace))


def ns_search(mixcli: MixCli, namespace: str,
              json_resp: bool = False, glblsrch_totmp: bool = None) -> Optional[Union[Dict, str]]:
    """
    Search meta info for given name of namespace.

    :param glblsrch_totmp: If true save global search result to temp file
    :param mixcli: a MixCli instance
    :param namespace: the name of namespace to look up for ID
    :param json_resp: should return Json of lookup result, if found, instead of just the ID
    :return: None if namespace of given name not found, Json object if found and
    json_resp is True, namespace ID as str otherwise.
    """
    return pyreq_ns_search(mixcli.httpreq_handler, namespace, json_resp=json_resp, glblsrch_totmp=glblsrch_totmp)


def cmd_ns_search(mixcli: MixCli, **kwargs: Union[str, bool]):
    """
    Default command function when MixCli ns search command is called.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: None
    """
    """
    Example payload Json
    when the user, for whom the auth token represents, is a member of the inquired namespace:
    {
      "id": 322, 
      "name": "zhuoyan.li@nuance.com", 
      "path": "zhuoyan.li@nuance.com", 
      "url": "", 
      "is_personal": true, 
      "accurate_model_enabled": true, 
      "is_member": true
    }
    when the user is not a member of the inquired namespace:
    {
      "name": "not.for.me@nuance.com", 
      "id": 111,
      "is_member": false
    }
    """
    ns_name = kwargs['name']
    saveto_tempfile = kwargs['tempfile']
    json_srchrslt = ns_search(mixcli, ns_name, json_resp=True, glblsrch_totmp=saveto_tempfile)
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=json_srchrslt, out_file=out_file, is_json=True, logger=mixcli)
    else:
        mixcli.info('Namespace search result: '+json.dumps(json_srchrslt))
    return True


@cmd_regcfg_func('ns', 'search', 'Search namespace ID for given name', cmd_ns_search)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-n', '--name', required=True, metavar='NAME_OF_NS_TO_LOOKUP',
                               help='Name of namespace to search')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")
    cmd_argparser.add_argument('-t', '--tempfile', action='store_true',
                               help='Save global search result to temporary file (DEBUG purpose)')

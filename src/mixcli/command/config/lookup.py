"""
MixCli **config** command group **lookup** command.

This command is used to lookup meta information on a particular Mix app configuration, with the
constraints of namespace, also app config group and context tag where the config belongs to.

This command is actually more intended to be used either internally by other commands, or used for lookup meta
info necessary to run app new-deploy command.

Please note that this command can perform 'global' search: Search namespaces of which the authorized account
is not a member. Such 'global' search will result in significant response latency and a response payload of considerable
size (~15Mb). The argument glblsrch_totmp is intended to be used only to triage this feature for development purpose.
"""
import json
from argparse import ArgumentParser
from typing import Optional, Union, Dict, List
from mixcli import MixCli
from ..ns.search import pyreq_ns_search
from ..ns.list import pyreq_list_affiliated_ns
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile

DEFAULT_APP_CFG_GROUP = 'Mix Sample App'
APP_CFG_META_FIELD_CTX_TAG_META = 'app_context_tag'
CTX_TAG_META_FIELD_TAG_MAGIC_ID = 'deploy_config_magic_id'

ATTRIB_LOOKUP_RTEXCP_ERRCODE = 'lookup_errorcode'
ERR_LOOKUP_RESP_ERROR = 10000
ERR_NAMESPACE_NOTFOUND = 10001
ERR_APP_CFG_GROUP_NOTFOUND = 10002
ERR_APP_CFG_TAG_NOTFOUND = 10003
ERR_NO_AFFILIATED_NAMESPACE = 10004


def pyreq_lookup_app_config(httpreq_handler: HTTPRequestHandler,
                            namespace: Optional[str], namespace_id: Optional[int],
                            app_config_group: str, app_config_tag: str,
                            global_search: bool = True, do_tempfile: bool = False) -> Optional[Dict]:
    """
    Lookup Application Config with given namespace ID, Application config group name, and tag name
    by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        GET '/bolt/applications?namespace_id={namespace_id}'


    :param httpreq_handler: a HTTPRequestHandler instance
    :param namespace: str, name of namespace where the application configuration group belongs
    :param namespace_id: str, the ID for the namespace where the application configuration group belongs
    :param app_config_group: str, the name of the application configuration group, usually it is 'My Sample Apps'
    :param app_config_tag: str, the name/tag of the applciation configuration
    :param global_search: If function should do global search
    :param do_tempfile: Generate temp file to store global inquiry result, for debugging purpose only.
    :return: None if such app config is not found; Json object for the meta of the config otherwise
    """

    # First of all we check all the affliated namespaces to the user account (represented by the auth token).
    # Affiliated namespace is a namespace of which the account is a member.
    result: List[Dict] = pyreq_list_affiliated_ns(httpreq_handler)
    # If the expected namespace, referred to by either argument namespace or namespace_id, is a
    # affiliate namespace, then we do NOT need global look-up.
    need_global_lookup = True
    # namespace ID 1 is reserved for the global nuance.com
    if namespace_id and namespace_id == 1:
        need_global_lookup = True
    else:
        # we go through all the found affiliated namespaces
        for ns_meta in result:
            # one ns_meta is a Json data for a namespace
            # try to match the names or IDs
            if (namespace and ns_meta['name'] == namespace) or \
                    (namespace_id and ns_meta['id'] == namespace_id):
                # yes we match, so no need for global lookup
                need_global_lookup = False
                # now we complete the value for either namespace or namespace ID
                if not namespace_id:
                    httpreq_handler.debug(f'Found member namespace {ns_meta["name"]} that matches name {namespace}')
                    namespace_id = ns_meta['id']
                elif not namespace:
                    httpreq_handler.debug(f'Found member namespace {ns_meta["id"]} that matches ID {namespace_id}')
                    namespace = ns_meta['name']
                break

    if need_global_lookup:
        if global_search is False:
            if namespace:
                ns_display = f'namespace [{namespace}]'
            else:
                ns_display = f'namespace ID #[{namespace_id}'
            exc_msg = f'No namespaces affiliated with credentials found matching {ns_display}! Global search disabled!'
            exc = RuntimeError(exc_msg)
            setattr(exc, ATTRIB_LOOKUP_RTEXCP_ERRCODE, ERR_NO_AFFILIATED_NAMESPACE)
            raise exc

    if need_global_lookup:
        httpreq_handler.debug('No affiliated namespaces matched filter: {f}, {rs}'
                              .format(f=f'namespace={namespace}' if namespace else f'namespace_id={namespace_id}',
                                      rs=repr(result)))
    else:
        httpreq_handler.debug(f'Found affiliated namespace with name {namespace} id {namespace_id}')
    if need_global_lookup:
        # we leverage the global lookup to ns search command
        debug_msg = 'Look up on universal nuance.com namespace.'
        if do_tempfile:
            debug_msg += " Shall direct API response to temporary file"
        httpreq_handler.debug(debug_msg)
        ns_search_result = pyreq_ns_search(httpreq_handler, namespace=namespace, json_resp=True,
                                           glblsrch_totmp=do_tempfile, need_global_lookup_result=True)
        # no global lookup didn't get us anything, have to abort
        if not ns_search_result:
            exc = RuntimeError('Global namespace lookup failed with empty result! Maybe server error!')
            setattr(exc, ATTRIB_LOOKUP_RTEXCP_ERRCODE, ERR_LOOKUP_RESP_ERROR)
            raise exc
        # when need_global_lookup_result is True, curl_ns_search returns a tuple
        (_, global_lookup_json) = ns_search_result
        resp: Dict = global_lookup_json
    else:
        api_endpoint = f'/bolt/applications?namespace_id={namespace_id}'
        resp = httpreq_handler.request(url=api_endpoint, method=GET_METHOD, default_headers=True, json_resp=True)
        """
        {"data": [
          {
            "id": 312, 
            "name": "Mix Sample App", 
            "created_at": "2019-12-11T20:03:39.690663Z", 
            "modified_at": "2019-12-11T20:03:39.690669Z", 
            "namespace_id": 322,
            "namespace_name": "zhuoyan.li@nuance.com",
            "app_configs": [
              // one thing to note here is the it seems that the app configs in the same
              // app config group are not further grouped by TAG names, even though Mix UI
              // do group them by different TAG names.
              {
                "id": 5897, 
                "created_at": "2020-09-21T00:00:30.859846Z", 
                "last_updated": "2020-09-21T00:00:30.859851Z", 
                "tag": "shark_hackz_2020", 
                "app_id": 312, 
                "nlu_model_versions": [
                  {
                    "id": 7253, "label": "NLU_7793_8", 
                    "build_type": "nlu", "version": 8, 
                    "created": "2020-09-19T05:51:43.166363Z", 
                    "project_id": 7793, "status": "COMPLETED", "failure_reason": null, 
                    "language_model": "gen", "notes": "", 
                    "sources": ["nuance_custom_data"], "ccss_build_id": "48310b8e-c8cd-46ce-b995-9cf003c47301", 
                    "ccss_model_id": "2f5fb9e8-ff79-41a4-8901-9a43dbeabecb", 
                    "locale": "en_US", "dynamic_concepts": [], 
                    "language_model_version": "4.7.0", "model_type": "FAST"
                  }
                ], 
                "asr_model_versions": [
                  {
                    "id": 6360, "label": "ASR_7793_8", 
                    "build_type": "asr", "version": 8, "created": "2020-09-19T05:51:47.946477Z", 
                    "project_id": 7793, "status": "COMPLETED", "failure_reason": null, "language_model": "gen", 
                    "notes": "", "sources": ["nuance_custom_data"], 
                    "ccss_build_id": "f1709b03-e861-4040-aab9-59ff450e30a6", 
                    "ccss_model_id": "06f11d6a-cc8a-4cc4-9984-2c33602e1c8d", 
                    "locale": "en_US", "nlu_model_version_id": 7253, "language_model_version": "4.7.0"
                  }
                ], 
                "dialog_model_versions": [
                  {"id": 5771, "label": "DIALOG_7793_4", "build_type": "dialog", "version": 4, 
                  "created": "2020-09-21T00:00:10.429908Z", "project_id": 7793, 
                  "status": "COMPLETED", "failure_reason": null, "language_model": "gen", 
                  "notes": "", "sources": null, 
                  "ccss_build_id": "756a3c9e-562a-4f8c-9a70-50e06640ab1b", 
                  "ccss_model_id": "55242528-799c-4e12-9168-16c1766f158f", "nlu_model_version_id": null
                  }
                ], 
                "parent_id": 5795, "children": [], "is_synced_with_ccss": true
              },
              ...
            },
            ...
          }, // end of one app config group
          ...
          ]
        }   
        """
    # do some empirical sanity checks
    if 'data' not in resp or not isinstance(resp['data'], list) or not resp['data']:
        exc = RuntimeError('App config lookup result does not have "data" field or it is not non-empty list')
        setattr(exc, ATTRIB_LOOKUP_RTEXCP_ERRCODE, ERR_LOOKUP_RESP_ERROR)
        raise exc
    result = resp['data']
    # As we got the list of all app config groups, we go through them
    # Firstly we check if the namespace  is valid
    # result now is a list of JSON objects, each being meta data for a App deployment config GROUP for the account
    # {
    #             "id": 312,
    #             "name": "Mix Sample App",
    #             "created_at": "2019-12-11T20:03:39.690663Z",
    #             "modified_at": "2019-12-11T20:03:39.690669Z",
    #             "namespace_id": 322,
    #             "namespace_name": "zhuoyan.li@nuance.com",
    #             "app_configs": [
    #               ...
    #             ]
    #             ...
    # }
    app_cfg_group_for_ns = []
    for app_config_group_meta in result:
        if (namespace and app_config_group_meta['namespace_name'] != namespace) or \
                (namespace_id and app_config_group_meta['namespace_id'] != int(namespace_id)):
            continue
        app_cfg_group_for_ns.append(app_config_group_meta)
    if not app_cfg_group_for_ns:
        if namespace:
            ns_display = f'namespace [{namespace}]'
        else:
            ns_display = f'namespace ID #[{namespace_id}'
        exc = RuntimeError(f'No app config group found for {ns_display}, check namespace [id] argument!')
        setattr(exc, ATTRIB_LOOKUP_RTEXCP_ERRCODE, ERR_NAMESPACE_NOTFOUND)
        raise exc

    app_cfg_group_for_name = []
    for app_config_group_meta in app_cfg_group_for_ns:
        cfg_group_name = app_config_group_meta['name']
        if app_config_group != cfg_group_name:
            continue
        app_cfg_group_for_name.append(app_config_group_meta)
    if not app_cfg_group_for_name:
        exc_msg = f'No config group found matching "{app_config_group}"!'
        # it could be an common error that user meant to select 'Mix Sample App' but spelling is incorrect
        arg_cfg_grp_strip = app_config_group.replace(' ', '')
        if 'sampleapp' in arg_cfg_grp_strip.lower():
            exc_msg += ' Did you mean "Mix Sample App" group (case-sensitive, with space)?'
        exc = RuntimeError(exc_msg)
        setattr(exc, ATTRIB_LOOKUP_RTEXCP_ERRCODE, ERR_APP_CFG_GROUP_NOTFOUND)
        raise exc
    if len(app_cfg_group_for_name) > 1:
        # We expect only one meta data object for one app config group.
        # If not, the API endpoint may have changed. As precautions we throw exceptions
        exc = RuntimeError(f'Unexpected meta data count for app config group: {len(app_cfg_group_for_name)}')
        setattr(exc, ATTRIB_LOOKUP_RTEXCP_ERRCODE, ERR_LOOKUP_RESP_ERROR)
        raise exc
    app_config_group_meta = app_cfg_group_for_name[0]

    app_config_for_tag_all = []
    app_config_for_tag = None
    for app_conf in app_config_group_meta['app_configs']:
        if app_conf['tag'] != app_config_tag:
            continue
        app_config_for_tag_all.append(app_conf)
        if app_config_for_tag:
            continue
        app_config_for_tag = dict()
        app_config_for_tag['namespace'] = {
            'name': namespace,
            'id': int(namespace_id)
        }
        # this ID should be used when users 'promote' the new config
        # e.g. clicking the checkbox on the target server in 'Sanbox' section
        # then clicking on the button of 'Deploy'
        deploy_promotion_magic_id = int(app_conf['parent_id']) \
            if 'parent_id' in app_conf and app_conf['parent_id'] else int(app_conf['id'])
        app_config_for_tag[APP_CFG_META_FIELD_CTX_TAG_META] = {
            'group_name': app_config_group_meta['name'],
            'group_id': int(app_config_group_meta['id']),
            'name': app_conf['tag'],
            'id': int(app_conf['id']),
            CTX_TAG_META_FIELD_TAG_MAGIC_ID: deploy_promotion_magic_id
        }
        break
    if app_config_for_tag_all:
        print(app_config_for_tag_all)
    # httpreq_handler.debug('Found the app conf group:\n{j}'.format(j=json.dumps(app_conf_grp)))
    # we found the righ app config group, same namespace, and same app config group name
    if not app_config_for_tag:
        exc = RuntimeError(f'Not app config tag in "{app_config_group}" found matching "{app_config_tag}"')
        setattr(exc, ATTRIB_LOOKUP_RTEXCP_ERRCODE, ERR_APP_CFG_TAG_NOTFOUND)
        raise exc
    return app_config_for_tag


def lookup_app_config(mixcli: MixCli, namespace: Optional[str], namespace_id: Optional[Union[int, str]],
                      app_config_group: str, app_context_tag: str,
                      global_search: bool = True, do_tempfile: bool = False) -> Optional[Dict]:
    """
    Lookup Application Config with given namespace ID, Application Configuration group name, and configuration name.

    :param mixcli: a MixCli instance
    :param namespace: str, name of namespace where the application configuration group belongs
    :param namespace_id: str, the ID for the namespace where the application configuration group belongs
    :param app_config_group: str, the name of the application configuration group, usually it is 'My Sample Apps'
    :param app_context_tag: str, the name/tag of the applciation configuration
    :param global_search: If function should do global search
    :param do_tempfile: Generate temp file to store global inquiry result, for debugging purpose only.
    :return:
    """
    """
    Example result in Json
    {
      'namespace': {
        'name': 'zhuoyan.li@nuance.com', 
        'id': '322'}, 
      'app_context_tag': {
        'group_name': 'ZhuoyanMixApps', 
        'group_id': 1710, 
        'name': 'testDeployAPI', 
        'id': 8568, 
        'deploy_config_magic_id': 8445
      }
    }
    """
    namespace_id = assert_id_int(namespace_id, 'namespace') if namespace_id else None
    return pyreq_lookup_app_config(mixcli.httpreq_handler, namespace=namespace, namespace_id=namespace_id,
                                   app_config_group=app_config_group, app_config_tag=app_context_tag,
                                   global_search=global_search, do_tempfile=do_tempfile)


def cmd_app_config(mixcli: MixCli, **kwargs: Union[str, bool]):
    """
    Default funciton when app lookup command is called.

    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from keyword arguments from cmd line
    :return: True
    """
    ns_name = kwargs['ns']
    ns_id = kwargs['ns_id']
    app_config_group = kwargs['config_group']
    config_name = kwargs['context_tag']
    do_tempfile = kwargs['save_globalsearch']
    result = lookup_app_config(mixcli, namespace=ns_name, namespace_id=ns_id,
                               app_config_group=app_config_group, app_context_tag=config_name,
                               do_tempfile=do_tempfile)
    if not result:
        raise ValueError(f'No App config found for filters: Namespace: {ns_id}, App Config Group: {app_config_group}, '
                         f'App Config: {config_name}')
    # result is a JSON payload
    out_file = kwargs['out_file']
    if out_file:
        mixcli.info(f'The following command result written to file: {out_file}')
        mixcli.info(json.dumps(result))
        write_result_outfile(content=result, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(json.dumps(result))
    return True


@cmd_regcfg_func('config', 'lookup', 'Lookup app config meta', cmd_app_config)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    mutex_grp_ns = cmd_argparser.add_mutually_exclusive_group(required=True)
    mutex_grp_ns.add_argument('--ns', metavar='NAMESPACE_NAME', help='Name of namespace for the App config')
    mutex_grp_ns.add_argument('--ns-id', metavar='NAMESPACE_ID', help='ID of namespace for the App config')
    cmd_argparser.add_argument('--config-group', metavar='APP_CONFIG_GROUP_NAME',
                               default=DEFAULT_APP_CFG_GROUP,
                               help=f'Name of the app config group. Default to "{DEFAULT_APP_CFG_GROUP}"')
    cmd_argparser.add_argument('--context-tag', required=True, metavar='APP_CONFIG_TAG_NAME',
                               help='Name of the application configuration tag, e.g. "AXXXX_CXXXX"')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")
    cmd_argparser.add_argument('--save-globalsearch', action='store_true',
                               help='Generate temp files to store global inquiry payload, for debugging purpose only.')

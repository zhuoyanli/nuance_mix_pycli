"""
MixCli **config** command group **rm** command.

This command is useful for removing all existing configs under a particular context tag.

Currently Mix platform does not offer UIs to removing more than one config in given context tag with some push-button
fashion UIs. If there are more than one app config under a context tag and user wants to remove all of them, user
would have to use the remove/delete UI for every config iteratively and manually. This is rather annoying and this
command offers a batch-removal solution.

Please note there are some considerations when use this command:

1.  As designed in current Mix platform, when a context tag is created, it is always created with a particular app
    config, which we can call as 'root config'. That being said, uses may not create an empty context tag with NO app
    configs at all. Any new app configs created for that context tag afterwards will be created as **child configs**
    of the **root config**.
2.  Regarding the **root configs**, there are certain special attributes from empirical observations
    2.1     A **root config** may not be removed/deleted when there are existing child app configs;
    2.2     When the **root configs** are removed/deleted, the context tags will also be removed/deleted by themselves.
            That being said, if users want to keep context tags, they must keep the associated **root configs**.
3.  There may have been an app config in a context tag that has been deployed/promoted to servers. If that is the case,
    this command will fail with exceptions. Users would have to firstly remove the **promotion** in Mix UI
    manually. This will be one-off action as there could be only one deployed/promoted config in a context tag.

"""

from argparse import ArgumentParser
from typing import Optional

from requests import HTTPError

from mixcli import MixCli
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD, DELETE_METHOD, get_api_resp_payload_data
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import assert_id_int
from .lookup import DEFAULT_APP_CFG_GROUP, ATTRIB_LOOKUP_RTEXCP_ERRCODE, ERR_NO_AFFILIATED_NAMESPACE,\
    lookup_app_config, APP_CFG_META_FIELD_CTX_TAG_META, CTX_TAG_META_FIELD_TAG_MAGIC_ID


def pyreq_get_ctx_tag_details(httpreq_handler: HTTPRequestHandler, ctx_tag_magic_id: int):
    """
    Get detailed meta data for give app context tag represented by its magic id. Effectively the meta data
    contains all app configs in a context tag.

    :param httpreq_handler:
    :param ctx_tag_magic_id:
    :return:
    """
    api_endpoint = f'api/v2/app-configs/{ctx_tag_magic_id}?with_details=true'
    data = '{}'
    resp = httpreq_handler.request(url=api_endpoint, method=GET_METHOD, default_headers=True,
                                   data=data, data_as_str=True,
                                   json_resp=True)
    return resp


def pyreq_del_app_config(httpreq_handler: HTTPRequestHandler, app_config_id: int):
    """
    Delete a specific app config identified by the app_config_id.

    :param httpreq_handler:
    :param app_config_id: The ID of app config to be removed
    :return:
    """
    api_endpoint = f'/api/v2/app-configs/{app_config_id}'
    data = '{}'
    try:
        _ = httpreq_handler.request(url=api_endpoint, method=DELETE_METHOD, default_headers=True, data=data,
                                    data_as_str=True)
    except HTTPError as he:
        # If there is app config that has already been deployed, we cannot deal with it here
        # Users would need to manually remove the deployment in Mix UI
        if he.response.status_code == 400:
            raise RuntimeError(f'Failed to delete {app_config_id} as regular app config!' +
                               " Are there some deployed models already? If yes you need to remove it!") from he
        else:
            raise he
    except Exception as ex:
        raise ex


def rm_app_cfg_ctx_tag(mixcli: MixCli, app_cfg_group: str, app_ctx_tag: str,
                       namespace: Optional[str] = None, namespace_id: Optional[str] = None,
                       rm_ctx_tag: bool = False):
    ns_name = namespace
    ns_id = namespace_id
    if ns_id:
        ns_id = assert_id_int(ns_id, 'namespace')
    try:
        ctxtag_meta = lookup_app_config(mixcli, namespace=ns_name, namespace_id=ns_id, app_config_group=app_cfg_group,
                                        app_context_tag=app_ctx_tag, global_search=False, do_tempfile=False)
    except RuntimeError as rtex:
        if not hasattr(rtex, ATTRIB_LOOKUP_RTEXCP_ERRCODE):
            raise RuntimeError('Failed to look up target app config with arguments!') from rtex
        if getattr(rtex, ATTRIB_LOOKUP_RTEXCP_ERRCODE) != ERR_NO_AFFILIATED_NAMESPACE:
            raise RuntimeError('Failed to look up target app config with arguments!') from rtex
        # we only remove app configs from namespace(s) of which the account represented by credentials is a member
        raise RuntimeError('No affiliated namespace found for credentials. Aborted as precaution!') from rtex
    ctxtag_meta_magic_id = ctxtag_meta[APP_CFG_META_FIELD_CTX_TAG_META][CTX_TAG_META_FIELD_TAG_MAGIC_ID]
    ctxtag_detail_meta = pyreq_get_ctx_tag_details(mixcli.httpreq_handler, ctx_tag_magic_id=ctxtag_meta_magic_id)
    ctxtag_detail_meta = get_api_resp_payload_data(ctxtag_detail_meta)
    # find the root
    field_parent_id = 'parent_id'
    for cfg_meta_blk in ctxtag_detail_meta:
        if cfg_meta_blk[field_parent_id] is None:
            if cfg_meta_blk['id'] != ctxtag_meta_magic_id:
                raise RuntimeError(f'Root config magic id {cfg_meta_blk["id"]} does not match with ' +
                                   f'{ctxtag_meta_magic_id} from context tag: {app_ctx_tag}')
        elif cfg_meta_blk[field_parent_id] != ctxtag_meta_magic_id:
            raise RuntimeError(f'Child config magic id {cfg_meta_blk[field_parent_id]} does not match with ' +
                               f'{ctxtag_meta_magic_id} from context tag: {app_ctx_tag}')

    child_cfg_ids = set()
    for cfg_meta_blk in ctxtag_detail_meta:
        if cfg_meta_blk[field_parent_id] is None:
            continue
        child_cfg_ids.add(cfg_meta_blk['id'])
    for child_cfg_id in sorted(child_cfg_ids):
        mixcli.info(f'Deleting child app config with id {child_cfg_id} from context tag {app_ctx_tag}')
        pyreq_del_app_config(mixcli.httpreq_handler, app_config_id=child_cfg_id)
    if rm_ctx_tag:
        # remove the last root config
        mixcli.info(f'Deleting root app config with id {ctxtag_meta_magic_id} from context tag {app_ctx_tag}')
        pyreq_del_app_config(mixcli.httpreq_handler, app_config_id=ctxtag_meta_magic_id)


def cmd_config_rm(mixcli: MixCli, **kwargs):
    ns_name = kwargs['ns']
    ns_id = kwargs['ns_id']
    app_cfg_grp = kwargs['config_group']
    app_ctx_tag = kwargs['context_tag']
    rm_ctx_tag = kwargs['rm_tag']
    rm_app_cfg_ctx_tag(mixcli, app_cfg_group=app_cfg_grp, app_ctx_tag=app_ctx_tag, namespace=ns_name,
                       namespace_id=ns_id, rm_ctx_tag=rm_ctx_tag)


@cmd_regcfg_func('config', 'rm',
                 'Remove all app configs for (namespace, config group, context tag) and the optionally context tag',
                 cmd_config_rm)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.epilog = """In Mix a context tag is always created with a particular app config, containing
source project reference (where models come from), target model build version(s), and etc. This app config is
the basis for the context tag, and any app configs created afterwards are linked to the basis config as children
configs. The basis config can only be removed after all children configs have been removed; once the basis config
is gone the context tag is also removed from Mix platform. As a result, by default this command would only remove
all children app configs for a given context tag, and only remove the basis app config, effectively also the context
tag, if "rm-tag" option is specified. That being said, by default the basis app config is always excluded from removal.

Furthermore, if there are app configs that have already been deployed to servers, this command will fail to remove them
and throw exceptions. Users would have to firstly remove the deployment manually in Mix MANAGE UI. That should be a
one-off action as there could be only one deployment in effect among all app configs in a context tag.    
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
    cmd_argparser.add_argument('--rm-tag', action='store_true',
                               help='Remove the context tag altogether. If not the base app config will be kept.')

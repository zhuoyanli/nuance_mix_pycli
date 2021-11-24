"""
MixCli **config** command group **create** command.

This command is useful when used to create a 'new' application configuration for a namespace,
e.g. zhuoyan.li@nuance.com, a Mix app config group, e.g. MySampleApps, a context tag, e.g. AC1245_4586,
from a Mix project, referred by ID. If no arguments on which models should be deployed, all of ASR/NLU/DLG
models will be included. If no arguments on which build versions of models should be deployed, or 0 is used,
the latest build version of models will be included.

**IMPORTANT NOTICE**: The **config tag** specified for this command must be an **EXISTING** tag. For the moment
this command can **NOT** create a new tag. Users would have to manually create their tags first in Mix dashboard UI
if they want new ones.

Nonetheless, at least one of {nlu,asr,dlg}-(model)version needs to be specified, as at least one model needs to
be included in a deployment. Use number **0** to refer to **latest** build version of models.

The argument '--do-deploy' accounts for the operations of
selecting 'new' build config in Mix MANAGE UI and clicking 'promote' to actually deploy models to servers.

The '--locale' argument is mandatory when NLU models are included in deployment.
"""
import json
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Optional, Dict, List, Union

from .lookup import lookup_app_config, DEFAULT_APP_CFG_GROUP as DEF_APP_CFG_GRP, \
    ATTRIB_LOOKUP_RTEXCP_ERRCODE, \
    ERR_APP_CFG_TAG_NOTFOUND, CTX_TAG_META_FIELD_TAG_MAGIC_ID, APP_CFG_META_FIELD_CTX_TAG_META
from ..project.get import get_project_meta
from mixcli import MixCli
from mixcli.util import count_notnone, assert_json_field_and_type
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile, MixLocale
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD, GET_METHOD

URL_DEPLOY_MAGIC_CODE_HOWTO = 'https://confluence.labs.nuance.com/x/j4K4D'
DLG_MODEL_NAME = 'dialog'
FIELD_DEPLOY_CFG_IN_CLIENT_CRED = 'deployment'


def assert_deploy_cfg_js(deploy_cfg_js: Dict) -> bool:
    """
    Validate JSON config for deployment. The deploy config should look like the following:


    :param deploy_cfg_js: JSON config for deployment
    :return: True
    """
    # for the moment we expect two fields in the deployment config
    # 1. step_id as a JSON number (integer)
    # 2. region_ids as a list of JSON number(s) (integer)
    if 'step_id' not in deploy_cfg_js or not isinstance(deploy_cfg_js['step_id'], int):
        raise RuntimeError(f'Deployment config NO field "step_id" as integer: {json.dumps(deploy_cfg_js)}')
    # noinspection PyPep8Naming
    FIELD_REGION_IDS = 'region_ids'
    if FIELD_REGION_IDS in deploy_cfg_js:
        if isinstance(deploy_cfg_js[FIELD_REGION_IDS], list):
            for rid in deploy_cfg_js[FIELD_REGION_IDS]:
                if not isinstance(rid, int):
                    raise RuntimeError('Element(s) in "region_ids" field of Deployment config JSON must be integer')
            return True
    raise RuntimeError(f'Deployment config NO field "{FIELD_REGION_IDS}" as list of int: {json.dumps(deploy_cfg_js)}')


def pyreq_deploy_buildcfg(httpreq_handler: HTTPRequestHandler, buildcfg_id: int,
                          deploy_cfg: Optional[Dict] = None) -> Dict:
    # first we get the necessary request payload for 'deploy' a config
    if not deploy_cfg:
        api_endpoint = f'api/v2/app-configs/{buildcfg_id}?with_details=true'
        resp: Dict = httpreq_handler.request(url=api_endpoint, method=GET_METHOD, default_headers=True, json_resp=True)
        assert_json_field_and_type(resp, 'data', list)
        resp_data: Dict = resp['data'][0]
        assert_json_field_and_type(resp_data, 'steps', list)
        deploy_cfg_blk = resp_data['steps'][0]
        assert_json_field_and_type(deploy_cfg_blk, 'step_id', int)
        assert_json_field_and_type(deploy_cfg_blk, 'regions', list)
        assert_json_field_and_type(deploy_cfg_blk['regions'][0], 'id', int)
        deploy_cfg = {
            'step_id': deploy_cfg_blk['step_id'],
            'region_ids': [
                deploy_cfg_blk['regions'][0]['id']
            ]
        }
        httpreq_handler.info(f'Using deploy config from API: {json.dumps(deploy_cfg)}')

    # the following values are taken from looking at the network request/response payloads
    # when users manually do such in Mix Manage Applications UI. They are being used as-is.
    # So this deployment thing may subject to fail anytime
    # because Mix team could change their internal protocols without any notices.
    api_endpoint = f'/bolt/app-configs/{buildcfg_id}/promotions'
    resp = httpreq_handler.request(url=api_endpoint, method=POST_METHOD, default_headers=True,
                                   data=deploy_cfg, data_as_str=True, json_resp=True)
    """
    {
        "data": [
            {
                "created_at": "...", 
                "last_updated": "...", 
                "id": 15145, 
                "approved": true, 
                "comment": null,
                "promotion_flow_step_id": 328, 
                "app_config_id": 8575
            }
        ]}
    """

    # Let's do some sanity checks based on empirical knowledge on the expected successful response
    if 'data' not in resp or \
        not isinstance(resp['data'], list) or not resp['data'] or \
            'id' not in resp['data'][0] or 'created_at' not in resp['data'][0]:
        jsonstr_deployment_payload = json.dumps(deploy_cfg)
        raise ValueError(f'Mix app config deployment seems to have failed: {jsonstr_deployment_payload}')

    return resp


def pyreq_create_new_build_cfg(httpreq_handler: HTTPRequestHandler, deploy_config_magic_id: int,
                               project_id: int, locale: str, project_meta: Dict,
                               nlu_model_version: Optional[int] = None,
                               asr_model_version: Optional[int] = None,
                               dlg_model_version: Optional[int] = None,
                               do_deploy: bool = False, do_deploy_w_cfg: Optional[Dict] = None) -> Dict:
    """
    Create new Mix deployment config in namespace, config group, config tag, for project and model builds
    by sending requests to API endpoint with Python 'requests' package.


    API endpoint
    ::
        POST '/api/v2/app-configs/{deploy_config_magic_id}/child-configs'

    :param httpreq_handler: a HTTPRequestHandler instance
    :param deploy_config_magic_id: The maigical ID for overriding app deployment config
    :param project_id: Mix project ID
    :param locale: locale of Mix project NLU model build to be deployed
    :param project_meta: project meta
    :param nlu_model_version: build version of NLU model to be deployed
    :param asr_model_version: build version of ASR model to be deployed
    :param dlg_model_version: build version of dialog model to be deployed
    :param do_deploy: Deploy the new build config after creation, mutually exclusive from do_deploy_cfg
    :param do_deploy_w_cfg: Deploy the new build config after creation with the JSON deployment config in string,
    :return:
    """
    version_spec = {
    }

    # We must use 'not None' because the integer could be 0 so as be treated as False
    if nlu_model_version is not None:
        version_spec["nlu"] = nlu_model_version
    if asr_model_version is not None:
        version_spec["asr"] = asr_model_version
    if dlg_model_version is not None:
        version_spec["dialog"] = dlg_model_version

    final_ver_spec = {
        'models': {},
        'hosts': []
    }

    def key_version(m):
        return m['version']

    for mdl_name, ver in version_spec.items():
        # no builds for this model
        field_mdl_build_history = f'{mdl_name}_builds'
        if field_mdl_build_history not in project_meta:
            continue
        if not ver or ver == 0:
            build_used = max(project_meta[field_mdl_build_history], key=key_version)['version']
            httpreq_handler.info(f'Using latest {mdl_name} build [v{build_used}] for project with ID {project_id}')
        else:
            build_used = int(ver)
        mdl_spec = [{
            'project_id': project_id,
            'builds': [
                {
                    'locale': locale,
                    'version': build_used
                }
            ]
        }]
        if mdl_name == DLG_MODEL_NAME:
            # the payload for dialog is different, no "builds": [...]
            # it is "dialog": [{"project_id": <int_id>, "version": <int_version>}]
            mdl_spec[0].pop('builds')
            mdl_spec[0]['version'] = build_used
        final_ver_spec['models'][mdl_name] = mdl_spec

    jsonstr_final_ver_spec = json.dumps(final_ver_spec)
    httpreq_handler.debug(f'Payload to be sent to create/override the config: {jsonstr_final_ver_spec}')
    api_endpoint = f'/api/v2/app-configs/{deploy_config_magic_id}/child-configs'
    headers = httpreq_handler.get_default_headers()
    headers['Content-Type'] = 'application/json'
    resp: Dict[str, List[Dict]] = httpreq_handler.request(url=api_endpoint, method=POST_METHOD, default_headers=True,
                                                          data=final_ver_spec, data_as_str=True,
                                                          json_resp=True)
    # {"data": [{"id": 8570, "created_at": "...",
    # "locale": null, "tag": "NuanceNextBankingDemo", "app_id": 1710, "parent_id": 7263, ...
    # the ['data'][0]['id'] becomes the new config tag id

    # Let's do some sanity checks based on empirical knowledge on the expected successful response
    if 'data' not in resp or \
        not isinstance(resp['data'], list) or not resp['data'] or \
            'id' not in resp['data'][0] or 'created_at' not in resp['data'][0]:
        raise ValueError(f'Mix app config tag overriding seems to have failed: {json.dumps(resp)}')

    new_build_cfg_id = resp['data'][0]['id']
    httpreq_handler.info(f'App config tag ID now becomes {new_build_cfg_id}')
    # should we deploy the new configuration?
    if not do_deploy and not do_deploy_w_cfg:
        return resp

    # yes we should deploy
    return pyreq_deploy_buildcfg(httpreq_handler=httpreq_handler, buildcfg_id=new_build_cfg_id,
                                 deploy_cfg=do_deploy_w_cfg)


def create_new_config(mixcli: MixCli, namespace: Optional[str], namespace_id: Optional[Union[int, str]],
                      app_config_group: str, cfg_ctx_tag: str,
                      project_id: Union[int, str], locale: str,
                      nlu_model_version: Optional[int], asr_model_version: Optional[int],
                      dlg_model_version: Optional[int],
                      do_deploy: bool = False, do_deploy_w_cfg: Optional[str] = None) -> Dict:
    """
    Create a new "overriding" build configuration, for a context tag, for model deployment.

    :param mixcli: a MixCli instance
    :param namespace: name of namespace to the deploy cfg belongs
    :param namespace_id: id of namespace to the deploy cfg belongs
    :param app_config_group: name of the application config group
    :param cfg_ctx_tag: context tag (name) of the application config
    :param project_id: id of mix project to be deployed
    :param locale: locale (name) of the NLU model build of project to be deployed
    :param nlu_model_version: build version of NLU model to be deployed
    :param asr_model_version: build version of ASR model to be deployed
    :param dlg_model_version: build version of DLG model to be deployed
    :param do_deploy: Deploy the new build config after creation, mutually exclusive from do_deploy_cfg
    :param do_deploy_w_cfg: Deploy the new build config after creation with the JSON deployment config in string,
    mutually exclusive from do_deploy.
    :return:
    """
    # validation

    # We need to deploy at least one model, {nlu,asr,dlg}_model_version can NOT be all NONE
    not_none = count_notnone(nlu_model_version, asr_model_version, dlg_model_version, exact_none=True)
    if not_none <= 0:
        raise RuntimeError('Must specify at least one of {nlu,asr,dlg} (model) version')

    # either do_deploy or do_deploy_cfg
    if do_deploy and do_deploy_w_cfg:
        raise RuntimeError('Cannot use both "do_deploy" and "do_deploy_cfg" at the same time')
    # process deployment
    if do_deploy_w_cfg:
        # if a deployment cfg is specified from cmd line,
        # we make that prioritized over the default one coming from client credential cfg file
        try:
            deploy_cfg_js = json.loads(do_deploy_w_cfg)
            assert_deploy_cfg_js(deploy_cfg_js)
        except Exception as ex:
            raise RuntimeError(f'Invalid JSON literal for deployment config: {do_deploy_w_cfg}') from ex
    else:
        deploy_cfg_js = None

    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    ns_id = namespace_id
    if namespace_id:
        ns_id = assert_id_int(namespace_id, 'namespace')

    try:
        app_config_tag_meta: Dict[str, Dict[str, Union[int, str]]] = \
            lookup_app_config(mixcli, namespace=namespace, namespace_id=ns_id,
                              app_config_group=app_config_group, app_context_tag=cfg_ctx_tag, do_tempfile=False)
    except RuntimeError as ex:
        if not hasattr(ex, ATTRIB_LOOKUP_RTEXCP_ERRCODE):
            raise ex
        lookup_exc_errcode = getattr(ex, ATTRIB_LOOKUP_RTEXCP_ERRCODE)
        if lookup_exc_errcode != ERR_APP_CFG_TAG_NOTFOUND:
            raise ex
        # This command could only create **new** app config in an EXISTING context tag, not a non-existing one
        exc_msg = "This command could only create new app config in an EXISTING app context tag. " + \
                  "If you want a totally new context tag please first create it manually in Mix MANAGE UI."
        raise RuntimeError(exc_msg) from ex

    deploy_cfg_magic_id = app_config_tag_meta[APP_CFG_META_FIELD_CTX_TAG_META][CTX_TAG_META_FIELD_TAG_MAGIC_ID]
    proj_meta = get_project_meta(mixcli, project_id=proj_id)

    return pyreq_create_new_build_cfg(mixcli.httpreq_handler, deploy_config_magic_id=deploy_cfg_magic_id,
                                      project_id=proj_id, locale=mixloc, project_meta=proj_meta,
                                      nlu_model_version=nlu_model_version,
                                      asr_model_version=asr_model_version,
                                      dlg_model_version=dlg_model_version,
                                      do_deploy=do_deploy, do_deploy_w_cfg=deploy_cfg_js)


def cmd_config_new(mixcli: MixCli, **kwargs: Union[bool, Optional[str]]):
    """
    Default command when the config create command is called
    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: True
    """
    ns_name = kwargs['ns']
    ns_id = kwargs['ns_id']
    cfg_grp = kwargs['cfg_group']
    ctx_tag = kwargs['ctx_tag']
    proj_id = kwargs['project_id']
    # we make sure users don't enter locale codes like aa-AA, they should be in formats of aa_AA
    loc = kwargs['locale']
    nlu_mdl_ver = kwargs['nlu_version']
    asr_mdl_ver = kwargs['asr_version']
    dlg_mdl_ver = kwargs['dlg_version']
    do_deploy = kwargs['do_deploy']
    do_deploy_w_cfg = kwargs['do_deploy_w_cfg']
    result = create_new_config(mixcli, namespace=ns_name, namespace_id=ns_id,
                               app_config_group=cfg_grp, cfg_ctx_tag=ctx_tag,
                               project_id=int(proj_id), locale=loc,
                               nlu_model_version=nlu_mdl_ver,
                               asr_model_version=asr_mdl_ver,
                               dlg_model_version=dlg_mdl_ver,
                               do_deploy=do_deploy, do_deploy_w_cfg=do_deploy_w_cfg)
    # the result would be a JSON payload
    output_file = kwargs['out_file']
    if output_file:
        write_result_outfile(content=result, is_json=True, out_file=output_file, logger=mixcli)
    else:
        action = 'created'
        if do_deploy:
            action = 'created and deployed'
        msg_tmplt = "Successfully {act} new app config for {n} {g} {t} {p} with response payload: ".\
            format(act=action,
                   n=f'namespace {ns_name}' if ns_name else f'namespace ID {ns_id}',
                   g=f'config group {cfg_grp}',
                   t=f'context tag {ctx_tag}',
                   p=f'Mix project ID {proj_id}')
        mixcli.info(msg_tmplt+json.dumps(result))
    return True


@cmd_regcfg_func('config', 'create', 'Create new build config for a context tag and optionally deploy', cmd_config_new)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """

    cmd_argparser.epilog = """Please note that the application context tag used in this command must be an **EXISTING** 
tag. If you want a totally new context tag please first create it manually in Mix MANAGE UI.

For regular Mix user on Mix production server with app config promotion flow enabled, a default application config
group will be created with name "{def_cfg_grp}", which would be the app config group for most users to create
new app configs. Therefore the default value of argument "cfg-group" is already set to {def_cfg_grp} so users usually
do not have to type the complete quoted string in command argument.""".format(
        def_cfg_grp=DEF_APP_CFG_GRP,
        url_magic_code_howto=URL_DEPLOY_MAGIC_CODE_HOWTO
    )

    cmd_argparser.formatter_class = RawTextHelpFormatter

    mutex_grp_ns = cmd_argparser.add_mutually_exclusive_group(required=True)
    mutex_grp_ns.add_argument('--ns', metavar='NAMESPACE_NAME', help='Name of namespace for the App config')
    mutex_grp_ns.add_argument('--ns-id', metavar='NAMESPACE_ID', help='ID of namespace for the App config')
    cmd_argparser.add_argument('--cfg-group', metavar='APP_CONFIG_GROUP_NAME', default=DEF_APP_CFG_GRP,
                               help=f'Name of the app config group, default to "{DEF_APP_CFG_GRP}"')
    cmd_argparser.add_argument('--ctx-tag', required=True, metavar='APP_CONTEXT_TAG_NAME',
                               help='Name of the application config context tag, e.g. "AXXXX_CXXXX"')
    cmd_argparser.add_argument('-p', '--project-id', type=int, metavar='PROJECT_ID', required=True,
                               help='ID of Mix project whose models would be used in deployment')
    cmd_argparser.add_argument('-l', '--locale', required=True, metavar='aa_AA_locale', help='Locale in aa_AA format')
    cmd_argparser.add_argument('-n', '--nlu-version', type=int, metavar='NLU_MODEL_BUILD_VERSION',
                               help='Integer version number of NLU model build used in deployment, 0 for latest')
    cmd_argparser.add_argument('-a', '--asr-version', type=int, metavar='ASR_MODEL_BUILD_VERSION',
                               help='Integer version number of ASR model build used in deployment, 0 for latest')
    cmd_argparser.add_argument('-d', '--dlg-version', type=int, metavar='NLU_MODEL_BUILD_VERSION',
                               help='Integer version number of DIALOG model build used in deployment, 0 for latest')
    mutexgrp_deployment = cmd_argparser.add_mutually_exclusive_group(required=False)
    mutexgrp_deployment.add_argument('--deploy', action='store_true', dest='do_deploy', required=False,
                                     help='Deploy latest build config with deploy config read from API')
    mutexgrp_deployment.add_argument('--deploy-cfg', dest='do_deploy_w_cfg', metavar='DEPLOYMENT_JSON_STR',
                                     help='Internal argument, do not use.')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

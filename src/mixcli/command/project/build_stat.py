"""
MixCli **project** command group **build-stat** command.

This command would retrieve meta info of build history of Mix project.

This command is not really intended to be used by users. The implementation of this command will be used
by other commands for model build related processes.
"""
import json
from argparse import ArgumentParser
from typing import Dict, Union, Optional
from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD, get_api_resp_payload_data
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile
from ..project.model_export import _MODEL_NLU, _MODEL_DLG, _MODEL_ASR

_PROJ_MDLS_WITH_BUILD = [_MODEL_ASR, _MODEL_NLU, _MODEL_DLG]
FIELD_ASR_DP_TOPIC = 'baseDatapack'
FIELD_LOCALES = 'languages'
FIELD_BLD_VER = 'version'


def get_latest_build_version(model_build_stat_json, model: str = _MODEL_NLU,
                             exc_na: bool = True) -> Optional[int]:
    """
    Get the latest build version of a model from a model build stat JSON.

    :param model_build_stat_json: A JSON payload of Mix project model build stat query result
    :param model: Name of Mix project model, must be one of nlu, asr, dialog
    :param exc_na: Raise exception if expected model build state not available from payload. Otherwise return None
    :return: The integer as latest build version for model, or None if build stat for model not available in payload.
    """
    assert model in _PROJ_MDLS_WITH_BUILD, f'{model} not a supported Mix model name'
    if model not in model_build_stat_json:
        if exc_na:
            raise RuntimeError(f'Build stat for model {model} not available in model build stat query payload')
        else:
            return None
    return max([stat_blk['version'] for stat_blk in model_build_stat_json[model]])


def pyreq_get_model_build_stat(httpreq_hdlr: HTTPRequestHandler, project_id: int) -> Optional[Dict]:
    """
    Get Mix project meta info by sending requests to API endpoint with Python 'requests' package.

    API endponit
    ::
        GET /api/v2/projects/{project_id}/models.

    :param httpreq_hdlr: a HTTPRequestHandler instance
    :param project_id: Mix project ID
    :return: json object, the project meta info in Json
    """
    resp = httpreq_hdlr.request(url=f'api/v2/projects/{project_id}/models', method=GET_METHOD, default_headers=True,
                                json_resp=True)
    return resp


def get_model_build_stat(mixcli: MixCli, project_id: Union[str, int]) -> Optional[Dict]:
    """
    Get Mix project model build stat.

    :param mixcli: a MixCli instance
    :param project_id: Mix project ID
    :return: json object, the query JSON payload for project model build stat(s)
    """
    """
    from the json payload
    {
        "project_id": "id_num",
        "data" : [
            {
                "nlu": [{...},{...},...],
                "asr": [{...},{...},...],
                "dialog": [{...},{...},{...}]
            }
        ]
    }
    """
    proj_id = assert_id_int(project_id, 'project')
    return pyreq_get_model_build_stat(mixcli.httpreq_handler, project_id=proj_id)


def cmd_project_build_stat(mixcli: MixCli, latest: bool = False, version: bool = False, **kwargs: str):
    """
    Default function when MixCli project get command is called. Processing concept list command.

    :param version: Only include the build version(s)
    :param mixcli: MixCli, a MixCli instance
    :param latest: Only include the status for the latest build of model(s)
    :param kwargs: keyword arguments from command-line arguments
    :return: True
    """
    proj_id = kwargs['project_id']
    mdl_bld_stat_json = get_api_resp_payload_data(get_model_build_stat(mixcli, proj_id))
    bld_stat_result = {}
    mdls_from_cmd = kwargs['model']

    def version_only(stat):
        if version:
            return stat[FIELD_BLD_VER]
        else:
            return stat

    for mdl_cmd in sorted(mdls_from_cmd):
        if mdl_cmd not in mdl_bld_stat_json:
            bld_stat_result[mdl_cmd] = {}
            continue
        else:
            if not latest:
                bld_stat_result[mdl_cmd] = version_only(mdl_bld_stat_json[mdl_cmd])
            else:
                latest_ver = -1
                for ver_stat in mdl_bld_stat_json[mdl_cmd]:
                    if ver_stat[FIELD_BLD_VER] <= latest_ver:
                        continue
                    latest_ver = ver_stat[FIELD_BLD_VER]
                    bld_stat_result[mdl_cmd] = version_only(ver_stat)

    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=bld_stat_result, is_json=True, out_file=out_file, logger=mixcli)
    else:
        mixcli.log(f'Model build stat(s) on {",".join(mdls_from_cmd)} for project with ID {proj_id}: ' +
                   json.dumps(bld_stat_result))
    return True


# the name of the actual register function can be whatever
@cmd_regcfg_func('project', 'build-stat', 'Get model build stats for Mix project', cmd_project_build_stat)
def config_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-m', '--model', metavar='MODEL_TO_QUERY', nargs='+',
                               choices=_PROJ_MDLS_WITH_BUILD, default=_PROJ_MDLS_WITH_BUILD,
                               help=f'Models to query, enum(s) from [{",".join(_PROJ_MDLS_WITH_BUILD)}]')
    cmd_argparser.add_argument('--latest', action='store_true', help='Show only latest build')
    cmd_argparser.add_argument('--version', action='store_true', help='Only include build version(s)')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")


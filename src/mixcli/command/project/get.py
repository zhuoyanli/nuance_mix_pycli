"""
MixCli **project** command group **get** command.

This command will retrieve meta information for Mix projects, referred by IDs.

This command is not expected to be used by users directly, except that they want to extract useful meta info for
purpose of automation flows. Many of commands in MixCli use the implementation codes in this command.
"""
import json
from argparse import ArgumentParser
from typing import Dict, Union, Optional, List
from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile, project_name_from_meta

FIELD_ASR_DP_TOPIC = 'baseDatapack'
FIELD_LOCALES = 'languages'
PROJ_META_FIELD_NAME = 'name'
PROJ_META_FIELD_ID = 'id'


def get_mix_project_name(mixcli: MixCli, project_id: Union[str, int]) -> str:
    """
    Get the name for Mix project with ID project_id.

    :param mixcli: a MixCli isntance
    :param project_id: project ID
    :return: str,
    """
    proj_meta_json = get_project_meta(mixcli, project_id)
    if not proj_meta_json or PROJ_META_FIELD_NAME not in proj_meta_json:
        raise ValueError(f'Cannot get meta info for project {project_id}')
    return project_name_from_meta(proj_meta_json)


def get_project_name(proj_meta: Dict) -> str:
    if PROJ_META_FIELD_NAME not in proj_meta:
        raise RuntimeError(f'Expected project "{PROJ_META_FIELD_NAME}" field not found in meta')
    return proj_meta[PROJ_META_FIELD_NAME]


def get_project_id(proj_meta: Dict) -> int:
    if PROJ_META_FIELD_ID not in proj_meta:
        raise RuntimeError(f'Expected project "{PROJ_META_FIELD_ID}" field not found in meta')
    return proj_meta[PROJ_META_FIELD_ID]


META_FIELD_NLU_MODEL_MODES_ENABLED = 'model_types_enabled'


def get_nlu_model_modes_enabled(proj_meta: Dict) -> Optional[List[str]]:
    if META_FIELD_NLU_MODEL_MODES_ENABLED not in proj_meta:
        return None
    meta_model_modes_enabled = proj_meta[META_FIELD_NLU_MODEL_MODES_ENABLED]
    if not meta_model_modes_enabled or not isinstance(meta_model_modes_enabled, list):
        return None
    for m in meta_model_modes_enabled:
        if not isinstance(m, str):
            return None
    return meta_model_modes_enabled


def pyreq_get_project_meta(httpreq_hdlr: HTTPRequestHandler, project_id: int) -> Optional[Dict]:
    """
    Get Mix project meta info by sending requests to API endpoint with Python 'requests' package.

    API endpoing
    ::
        GET /api/v3/projects/{projectID}

    :param httpreq_hdlr: a HTTPRequestHandler instance
    :param project_id: Mix project ID
    :return: json object, the project meta info in Json
    """
    resp = httpreq_hdlr.request(url=f'api/v3/projects/{project_id}', method=GET_METHOD, default_headers=True,
                                json_resp=True)
    return resp


def get_project_meta(mixcli: MixCli, project_id: Union[str, int]) -> Optional[Dict]:
    """
    Get Mix project meta info by GET /api/v3/projects/{projectID}.

    :param mixcli: a MixCli instance
    :param project_id: Mix project ID
    :return: json object, the project meta info in Json
    """
    """
    from the json payload
    namespace: json['namespace_name']
    namespace_id: json['namespace_id']
    project_id: json['id']
    project_name: json['name']
    channels_meta: json['channels']
    NLU build meta: json['nlu_builds'] -> List[...]
    ASR build meta: json['asr_builds'] -> List[...]
    DIALOG build meta: json['dialog_builds'] -> List[...]
    """
    proj_id = assert_id_int(project_id, 'project')
    return pyreq_get_project_meta(mixcli.httpreq_handler, project_id=proj_id)


def cmd_project_get(mixcli: MixCli, **kwargs: str):
    """
    Default function when MixCli project get command is called.

    :param mixcli: MixCli, a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: True
    """
    proj_id = kwargs['project_id']
    proj_meta_json = get_project_meta(mixcli, proj_id)
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=proj_meta_json, is_json=True, out_file=out_file, logger=mixcli)
    else:
        mixcli.log(f'Meta for project with ID {proj_id}: '+json.dumps(proj_meta_json))
    return True


# the name of the actual register function can be whatever
@cmd_regcfg_func('project', 'get', 'Get Mix project meta info in Json', cmd_project_get)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

"""
MixCli **dlg** command group **try-build** command.

This command will do a run-time test build of DLG models. It is equivalent to the model building which
is activated when users click 'Try' button in Mix.dialog UI.

This would be particularly useful to test if Dialog models would build successfully, before running 'project build'
command to actually build the Dialog models.

Please note that Mix API endpoint will take some considerable processing time on the request.
"""
import json
from argparse import ArgumentParser
from typing import Union

from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD, get_api_resp_payload_data
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile

RESULT_DATA_STATUS_FIELD = 'status'
RESULT_STATUS_SUCCESS = 'SUCCESS'
RESULT_DATA_ERROR_FILED = 'errors'


def pyreq_dlg_trybuild(httpreq_hdlr: HTTPRequestHandler, project_id: int):
    """
    Run trial-build on dialog model for Mix project with ID project_id, by sending requests to
    API endpoint with Python 'requests' package.

    Please note that the dialog trial build may have result where status is 'SUCCESS' while there are warning messages
    in 'error' field.

    API endpoint
    ::
        POST api/v3/dialog/projects/<project_id>/generate

    :param httpreq_hdlr: a HTTPRequestHandler instance
    :param project_id: Mix project ID
    :return:
    """

    api_endpoint = f"api/v3/dialog/projects/{project_id}/generate"
    # we do NOT validate the response as JSON, in that the response payload will be in JSON format
    # but NOT a regular API response payload. The response will be the content of the exported JSON artifact.
    resp = httpreq_hdlr.request(url=api_endpoint, method=POST_METHOD, default_headers=True, json_resp=True,
                                check_error=False)
    resp_data = get_api_resp_payload_data(resp)
    return resp_data


def dlg_trybuild(mixcli: MixCli, project_id: Union[str, int], warning_ok: bool = True):
    """
    Run trial-build on dialog model for Mix project with ID project_id.

    :param warning_ok: Do not consider build results with warning as failures.
    :param mixcli: a MixCli instance
    :param project_id: Mix project ID
    :return: None
    """
    project_id = assert_id_int(project_id, 'project')
    result = pyreq_dlg_trybuild(mixcli.httpreq_handler, project_id=project_id)
    if RESULT_DATA_STATUS_FIELD not in result or result[RESULT_DATA_STATUS_FIELD] != RESULT_STATUS_SUCCESS:
        raise RuntimeError(f'Dialog model try-build failed for project {project_id}: {json.dumps(result)}')
    print(json.dumps(result))
    if not warning_ok and result[RESULT_DATA_ERROR_FILED]:
        raise RuntimeError(f'Warning(s) found in trial-build result: {json.dumps(result)}')
    return result


def cmd_dlg_trybuild(mixcli, **kwargs: str):
    """
    Default function when MixCli dlg export command is called.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: None
    """
    proj_id = kwargs['project_id']
    warning_aserr = kwargs['warning_aserr']
    result = dlg_trybuild(mixcli, proj_id, warning_ok=(not warning_aserr))
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=result, is_json=True, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(f'Dialog model try-build completed for project {proj_id}: {json.dumps(result)}')
    return True


@cmd_regcfg_func('dlg', 'try-build', 'Do run-time trial build of Dialog model for project', cmd_dlg_trybuild)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-w', '--warning-aserr', action='store_true',
                               help='Consider warning as build errors')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

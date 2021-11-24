"""
MixCli **job** command group **list** command

This command is not really expected to be used by users directly. The implementation codes are
being used by other commands.
"""
from argparse import ArgumentParser
import json
from typing import Dict, Union
from mixcli import MixCli
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD as REQ_GET_METHOD
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile


def pyreq_check_job_status(httpreq_handler: HTTPRequestHandler, project_id: int) -> Dict:
    """
    Check Mix job status for project by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        GET "/api/v2/projects/{project_id}/jobs"

    :param httpreq_handler: CurlRunner instance to run curl
    :param project_id: Mix project id
    :return: Json object as inquiry result
    """
    api_endpoint = f"/api/v2/projects/{project_id}/jobs"
    resp = httpreq_handler.request(url=api_endpoint, method=REQ_GET_METHOD, default_headers=True, json_resp=True)
    try:
        if isinstance(resp['data'], list) and resp['data']:
            return resp['data']
        else:
            return resp
    except Exception as ex:
        msg = f"Error when getting status for project {project_id}"
        if resp:
            msg += json.dumps(resp)
        print(msg)
        raise ex


def list_job(mixcli: MixCli, project_id: Union[int, str]) -> Dict:
    """
    List submitted jobs for Mix project.

    :param mixcli:
    :param project_id:
    :return:
    """
    """
    Example payload Json
    [
        {
          "response": {"errors": []}, 
          "id": "ad6e1b43b3abb67330cfeb13e6a501d8b392fb10", 
          "type": "train_build", 
          "status": "completed", 
          "start_time": "2020-08-30T04:26:01+00:00", 
          "end_time": "2020-08-30T04:26:17+00:00", 
          "duration": 16,
          "locale": "en-US"
        }, 
        {
          "response": {"errors": []}, 
          "id": "3e9884420c3fb06c7b6c6226b822ff07478c0b1d", 
          "type": "train_build", 
          "status": "completed", 
          "start_time": "2020-08-30T04:33:18+00:00", 
          "end_time": "2020-08-30T04:33:34+00:00", 
          "duration": 16, "locale": "en-US"
        },
        ...
    ]
    """
    proj_id = assert_id_int(project_id, 'project')
    # return curl_check_job_status(mixcli.httpreq_handler, project_id=proj_id)
    return pyreq_check_job_status(mixcli.httpreq_handler, project_id=proj_id)


def cmd_job_list(mixcli: MixCli, **kwargs: str):
    """
    Default function when MixCli job list command is called
    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command line
    :return: None
    """
    proj_id = kwargs['project_id']
    jsonarray_job_meta = list_job(mixcli, project_id=proj_id)
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=jsonarray_job_meta, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(f'Job meta(s) for project with ID {proj_id}: '+json.dumps(jsonarray_job_meta))
    return True


@cmd_regcfg_func('job', 'list', 'List Mix job(s) for project by project ID', cmd_job_list)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True,
                               help='Mix project ID')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")


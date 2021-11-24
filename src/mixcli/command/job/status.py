"""
MixCli **job** command group **status** command

This command is not really expected to be used by users directly. The implementation codes are
being used by other commands.
"""
from argparse import ArgumentParser
import json
from typing import Dict, Union, Optional, List, Callable
from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD
from mixcli.util.commands import cmd_regcfg_func

JOB_STATUS_FIELD = 'status'
JOB_STATUS_COMPLETED = 'completed'
JOB_STATUS_FAILED = 'failed'
JOB_STATUS_SUBMITTED = 'submitted'
JOB_ID_FILED = 'id'
_JOB_DATA_FIELD_IN_PAYLOAD = 'data'


def assert_job_meta_json(job_meta_json: Dict):
    """
    Assert a valid job status meta Json.

    :param job_meta_json:
    :return: None
    """
    if JOB_STATUS_FIELD not in job_meta_json:
        raise ValueError(f'Invalid job meta Json, not "{JOB_STATUS_FIELD} field found: {json.dumps(job_meta_json)}')


def assert_job_meta(func: Callable) -> Callable:
    """
    Decorator on function that is supposed to receive JSON object of meta info of Mix jobs as single argument.

    :param func: Function that is supposed to receive JSON object of meta info of Mix jobs as single argument.
    :return: A wrapper function
    """
    def wrapper(job_meta_json, *args, **kwargs):
        # print(f"Validating job meta: {json.dumps(job_meta_json)}")
        assert_job_meta_json(job_meta_json)
        return func(job_meta_json, *args, **kwargs)
    return wrapper


@assert_job_meta
def job_id_from_meta(job_meta_json: Dict) -> str:
    return job_meta_json[JOB_ID_FILED]


@assert_job_meta
def job_status_from_meta(job_meta_json: Dict) -> str:
    return job_meta_json[JOB_STATUS_FIELD]


@assert_job_meta
def job_succeeded(job_meta_json: Dict) -> bool:
    return job_status_from_meta(job_meta_json).lower() == JOB_STATUS_COMPLETED


@assert_job_meta
def job_failed(job_meta_json: Dict) -> bool:
    return job_status_from_meta(job_meta_json).lower() == JOB_STATUS_FAILED


@assert_job_meta
def job_completed(job_meta_json: Dict) -> bool:
    job_st = job_status_from_meta(job_meta_json).lower()
    return job_st == JOB_STATUS_COMPLETED or job_st == JOB_STATUS_FAILED


def pyreq_check_job_status(httpreq_handler: HTTPRequestHandler, project_id: int, job_id: str) -> Optional[Dict]:
    """
    Check Mix job status for project <project_id> job <job_id> by sending requests to API endpoint
    with Python 'requests' package.

    API endpoint
    ::
        GET /api/v2/projects/{project_id}/jobs/{job_id}

    :param httpreq_handler: A HTTPRequestHandler instance
    :param project_id: Mix project ID
    :param job_id: ID of the job to query
    :return: Json object as inquiry result
    """
    api_endpoint = f"/api/v2/projects/{project_id}/jobs/{job_id}"
    resp = None
    try:
        resp: Optional[Dict, Dict[str, List]] = \
            httpreq_handler.request(url=api_endpoint, method=GET_METHOD, default_headers=True, json_resp=True)
        if not resp:
            return None
        elif isinstance(resp['data'], list) and len(resp['data']) == 1:
            return resp['data'][0]
        else:
            return resp
    except Exception as ex:
        msg = f"Error when getting status for project {project_id} job {job_id}"
        if resp:
            msg += json.dumps(resp)
        httpreq_handler.error(msg)
        raise ex


def check_job_status(mixcli: MixCli, project_id: Union[str, int], job_id: str) -> Dict:
    """
    Check Mix job status for a given project.

    :param mixcli: A MixCli instance
    :param project_id: Mix project ID
    :param job_id: ID of job to inquire
    :return: Meta info of the job, where job status can be found
    """
    """
    example payload Json: (details for 'response' field could vary for NLU or ASR train jobs)
    {
      "response": {"voc_generation": {}, "data_sources": ["nuance_custom_data"], "errors": []},
      "id": "c016fe3db7bfaf161c1bd54003c94a3ffca99220",
      "type": "train_build",
      "status": "completed",
      "start_time": "2020-07-03T02:53:05+00:00",
      "end_time": "2020-07-03T02:55:00+00:00",
      "duration": 115,
      "locale": "en-US"
    }
    """
    project_id = assert_id_int(project_id, 'project')
    job_meta = pyreq_check_job_status(mixcli.httpreq_handler, project_id=project_id, job_id=job_id)
    return job_meta


def cmd_job_status(mixcli: MixCli, **kwargs: Union[str, bool]):
    """
    Default function when MixCli job status command is called.

    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command line
    :return: None
    """
    proj_id = kwargs['project_id']
    job_id = kwargs['job_id']
    json_job_status = check_job_status(mixcli, project_id=proj_id, job_id=job_id)
    if not json_job_status:
        mixcli.error_exit(f'Failed to inquire Job result for project {proj_id} job {job_id}')
    out_file = kwargs['out_file']
    status_only = kwargs['status_only']
    if out_file:
        if status_only:
            write_result_outfile(content=job_status_from_meta(json_job_status), out_file=out_file,
                                 is_json=False, logger=mixcli)
        else:
            write_result_outfile(content=json_job_status, out_file=out_file, is_json=True, logger=mixcli)
    else:
        msg_prefix = f'Status for project ID {proj_id} job ID {job_id}: '
        if status_only:
            mixcli.info(msg_prefix+job_status_from_meta(json_job_status))
        else:
            mixcli.info(msg_prefix+json.dumps(json_job_status))
    return True


@cmd_regcfg_func('job', 'status', 'Check Mix job status by job ID', cmd_job_status)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True,
                               help='Mix project ID')
    cmd_argparser.add_argument('-j', '--job-id', metavar='JOB_ID', required=True,
                               help='Mix job ID for the project')
    cmd_argparser.add_argument('-s', '--status-only', action='store_true', help='Only show status not response payload')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")


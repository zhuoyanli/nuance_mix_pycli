"""
MixCli **job** command group **wait** command

This command is not really expected to be used by users directly. The implementation codes are
being used by other commands.
"""
import json
import time
from typing import Union, Optional, Dict, Tuple, TypeVar
from argparse import ArgumentParser
from mixcli import MixCli
from .status import check_job_status, job_succeeded, job_failed, job_completed
from mixcli.util.cmd_helper import assert_id_int, run_coro_sync
from mixcli.util.commands import cmd_regcfg_func

JOB_STATUS_CHK_INTVL = 5
DEFAULT_JOB_WAIT_TIMEOUT_SEC = 10 * 60

T = TypeVar('T')


class OptJsonResult:
    """
    Utility class to produce the appropriate results to be returned
    in job_wait function, depending on the bool value of json_resp
    """
    def __init__(self, need_json=False):
        """
        Constructor
        :param need_json: bool value to decide if the associated
        Json payload object should be returned as well.
        """
        self._json_result = None
        self._need_json = need_json

    @property
    def json_result(self) -> Dict:
        return self._json_result

    @json_result.setter
    def json_result(self, new_jr: Dict):
        self._json_result = new_jr

    def result(self, rv: T) -> Union[T, Tuple[Dict, T]]:
        if self._need_json:
            return self._json_result, rv
        else:
            return rv


async def job_wait(mixcli: MixCli, project_id: int, job_id: str,
                   timeout: int = None, infinite_wait: bool = False,
                   exc_if_timeout: bool = True, exc_if_failed: bool = False,
                   json_resp: bool = False) -> Union[Tuple[Dict, Optional[bool]], Optional[bool]]:
    """
    Asynchronous function to wait for Mix job to complete (either succeed or fail).

    :param mixcli: MixCli instance
    :param project_id: the project ID for the job (all jobs in Mix are bound with projects.
    :param job_id: the job ID which is an ASCII string
    :param timeout: Timeout (in seconds) while waiting, discarded if infinite_wait is True
    :param infinite_wait: Should wait for the job infinitely
    :param exc_if_timeout: If True, raise Exception if Timeout, otherwise return None
    :param exc_if_failed: If True, raise Exception if the end status of job is not 'completed'
    :param json_resp: If True, should return the Json response payload, otherwise just True/False
    :return: If json_resp is False, return None if timeout, True if job succeeds, False if job fails; If
    json_resp is True, return (last_job_query_resp_payload, None) if timeout, return (end_query_resp_payload, True)
    if job succeeds, (end_query_resp_payload, False) if job failed
    """
    opt_rv = OptJsonResult(json_resp)

    project_id = assert_id_int(project_id, 'project')
    # get the job status
    try:
        opt_rv.json_result = check_job_status(mixcli=mixcli, project_id=project_id, job_id=job_id)
    except Exception as ex:
        raise ValueError(f'Cannot find the job to wait for: project {project_id} job {job_id}') from ex

    time_waited = 0
    if not timeout:
        timeout = DEFAULT_JOB_WAIT_TIMEOUT_SEC
    mixcli.info(f'Starting to wait for job project {project_id} job {job_id}')
    # is the job completed already?
    while not job_completed(opt_rv.json_result):
        # not yet
        if not infinite_wait:
            # we are not waiting infinitely
            # already TIMEOUT?
            if time_waited >= timeout:
                # yes TIMEOUT
                if exc_if_timeout:
                    # should raise exception?
                    raise TimeoutError('Time-out after {t} seconds for project {p} job {j}'
                                       .format(t=DEFAULT_JOB_WAIT_TIMEOUT_SEC,
                                               p=project_id,
                                               j=job_id))
                else:
                    # no, just retur None
                    return opt_rv.result(None)
            else:
                # not yet TIMEOUT
                # no we should continue waiting
                pass
        else:
            # we wait infinitely
            pass
        # sleep
        mixcli.debug(f'Sleep for {JOB_STATUS_CHK_INTVL} secs before updating status from {job_id}')
        time.sleep(JOB_STATUS_CHK_INTVL)
        # add the total wait time
        time_waited += JOB_STATUS_CHK_INTVL
        # update status again
        mixcli.debug(f'Updating status from {job_id} after {JOB_STATUS_CHK_INTVL} secs')
        opt_rv.json_result = check_job_status(mixcli, project_id=project_id, job_id=job_id)
        mixcli.debug(f'Received job status {json.dumps(opt_rv.json_result)}')
    # end of the waiting loop
    # now check the status
    if job_succeeded(opt_rv.json_result):
        # succeed
        mixcli.info(f'Completed waiting for job project {project_id} job {job_id}')
        return opt_rv.result(True)
    elif job_failed(opt_rv.json_result):
        if exc_if_failed:
            raise RuntimeError(f'Mix job failed: project {project_id} job {job_id}')
        else:
            return opt_rv.result(False)
    else:
        raise ValueError(f'Unexpected job status enum from meta: {json.dumps(opt_rv.json_result)}')


def job_wait_sync(mixcli: MixCli, project_id: Union[str, int], job_id: str,
                  timeout: Optional[int] = None, infinite_wait: bool = False,
                  exc_if_timeout: bool = True, exc_if_failed: bool = False,
                  json_resp: bool = False) -> Optional[bool]:
    """
    The non-asynchronous counterpart of job_wait.

    :param mixcli: MixCli instance
    :param project_id: the project ID for the job (all jobs in Mix are bound with projects.
    :param job_id: the job ID which is an ASCII string
    :param timeout: Timeout (in seconds) while waiting, discarded if infinite_wait is True
    :param infinite_wait: Should wait for the job infinitely
    :param exc_if_timeout: If True, raise Exception if Timeout, otherwise return None
    :param exc_if_failed: If True, raise Exception if the end status of job is not 'completed'
    :param json_resp: If True, should return the Json response payload, otherwise just True/False
    :return: If json_resp is False, return None if timeout, True if job succeeds, False if job fails; If
    json_resp is True, return (last_job_query_resp_payload, None) if timeout, return (end_query_resp_payload, True)
    if job succeeds, (end_query_resp_payload, False) if job failed
    """
    project_id = assert_id_int(project_id)
    # we just use the run_coro_sync function to run the job_wait asynchronous corountine in synchronous way
    return run_coro_sync(job_wait(mixcli, project_id=project_id, job_id=job_id,
                                  timeout=timeout, infinite_wait=infinite_wait,
                                  exc_if_timeout=exc_if_timeout, exc_if_failed=exc_if_failed,
                                  json_resp=json_resp))


def cmd_job_wait(mixcli: MixCli, **kwargs: Union[str, int, bool]):
    """
    Default function when job wait command is called
    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command line
    :return: None
    """
    proj_id = kwargs['project_id']
    job_id: str = kwargs['job_id']
    wait_infinite = kwargs['infinite']
    timeout = kwargs['timeout']
    if timeout:
        try:
            timeout = int(timeout)
        except Exception as ex:
            raise ValueError(f'Timeout must be valid integer for seconds: {timeout}') from ex
    err_on_failed = kwargs['err_on_failed']
    if wait_infinite:
        result = job_wait_sync(mixcli, project_id=proj_id, job_id=job_id,
                               infinite_wait=wait_infinite, exc_if_failed=err_on_failed)
    else:
        result = job_wait_sync(mixcli, project_id=proj_id, job_id=job_id,
                               timeout=timeout, exc_if_failed=err_on_failed)
    if result:
        mixcli.info(f'Mix job project {proj_id} job {job_id} has successfully completed')
        return True
    else:
        raise RuntimeError(f'Error occurred when waiting for project {proj_id} job {job_id}')


@cmd_regcfg_func('job', 'wait', 'Wait for Mix job to complete either successfully or failed', cmd_job_wait)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True,
                               help='Mix project ID')
    cmd_argparser.add_argument('-j', '--job-id', metavar='JOB_ID', required=True,
                               help='Mix job ID for the project')
    cmd_argparser.add_argument('--err-on-failed', action='store_true',
                               help="Command should exit as error when job failed")
    mutex_grp_wait_policy = cmd_argparser.add_mutually_exclusive_group(required=False)
    mutex_grp_wait_policy.add_argument('--infinite', action='store_true',
                                       help='Wait for the job infinitely')
    mutex_grp_wait_policy.add_argument('-t', '--timeout', type=int, metavar='TIMEOUT_IN_SECOND',
                                       help='Timeout in seconds when waiting for the job')

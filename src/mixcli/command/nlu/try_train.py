"""
MixCli **nlu** command group **try** command.

This command would replicate the 'Train Model' function in Mix.nlu UI to train a run-time NLU model for testing
annotations on utterances.
"""
import json
from argparse import ArgumentParser
from typing import Union, Optional, Dict

from mixcli import MixCli
from mixcli.command.job.wait import job_wait_sync
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile, MixLocale
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD


def pyreq_nlu_trytrain(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str) -> Optional[Dict]:
    """
    Get try-annotation on utterance with latest run-time NLU model for a Mix project and locale, by sending requests
    to Mix API endpoint with Python 'requests' package.

    API endpoint: POST /nlu/api/v1/nlu/<PROJ_ID>/annotations/train?sources=nuance_custom_data&locale=<LOCALE>
    Request payload: None

    :param httpreq_handler: HTTPRequestHandler to process requests and responses
    :param project_id: Mix project ID
    :param locale: Mix project NLU locale
    :return: JSON reponse payload from API endpoint
    """
    api_endpoint = f'/nlu/api/v1/nlu/{project_id}/annotations/train?sources=nuance_custom_data&locale={locale}'
    resp = httpreq_handler.request(url=api_endpoint, method=POST_METHOD, data='{}',
                                   default_headers=True, json_resp=True)
    return resp


def nlu_try_train(mixcli: MixCli, project_id: Union[int, str], locale: str, waitfor: bool = True) -> Dict:
    """
    Train a run-time NLU model for trying annotations on utterances, by sending requests to API endpoint
    with 'requests' package. If waitfor is False, function will return
    immediately after train jobs are launched; otherwise will return after train jobs are completed, either
    succeed or fail.

    The returned result from this function is a JSON object with at least one field 'train_response'. Its value
    will be the JSON response payload from model training API endpoint. If function waits for train job to complete,
    the returned result will have another field 'job_result'. Its value is the result from job-waiting function.

    :param mixcli: MixCli instance
    :param project_id: Mix project ID
    :param locale: Locale for NLU model
    :param waitfor: Wait until model train/build job is completed before returning
    :return: API response payload in JSON
    """
    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    trytrain_resp = pyreq_nlu_trytrain(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc)
    if 'id' not in trytrain_resp:
        raise RuntimeError(f'No "id" field in Try-Train API response payload: {json.dumps(trytrain_resp)}')
    result = json.loads('{}')
    result['train_response'] = trytrain_resp
    # should we wait for the job to complete?
    if not waitfor:
        # Nope
        mixcli.info(f'Return from try-train command without waiting: {json.dumps(result)}')
        return result
    # use the function from command.job.wait to wait for the job
    trainjob_id = trytrain_resp['id']
    result_jobst = job_wait_sync(mixcli, project_id=proj_id, job_id=trainjob_id, json_resp=True)
    result['job_status'] = result_jobst
    return result


def cmd_nlu_trytrain(mixcli: MixCli, **kwargs) -> bool:
    """
    Default function when command is called.

    :param mixcli: MixCli instance
    :param kwargs:
    :return:
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    waitfor_job = kwargs['no_wait'] is not True
    nlu_try_anno = nlu_try_train(mixcli, project_id=proj_id, locale=loc, waitfor=waitfor_job)
    out_file = kwargs['out_file']
    if not out_file:
        mixcli.info(json.dumps(nlu_try_anno))
    else:
        write_result_outfile(content=json.dumps(nlu_try_anno), out_file=out_file, logger=mixcli)
    return True


@cmd_regcfg_func('nlu', 'try-train', 'Train the run-time trial NLU model', cmd_nlu_trytrain)
def config_cmd_argparser(argparser: ArgumentParser):
    """
    Configure the ArgumentParser for the command.

    :param argparser: The ArgumentParser instance that supports this command.
    :return: None
    """
    argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help="Mix project ID")
    argparser.add_argument('-l', '--locale', metavar='LOCALE', required=True, help='Locale for the NLU model')
    argparser.add_argument('-W', '--no-wait', action='store_true', required=False,
                           help='Do NOT wait for train job to completes before ending the command.')
    argparser.add_argument('-o', '--out-file', metavar='OUTPUT_FILE', required=False, help='Send output to file')

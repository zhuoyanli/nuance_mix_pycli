"""
MixCli **nlu** command group **import** command.

This command will import a TRSX artifact, which should be result of a NLU model export of Mix projects. The import
will be sort of incremental merging processing between the current NLU model and the one represented by TRSX. If there
are conflicts between the two, such as same training sample in both current NLU model and TRSX, non-fatal errors will
be raised and that sample will be skipped for import.

Another thing to note is that Mix project NLU model TRSX import is asynchronous process. Mix platform will create
asynchronous import jobs and meta info of those jobs will be returned as response payload. It is users'
responsibility to query appropriate Mix API endpoints to keep track of the status of those jobs.

This in turn introduces an important feature of this nlu import command: If users specify '--wait' argument, this
command will do the tracking routine for users: Receive the response payloads to extract import job IDs, keep querying
API endpoints for the status of jobs, and only return when jobs are completed, either 'completed' for success or
'failed' for failure. The tracking of job status is done with the implementations of job list/status/wait commands.
"""
import json
import os.path
from argparse import ArgumentParser
from typing import Dict, Union, Optional

from mixcli import MixCli
from mixcli.command.job.status import job_id_from_meta
from mixcli.command.job.wait import job_wait_sync
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile, MixLocale
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD, get_api_resp_payload_data

NLU_IMPORT_TYPE_TRSX = 'trsx'


def import_job_meta_from_resp_payload(resp_payload: Dict) -> Dict:
    """
    Get the asynchronous import job meta from response payload. The expected meta is found
    at payload['data'][0].

    :param resp_payload:
    :return:
    """
    # do some sanity check
    assert 'data' in resp_payload and isinstance(resp_payload['data'], list) and resp_payload['data'], \
        f'Expecte non-empty array ["data"] not found in import response payload: {json.dumps(resp_payload)}'
    return get_api_resp_payload_data(resp_payload)


def pyreq_nlu_import_trsx(httpreq_handler: HTTPRequestHandler, project_id: int, src_trsx: str,
                          locale: Optional[str] = None) -> Dict:
    """
    Import a TRSX artifact into NLU model of Mix project by sending requests to API endpoint with Python 'requests'
    package. The request will be a file-upload fashion request.

    API endpoint
    ::
        POST "api/v2/projects/{project_id}/.async-import?allow_duplicate_samples=true&type=trsx"

    :param locale:
    :param httpreq_handler: HTTPRequestHandler instance
    :param project_id: project ID
    :param src_trsx: TRSX file to be imported
    :return: A Json object that is the response payload on import request
    """
    headers = httpreq_handler.get_default_headers()
    req_files = {'file': (src_trsx, open(src_trsx, 'rb'), 'text/xml')}
    api_endpoint = f"api/v2/projects/{project_id}/.async-import?allow_duplicate_samples=true&type=trsx"
    if locale:
        api_endpoint += '&locale='+locale
    try:
        resp_payload = httpreq_handler.request(url=api_endpoint, method=POST_METHOD,
                                               headers=headers, files=req_files, json_resp=True)
        httpreq_handler.debug(f'Import job meta: {json.dumps(resp_payload)}')
        return import_job_meta_from_resp_payload(resp_payload)
    except Exception as ex:
        msg = f"Error detected when importing trsx to project {project_id}"
        httpreq_handler.error(msg)
        raise RuntimeError(msg) from ex


def nlu_import_trsx(mixcli: MixCli, project_id: Union[int, str], import_src: str,
                    locale: Optional[str] = None) -> Dict:
    """
    Import source TRSX files into project NLU models.

    :param locale: Locale of import
    :param mixcli: MixCli instance
    :param project_id: project ID.
    :param import_src: Path to the import source file.
    :return: The Json object of the import response payload
    """
    if not os.path.isfile(import_src):
        mixcli.error(f"Source file not found for import: {import_src}")
        raise FileNotFoundError(f'TRSX not found for import: {import_src}')
    import_src = os.path.realpath(import_src)
    project_id = assert_id_int(project_id, 'project')
    loc = MixLocale.to_mix(locale) if locale else None
    return pyreq_nlu_import_trsx(mixcli.httpreq_handler, project_id=project_id, locale=loc, src_trsx=import_src)


def get_import_func(import_type: str):
    """
    Get the import function based on the type of import source data. Currently only supports TRSX files.

    :param import_type: Name of the source data type. Currently only supports TRSX files.
    :return: A function that should be called to execute the import
    """
    if import_type != NLU_IMPORT_TYPE_TRSX:
        # we currently only support TRSX import
        raise ValueError(f'Import type except trsx not supported: {import_type}')
    return nlu_import_trsx


def nlu_import(mixcli: MixCli, project_id: Union[int, str], import_type: str, import_src: str, wait_for: bool,
               locale: Optional[str] = None) -> Dict:
    """
    Import source data into NLU models of project.

    :param locale: Locale for the import
    :param mixcli: MixCli instance
    :param project_id: the project ID
    :param import_type: Name of the type of the source data, currently only supports 'trsx'
    :param import_src: Path to the import source file
    :param wait_for: If True process will wait until the asynchronous import jobs complete
    :return: Json response payloads from the import requests.
    """
    import_func = get_import_func(import_type)
    import_result = import_func(mixcli, project_id=project_id, locale=locale, import_src=import_src)
    if not wait_for:
        return import_result
    mixcli.debug(f"Start waiting for import job project {project_id} job {job_id_from_meta(import_result)}")
    job_id = job_id_from_meta(import_result)
    job_meta, suc = job_wait_sync(mixcli, project_id, job_id, infinite_wait=True, json_resp=True)
    if not suc:
        raise RuntimeError(f'Import job failed for project {project_id} with {import_src}: {json.dumps(job_meta)}')
    return job_meta


def cmd_nlu_import(mixcli: MixCli, **kwargs: Union[str, bool]):
    """
    Default function when nlu import command is called.

    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command line
    :return: None
    """
    import_type: str = kwargs['type']
    proj_id: str = kwargs['project_id']
    locale: Optional = kwargs['locale'] if 'locale' in kwargs else None
    import_src_file: str = kwargs['src']
    wait_for_job: bool = kwargs['no_wait'] is not True
    result = nlu_import(mixcli, project_id=proj_id, locale=locale,
                        import_type=import_type, import_src=import_src_file,
                        wait_for=wait_for_job)
    out_content = {}
    if result:
        out_content = result
    out_file = kwargs['out_file']
    if out_file:
        write_result_outfile(content=out_content, is_json=True, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(f'Successfully imported NLU from {import_src_file} with response {json.dumps(out_content)}')
    return True


@cmd_regcfg_func('nlu', 'import', 'Import artifact into NLU models for project, currently only TRSX', cmd_nlu_import)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', required=True, metavar='PROJECT_ID', help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', required=False, metavar='LOCALE_TO_IMPORT',
                               help='To which locale of NLU model the imported data should go')
    cmd_argparser.add_argument('-s', '--src', required=True,
                               metavar='IMPORT_SRC_FILE', help='Path to artifact to be imported')
    cmd_argparser.add_argument('-t', '--type', metavar='IMPORT_ARTIFACT_TYPE', default=NLU_IMPORT_TYPE_TRSX,
                               help=f'Type of artifact to be imported, currently only "{NLU_IMPORT_TYPE_TRSX}"')
    cmd_argparser.add_argument('-W', '--no-wait', action='store_true',
                               help='Do NOT Wait for import job to complete before ending the command')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

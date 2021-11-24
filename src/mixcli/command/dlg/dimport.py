"""
MixCli **dlg** command group **import** command.

This command will import a JSON artifact, which should be result of a dialog model export of Mix projects. The import
will completely override the current dialog model of destination Mix project. (Please note there is NO guarantee that
the dialog model after import will be consistent with the NLU model of the destination project.)

Another thing to note is that Mix project dialog model import is a blocking process. Requests to API endpoints will
only return when import jobs are completed, as contrast to NLU TRSX import actions.
"""
import codecs
import json
import os.path
from argparse import ArgumentParser
from typing import Dict, Union, Optional
from mixcli import MixCli
from mixcli.command.job.status import job_id_from_meta
from mixcli.command.job.wait import job_wait_sync
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD

DLG_IMPORT_TYPE_JSON = 'json'


def pyreq_dlg_import_json(httpreq_handler: HTTPRequestHandler, project_id: int, dlg_json: str) -> Dict:
    """
    Import JSON into Mix project Dialog models by sending Mix API requests with Python requests library.

    API endpoint
    ::
        POST "/api/v3beta1/dialog/projects/{project_id}/import"
        Dialog Json artifact is sent as data in payload.

    :param httpreq_handler: HTTPRequestHandler instance
    :param project_id: Mix project ID for whose dlg models json should be imported
    :param dlg_json: Path to json file to be imported
    :return: Json object of the response payload of import API requests, containing the submitted job meta info
    for the import operation
    """
    headers = httpreq_handler.get_default_headers()
    headers['Content-Type'] = 'application/json'
    if 'Connection' in headers:
        headers.pop('Connection')
    httpreq_handler.info(f'Reading content from import src file as API request data: {dlg_json}')
    with codecs.open(dlg_json, 'r', 'utf-8') as fhi_dlg_json:
        str_dlg_json = json.dumps(json.load(fhi_dlg_json))
    httpreq_handler.info(f'Successfully completed Reading import src file: {dlg_json}')
    resp_json = httpreq_handler.request(url=f'/api/v3beta1/dialog/projects/{project_id}/import',
                                        method=POST_METHOD,
                                        headers=headers, data=str_dlg_json, json_resp=True)
    return resp_json


def dlg_import_json(mixcli: MixCli, project_id: Union[int, str], import_src: str) -> Dict:
    """
    Import Json artifact into Dialog models for project <project_id>.

    :param mixcli: MixCli instance
    :param project_id: Project ID
    :param import_src: Path to source Json file of import
    :return: The Json object of the import response payload
    """
    if not os.path.isfile(import_src):
        mixcli.error(f"Source file not found for import: {import_src}")
        raise FileNotFoundError(f'json not found for import: {import_src}')
    import_src = os.path.realpath(import_src)
    project_id = assert_id_int(project_id, 'project')
    return pyreq_dlg_import_json(mixcli.httpreq_handler, project_id=project_id, dlg_json=import_src)


def get_import_func(import_type: str):
    """
    Get the import function based on the type of import source data. Currently only supports Json files.

    :param import_type: Name of the source data type. Currently only supports Json files.
    :return: A function that should be called to execute the import
    """
    if import_type != DLG_IMPORT_TYPE_JSON:
        # we currently only support json import
        raise ValueError(f'Import type except json is not supported: {import_type}')
    return dlg_import_json


# noinspection PyBroadException
def dlg_import(mixcli: MixCli, project_id: Union[int, str],
               import_src: str, import_type: str = DLG_IMPORT_TYPE_JSON, wait_for: bool = True) \
        -> Optional[Dict]:
    """
    Import source data into NLU models of project.

    :param mixcli: MixCli instance
    :param project_id: the project ID
    :param import_type: Name of the type of the source data, currently only supports 'JSON'
    :param import_src: Path to the import source file
    :param wait_for: If True process will wait until the asynchronous import jobs complete. Currently it has
    no effects as dialog import requests will only get responses from API endpoints AFTER imports are done.
    :return: Json response payloads from the import requests.
    """
    import_func = get_import_func(import_type)
    import_result = import_func(mixcli, project_id=project_id, import_src=import_src)
    # the wait_for has no effects for the moment: Dialog import requests will only get responses from API endpoints
    # AFTER imports are done
    if not wait_for:
        return import_result
    try:
        job_id = job_id_from_meta(import_result)
    except Exception:
        mixcli.info("Dialog import didnot return job meta. Import should have already been completed")
        return None
    mixcli.debug(f"Start waiting for import job project {project_id} job {job_id_from_meta(import_result)}")
    job_meta, suc = job_wait_sync(mixcli, project_id, job_id, infinite_wait=True, json_resp=True)
    if not suc:
        raise ValueError(f'Import job failed for project {project_id} with src {import_src}: {json.dumps(job_meta)}')
    return job_meta


def cmd_dlg_import(mixcli: MixCli, **kwargs: Union[str, bool]):
    """
    Default function when MixCli nlu import command is called.

    :param mixcli: MixCli instance
    :param kwargs: keyword arguments from command line
    :return: None
    """
    # import_type: str = kwargs['type']
    proj_id: str = kwargs['project_id']
    import_src_file: str = kwargs['src']
    wait_for_job: bool = kwargs['wait']
    result = dlg_import(mixcli, project_id=proj_id, import_type=DLG_IMPORT_TYPE_JSON,
                        import_src=import_src_file, wait_for=wait_for_job)
    out_file = kwargs['out_file']
    out_content = {}
    if result:
        out_content = result
    if out_file:
        write_result_outfile(content=out_content, is_json=True, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(f'Successfully imported dialog from {import_src_file} with response: {json.dumps(out_content)}')
    return True


@cmd_regcfg_func('dlg', 'import', 'Import artifact into Dialog models for project, currently only JSON', cmd_dlg_import)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', required=True, metavar='PROJECT_ID', help='Mix project ID')
    cmd_argparser.add_argument('-s', '--src', required=True,
                               metavar='IMPORT_SRC_FILE', help='Path to source file to be imported')
    # cmd_argparser.add_argument('-t', '--type', metavar='IMPORT_ARTIFACT_TYPE', default=DLG_IMPORT_TYPE_JSON,
    #                            help=f'Type of artifact to be imported, currently only "{_DLG_IMPORT_TYPE_JSON}"')
    cmd_argparser.add_argument('-w', '--wait', action='store_true', help='Wait for import job to complete')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

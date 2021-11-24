"""
MixCli **project** command group **build** command

This command would launch model builds for a Mix project. Please note to launch NLU model builds, if
specified, command line argument 'locale' is mandatory. Furthermore the build note will be set for all
model builds, same as in Mix UI. Last but not least, same as in Mix UI, model building jobs will be submitted
as asynchronous jobs and then API responses will be returned. If argument 'wait' is specified, this command will work
as blocking calls, i.e. will not return until all launched jobs are completed.

One particular highlight of this command is the ability to export the NLU/dialog models, if they have been included
in model builds, to artifacts, which can then be preserved. This is technically an automation of completing model
builds, and then run 'nlu export' and 'dlg export' commands. The purpose of doing such is to preserve the model sources
together with particular build versions of model builds, not just the built models. This would serve as workarounds
to make possible versioning and branching processes for Mix NLU/dialog models, a feature currently not yet available
in Mix platform.

Clarification: Currently Mix platform can roll back ASR/NLU/Dialog models of Mix projects to history build versions.
However it is impossible to roll back the model sources to the status when those builds were created. Therefore no
rebase nor branch are possible.
"""
import os.path
import json
from argparse import ArgumentParser
from asyncio import gather, Lock
from typing import Union, Optional, List, Dict
from .get import get_project_meta, get_nlu_model_modes_enabled
from ..project.model_export import _MODEL_NLU, _MODEL_DLG, _MODEL_ASR
from ..nlu.export import nlu_export_trsx, TRSX_DATATYPES
from ..dlg.export import dlg_export as dlg_export_json
from ..job.status import JOB_STATUS_FIELD, JOB_STATUS_COMPLETED, \
    JOB_STATUS_FAILED
from ..job.wait import job_wait
from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int, run_coro_sync, write_result_outfile, get_project_id_file, MixLocale
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, POST_METHOD, get_api_resp_payload_data

BUILD_JOB_VERSION_FIELD = 'version'

MDLS_TO_BUILD = [_MODEL_ASR, _MODEL_NLU, _MODEL_DLG]
# Constants about NLU model training mode
NLU_MODEL_MODE_FAST = 'FAST'
NLU_MODEL_MODE_ACCURATE = 'ACCURATE'
DEFAULT_NLU_MODEL_MODE = NLU_MODEL_MODE_FAST
NLU_MODEL_MODES = [NLU_MODEL_MODE_FAST, NLU_MODEL_MODE_ACCURATE]
DEFAULT_MODEL_BUILD_REQ_DATA: Dict[str, Dict] = {
    _MODEL_ASR: {'data_sources': []},
    _MODEL_NLU: {'data_sources': [],
                 'dynamic_concepts': [],
                 'retrain': False,
                 'settings': {
                     'modelType': NLU_MODEL_MODE_FAST
                 }},
    _MODEL_DLG: {'data_sources': []}
}


def pyreq_project_build(httpreq_runner: HTTPRequestHandler, project_id: int, build_models: List[str],
                        locale: Optional[str] = None, build_note: Optional[str] = None, **kwargs) -> Dict:
    """
    Launch model build(s) for Mix project by sending requests to API endpoint with Python 'requests' package.

    API endpoint
    ::
        POST /api/v2/projects/{proj_id}/models?{model_list}&locale={loc}.
        model_list = type={nlu|asr|dialog}[&type={nlu|asr|dialog}][&type={nlu|asr|dialog}]


    request body
    ::
        {
            "asr":{"notes":<build_note>,"data_sources":[]},
            "nlu":{
               "notes":<build_note>,
               "data_sources":[],
               "dynamic_concepts":[],
               "retrain":false,
               "settings":{"modelType":"FAST"}
            },
            "dialog":{
                "notes":<build_note>,
                "data_sources":[]
            }
        }


    :param httpreq_runner: A HTTPRequestHandler instance
    :param project_id: Mix project id to be built
    :param locale: locale (of NLU model) to be built
    :param build_models: Models to be built
    :param build_note: Build note to be posted with build
    :return:
    """
    if _MODEL_NLU in build_models:
        if not locale:
            raise RuntimeError('Must specify locale to build NLU model')
    if not build_note:
        build_note = 'Built by MixCli'
    req_data: Dict[str, Dict] = dict()
    if _MODEL_ASR in build_models:
        req_data[_MODEL_ASR] = {'notes': build_note}
    if _MODEL_NLU in build_models:
        req_data[_MODEL_NLU] = {'notes': build_note}
    if _MODEL_DLG in build_models:
        req_data[_MODEL_DLG] = {'notes': build_note}
    # add the default request data
    for m_name, m_data in req_data.items():
        req_data[m_name].update(DEFAULT_MODEL_BUILD_REQ_DATA[m_name])
    if _MODEL_NLU in build_models:
        if 'nlu_model_mode' in kwargs:
            # set the model training mode
            req_data[_MODEL_NLU]['settings']['modelType'] = kwargs['nlu_model_mode']

    api_endpoint = f'/api/v2/projects/{project_id}/models?'
    model_args = '&'.join([f'type={m}' for m in build_models])
    if 'nlu' in build_models:
        model_args += f'&locale={locale}'
    api_endpoint += model_args
    resp = httpreq_runner.request(url=api_endpoint, method=POST_METHOD, default_headers=True,
                                  data=req_data, json_resp=True)
    launch_result = get_api_resp_payload_data(resp)
    return launch_result


def project_build(mixcli: MixCli, project_id: Union[int, str], build_models: List[str], build_note: Optional[str],
                  locale: Optional[str] = None, nlu_model_mode: Optional[str] = None,
                  wait_for: bool = True, **kwargs) -> Dict:
    """
    Launch model builds for Mix project.

    :param nlu_model_mode: NLU model mode, if not None either FAST or ACCURATE
    :param wait_for:
    :param mixcli: MixCli instance
    :param project_id: ID of mix project
    :param locale:
    :param build_models:
    :param build_note:
    :return:
    """
    if _MODEL_NLU in build_models:
        if not locale:
            raise RuntimeError('Must specify locale to build NLU model')
    proj_id = assert_id_int(project_id, 'project')
    mixloc = None
    if locale:
        mixloc = MixLocale.to_mix(locale)
    if nlu_model_mode:
        if nlu_model_mode not in NLU_MODEL_MODES:
            raise RuntimeError(f'Unsupported NLU model training mode: {nlu_model_mode}')
        if nlu_model_mode == NLU_MODEL_MODE_ACCURATE:
            # we need to check if ACCURATE mode has been enabled
            proj_meta = get_project_meta(mixcli, project_id=proj_id)
            nlu_model_modes_enabled = get_nlu_model_modes_enabled(proj_meta)
            if not (nlu_model_modes_enabled and nlu_model_mode in nlu_model_modes_enabled):
                # ACCURATE mode not enabled!
                raise RuntimeError(f'Project {proj_id} does not have {nlu_model_mode} enabled!')
    launch_result = pyreq_project_build(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc,
                                        build_models=build_models, build_note=build_note,
                                        nlu_model_mode=nlu_model_mode, **kwargs)
    model_disp = f'[{",".join(build_models)}]'
    mixcli.info(f'Completed launching build jobs for project #{proj_id} on models {model_disp}')
    if wait_for:
        model_build_job_status = {}
        model_bld_jobs: Dict[str, str] = {}
        for mdl, bld_stat_for_mdl in launch_result.items():
            if mixloc in bld_stat_for_mdl:
                bld_stat = bld_stat_for_mdl[mixloc]
            else:
                bld_stat = bld_stat_for_mdl
            model_build_job_status[mdl] = {
                BUILD_JOB_VERSION_FIELD: 0,
                JOB_STATUS_FIELD: ''
            }
            for e_key in ['error', 'errors']:
                if e_key in bld_stat and bld_stat[e_key]:
                    raise RuntimeError(f'Error found in model build resp: {json.dumps(bld_stat_for_mdl)}')
            if 'job_id' in bld_stat:
                model_bld_jobs[mdl] = bld_stat['job_id']
                model_build_job_status[mdl][BUILD_JOB_VERSION_FIELD] = \
                    bld_stat[BUILD_JOB_VERSION_FIELD]
            else:
                # the job already completed!
                if JOB_STATUS_FIELD in bld_stat:
                    model_build_job_status[mdl][JOB_STATUS_FIELD] = bld_stat[JOB_STATUS_FIELD]
                    model_build_job_status[mdl][BUILD_JOB_VERSION_FIELD] = \
                        bld_stat[BUILD_JOB_VERSION_FIELD]
                else:
                    mixcli.error(f'No build job created for project {project_id} model {mdl}: {json.dumps(bld_stat)}')
                    model_build_job_status[mdl][JOB_STATUS_FIELD] = JOB_STATUS_FAILED
                    model_build_job_status[mdl][BUILD_JOB_VERSION_FIELD] = \
                        bld_stat[BUILD_JOB_VERSION_FIELD]
        # now we use async function to wait for the build jobs
        waited_model_job_status: Dict[str, str] = \
            run_coro_sync(wait_for_model_build_jobs(mixcli, project_id, mixloc, model_bld_jobs))
        mixcli.debug(f'Result returned from async function: {json.dumps(waited_model_job_status)}')
        for mdl, status in waited_model_job_status.items():
            model_build_job_status[mdl][JOB_STATUS_FIELD] = waited_model_job_status[mdl]
        return model_build_job_status
    else:
        return launch_result


async def update_model_job_status(model_job_meta: Dict[str, str], model: str, status: str, lock: Lock):
    """
    Update the meta status Json with the status of build jobs for model.

    :param model_job_meta: A json holding the status for build jobs of specific models
    :param model: name of model the status of build job for which shall be updated
    :param status: status label for the update
    :param lock: An asynchronous mutual lock for resource access
    :return: None
    """
    async with lock:
        model_job_meta[model] = status


async def build_job_wait(mixcli: MixCli, project_id: int, locale: str,
                         model: str, job_id: str,
                         model_job_result: Dict[str, str], lock: Lock):
    """
    Asynchronous function to wait for completions of Mix jobs in blocking mode.

    :param mixcli:
    :param project_id:
    :param locale:
    :param model:
    :param job_id:
    :param model_job_result:
    :param lock:
    :return:
    """
    mixcli.debug(f'Start waiting for builds: project {project_id} locale {locale} model {model} job {job_id}')
    result_status = await job_wait(mixcli, project_id, job_id, infinite_wait=True, exc_if_failed=False)
    await update_model_job_status(model_job_result, model,
                                  JOB_STATUS_COMPLETED if result_status else JOB_STATUS_FAILED, lock)


async def wait_for_model_build_jobs(mixcli: MixCli, project_id: int, locale: str,
                                    model_build_jobs: Dict[str, str]) -> Dict[str, str]:
    """
    Asynchronous function to wait for one or more model build jobs.

    :param mixcli: MixCli instance.
    :param locale:
    :param model_build_jobs:
    :param project_id:
    :return:
    """
    model_job_result: Dict[str, str] = {
    }
    for model, _ in model_build_jobs.items():
        model_job_result[model] = ''
    lock = Lock()
    coro_list = []
    for model, job_id in model_build_jobs.items():
        if model == _MODEL_NLU:
            coro_list.append(build_job_wait(mixcli, project_id, locale,
                                            model, job_id, model_job_result, lock))
        else:
            coro_list.append(build_job_wait(mixcli, project_id, locale,
                                            model, job_id, model_job_result, lock))
    await gather(*coro_list)
    return model_job_result


def cmd_project_build(mixcli: MixCli, **kwargs: Union[str, List[str], None]):
    """
    Default function when the command is called.

    :param mixcli: MixCli instance.
    :param kwargs:
    :return:
    """
    proj_id = assert_id_int(kwargs['project_id'], 'project')
    bld_models = kwargs['model']
    loc = kwargs['locale']
    nlu_mdl_mode = kwargs['nlu_mode']
    bld_note = kwargs['note']
    wait_for = kwargs['no_wait'] is not True

    result = project_build(mixcli, project_id=proj_id, locale=loc, nlu_model_mode=nlu_mdl_mode,
                           build_models=bld_models, build_note=bld_note, wait_for=wait_for)
    out_file = kwargs['out_file']
    if wait_for:
        if out_file:
            write_result_outfile(content=result, out_file=out_file, is_json=True, logger=mixcli)
        else:
            mixcli.info(f'Model build results for project with ID {proj_id}: '+json.dumps(result))
    else:
        if out_file:
            write_result_outfile(content=result, out_file=out_file, is_json=True, logger=mixcli)
        else:
            list_models_built = '[{m_str}]'.format(m_str=','.join(bld_models))
            mixcli.info(f'Successfully launched model build for project {proj_id}: {list_models_built} ' +
                        f'with following response payload: {json.dumps(result)}')

    export_dst = kwargs['export_model']
    if export_dst:
        # we may want to export the models to artifacts while we launch the builds
        # background: There are currently NO ways in Mix to recover the source model data from the built results.
        # That being said, if users make a build on NLU model, e.g. v7, and then modify the model source data. There
        # would not be any ways if users want to get the exact model source data on which NLU v7 model has been trained.
        # The only possible way is users have exported the NLU model, at the time of launching v7 build, to some
        # external artifact (TRSX) and save that.
        dst_is_file = os.path.isfile(export_dst)
        dst_is_dir = os.path.isdir(export_dst)
        if len(bld_models) > 1:
            # where there are more than one model being built, can not export to one single file
            if dst_is_file:
                raise RuntimeError('Cannot export to single file when multiple models are involved')
            elif not dst_is_dir:
                raise RuntimeError('Must specify valid dir to export for multiple models')

        proj_meta = get_project_meta(mixcli, project_id=proj_id)

        # now we export them one by one
        # we do not export ASR models
        for mdl in bld_models:
            if mdl == _MODEL_NLU:
                # export NLU model
                exf_basename = get_project_id_file(project_id=proj_id, project_meta=proj_meta, ext='.trsx',
                                                   model=f'NLU__bv{result[mdl][BUILD_JOB_VERSION_FIELD]}')
                export_trsx = export_dst
                if dst_is_dir:
                    export_trsx = os.path.join(export_dst, exf_basename)
                mixcli.debug(f'Exporting NLU model to {export_trsx}')
                nlu_export_trsx(mixcli, project_id=proj_id, locale=loc, out_trsx=export_trsx,
                                export_types=TRSX_DATATYPES)
                mixcli.info(f'Successfully exported Project {proj_id} NLU model to {export_trsx}')
            elif mdl == _MODEL_DLG:
                # export DLG model
                export_json = export_dst
                if dst_is_dir:
                    exf_basename = get_project_id_file(project_id=proj_id, project_meta=proj_meta, ext='.json',
                                                       model=f'DIALOG__bv{result[mdl][BUILD_JOB_VERSION_FIELD]}')
                    export_json = os.path.join(export_dst, exf_basename)
                mixcli.debug(f'Exporting DIALOG model to {export_json}')
                dlg_export_json(mixcli, project_id=proj_id, output_json=export_json)
                mixcli.info(f'Successfully exported Project {proj_id} DIALOG model to {export_json}')

    return True


def ucstr(o) -> str:
    return str(o).upper()


@cmd_regcfg_func('project', 'build', 'Launch model builds for Mix project', cmd_project_build)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command
    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True,
                               help='Mix project ID to build')
    cmd_argparser.add_argument('-m', '--model', metavar='MODEL_TO_BUILD',
                               choices=MDLS_TO_BUILD, nargs='+',
                               default=MDLS_TO_BUILD,
                               help=f'Models to build, choicess are enums from {repr(MDLS_TO_BUILD)}')
    cmd_argparser.add_argument('-l', '--locale', metavar='LOCALE', required=False,
                               help='Locale in aa_AA foramt of project for which models will be built')
    cmd_argparser.add_argument('--nlu-mode', type=ucstr, choices=NLU_MODEL_MODES, default=NLU_MODEL_MODE_FAST,
                               metavar='NLU_MODEL_TRAIN_MODE', help='(default) FAST for linear or ACCURATE for DNN')
    cmd_argparser.add_argument('-n', '--note', metavar='BUILD_NOTE', required=False,
                               help='Build note')
    cmd_argparser.add_argument('-W', '--no-wait', action='store_true', required=False,
                               help='Wait until all builds to terminate, either completed/succeeded or failed')
    cmd_argparser.add_argument('-e', '--export-model', required=False, metavar='EXPORT_FILEORDIR',
                               help='Export model(s) being built for version control or backup purpose')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

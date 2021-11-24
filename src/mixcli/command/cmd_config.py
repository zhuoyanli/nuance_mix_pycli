"""
The data module which would carry the configuration for MixCli commands
"""
import sys
import types

MIXCLI_CMD_PKG_NAMESPACE = 'mixcli.command'


# noinspection PyUnresolvedReferences
def get_cmd_modules():
    from .auth import client as auth_client
    from .sys import version as sys_version
    from .ns import search as ns_search, list as ns_list
    from .project import get as proj_get, reset as proj_reset, create as proj_create, copy as proj_cp_create, \
        build as proj_build, build_stat as proj_bld_stat, model_export as mdl_exp, rm as proj_rm, \
        update_qnlp_prop as proj_update_qnlp_prop, cp_member as proj_cp_member
    from .channel import get as channel_get
    from .intent import list as list_intent
    from .concept import list as concept_list, rm as concept_rm
    # from .model import download as model_dl
    from .nlu import export as nlu_export, try_utt as nlu_tryutt, try_train as nlu_trytrain, nimport as nlu_import, \
        trsx2qnlp as nlu_trsx2qnlp
    from .dlg import export as dlg_export, dimport as dlg_import, try_build as dlg_trybuild
    from .job import status as job_status, list as job_list, wait as job_wait
    # from .example import cmd_as_mod
    from .sample import upload as sample_upload, count as count_sample, get as get_sample, rm as rm_sample
    from .config import lookup as cfg_lookup, create as cfg_create, rm as cfg_rm
    from .run import script as run_script
    from .grpc import export as grpc_export
    from .util import jsonpath as util_jsonpath, api as util_queryapi

    local_vars = [val for val in locals().values()]
    for var in local_vars:
        if isinstance(var, types.ModuleType):
            if var.__name__.startswith(MIXCLI_CMD_PKG_NAMESPACE):
                yield sys.modules[var.__name__]

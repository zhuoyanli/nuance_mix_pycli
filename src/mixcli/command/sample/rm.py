"""
Mix **sample** command group **rm** command.

This command is useful to rm sample(s) from given intent in a locale of NLU model of Mix project.
"""
import json
from argparse import ArgumentParser
from typing import Union, Optional

from . import assert_intent_in_nlu_locale
from .get import pyreq_get_intent_samples
from .count import pyreq_count_nlu_sample
from ..project.get import get_mix_project_name
from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int, MixLocale, write_result_outfile
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, DELETE_METHOD


class Counter:
    """
    Utility class to serve as counter
    """
    def __init__(self, base=0):
        self._base = base

    def add_one(self):
        """
        Add one on counter
        :return: integer, new count
        """
        self._base += 1
        return self._base

    @property
    def count(self):
        """
        Get the count
        :return: integer, count
        """
        return self._base


def pyreq_rm_all_samples(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str):
    """
    Remove all samples in a locale of NLU model in Mix project by querying API endpoint
    with DELETE method using "requests" package

    API endpoint
    ::
        DELETE f"nlu/api/v1/nlu/<PROJECT_ID>/interactions?locales=<LOCALE>&confirmed=true"


    :param httpreq_handler:
    :param project_id:
    :param locale:
    :return:
    """
    api_endpoint = f"nlu/api/v1/nlu/{project_id}/interactions?locales={locale}&confirmed=true"
    data = '{}'
    httpreq_handler.request(url=api_endpoint, method=DELETE_METHOD, data=data, data_as_str=True, default_headers=True,
                            json_resp=True)
    return True


def pyreq_rm_intent_samples(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str, intent: str):
    """
    Remove samples in an intent of a locale of NLU model in a Mix project, by querying API endpoint with DELETE method
    and individual sample UUID, one sample by one.

    API endpoint
    ::
        DELETE f"nlu/api/v1/nlu/<project_id>/interactions?locales=<locale>&intention=<intent>&iids=<sample_iid>"


    :param httpreq_handler:
    :param project_id:
    :param locale:
    :param intent:
    :return:
    """
    httpreq_handler.debug(f"Retrieving samples for project {project_id} locale {locale} intent {intent}")
    sample_cnt = pyreq_count_nlu_sample(httpreq_handler, project_id=project_id, locale=locale, intent=intent,
                                        count_only=True)
    if sample_cnt <= 0:
        httpreq_handler.info(f'No samples for project #{project_id} locale {locale} intent {intent}: {sample_cnt}')
        return True
    json_allsamples_meta = pyreq_get_intent_samples(httpreq_handler, project_id=project_id, locale=locale,
                                                    intent=intent)
    sample_size = int(json_allsamples_meta['meta']['size'])
    sample_cnt = int(json_allsamples_meta['meta']['total'])
    assert sample_size == sample_cnt, \
        f"NLU sample size and total inconsistent: " \
        + f"project {project_id} locale {locale} intent {intent}: size {sample_size} total {sample_cnt}"
    httpreq_handler.debug(f"Count of samples to remove for {project_id} locale {locale} intent {intent}: {sample_cnt}")
    httpreq_handler.info('Mix NLU sample removal is done one by one therefore could be slow, please be patient.')
    cnt_sample_proc = Counter(0)

    # we have to remove sample one by one!
    def rm_sample(sample_meta, counter):
        try:
            # for sample_meta in json_allsamples_meta['results']:
            sample_iid = sample_meta['uid']
            arg_part = f"locales={locale}&intention={intent}&iids={sample_iid}"
            api_endpoint = f"nlu/api/v1/nlu/{project_id}/interactions?{arg_part}"
            data = '{}'
            httpreq_handler.request(url=api_endpoint, method=DELETE_METHOD, data=data, data_as_str=True,
                                    default_headers=True)
            counter.add_one()
        except Exception as ex:
            sample_meta_json = json.dumps(sample_meta)
            raise RuntimeError(f"Error after removing {counter.count} sample(s): " +
                               f"project {project_id} {locale} intent {intent} sample {sample_meta_json}") from ex

    def rm_sample_in_range(s, e, sample_counter):
        httpreq_handler.info(f"Removing project {project_id} intent {intent} sample from {s} to {e}")
        for idx in range(s, e + 1):
            m = json_allsamples_meta['results'][idx]
            rm_sample(m, sample_counter)

    cur_end = 0
    step = 50
    for trunk in range(0, sample_cnt + 1, step):
        cur_start = trunk
        cur_end = trunk + step - 1
        if cur_end > sample_cnt - 1:
            cur_end = sample_cnt - 1
        rm_sample_in_range(cur_start, cur_end, cnt_sample_proc)
    if cur_end < sample_cnt - 1:
        cur_start = cur_end
        cur_end = sample_cnt - 1
        rm_sample_in_range(cur_start, cur_end, cnt_sample_proc)
    return True


def rm_intent_samples(mixcli: MixCli, project_id: Union[str, int], locale: str,
                      intent: Optional[str] = None, confirm_project: Optional[str] = None):
    """
    Remove samples for an intent in a locale of NLU model of a Mix project.

    :param mixcli: MixCli instance
    :param project_id: ID of Mix project
    :param locale: locale in NLU model
    :param intent: Name of intent for the samples, if None remove all samples in locale of NLU model.
    :param confirm_project: Project name as confirmation if shall remove all samples in locale of NLU model
    :return:
    """
    # if no intent is specified we shall remove all samples in locale of NLU model
    proj_id = assert_id_int(project_id, 'project')
    if not intent:
        if not confirm_project:
            raise RuntimeError('Must provide project name as confirmation to remove all NLU samples in NLU locale')
        proj_name_from_id = get_mix_project_name(mixcli, project_id=proj_id)
        if proj_name_from_id != confirm_project:
            raise RuntimeError('Confirmed project name from cmd {cn} not match Mix info: {mn}'.
                               format(cn=confirm_project,
                                      mn=proj_name_from_id))
    mixloc = MixLocale.to_mix(locale)
    if not intent:
        # we shall remove all NLU samples from a locale of NLU model
        pyreq_rm_all_samples(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc)
        return True
    # we want to verify if intent exists for locale of NLU model in project
    assert_intent_in_nlu_locale(mixcli, project_id=proj_id, locale=mixloc, intent=intent)
    resp = pyreq_rm_intent_samples(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc, intent=intent)
    return resp


def cmd_sample_rm(mixcli: MixCli, **kwargs):
    """
    Default function when **sample get** command is called.

    :param mixcli: MixCli instance
    :param kwargs:
    :return:
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    intent_name = kwargs['intent']
    conf_proj_nm = kwargs['confirm_proj']
    _ = rm_intent_samples(mixcli, project_id=proj_id, locale=loc, intent=intent_name, confirm_project=conf_proj_nm)
    result = '0'
    out_file = kwargs['out_file']
    if out_file:
        mixcli.info(f'The following command result written to file: {out_file}')
        mixcli.info(json.dumps(result))
        write_result_outfile(content=result, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(json.dumps(result))


@cmd_regcfg_func('sample', 'rm', 'Remove samples from specific intent in a locale of NLU model', cmd_sample_rm)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='NLU_LOCALE', required=True, help='NLU locale code')
    cmd_argparser.add_argument('-i', '--intent', metavar='INTENT_NAME', required=False,
                               help='NLU intent name. Skip to remove all samples from locale (must confirm project).')
    cmd_argparser.add_argument('-c', '--confirm-proj', metavar='CONFIRM_PROJECT_NAME', required=False,
                               help='Type exact project name as confirmation to remove all samples from NLU locale.')

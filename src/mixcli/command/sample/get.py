"""
Mix **sample** command group **get** command.

This command is useful to get the sample(s) for a give intent in a locale of NLU model of a Mix project.
"""
import copy
# the name of the actual register function can be whatever
import json
from argparse import ArgumentParser
from typing import Union

from . import assert_intent_in_nlu_locale
from .count import pyreq_count_nlu_sample
from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int, MixLocale, write_result_outfile
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD, get_api_resp_payload_data


def pyreq_get_intent_samples(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str, intent: str):
    """
    Get meta data of all samples for an NLU intent in a locale of NLU model of a Mix project, by querying API endpoint
    with GET method using "requests" package

    API endpoint
    ::
        f"nlu/api/v1/nlu/<PROJECT_ID>?intention=<INTENT>&locales=<LOCALE>&start=<START_OFFSET>&end=<END_OFFSET>"

    Please note that Mix API only allows to get samples within an segment of 500 counts. That being said, if an intent
    contains more than 500 samples, they must be retrieved in batches, where the requested counts of each batch can not
    be more than 500.

    :param httpreq_handler:
    :param project_id:
    :param locale:
    :param intent:
    :return:
    """
    sample_cnt = pyreq_count_nlu_sample(httpreq_handler=httpreq_handler, project_id=project_id, locale=locale,
                                        intent=intent, count_only=True)

    # we make a lambda to do the function calls
    def assert_sample_results(sample_result_json, can_none=True):
        if not sample_result_json:
            if can_none:
                return True
            else:
                raise ValueError('Mix NLU sample Json is None')
        if 'meta' in sample_result_json and \
                'total' in sample_result_json['meta'] and \
                'results' in sample_result_json:
            return True
        else:
            raise ValueError('Invalid Mix NLU sample Json: meta, meta.total, or results field not found')

    def pyreq_get_sample(start, end):
        api_endpoint = f"nlu/api/v1/nlu/{project_id}?intention={intent}&locales={locale}&start={start}&end={end}"
        data = '{}'
        resp = httpreq_handler.request(url=api_endpoint, method=GET_METHOD, data=data, data_as_str=True,
                                       default_headers=True, json_resp=True)
        resp_data = get_api_resp_payload_data(resp)
        assert_sample_results(resp_data, can_none=False)
        return resp_data

    def merge_sample_results(buf, new_result):
        if not buf:
            if new_result:
                return copy.copy(new_result)
            else:
                return None
        if not new_result:
            return buf
        buf['meta']['size'] += new_result['meta']['size']
        buf['results'].extend(new_result['results'])
        return buf

    if sample_cnt <= 500:
        # we cannot go over the limit of 500
        result = pyreq_get_sample(0, sample_cnt)
        return result
    else:
        cur_start = 0
        step = 500
        result_buf = None
        for x in range(cur_start, sample_cnt, step):
            cur_end = cur_start + step
            if cur_end > sample_cnt:
                cur_end = sample_cnt
            cur_result = pyreq_get_sample(cur_start, cur_end)
            result_buf = merge_sample_results(result_buf, cur_result)
            cur_start = cur_end
        return result_buf


def get_intent_samples(mixcli: MixCli, project_id: Union[str, int], locale: str, intent: str):
    """
    Get meta data of all samples for an intent in a locale of NLU model of a Mix project.

    :param mixcli: MixCli instance
    :param project_id: ID of Mix project
    :param locale: locale in NLU model
    :param intent: Name of intent for the samples
    :return:
    """
    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    # we want to verify if intent exists for locale of NLU model in project
    assert_intent_in_nlu_locale(mixcli, project_id=proj_id, locale=mixloc, intent=intent)
    resp = pyreq_get_intent_samples(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc, intent=intent)
    return resp


def cmd_sample_get(mixcli: MixCli, **kwargs):
    """
    Default function when **sample get** command is called.

    :param mixcli: MixCli instance
    :param kwargs:
    :return:
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    intent_name = kwargs['intent']
    result = get_intent_samples(mixcli, project_id=proj_id, locale=loc, intent=intent_name)
    out_file = kwargs['out_file']
    if out_file:
        mixcli.info(f'The following command result written to file: {out_file}')
        mixcli.info(json.dumps(result))
        write_result_outfile(content=result, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(json.dumps(result))


@cmd_regcfg_func('sample', 'get', 'Get meta data of all samples for intent in a locale NLU model', cmd_sample_get)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='NLU_LOCALE', required=True, help='NLU locale code')
    cmd_argparser.add_argument('-i', '--intent', metavar='INTENT_NAME', required=True, help='NLU intent name')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

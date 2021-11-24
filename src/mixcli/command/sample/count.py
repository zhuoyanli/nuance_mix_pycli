"""
Mix **sample** command group **count** command.

This command is useful to get the total count of sample(s) for a give intent in NLU model of a Mix project.
"""
# the name of the actual register function can be whatever
import json
from argparse import ArgumentParser
from typing import Union, Dict

from . import assert_intent_in_nlu_locale
from mixcli import MixCli
from mixcli.util.cmd_helper import assert_id_int, MixLocale, write_result_outfile
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD


def pyreq_count_nlu_sample(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str, intent: str,
                           count_only: bool = True) -> Union[int, Dict]:
    """
    Count sample(s) for an intent in a locale of NLU model in a Mix project by querying API with GET method.

    API endpoint:
    ::
        GET f"nlu/api/v1/nlu/<PROJ_ID>?intention=<INTENT_NAME>&locales=<NLU_LOCALE>"

    Sample API response payload:
    ::
        {"meta": {"offset": 0, "size": 0, "total": <COUNT>}, "results": []}

    :param httpreq_handler:
    :param project_id:
    :param locale:
    :param intent:
    :param count_only:
    :return: Either an integer as the count or the original API response payload containing the count in $.meta.total
    """
    api_endpoint = f"nlu/api/v1/nlu/{project_id}?intention={intent}&locales={locale}"
    data_str = '{}'
    resp: Dict = httpreq_handler.request(url=api_endpoint, method=GET_METHOD, data=data_str, data_as_str=True,
                                         default_headers=True, json_resp=True)
    if count_only:
        return resp['meta']['total']
    else:
        return resp


def count_nlu_sample(mixcli: MixCli, project_id: Union[str, int], locale: str, intent: str, count_only: bool = True):
    """
    Count sample(s) for an intent in a locale of NLU model in a Mix project.

    :param count_only: Only return an integer as the count of sample(s)
    :param mixcli:
    :param project_id:
    :param locale:
    :param intent:
    :return: Either an integer as the count or the original API response payload containing the count in $.meta.total
    """
    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    # we want to verify if the intent does exist for project NLU model and locale
    assert_intent_in_nlu_locale(mixcli, project_id=proj_id, locale=mixloc, intent=intent)
    return pyreq_count_nlu_sample(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc,
                                  intent=intent, count_only=count_only)


def cmd_sample_count(mixcli: MixCli, **kwargs):
    """
    Default function when **sample count** command is called.

    :param mixcli: MixCli instance.
    :param kwargs:
    :return: True
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    intent_name = kwargs['intent']
    need_count_only = kwargs['orig_resp']
    result = count_nlu_sample(mixcli, project_id=proj_id, locale=loc, intent=intent_name, count_only=need_count_only)
    out_file = kwargs['out_file']
    if out_file:
        mixcli.info(f'The following command result written to file: {out_file}')
        mixcli.info(json.dumps(result))
        write_result_outfile(content=result, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(json.dumps(result))
    return True


@cmd_regcfg_func('sample', 'count', 'Count samples(s) for intent in a locale of NLU model', cmd_sample_count)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='NLU_LOCALE', required=True, help='NLU locale code')
    cmd_argparser.add_argument('-i', '--intent', metavar='INTENT_NAME', required=True, help='NLU intent name')
    cmd_argparser.add_argument('--orig-resp', action='store_false', default=True,
                               help='Get the complete original response payload from API containing the count.')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

"""
Mix **intent** command group **list** command.

This command is useful to get information about intents in a locale of NLU model for Mix project.
"""
import json
from argparse import ArgumentParser
from typing import Union, Dict, Set, List

from mixcli import MixCli
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.cmd_helper import assert_id_int, MixLocale, write_result_outfile
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD, get_api_resp_payload_data

INTENT_META_NAME_FIELD = 'name'


def pyreq_list_nlu_intent(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str) -> List[Dict]:
    """
    Get the list of NLU intents in given locale in NLU model for Mix project

    API endpoint
    ::
        /v3/nlu/api/v1/ontology/{projectID}/intentions

    :param httpreq_handler:
    :param project_id:
    :param locale:
    :return: The 'data' field of API response payload
    """

    # Sample API response payload
    # {"data" :
    #
    # [{
    #   'name': 'I_ADD_PAYEE',
    #   'links': [{
    #       'linkedNodeName': 'AMOUNT', 'boltLinkName': 'hasA'},
    #       {'linkedNodeName': 'MODIFIER', 'boltLinkName': 'hasA'},
    #       ...
    #   ],
    #   'isIntention': True,
    #   'isFreetext': False,
    #   'isDynamic': False,
    #   'canonicalize': True,
    #   'isInBaseOntology': False,
    #   'isOperator': False,
    #   'isReference': False,
    #   'uuid': '17030ea9-5556-4254-9786-e2db3cdcf04b',
    #   'isSensitive': False
    #  },
    #  <INTENT_META>
    #  ...
    # ]
    # }
    api_endpoint = f'/nlu/api/v1/ontology/{project_id}/intentions?locale={locale}'
    data = '{}'
    resp = httpreq_handler.request(url=api_endpoint, method=GET_METHOD, data=data, data_as_str=True,
                                   default_headers=True, json_resp=True)
    resp_data = get_api_resp_payload_data(resp, reduce_list=False)
    # we do some empirical checking: The 'data' field should be a list of intent meta
    if not isinstance(resp_data, list):
        raise RuntimeError(f'API didnot return resp with "data" field being list of intent metas: {repr(resp_data)}')
    return resp_data


def list_nlu_intent(mixcli: MixCli, project_id: Union[int, str], locale: str,
                    need_meta: bool = False) -> Union[Set[str], List[Dict]]:
    """
    Get the list of NLU intents in given locale in NLU model for Mix project.

    :param mixcli:
    :param project_id:
    :param locale:
    :param need_meta: Need the original API response payload
    :return: Set of names of intents if need_meta is False, the JSON payload of API response otherwise.
    """
    proj_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    resp = pyreq_list_nlu_intent(mixcli.httpreq_handler, project_id=proj_id, locale=mixloc)
    if need_meta:
        return resp
    intent_names = set()
    for intent_meta in resp:
        if INTENT_META_NAME_FIELD not in intent_meta:
            raise RuntimeError(f'Intent meta didnot contain "name" field: {repr(intent_meta)}')
        intent_names.add(intent_meta[INTENT_META_NAME_FIELD])
    return intent_names


def cmd_intent_list(mixcli: MixCli, **kwargs):
    """
    Default function when command **intent list** is called.

    :param mixcli: MixCli instance
    :param kwargs:
    :return:
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    need_meta = kwargs['need_meta']
    result = list_nlu_intent(mixcli, project_id=proj_id, locale=loc, need_meta=need_meta)
    out_file = kwargs['out_file']
    if out_file:
        mixcli.info(f'The following command result written to file: {out_file}')
        mixcli.info(json.dumps(result))
        write_result_outfile(content=result, out_file=out_file, logger=mixcli)
    else:
        mixcli.info(json.dumps(result))


@cmd_regcfg_func('intent', 'list', 'List intents for Mix project NLU models', cmd_intent_list)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='aa_AA_LOCALE', required=True, help='aa_AA locale code')
    cmd_argparser.add_argument('--need-meta', action='store_true', required=False,
                               help='Need meta info for concepts. Otherwise only names would be returned.')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

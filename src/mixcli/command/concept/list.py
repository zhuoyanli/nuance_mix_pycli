"""
MixCli **concept** command group **list** command.

This command will retrieve meta information of all entities in NLU ontology of a Mix project. Users can choose
to take list of entity names or JSON of entity meta info as finalized output.

One note here is the currently there are three special NLU entities: YES_NO, DATE, and TIME. They will always
created for users when new Mix projects are created but they are NOT built-in nuance entities.
"""
from argparse import ArgumentParser
from . import ENTITY_ATTRIB_ISINTENT, ENTITY_ATTRIB_PREDEFINED
from mixcli import MixCli
from typing import Dict, List, Iterable, Union
from mixcli.util.commands import cmd_regcfg_func
from mixcli.util.requests import HTTPRequestHandler, GET_METHOD, get_api_resp_payload_data
from mixcli.util.cmd_helper import assert_id_int, write_result_outfile, MixLocale

KNOWN_PREDEFINED_CONCEPT_EXCEPTIONS = {'DATE', 'TIME', 'YES_NO'}
"""Set of known exception concepts whose metas look like custom but indeed are predefined"""


class ConceptFilter:
    """
    Class to perform filtering on NLU concept meta
    """
    def __init__(self, accept_intent: bool = False, accept_predefined: bool = False):
        """
        Constructor
        :param accept_intent: should accept Intention when True, only accept entity concepts when being False
        :param accept_predefined: should accept predefined concepts when True, reject otherwise
        """
        self._acpt_intent = accept_intent
        self._acpt_predefined = accept_predefined

    def filter(self, concept_meta_json: Dict) -> bool:
        """
        Return True if concept is accepted
        :param concept_meta_json: Json object for meta of Mix entity/concept
        :return: True if accepted, False otherwise
        """
        if not self._acpt_intent:
            if concept_meta_json[ENTITY_ATTRIB_ISINTENT]:
                return False
        if not self._acpt_predefined:
            if concept_meta_json['name'] in KNOWN_PREDEFINED_CONCEPT_EXCEPTIONS:
                return False
            if concept_meta_json[ENTITY_ATTRIB_PREDEFINED]:
                return False
        return True

    def filter_concept_meta_iterable(self, iterable: Iterable) -> List[Dict]:
        """
        Filter an iterable
        :param iterable: Iterable of Json objects
        :return list of Json objects after filtering:
        """
        return [meta_c for meta_c in filter(lambda meta_c: self.filter(meta_c), iterable)]


def pyreq_list_concepts(httpreq_handler: HTTPRequestHandler, project_id: int, locale: str,
                        include_predefined: bool = False) -> Union[List[Dict], List[str]]:
    """
    Get the list of concepts from Mix project with project_id and in locale 'locale', by sending requests to
    API endpoint with Python 'requests' package. This function will return the 'data' field of the original
    API response payload JSON.

    API endpoint
    ::
        GET 'nlu/api/v1/ontology/{project_id}/concepts?locale={locale}'

    :param httpreq_handler: a HTTPRequestHandler instance
    :param project_id: Mix project ID
    :param locale: the locale code in aa_AA
    :param include_predefined: True if should include predefined concepts/entities
    :return: list of Json objects if json_resp is True, list of str otherwise
    """
    """
    Example payload json:
    { 'data':
        [
          {
            "name": "CHECKIN_DATE", 
            "links": [{"linkedNodeName": "nuance_CALENDARX", "boltLinkName": "isA"}], 
            "isIntention": false, 
            "isFreetext": false, 
            "isDynamic": false, 
            "canonicalize": true, 
            "isInBaseOntology": false, 
            "isOperator": false, 
            "isReference": false, 
            "uuid": "7553792d-9b10-4b3f-8f87-8f024b7cd2b5", 
            "nbPatterns": 0, 
            "isSensitive": false, 
            "type": "relationship"
          }, 
          {
            "name": "PICKUP_DATE", 
            "links": [], 
            "isIntention": false, 
            "isFreetext": false, 
            "isDynamic": false, 
            "canonicalize": true, 
            "isInBaseOntology": false, 
            "isOperator": false, 
            "isReference": false, 
            "uuid": "9e375bc5-b99c-4e5d-8203-58f1938b7d27", 
            "nbPatterns": 2, 
            "isSensitive": false, 
            "type": "literals"
          }
        ]
    }
    """

    api_endpoint = f'nlu/api/v1/ontology/{project_id}/concepts?locale={locale}'
    resp = httpreq_handler.request(url=api_endpoint, method=GET_METHOD, default_headers=True, json_resp=True)
    filterer = ConceptFilter(accept_predefined=include_predefined)
    resp_data = get_api_resp_payload_data(resp)
    result_concept_meta_json = filterer.filter_concept_meta_iterable(resp_data)
    return result_concept_meta_json


def list_concepts(mixcli: MixCli, project_id: Union[str, int], locale: str,
                  include_predefined=False, need_meta: bool = True) -> Union[List[Dict], List[str]]:
    """
    Get the list of concepts from Mix project with project_id and in locale 'locale'.

    :param need_meta:
    :param mixcli: MixCli instance
    :param project_id: Mix project ID
    :param locale: the locale code in aa_AA
    :param include_predefined: True if should include predefined concepts/entities
    :return: list of Json objects if json_resp is True, list of str otherwise
    """
    """
    For example resp content, consult function pyreq_list_concepts. Note that only the list from 'data' field will
    be returned from that function.
    """

    project_id = assert_id_int(project_id, 'project')
    mixloc = MixLocale.to_mix(locale)
    resp = pyreq_list_concepts(mixcli.httpreq_handler, project_id=project_id, locale=mixloc,
                               include_predefined=include_predefined)
    # do we want the JSON meta?
    if need_meta:
        return resp
    else:
        # no we return the list of concept (names)
        return [c_meta_j['name'] for c_meta_j in resp]


def cmd_concept_list(mixcli: MixCli, **kwargs: Union[str, bool]):
    """
    Default function when MixCli concept list command is called.

    :param mixcli: a MixCli instance
    :param kwargs: keyword arguments from command-line arguments
    :return: None
    """
    proj_id = kwargs['project_id']
    loc = kwargs['locale']
    incl_predef = kwargs['with_predef']
    need_meta = kwargs['need_meta']
    # result is a JSON array
    out_file = kwargs['out_file']
    result = list_concepts(mixcli, project_id=proj_id, locale=loc, include_predefined=incl_predef, need_meta=need_meta)
    res_str = ' '.join(result)
    if out_file:
        write_result_outfile(content=res_str, out_file=out_file, is_json=True, logger=mixcli)
    else:
        # display space-delimited list of concept names

        mixcli.info(f'Concepts for project with ID {proj_id}: '+res_str)
    return True


@cmd_regcfg_func('concept', 'list', 'List concepts for Mix project NLU models', cmd_concept_list)
def config_cmd_argparser(cmd_argparser: ArgumentParser):
    """
    Configure the ArgumentParser instance for this MixCli command.

    :param cmd_argparser: the ArgumentParser instance corresponding to this command
    :return: None
    """
    cmd_argparser.add_argument('-p', '--project-id', metavar='PROJECT_ID', required=True, help='Mix project ID')
    cmd_argparser.add_argument('-l', '--locale', metavar='aa_AA_LOCALE', required=True, help='aa_AA locale code')
    cmd_argparser.add_argument('--with-predef', action='store_true', help='Include predefined concepts')
    cmd_argparser.add_argument('--need-meta', action='store_true', required=False,
                               help='Need meta info for concepts. Otherwise only names would be returned.')
    cmd_argparser.add_argument('-o', '--out-file', metavar='RESULT_OUTPUT_FILE', required=False,
                               help="Save command result to output file")

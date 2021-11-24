import json
from typing import Optional, Union, Dict, Tuple
import urllib.parse
# noinspection PyUnreachableCode
if False:
    from mixcli import MixCli
from . import MixApiAuthHandler, MixApiClientCred, MixApiAuthFailureError,\
    DEFAULT_API_AUTH_HOST, DEFAULT_API_CLIENTCRED_AUTH_DATA
from ..requests import HTTPRequestHandler, GET_METHOD, POST_METHOD
# This is for PyCharm warning on forward reference
# noinspection PyUnreachableCode
if False:
    from mixcli import MixCli


class PyReqMixApiAuthHandler(MixApiAuthHandler):
    """
    The class implements MixApiAuthHandler by using CURL to complete client credentials auth flow
    """
    # we must use forward reference here for type hinting, otherwise we will run
    # into circular references
    def __init__(self, mixcli: Optional['MixCli'] = None,
                 token_str: Optional[str] = None, token_file: Optional[str] = None,
                 client_cred_json: Optional[str] = None, log_level: Optional[Union[str, int]] = None):
        MixApiAuthHandler.__init__(self, mixcli=mixcli, token_str=token_str, token_file=token_file,
                                   client_cred_json=client_cred_json, log_level=log_level)

    def client_cred_auth(self, mixcli: 'MixCli',
                         client_cred: Optional[MixApiClientCred] = None,
                         client_id: Optional[str] = None,
                         service_secret: Optional[str] = None) -> Dict:
        """
        Generate Mix API auth token with user client ID and service secret.

        :param mixcli:
        :param client_cred: MixClientCred instance
        :param client_id: Mix user client ID
        :param service_secret: Mix user service secret
        :return: The latest generated API auth token generated from client credential auth workflow
        """
        if not client_id or not service_secret:
            if not client_cred:
                raise ValueError('Must specifiy either MixClientCred or Client-id/Service-cred')
            self.debug('Mix user client credentials auth mode')
            client_id = client_cred.client_id
            service_secret = client_cred.service_secret
        client_auth_token: Dict = self.pyreq_client_cred_auth(mixcli.httpreq_handler, client_id, service_secret)
        mixcli.auth_handler.client_cred = MixApiClientCred.from_client_id_srvc_sec(client_id, service_secret)
        mixcli.auth_handler.client_auth_token = client_auth_token
        return client_auth_token

    def pyreq_client_cred_auth(self, httpreq_handler: HTTPRequestHandler, client_id: str,
                               service_secret: str) -> Dict:
        """
        Generate Mix API auth token with user client ID and service secret by curl. This function
        makes use of curl command to exercises the client credentials authorization workflow
        as instructed in Mix documentation.

        :param httpreq_handler: a HTTPRequestHandler instance
        :param client_id: Mix user client ID
        :param service_secret: Mix user service secret
        :return: The generated API auth token as JSON object
        """
        self.debug('Using Python requests for Mix user client credentials auth mode')
        cliid_quoted = urllib.parse.quote(client_id)
        srvcsec_quoted = urllib.parse.quote(service_secret)
        # we must put default_headers as False because we do NOT use any headers
        # in auth token request!
        try:
            result: Tuple[Dict, int] = \
                httpreq_handler.request(DEFAULT_API_AUTH_HOST, method=POST_METHOD, default_headers=False,
                                        data_as_str=False, url_fq=True, data=DEFAULT_API_CLIENTCRED_AUTH_DATA,
                                        auth=(cliid_quoted, srvcsec_quoted), json_resp=True, validate_json=True,
                                        check_error=False, need_status=True)
            resp_json, st_code = result
            try:
                assert st_code == 200 and resp_json, 'Invalid Mix Oauth client credential auth result'
            except Exception as ex:
                raise MixApiAuthFailureError('Invalid Mix Oauth client credential auth response') from ex
            self.debug(f'Adding expiration timestamp to the token generated')
            MixApiAuthHandler.add_expiration_timestamp(resp_json)
            self.debug(f'Mix client auth token generated: {json.dumps(resp_json)}')
            return resp_json
        except Exception as ex:
            raise ValueError(f'Requests not returning token as valid Json', ex)

    @classmethod
    def probe_service(cls, mixcli: 'MixCli', token: str) -> Dict:
        """
        Make a probe at the service with the given token to confirm if the token is still valid
        :param mixcli: a MixCli instance
        :param token: A given Mix API auth token
        :return: A Json object that is the Mix API endpoint response if there are no errors
        """
        api_endpoint = '/api/v2/version'
        headers = mixcli.httpreq_handler.get_default_headers(auth_token=token)
        resp = mixcli.httpreq_handler.request(url=api_endpoint, method=GET_METHOD, headers=headers, json_resp=True)
        return resp

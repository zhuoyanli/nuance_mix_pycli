"""
Utility class and functions for Mix API authorization flows
"""
import codecs
import json
import datetime
import os
import os.path
from abc import ABCMeta, abstractmethod
from typing import Optional, Union, Tuple, Dict

# this is for PyCharm warning on forward reference
# noinspection PyUnreachableCode
if False:
    from mixcli import MixCli
from mixcli.util.logging import Loggable
from mixcli.util import count_notnone
from ..commands import DEFAULT_MIX_SERVICE_CRED_JSON, DEFAULT_MIX_API_TOKEN_FILE

DEFAULT_API_AUTH_HOST = "https://auth.crt.nuance.com/oauth2/token"
"""
Default host to which authorization requests should be sent
"""
DEFAULT_API_CLIENTCRED_AUTH_DATA = {'grant_type': 'client_credentials', 'scope': 'mix-api'}
"""
Default headers used in Mix client credentials authorization flow HTTP requests
"""

ENVAR_MIXCLI_USERHOME = 'MIXCLI_USERHOME'


class MixApiAuthTokenExpirationError(Exception):
    """
    Custom exception to represent that a Mix API auth token has expired
    """
    _DEFAULT_EXC_MSG = "Mix API auth token has expired"
    """
    Default message used in exception
    """

    def __init__(self, ex_msg: Optional[str] = None):
        """
        Constructor.

        :param ex_msg: str, Message to be used in this exception instance. If None _DEFAULT_EXC_MSG will be used.
        """
        if ex_msg:
            Exception.__init__(self, ex_msg)
        else:
            Exception.__init__(self, self._DEFAULT_EXC_MSG)


class MixApiAuthFailureError(Exception):
    """
    Custom exception to represent that a Mix API auth token has expired
    """
    _DEFAULT_EXC_MSG = "Mix Oauth client credential authorization failed"
    """
    Default message used in exception
    """

    def __init__(self, ex_msg: Optional[str] = None):
        """
        Constructor
        :param ex_msg: str, Message to be used in this exception instance. If None _DEFAULT_EXC_MSG will be used.
        """
        if ex_msg:
            Exception.__init__(self, ex_msg)
        else:
            Exception.__init__(self, self._DEFAULT_EXC_MSG)


class MixApiClientCred:
    """
    Class representing the client (service) credentials used for Mix API authorization
    """
    def __init__(self, path_cred_json: Optional[str] = None,
                 cli_id: Optional[str] = None, srvc_sec: Optional[str] = None):
        """
        Constructor.
        :param path_cred_json: str, path to Json file containing Mix user client credentials. Simply put, there
        should be at least two top-level fields, each being string, whose names are respectively 'client-id' and
        'service-secret'. The names come from the official Mix documentations
        """
        if not cli_id or not srvc_sec:
            try:
                with codecs.open(path_cred_json, 'r', 'utf-8') as fhi_credjson:
                    json_cred = json.load(fhi_credjson)
                    if 'client-id' not in json_cred:
                        raise ValueError('Field "client-id" missing in credential Json')
                    if 'service-secret' not in json_cred:
                        raise ValueError('Field "service-secret" missing in credential Json')
                    cli_id = json_cred['client-id']
                    srvc_sec = json_cred['service-secret']
            except Exception as ex:
                print("Error processing Mix client credential Json")
                raise ex
        self._client_id = cli_id
        self._srvc_sec = srvc_sec

    @classmethod
    def from_client_id_srvc_sec(cls, cli_id: Optional[str] = None, srvc_sec: Optional[str] = None) \
            -> 'MixApiClientCred':
        return MixApiClientCred(cli_id=cli_id, srvc_sec=srvc_sec)

    @classmethod
    def from_json_file(cls, path_cred_json: str) -> 'MixApiClientCred':
        return MixApiClientCred(path_cred_json=path_cred_json)

    @property
    def client_id(self) -> str:
        """
        Get the client-id of the client credentials.

        :return: str, the client-id of the client credentials
        """
        return self._client_id

    @property
    def service_secret(self) -> str:
        """
        Get the service-secret of the client credentials.

        :return: str, he service-secret of the client credentials
        """
        return self._srvc_sec

    @classmethod
    def client_credentials_from_json_file(cls, path_cred_json: str) -> Tuple[str, str]:
        """
        Read client id and service secret from Json file with expected format by MixApiClientCred
        :param path_cred_json: Path to Json file with expected format by MixApiClientCred
        :return: tuple of str for (client_id, service_secret)
        """
        srvc_cred_json = MixApiClientCred(path_cred_json)
        return srvc_cred_json.client_id, srvc_cred_json.service_secret


class MixApiAuthToken(metaclass=ABCMeta):
    """
    Abstract class for Mix API authorization tokens
    """
    def __init__(self):
        pass

    # the order matters here!
    @property
    @abstractmethod
    def token(self):
        raise NotImplementedError()


class MixStrToken(MixApiAuthToken):
    """
    Class representing a literal Mix token in string
    """
    def __init__(self, token: str):
        MixApiAuthToken.__init__(self)
        self._tok = token

    @property
    def token(self) -> str:
        return self._tok


class MixJsonToken(MixApiAuthToken):
    """
    Class representing a Mix authorization token in Json data, typically obtained from client authorization flow.
    The Json is expected to carry several fields for meta-info of the token
    """
    FIELD_TOKEN = 'access_token'
    """
    The literal Mix authorization token string.
    """
    FILED_SCOPE = 'scope'
    """
    The authorization scope for this token
    """
    VALUE_SCOPE = 'mix-api'
    """
    The authorization scope is expected to be mix-api
    """
    FILED_TOKTYPE = 'token_type'
    VALUE_TOKTYPE = 'bearer'
    FIELD_EXPIRATION = 'expires_at'
    """
    Approximate expiration timestamp for this token. This timestamp is generated by adding 14 minutes to the creation
    time. NOTE: The actually life span should be 15 minutes but we take away one minute to be safe.
    """
    TIMESTAMP_FORMAT = '%Y%m%dT%H:%M'
    """
    The formatter specification for the timestamp used in str{p/f}time functions.
    """

    def __init__(self, json_token: Optional[Dict] = None, json_file: Optional[str] = None):
        """
        Constructor.

        :param json_token: json object, the parsed Json objects from the client credentials configs
        :param json_file: str, path to the Json file containing the client credentials configs
        """
        MixApiAuthToken.__init__(self)
        if not json_token:
            try:
                with codecs.open(json_file, 'r', 'utf-8') as fhi_json:
                    json_token = json.load(fhi_json)
            except Exception as ex:
                print(f"Error loading Mix API auth token from Json {json_file}")
                raise ex
        self.assert_json_token(json_token)
        self._json_tok = json_token
        self._expires_at = None
        if self.FIELD_EXPIRATION in self._json_tok:
            self._expires_at = datetime.datetime.strptime(self._json_tok[self.FIELD_EXPIRATION],
                                                          self.TIMESTAMP_FORMAT)

    def assert_json_token(self, json_token: Dict) -> bool:
        """
        Assert if the json object carries expected fields and values

        :param json_token:
        :return: True
        """
        if self.FIELD_TOKEN in json_token and \
            self.FILED_SCOPE in json_token and json_token[self.FILED_SCOPE] == self.VALUE_SCOPE and \
                self.FILED_TOKTYPE in json_token and json_token[self.FILED_TOKTYPE] == self.VALUE_TOKTYPE:
            return True
        raise ValueError("Invalid Mix API auth token Json: Error(s) in expected field(s) and/or value(s)")

    @property
    def token(self) -> str:
        """
        Get the literal token string in the complex object.

        :return: str, the literal token string
        """
        return self._json_tok[self.FIELD_TOKEN]

    @property
    def json_token(self):
        return self._json_tok

    def expires_at(self):
        """
        :return: A datetime.datetime instance or None
        """
        return self._expires_at


class MixApiAuthHandler(Loggable):
    """
    Handler class for Mix API auth token management
    """
    def __init__(self, mixcli: Optional['MixCli'] = None,
                 token_str: Optional[str] = None, token_file: Optional[str] = None,
                 client_cred_json: Optional[str] = None, log_level: Optional[Union[str, int]] = None):
        """
        Constructor.

        :param mixcli: MixCli instance, the MixCli to be bound with this MixApiAuthHandler instance.
        :param token_str: str, a Mix API authorization token already generated and directly assigned
        :param token_file: str, path to a plain text file containing a token already generated
        :param client_cred_json: str, path to Json file containing Mix user client credentials for authorization flows.
        """
        Loggable.__init__(self, log_level=log_level)
        if mixcli:
            self._mixcli = mixcli
            mixcli.auth_handler = self
        self._token_str = None
        self._token_file = None
        self._client_cred = None
        self._client_cred_file = None
        self._token_clientauth = None
        if token_str or token_file or client_cred_json:
            self._token_str, self._token_file, self._client_cred_file, self._client_cred =\
                self.config_from_sources(token_str=token_str, token_file=token_file, client_cred_json=client_cred_json)

    def config(self, token_str=None, token_file=None, client_cred_json=None):
        self._token_str, self._token_file, self._client_cred_file, self._client_cred = \
            self.config_from_sources(token_str=token_str, token_file=token_file, client_cred_json=client_cred_json)

    @property
    def __name__(self):
        return 'AuthHandler'

    @classmethod
    def config_from_sources(cls, token_str: Optional[str] = None, token_file: Optional[str] = None,
                            client_cred_json: Optional[str] = None):
        """
        Configure this MixApiAuthHandler instance from various sources.

        :param token_str: str, a literal Mix API auth token
        :param token_file: str, path to a plain text file containing literal Mix API auth token
        :param client_cred_json: string, path to a Json file containing Mix client credentials (for token generation)
        :return:
        """
        if token_str is None and token_file is None and client_cred_json is None:
            raise ValueError("Must specify either one of toke string, token file, or Mix service credentials Json")
        if count_notnone(token_str, token_file, client_cred_json) > 1:
            raise ValueError("Can only specify either one of toke string, token file, or Mix service credentials Json")

        _token_str = None
        _token_file = None
        _client_cred = None
        _client_cred_file = None

        if token_str:
            _token_str = token_str
        elif token_file:
            _token_file = os.path.realpath(token_file)
            with codecs.open(_token_file, 'r', 'utf-8') as fhi_tokenfile:
                _token = fhi_tokenfile.read().strip()
                if _token.startswith('"') and _token.endswith('"'):
                    # print("Stripping the closing double-quotes from token")
                    _token_str = _token[1:-1]
        else:
            _client_cred_file = client_cred_json
            _client_cred = MixApiClientCred.from_json_file(client_cred_json)
        return _token_str, _token_file, _client_cred_file, _client_cred

    @property
    def token(self):
        """
        Get the Mix API auth token. If the token on file has expired: If it is generated with Mix client
        credentials, a new token will be generated; If it is a literal assigned token (either string or file),
        MixApiAuthTokenExpirationError will be thrown.

        :return: str, the Mix API auth token. If token has expired, MixApiAuthTokenExpirationError will be thrown
        """
        try:
            self.debug('Requesting token')
            try_token = self.token_valid(exc_if_expire=True)
            return try_token
        except MixApiAuthTokenExpirationError as ex:
            if self._client_cred is not None:
                # we can redo service auth
                self.debug(f"Replacing expired token with service creds from {self._client_cred_file}")
                _token_json = self.client_cred_auth(self._mixcli,
                                                    client_id=self._client_cred.client_id,
                                                    service_secret=self._client_cred.service_secret)
                self._token_clientauth = MixJsonToken(json_token=_token_json)
                self.debug(f"Token generated, will expire at {self._token_clientauth.expires_at()}")
                return self._token_clientauth.token
            # for literal token or literal token from plain text file, we can't do anything
            raise ex

    def token_valid(self, exc_if_expire=False) -> Optional[str]:
        """
        Validate if the token on file is still valid.

        :param exc_if_expire: Raise MixApiAuthTokenExpirationError exception if token has expired
        :return: str for the token if it is valid (has not expired); if token has expired, return None if exc_if_expire
        is not True, otherwise raise MixApiAuthTokenExpirationError exception
        """
        if self._client_cred:
            self.debug('User client credential auth mode')
            if self._token_clientauth is None:
                self.debug('User client credential auth token not ready')
                self.client_cred_auth(self._mixcli, client_cred=self._client_cred)
                if self._token_clientauth:
                    return self._token_clientauth.token
                else:
                    raise ValueError("Failed to perform Mix client credentials auth flow!")
            self.debug(f"MixApiAuthHandler: Using token generated with service creds from {self._client_cred_file}")
            time_now = datetime.datetime.now()
            if time_now <= self._token_clientauth.expires_at():
                self.debug(f"MixApiAuthHandler: Re-using token generated with service creds")
                return self._token_clientauth.token
            else:
                if exc_if_expire:
                    raise MixApiAuthTokenExpirationError()
                return None
        elif self._token_str:
            try:
                self.probe_service(self._mixcli, token=self._token_str)
                return self._token_str
            except MixApiAuthTokenExpirationError as ex:
                if exc_if_expire:
                    raise ex
                return None

    @property
    def client_auth_token(self):
        if not self._client_cred:
            return None
        return self._token_clientauth

    @client_auth_token.setter
    def client_auth_token(self, new_client_auth_token) -> None:
        try:
            # must be valid json object!
            auth_token = MixJsonToken(json_token=new_client_auth_token)
            self._token_clientauth = auth_token
        except Exception as ex:
            raise RuntimeError('Client auth token must be valid Json object') from ex

    @property
    def client_cred(self):
        return self._client_cred

    @client_cred.setter
    def client_cred(self, new_cli_cred):
        self._client_cred = new_cli_cred

    @property
    def token_expiration_msg(self):
        """
        Get the message when token expires
        :return:
        """
        if self._token_file:
            msg = f"Token from file may have expired: {self._token_file}"
        else:
            msg = "Token may have expired"
        return msg

    @classmethod
    def add_expiration_timestamp(cls, json_client_auth):
        """
        Add the expiration timestamp to the Json object from client credentials authorization

        :param json_client_auth: json, the Json object from client credentials authorization
        :return:
        """
        expires_at = datetime.datetime.now() + datetime.timedelta(minutes=14)
        str_expires_at = datetime.datetime.strftime(expires_at, MixJsonToken.TIMESTAMP_FORMAT)
        json_client_auth[MixJsonToken.FIELD_EXPIRATION] = str_expires_at

    @classmethod
    def token_from_client_auth_json(cls, json_client_auth):
        """
        Get the token string from Mix client credentials authorization Json result
        :param json_client_auth: Json object, results from Mix client credentials authorization
        :return: str, literal string for Mix API auth token
        """
        return f'"{json_client_auth[MixJsonToken.FIELD_TOKEN]}"'

    def auth_with_cmd_sources(self, token_str: str = None, token_file: str = None,
                              client_cred_file: str = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Register authorization sources for the MixApiAuthHandler

        :param token_str: str, the literal Mix API auth token
        :param token_file: str, path to plain text file containing the Mix API auth token
        :param client_cred_file: str, path to Json file containing Mix user client credentials
        :return: True
        """
        used_token = used_token_file = used_client_cred_file = None
        if token_str is None and token_file is None and client_cred_file is None:
            # if none of the auth token arguments have been specified, we try to find them from CWD
            # we prefer service credentials
            path_client_cred_json = lookup_default_client_credentials_json()
            if path_client_cred_json:
                # yes we find the file
                self.info(f"Using Mix service credentials from default Json: {path_client_cred_json}")
                self.config(client_cred_json=path_client_cred_json)
                used_client_cred_file = path_client_cred_json
            else:
                token_file = lookup_default_token_file()
                if token_file:
                    self.debug(f"Using token file at {token_file}")
                    self.config(token_file=token_file)
                else:
                    raise RuntimeError("Must specify either API token, text containing it, or service credentials Json")
        elif count_notnone(token_str, token_file, client_cred_file) > 1:
            raise RuntimeError("Can specify ONLY ONE of API token, text containing it, or service credentials Json")
        else:
            if token_str:
                used_token = token_str
                self.config(token_str=token_str)
            elif token_file:
                used_token_file = token_file
                self.config(token_file=token_file)
            elif client_cred_file:
                used_client_cred_file = client_cred_file
                self.config(client_cred_json=client_cred_file)
        return used_token, used_token_file, used_client_cred_file

    @abstractmethod
    def client_cred_auth(self, mixcli: 'MixCli',
                         client_cred: Optional[MixApiClientCred] = None,
                         client_id: Optional[str] = None,
                         service_secret: Optional[str] = None):
        """
        Generate Mix API auth token with user client ID and service secret.

        :param mixcli: MixCli instance
        :param client_cred: MixClientCred instance
        :param client_id: Mix user client ID
        :param service_secret: Mix user service secret
        :return:
        """
        ...

    @abstractmethod
    def probe_service(self, mixcli: 'MixCli', token: str):
        ...

    def exc_token_expiration(self, exc_msg: Optional[str] = None):
        if exc_msg:
            raise MixApiAuthTokenExpirationError(ex_msg=exc_msg)
        else:
            raise MixApiAuthTokenExpirationError(self.token_expiration_msg)


def client_credentials_from_json_file(path_cred_json: str) -> Tuple[str, str]:
    """
    Read client id and service secret from Json file with expected format by MixApiClientCred

    :param path_cred_json: Path to Json file with expected format by MixApiClientCred
    :return: tuple of str for (client_id, service_secret)
    """
    srvc_cred_json = MixApiClientCred(path_cred_json)
    return srvc_cred_json.client_id, srvc_cred_json.service_secret


def client_auth_with_default_json(logger: Optional[Loggable] = None) -> Optional[Tuple[str, str]]:
    path_client_cred_json = lookup_default_client_credentials_json()
    if not path_client_cred_json:
        return None
    if logger:
        logger.debug(f'Reading Mix user client credetials from default Json: {path_client_cred_json}')
    client_id, srvc_sec = MixApiClientCred.client_credentials_from_json_file(path_client_cred_json)
    if logger:
        logger.debug(f'Successfully read Mix user client credetials from default Json: {path_client_cred_json}')
    return client_id, srvc_sec


def client_auth_with_json(path_json: str, logger: Optional[Loggable] = None) -> Tuple[str, str]:
    if logger:
        logger.debug(f'Reading Mix user client credetials from Json: {path_json}')
    client_id, srvc_sec = MixApiClientCred.client_credentials_from_json_file(path_json)
    if logger:
        logger.debug(f'Successfully read Mix user client credetials from Json: {path_json}')
    return client_id, srvc_sec


def lookup_file_from_mixcli_userhome(filename: str) -> Optional[str]:
    """
    Try to lookup a file with given name, if environment variable for MixCli user home is present, is a valid dir,
    and if a file with given name is found in that dir.

    :param filename: Name of expected file to lookup
    :return: None if environment variable is absent, value of variable is not a valid directory, or no file with
    given name is found in that dir; Otherwise returns the path to the file.
    """
    if ENVAR_MIXCLI_USERHOME in os.environ:
        if os.path.isdir(os.environ[ENVAR_MIXCLI_USERHOME]):
            path_lookup_file = os.path.realpath(os.path.join(os.environ[ENVAR_MIXCLI_USERHOME], filename))
            if os.path.isfile(path_lookup_file):
                return path_lookup_file
    return None


def lookup_default_client_credentials_json() -> Optional[str]:
    """
    Try to look up the default Json file containing the Mix client credentials

    :return: str or None, the path to the default Json file, or none if not found
    """
    path_client_cred_json = os.path.realpath(os.path.join(os.getcwd(), DEFAULT_MIX_SERVICE_CRED_JSON))
    if os.path.isfile(path_client_cred_json):
        return path_client_cred_json
    else:
        return lookup_file_from_mixcli_userhome(DEFAULT_MIX_SERVICE_CRED_JSON)


def lookup_default_token_file() -> Optional[str]:
    """
    Try to look up the default Mix API token file
    :return: str or None, the path to the token file, or None if not found
    """
    path_token_file = os.path.realpath(os.path.join(os.getcwd(), DEFAULT_MIX_API_TOKEN_FILE))
    if os.path.isfile(path_token_file):
        return path_token_file
    else:
        return lookup_file_from_mixcli_userhome(DEFAULT_MIX_API_TOKEN_FILE)

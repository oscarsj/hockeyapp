"""
Base API Class and Request Functionality

"""
__author__ = 'Gavin M. Roy'
__email__ = 'gmr@myyearbook.com'
__since__ = '2011-09-12'

import json
import logging
import httplib
import urllib

import urllib2
from poster.encode import multipart_encode
from poster.streaminghttp import register_openers

import urlparse

from types import FileType

SERVER = 'rink.hockeyapp.net'
BASE_URI = '/api/2/'

def _requires_multipart(params):
    """Determine if multipart request needs to be made

    :param params: Dictionary of parameters to send
    :type params: dict

    :returns: True if params contain file objects to send

    """
    if not params:
        return False

    for value in params.values():
        if isinstance(value, FileType):
            return True;

    return False


def _request(api_key, method, uri, parameters):
    """Make a request to the Hockeyapp API server

    :param api_key: The API Key for the request
    :type api_key: str
    :param method: The HTTP method for the request.
    :type method: str
    :param uri: The URI to make a request for
    :type uri: str
    :param parameters: URL parameters
    :type parameters: dict
    :returns: tuple of headers dict and json decoded response data

    """

    if _requires_multipart(parameters):
        return _dispatch_multipart_request(api_key, method, uri, parameters)
    
    return _dispatch_request(api_key, method, uri, parameters)

def _dispatch_request(api_key, method, uri, parameters):

    logger = logging.getLogger('hockeyapp.api')
    headers = {'X-HockeyAppToken': api_key, 'Accept': '*/*'}
    params = None
    url = "https://%s/%s" % (SERVER, uri)
    if parameters:
        logger.debug('Encoding parameters: %r', parameters)
        params = urllib.urlencode(parameters)
        url = "%s?%s" % (uri, params)

    logger.debug('Sending %s: %s with headers: %r', method, uri, headers)
    request = urllib2.Request(url, params, headers)

    # Get the response
    response = urllib2.urlopen(request)
    logger.debug('Return Response: %i %s %r',
                 response.code, response.msg, response.headers.dict)

    # Read in the data from the response
    data = response.read()
    
    # If we have data, json decode it
    if data and response.headers.get('content-type').find('application/json') >= 0:
        data = json.loads(data)

    return response.code, data

def _dispatch_multipart_request(api_key, method, uri, parameters):
    
    logger = logging.getLogger('hockeyapp.api')

    if method != 'POST':
        raise APIError('Multi-part support is only provided for POST')

    #register streaming http handlers with urlib2
    register_openers()

    logger.debug("Sending with parameters %r" % parameters)

    simple_params = {}
    file_params = {}

    for key in parameters:
        if isinstance(parameters[key], file):
            file_params[key] = parameters[key]
        else:
            simple_params[key] = parameters[key]


    datagen, headers = multipart_encode(file_params)
    headers['X-HockeyAppToken'] = api_key
    headers['Accept'] = '*/*'

    if len(simple_params) > 0:
        uri = "%s?%s" % (uri, urllib.urlencode(simple_params))

    url = "https://%s%s" % (SERVER, uri)
    data = str().join(datagen) #To get around the __len__ problem sending datagen directly
    request = urllib2.Request(url, data, headers)
  
    result = None
    status = None
    h = urllib2.HTTPHandler(debuglevel=1)
    opener = urllib2.build_opener(h)
    try:
        req = opener.open(request)
        result = req.read()
        if result and req.headers.getheader('content-type').find('application/json') >= 0:
            result = json.loads(result)
        status = req.code
    except urllib2.HTTPError as e:
        result = e.read()
        if result and e.headers['content-type'].find('application/json') >= 0:
            result = json.loads(result)
        status = e.code

    return status, result 

class APIError(Exception):
    def __init__(self, value):
        """Construct an APIError object
        :param value: The error data returned from the remote call

        """
        self.value = value

    def __str__(self):
        """ Format exception data

        :returns: the string representation of the errror

        """
        m = ""
        for k in self.value.keys():
            m += "[%s]: %s\n" % (k, ", ".join(self.value[k]))
        return m

class APIRequest(object):
    """Base Hockeyapp APIRequest Object"""
    def __init__(self, api_key):
        """Construct the APIRequestObject

        :param api_key: The API Key for the request
        :type api_key: str

        """
        self._logger = logging.getLogger(__name__)
        self._api_key = api_key
        self._key = None
        self._method = 'GET'
        self._logger.debug('Initialized an %s instance with the api key: %s',
                           self.__class__.__name__, self._api_key)

    def execute(self):
        """Execute the API request. If parameters are provided, join them as
        a URI.

        :returns: an iterable or None
        :raises APIError: if status code is not 200

        """
        status, data = _request(self._api_key, self._method, self.path, self.parameters)
        
        if status >= 200 and status < 300:
            if isinstance(data, dict) and self._key:
                return data[self._key]
            return data
        else:
            if isinstance(data, dict):
                if 'errors' in data:
                    data = data['errors']
                raise APIError(data)

        return data

    @property
    def parameters(self):
        """Returns the request parameters

        :returns: dict or None

        """
        return None

    @property
    def path(self):
        """Returns the request path

        :returns: str

        """
        return BASE_URI

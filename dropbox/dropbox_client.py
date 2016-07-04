import re
import json
from .dropbox_connection import *
from .dropbox_session import *
from .dropbox_util import *


OAUTH2_ACCESS_TOKEN_PATTERN = re.compile(r"\A[-_~/A-Za-z0-9\.\+]+=*\Z")


class DropboxClient:
    def __init__(self, access_token, prefix_path=None):
        self.connection = DropboxConnection(prefix_path)
        if type(access_token) == str:
            if not OAUTH2_ACCESS_TOKEN_PATTERN.match(access_token):
                raise ValueError("invalid format for oauth2_access_token: %r" % (access_token))
            self.session = DropboxSession(access_token)
        else:
            raise ValueError("'oauth2_access_token' must either be a string or a DropboxSession")

    def request(self, target, params=None, method="POST", content_server=False):
        if params is None:
            params = {}
        host = DropboxUtil.API_CONTENT_HOST if content_server else DropboxUtil.API_HOST
        base = DropboxUtil.build_url(host, target)
        headers, params = self.session.build_access_headers(method, base, params)
        if method in ("GET", "PUT"):
            url = DropboxUtil.build_url(host, target, params=params)
        else:
            url = DropboxUtil.build_url(host, target)
        return url, params, headers

    def account_info(self):
        url, params, headers = self.request("/users/get_current_account", method="POST")
        return self.connection.post(url, headers=headers)

    def put_file(self, full_path, file_obj):
        path = "/files/upload"
        params = {
            "path": DropboxUtil.format_path(full_path),
            "mode": "overwrite"
        }
        url, params, headers = self.request(path, params, method="POST", content_server=True)
        headers["Content-Type"] = "application/octet-stream"
        headers["Dropbox-API-Arg"] = json.dumps(params)
        return self.connection.request("POST", url, body=file_obj, headers=headers)

    def get_file(self, full_path):
        path = "/files/download"
        params = {
            "path": DropboxUtil.format_path(full_path)
        }
        url, params, headers = self.request(path, params, method="GET", content_server=True)
        headers["Dropbox-API-Arg"] = json.dumps(params)
        return self.connection.request("POST", url, body=file_obj, headers=headers)
    
    def list_folder(self, full_path):
        path = "/files/list_folder"
        params = {
            "path": DropboxUtil.format_path(full_path)
        }
        url, params, headers = self.request(path, params, method="POST")
        headers["Content-Type"] = "application/json"
        return self.connection.request("POST", url, body=json.dumps(params), headers=headers)

    def metadata(self, full_path):
        path = "/files/get_metadata"
        params = {
            "path": DropboxUtil.format_path(full_path)
        }
        url, params, headers = self.request(path, params, method="GET")
        headers["Content-Type"] = "application/json"
        return self.connection.request("POST", url, body=json.dumps(params), headers=headers)

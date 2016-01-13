import re
import os
import urllib


class DropboxUtil:
    API_VERSION = 1
    WEB_HOST = "www.dropbox.com"
    API_HOST = "api.dropbox.com"
    API_CONTENT_HOST = "api-content.dropbox.com"

    @staticmethod
    def get_cert_file(prefix=None):
        prefix = prefix or ""
        return os.path.join(prefix, "certs/dropbox.certification")

    @staticmethod
    def build_path(target, params=None):
        target_path = urllib.quote(target)
        params = params or {}
        params = params.copy()
        if params:
            return "/%s%s?%s" % (DropboxUtil.API_VERSION, target_path, urllib.urlencode(params))
        else:
            return "/%s%s" % (DropboxUtil.API_VERSION, target_path)

    @staticmethod
    def build_url(host, target, params=None):
        return "https://" + host + DropboxUtil.build_path(target, params)

    @staticmethod
    def split_path(path):
        sep = "/"
        if path.startswith(sep):
            return ["/"] + DropboxUtil.split_path(path[1:])
        else:
            return path.split(sep)

    @staticmethod
    def format_path(path):
        if path is None:
            return ""
        while "\\" in path:
            path = path.replace("\\", "/")
        while "//" in path:
            path = path.replace("//", "/")
        if path.startswith("/"):
            path = path[1:]
        if path == "/" or path == "":
            return ""
        else:
            split_paths = DropboxUtil.split_path(path)
            return "/" + "/".join(split_paths)

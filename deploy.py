import os
import sys
import re
import zipfile
import fnmatch
import biplist
from dropbox import *

CONFIG_OPTION_PATTERN = re.compile("(\\w+)(=(.*))")


def to_readable_size(filesize):
    scales = [
        [1000 ** 5, "PB"],
        [1000 ** 4, "TB"],
        [1000 ** 3, "GB"],
        [1000 ** 2, "MB"],
        [1000 ** 1, "kB"],
        [1000 ** 0, "B"]
    ]
    for scale in scales:
        if filesize >= scale[0]:
            break
    return "%.2f%s" % (filesize / scale[0], scale[1])


def validate_path(client, path):
    try:
        root_data = client.metadata(path)
        return root_data["is_dir"]
    except:
        return None


def get_ipa_file(path):
    if not os.path.exists(path):
        return None
    for item in os.listdir(path):
        if item.endswith(".ipa"):
            return os.path.join(path, item)
    return None


def analyse_ipa(ipa_file):
    with zipfile.ZipFile(ipa_file, "r") as ipa:
        ipa_info = {}
        files = ipa.namelist()
        info_plist = fnmatch.filter(files, "Payload/*.app/Info.plist")[0]
        info_plist_bin = ipa.read(info_plist)
        try:
            info = biplist.readPlistFromString(info_plist_bin)
            ipa_info = info
        except:
            pass
        ipa.close()
        return ipa_info
    return None


def deploy(client, settings=None):
    settings = settings or {}


def run(args):
    if "--clear" in args:
        os.remove(".iosdeploy")
        exit(0)

    app_key = None
    app_secret = None
    setup_mode = "--setup" in args
    while "--setup" in args:
        args.remove("--setup")
    access_token = None
    binary_path = None
    storage_path = "/Deployment"
    client = None

    if os.path.exists(".iosdeploy"):
        config = open(".iosdeploy", "r")

        for line in config.readlines():
            match = CONFIG_OPTION_PATTERN.search(line)
            if not match:
                continue
            key = match.group(1)
            if match.group(3):
                value = match.group(3)
                if key == "APP_KEY":
                    app_key = value
                elif key == "APP_SECRET":
                    app_secret = value
                elif key == "ACCESS_TOKEN":
                    access_token = value
                elif key == "STORAGE_PATH":
                    storage_path = value
                elif key == "BINARY_PATH":
                    binary_path = value
        config.close()

        client = DropboxClient(access_token)
        try:
            print("Validating access token...")
            client.account_info()
        except:
            if setup_mode:
                print("Access token has expired")
            else:
                print("error:Previous access token has expired")
                exit(1)
            client = None
            access_token = None

    while args:
        if args[0] == "--storage_path":
            del args[0]
            if not args:
                if setup_mode:
                    print("Expected path for storage path option")
                else:
                    print("error:Expected path for storage path option")
                exit(1)
            storage_path = args[0]
        del args[0]

    if not setup_mode and not access_token:
        print(
            "error:iOSDeploy setup required. " +
            "Please run this script using \"python deploy.py --setup\"" +
            " in the Terminal."
        )
        exit(1)

    while not access_token:
        while True:
            if not app_key:
                app_key = raw_input("Enter Dropbox app key: ")
            if not app_secret:
                app_secret = raw_input("Enter Dropbox app secret: ")
            auth = DropboxAuth(app_key, app_secret)
            print("Get authorization code from: " + auth.get_authorize_url())
            code = raw_input("Enter authorization code: ")
            try:
                access_token, user_id = auth.authorize(code)
                break
            except:
                print("Invalid authorization code")
                continue
        access_token = str(access_token)

        first_time = True
        while (
            not binary_path or
            (os.path.exists(binary_path) or not os.path.isdir(binary_path))
        ):
            if not first_time:
                print("Invalid path")
            binary_path = raw_input("Enter path contains .ipa files: ")

        client = DropboxClient(access_token)
        while True:
            path = raw_input("Enter Dropbox path to store .ipa files [%s]: " % (storage_path))

            path_validation = validate_path(client, path)
            if path_validation is not None and not path_validation:
                print("Target path is not a directory")
                continue

            if path:
                storage_path = path
            break

        config = open(".iosdeploy", "w")
        config.write("APP_KEY=%s\n" % (app_key))
        config.write("APP_SECRET=%s\n" % (app_secret))
        config.write("ACCESS_TOKEN=%s\n" % (access_token))
        config.write("STORAGE_PATH=%s\n" % (storage_path))
        config.write("BINARY_PATH=%s\n" % (binary_path))
        config.close()
        print("Setup finished")
        exit(0)

    print("Validating output .ipa path [%s]..." % (binary_path))
    if (
        not binary_path or
        (os.path.exists(binary_path) and not os.path.isdir(binary_path))
    ):
        if setup_mode:
            print("Invalid .ipa path.")
        else:
            print("error:Invalid .ipa path.")
        exit(1)

    print("Validating storage path [%s]..." % (storage_path))
    path_validation = validate_path(client, storage_path)
    if path_validation is not None and not path_validation:
        if setup_mode:
            print("Target path is not a directory")
        else:
            print("error:Target path is not a directory")
        exit(1)

    ipa_file = get_ipa_file(binary_path)
    if not ipa_file:
        if setup_mode:
            print(".ipa file is not found. The deployment will be skipped.")
        else:
            print(
                "warning:.ipa file is not found. " +
                "The deployment will be skipped."
            )
        exit(0)
    ipa_file_name = os.path.basename(ipa_file)
    print("Analysing %s..." % (ipa_file_name))
    ipa_info = analyse_ipa(ipa_file)
    if ipa_info:
        print("=" * 20)
        print("Application Overview:")
        print("%sApplication Name: %s" % (
            " " * 4, ipa_info["CFBundleDisplayName"]
        ))
        print("%sApplication Version: %s" % (
            " " * 4, ipa_info["CFBundleVersion"]
        ))
        print("Application Details:")
        print("%sBundle Identifier: %s" % (
            " " * 4, ipa_info["CFBundleIdentifier"]
        ))
        print("%sDevice Family: %s" % (
            " " * 4, ", ".join([
                "iPhone" if family == 1 else "iPad"
                for family in ipa_info["UIDeviceFamily"]
            ])
        ))
        print("%sMinimum OS Version: %s" % (
            " " * 4, ipa_info["MinimumOSVersion"]
        ))
        print("%sSize: %s" % (
            " " * 4, to_readable_size(os.path.getsize(ipa_file))
        ))
        print("=" * 20)
    else:
        if setup_mode:
            print("%s is corrupted." % (ipa_file_name))
        else:
            print("error:%s is corrupted." % (ipa_file_name))
        exit(1)
    deploy(client or DropboxClient(access_token), {
        "storage_path": storage_path
    })


if __name__ == "__main__":
    run(sys.argv)

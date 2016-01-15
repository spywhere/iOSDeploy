import os
import sys
import re
import zipfile
import fnmatch
import biplist
import json
from dropbox import *

CONFIG_OPTION_PATTERN = re.compile("(\\w+)(=(.*))")
MACRO_PATTERN = re.compile("<!--\\s*\\[(\\w+)]\\s*-->")

EXEC_DIR = os.path.dirname(os.path.abspath(__file__))
WORKING_DIR = os.getcwd()

DUMP_JSON = False


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


def parse_macro(match, ipa_info=None, build_info=None):
    ipa_info = ipa_info or {}
    build_info = build_info or {}
    if match.group(1) in build_info:
        return build_info[match.group(1)]
    elif match.group(1) in ipa_info:
        return ipa_info[match.group(1)]
    else:
        return ""


def dump_error(error_message):
    print("error:%s" % (error_message))
    error = {
        "error": error_message
    }
    dump_result(error)


def dump_result(result):
    if DUMP_JSON:
        output_file = open(os.path.join(WORKING_DIR, "output.json"), "w")
        json.dump(result, output_file)
        output_file.close()


def deploy(client, settings):
    setup_mode = settings["setup_mode"]
    storage_path = settings["storage_path"]
    ipa_file = settings["ipa_file"]
    ipa_file_name = settings["ipa_file_name"]
    ipa_info = settings["ipa_info"]
    tmp_file = os.path.join(EXEC_DIR, "tmpfile")
    template = {
        "index": "index.html",
        "item": "item.html",
        "new-item": "new-item.html",
        "manifest": "manifest.plist"
    }
    for key in template:
        template[key] = os.path.join(EXEC_DIR, "template", template[key])
        if key != "new-item" and not os.path.exists(template[key]):
            if setup_mode:
                print("Template file for \"%s\" is not found" % (key))
            else:
                dump_error("Template file for \"%s\" is not found" % (key))
                exit(1)
    user_info = client.account_info()
    public_url = "https://dl.dropboxusercontent.com/u/%s" % (user_info["uid"])
    app_name = (
        ipa_info["CFBundleDisplayName"]
        if "CFBundleDisplayName" in ipa_info
        else ipa_info["CFBundleName"]
    )
    app_url = "%s/%s" % (storage_path, app_name)
    ipa_url = "%s/%s/%s" % (
        app_url,
        ipa_info["CFBundleVersion"],
        ipa_file_name
    )
    manifest_url = "%s/%s/%s" % (
        app_url,
        ipa_info["CFBundleVersion"],
        "manifest.plist"
    )

    print("Uploading %s..." % (ipa_file_name))
    client.put_file("/Public" + ipa_url, open(ipa_file, "r"))

    print("Creating manifest.plist file...")
    template_manifest_file = open(template["manifest"], "r")
    template_manifest = template_manifest_file.read()
    template_manifest_file.close()
    build_info = {
        "APP_NAME": app_name,
        "IPA_URL": public_url + ipa_url,
        "MANIFEST_URL": public_url + manifest_url
    }
    template_manifest = MACRO_PATTERN.sub(
        lambda m: parse_macro(m, ipa_info, build_info),
        template_manifest
    )
    manifest = open(tmp_file, "w")
    manifest.write(template_manifest)
    manifest.close()

    print("Uploading manifest.plist...")
    client.put_file("/Public" + manifest_url, open(tmp_file, "r"))
    os.remove(tmp_file)

    print("Generating builds info...")
    public_app_url = "/Public" + app_url
    app_dir_info = client.metadata(public_app_url)

    builds = []
    contents = app_dir_info["contents"]
    contents.reverse()
    for entry in contents:
        if not entry["is_dir"]:
            continue
        bundle_version = entry["path"][len(public_app_url) + 1:]
        if (
            bundle_version == ipa_info["CFBundleVersion"] and
            os.path.exists(template["new-item"])
        ):
            template_build_file = open(template["new-item"], "r")
            template_build = template_build_file.read()
            template_build_file.close()

            build_info["APP_NAME"] = app_name
            build_info["BUNDLE_VERSION"] = ipa_info["CFBundleVersion"]
            build_info["MODIFIED"] = entry["modified"]

            template_build = MACRO_PATTERN.sub(
                lambda m: parse_macro(m, ipa_info, build_info),
                template_build
            )

            builds = [template_build] + builds
            continue
        build = {
            "APP_NAME": app_name,
            "BUNDLE_VERSION": bundle_version,
            "MANIFEST_URL": public_url + app_url + "/%s/manifest.plist" % (
                bundle_version
            ),
            "MODIFIED": entry["modified"]
        }

        template_build_file = open(template["item"], "r")
        template_build = template_build_file.read()
        template_build_file.close()

        template_build = MACRO_PATTERN.sub(
            lambda m: parse_macro(m, build),
            template_build
        )

        builds.append(template_build)

    print("Creating HTML page...")
    template_index_file = open(template["index"], "r")
    template_index = template_index_file.read()
    template_index_file.close()

    build_info = {
        "APP_NAME": app_name,
        "BUILDS": "".join(builds)
    }

    template_index = MACRO_PATTERN.sub(
        lambda m: parse_macro(m, ipa_info, build_info),
        template_index
    )

    index = open(tmp_file, "w")
    index.write(template_index)
    index.close()

    print("Uploading HTML page...")
    client.put_file("/Public" + app_url + "/index.html", open(tmp_file, "r"))
    os.remove(tmp_file)

    print("=" * 20)
    result = {
        "name": app_name,
        "ipa_url": public_url + ipa_url,
        "manifest_url": public_url + manifest_url,
        "ipa_file_name": ipa_file_name,
        "app_url": public_url + app_url,
        "deploy_url": public_url + app_url + "/index.html"
    }
    result.update(ipa_info)
    dump_result(result)
    print("Deployment complete: %s" % (public_url + app_url + "/index.html"))


def run(args):
    if "--help" in args:
        print("Usage: python deploy.py [option] ...")
        print("Options")
        print("--binary-path <path>\t: Local path contains built .ipa files")
        print("--clear\t\t\t: Remove previously store informations")
        print("--help\t\t\t: Print this help message")
        print("--json\t\t\t: Generate output as json file")
        print("--setup\t\t\t: Enter setup mode when informations is outdated")
        print("--storage-path <path>\t: Dropbox path to store .ipa files")
        print("--store-app-info\t: Save app key and app secret")
        exit(0)

    if "--clear" in args:
        os.remove(os.path.join(WORKING_DIR, ".iosdeploy"))
        exit(0)

    app_key = None
    app_secret = None
    setup_mode = "--setup" in args
    store_app_info = "--store-app-info" in args
    DUMP_JSON = "--json" in args
    while "--json" in args:
        args.remove("--json")
    while "--setup" in args:
        args.remove("--setup")
    while "--store-app-info" in args:
        args.remove("--store-app-info")
    access_token = None
    binary_path = None
    storage_path = "/Deployment"
    client = None

    if os.path.exists(os.path.join(WORKING_DIR, ".iosdeploy")):
        config = open(os.path.join(WORKING_DIR, ".iosdeploy"), "r")

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

        client = DropboxClient(access_token, EXEC_DIR)
        try:
            print("Validating access token...")
            client.account_info()
        except:
            if setup_mode:
                print("Access token has expired")
            else:
                dump_error("Previous access token has expired")
                exit(1)
            client = None
            access_token = None

    while args:
        if args[0] == "--storage-path":
            del args[0]
            if not args:
                if setup_mode:
                    print("Expected path for storage path option")
                else:
                    dump_error("Expected path for storage path option")
                exit(1)
            storage_path = args[0]
        elif args[0] == "--binary-path":
            del args[0]
            if not args:
                if setup_mode:
                    print("Expected path for binary path option")
                else:
                    dump_error("Expected path for binary path option")
                exit(1)
            binary_path = args[0]
        del args[0]

    if not setup_mode and not access_token:
        dump_error(
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
            auth = DropboxAuth(app_key, app_secret, EXEC_DIR)
            print("Get authorization code from: " + auth.get_authorize_url())
            code = raw_input("Enter authorization code: ")
            try:
                access_token, user_id = auth.authorize(code)
                break
            except Exception as e:
                print("Invalid authorization code: %s" % (e))
                continue
        access_token = str(access_token)

        first_time = True
        while (
            not binary_path or
            (os.path.exists(binary_path) and not os.path.isdir(binary_path))
        ):
            if not first_time:
                print("Invalid path")
            binary_path = raw_input("Enter path contains .ipa files: ")
            first_time = False

        client = DropboxClient(access_token, EXEC_DIR)
        while True:
            path = raw_input(
                "Enter Dropbox path to store .ipa files [%s]: " % (storage_path)
            )

            path_validation = validate_path(client, path)
            if path_validation is not None and not path_validation:
                print("Target path is not a directory")
                continue

            if path:
                storage_path = path
            break

        config = open(os.path.join(WORKING_DIR, ".iosdeploy"), "w")
        if store_app_info:
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
            dump_error("Invalid .ipa path.")
        exit(1)

    print("Validating storage path [%s]..." % ("/Public" + storage_path))
    path_validation = validate_path(client, "/Public" + storage_path)
    if path_validation is not None and not path_validation:
        if setup_mode:
            print("Target path is not a directory")
        else:
            dump_error("Target path is not a directory")
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
    app_name = (
        ipa_info["CFBundleDisplayName"]
        if "CFBundleDisplayName" in ipa_info
        else ipa_info["CFBundleName"]
    )
    if ipa_info:
        print("=" * 20)
        print("Application Overview:")
        print("%sApplication Name: %s" % (
            " " * 4, app_name
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
            dump_error("%s is corrupted." % (ipa_file_name))
        exit(1)
    deploy(client or DropboxClient(access_token, EXEC_DIR), {
        "setup_mode": setup_mode,
        "storage_path": storage_path,
        "ipa_file": ipa_file,
        "ipa_file_name": ipa_file_name,
        "ipa_info": ipa_info
    })


if __name__ == "__main__":
    run(sys.argv)

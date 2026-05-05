import datetime
import glob
import logging
import os
import re
import subprocess
import sys
import threading
import time
from collections import namedtuple
from typing import Optional

from _shutil import (
    call2,
    call_echo,
    check_output,
    download,
    prepend_to_path,
    print2,
    read_proc_lines,
    unzip,
)

logger = logging.getLogger(__name__)


ANDROID_SDK_INSTALL_DIR = os.path.join(
    os.path.expandvars("%LOCALAPPDATA%"), "Android", "Sdk"
)


def reset_debug_sysprops():
    subprocess.check_call(["adb", "root"])
    try:
        lines = subprocess.check_output(
            ["adb", "shell", "getprop -Z | grep :debug_oculus_prop:"],
            universal_newlines=True,
        ).splitlines()

        for line in lines:
            line = line.strip()
            matches = re.findall(r"^\[(.*?)\]", line)
            prop_name = matches[0]

            logger.debug("Reset %s" % prop_name)
            adb_shell(["setprop", prop_name, "''"])
    except Exception as ex:
        logging.error(ex)


def wake_up_device():
    out = subprocess.check_output(
        ["adb", "shell", "dumpsys power | grep 'mWakefulness='"],
        universal_newlines=True,
    )
    if "Asleep" in out:
        logging.info("Device is asleep, wake up by press power button.")
        subprocess.check_call(["adb", "shell", "input", "keyevent", "26"])  # power key


def get_main_activity(pkg):
    out = subprocess.check_output(
        ["adb", "shell", f"dumpsys package | grep -i {pkg}/ | grep Activity"],
        universal_newlines=True,
    )
    lines = out.strip().splitlines()
    line = lines[0].strip()
    _, pkg_activity = line.split()
    return pkg_activity


def start_app(pkg, use_monkey=False, wake_up=True):
    if wake_up:
        wake_up_device()

    if use_monkey:
        args = [
            "adb",
            "shell",
            "monkey",
            "-p",
            pkg,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ]
        logger.info("shell_cmd: %s" % " ".join(args))
        with open(os.devnull, "w") as fnull:
            ret = subprocess.call(
                args,
                stdout=fnull,
                stderr=fnull,
            )
        if ret != 0:
            raise Exception(
                'Launch package "%s" failed. Please check if it is installed.' % pkg
            )
    else:
        pkg_activity = get_main_activity(pkg)
        args = ["adb", "shell", "am", "start", "-n", pkg_activity]
        logger.info("shell_cmd: %s" % " ".join(args))
        out = subprocess.check_output(args, universal_newlines=True)
        logger.debug(out)


def clear_logcat():
    logger.debug("Clearing logcat")

    # Retry on error
    while True:
        try:
            subprocess.check_call(["adb", "logcat", "-c"])
            break
        except subprocess.CalledProcessError:
            logger.debug("WARNING: clear logcat failed. Retrying")


def kill_app(pkg):
    args = ["adb", "shell", "am", "force-stop", pkg]
    call_echo(args)


def restart_app(pkg, use_monkey=False, wake_up=True):
    logger.info("Stop app: " + pkg)
    args = ["adb", "shell", "am", "force-stop", pkg]
    call2(args)

    start_app(pkg, use_monkey=use_monkey, wake_up=wake_up)


def restart_current_app():
    pkg, activity = get_active_pkg_and_activity()

    call2(["adb", "shell", "am", "force-stop", pkg])
    call2(["adb", "shell", "am", "start", "-n", "%s/%s" % (pkg, activity)])


def logcat(
    pkg=None,
    highlight=None,
    regex=None,
    clear=False,
    show_log_after_secs=-2,
    level=None,
    exclude=None,
    exclude_proc=None,
    ignore_duplicates=False,
    show_fatal_error=False,
):
    LOGCAT_PATTERN = re.compile(
        r"^(\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([A-Z])\s+(.*)$"
    )

    wait_for_device()
    fnull = open(os.devnull, "w")

    if ignore_duplicates:
        last_message = None
        dup_messages = 0

    if level:
        level = re.compile(level)
    if exclude:
        exclude = re.compile(exclude)
    if regex:
        regex = re.compile(regex)
    if exclude_proc:
        exclude_proc = re.compile(exclude_proc)

    args = ["adb", "logcat"]

    if show_log_after_secs is not None:
        out = subprocess.check_output(["adb", "shell", "date '+%m-%d %H:%M:%S'"])
        out_str = out.decode().strip()
        dt_start = datetime.datetime.strptime(out_str, "%m-%d %H:%M:%S")
        dt_start += datetime.timedelta(seconds=show_log_after_secs)
        args += ["-T", dt_start.strftime("%m-%d %H:%M:%S") + ".000"]

    if clear:
        call2(["adb", "logcat", "-c"])

    if highlight is None:
        highlight = {}

    pid_proc_map = {}
    last_proc = None

    while True:
        show_fatal_error_pid = None
        try:
            for line in read_proc_lines(args):
                match = re.match(LOGCAT_PATTERN, line)
                if match is None:
                    logger.debug(line)
                    continue

                pid = int(match.group(2))
                if pid <= 0:
                    continue

                # Get process name
                if pid not in pid_proc_map:
                    try:
                        proc = subprocess.check_output(
                            ["adb", "shell", f"cat /proc/{pid}/cmdline"],
                            universal_newlines=True,
                            stderr=fnull,
                        ).strip()
                    except subprocess.CalledProcessError:
                        proc = None
                    pid_proc_map[pid] = proc
                else:
                    proc = pid_proc_map[pid]

                lvl = match.group(4)
                if show_fatal_error and lvl == "F":
                    if pkg is not None and pkg in line:
                        show_fatal_error_pid = pid
                    if show_fatal_error_pid == pid:
                        pass
                    else:
                        continue
                else:
                    # Filter by level
                    if level and not re.search(level, lvl):
                        continue

                    # Filter by tag or message
                    message = match.group(5)
                    if regex and not re.search(regex, message):
                        continue

                    # Exclude by tag or message
                    if exclude and re.search(exclude, message):
                        continue

                    # Filter by package
                    if pkg is not None:
                        if proc is None:
                            continue
                        else:
                            # Filter by process name (include)
                            if pkg not in proc:
                                continue

                            # Exclude by process name (exclude)
                            if exclude_proc and re.search(exclude_proc, proc):
                                continue

                    if ignore_duplicates:
                        if message == last_message:
                            dup_messages += 1
                            print("\r(%d) " % dup_messages, end="")
                            continue

                # Output process name
                if last_proc != proc:
                    print2("%s (%d)" % (proc, pid))
                    last_proc = proc

                print(line)

                if ignore_duplicates:
                    last_message = message
                    dup_messages = 0

        except Exception as ex:
            print2(ex)


def get_apk_path(pkg):
    out = subprocess.check_output(
        ["adb", "shell", "pm", "path", pkg], universal_newlines=True
    )
    apk_path = out.splitlines()[0]
    apk_path = apk_path.replace("package:", "")
    return apk_path


def backup_pkg(
    pkg, out_dir=None, backup_apk=True, backup_user_data=False, backup_obb=True
):
    if out_dir is not None:
        os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = os.getcwd()

    if backup_obb:
        obb_dir = os.path.join(out_dir, "obb")
        os.makedirs(obb_dir, exist_ok=True)

    # Pull apk
    if backup_apk:
        # Get apk path
        # 'package:/data/app/com.github.uiautomator-1AfatTFmPxzjNwUtT-5h7w==/base.apk'
        apk_path = get_apk_path(pkg)

        subprocess.check_call(["adb", "pull", apk_path, f"{pkg}.apk"], cwd=out_dir)

    # Check root permission
    if subprocess.call(["adb", "shell", "type", "su"]) == 0:
        su = ["su", "-c"]
    else:
        su = []

    if backup_user_data:
        logging.info("Backup app data")
        subprocess.call(
            ["adb", "exec-out"]
            + su
            + [
                f"tar -cf /sdcard/{pkg}.tar --exclude='data/data/{pkg}/cache' /data/data/{pkg}"
            ]
        )
        subprocess.call(["adb", "pull", f"/sdcard/{pkg}.tar"], cwd=out_dir)
        subprocess.call(["adb", "shell", "rm", f"/sdcard/{pkg}.tar"])

    if backup_obb:
        logging.info("Backup obb")
        subprocess.call(["adb", "pull", f"/sdcard/android/obb/{pkg}"], cwd=obb_dir)


def adb_tar(d, out_tar):
    temp_tar = "/data/local/tmp/backup.tar"
    subprocess.check_call(
        [
            "adb",
            "exec-out",
            "tar",
            "-cf",
            temp_tar,
            d,
        ]
    )
    subprocess.check_call(["adb", "pull", temp_tar, out_tar])
    subprocess.check_call(["adb", "shell", "rm", temp_tar])


def adb_untar(tar_file):
    subprocess.check_call(["adb", "push", tar_file, "/data/local/tmp/"])
    adb_shell(["tar", "-xf", f"/data/local/tmp/{tar_file}"])


def screenshot(out_file=None, scale=None):
    from _image import scale_image

    if out_file is None:
        out_file = datetime.datetime.now().strftime("screencap_%y%m%d%H%M%S.png")
        src_file = os.path.basename(out_file)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        src_file = os.path.basename(out_file)

    while True:
        try:
            logger.info("Taking screenshot")
            subprocess.check_call(
                ["adb", "shell", "screencap", "-p", "/sdcard/%s" % src_file]
            )
            logger.debug(["adb", "pull", "-a", "/sdcard/%s" % src_file, out_file])
            subprocess.check_call(
                ["adb", "pull", "-a", "/sdcard/%s" % src_file, out_file]
            )
            subprocess.check_call(["adb", "shell", "rm", "/sdcard/%s" % src_file])

            break
        except subprocess.CalledProcessError as ex:
            logger.warning(ex)
            time.sleep(1)

    if scale is not None:
        scale_image(out_file, scale, scale)
    return out_file


def get_active_pkg_and_activity():
    out = subprocess.check_output(
        [
            "adb",
            "shell",
            "dumpsys activity activities | grep -E 'mFocusedActivity"
            "|mResumedActivity"
            "|mFocusedApp'",  # Android 12+
        ],
        universal_newlines=True,
    ).strip()
    match = re.search(r"\{([^}]+)\}", out).group(1)
    pkg_activity = match.split()[2]
    pkg, activity = pkg_activity.split("/")
    return pkg, activity


def get_device_name():
    out = subprocess.check_output(
        ["adb", "shell", "getprop", "ro.build.fingerprint"]
    ).decode()
    model = out.split("/")[1]
    return model


def get_adk_path():
    if sys.platform == "win32":
        ADK_SEARCH_PATH = [
            # Default Android SDK path installed by Android Studio
            ANDROID_SDK_INSTALL_DIR,
            # Installed by choco
            r"C:\Android\android-sdk",
            # Default SDK path installed by Android Studio
            os.path.abspath(os.environ["LOCALAPPDATA"] + "/Android/Sdk"),
        ]

    elif sys.platform == "linux":
        ADK_SEARCH_PATH = [
            "/opt/android-sdk/",  # arch linux
            os.path.expanduser("~/Android/Sdk"),
            os.path.expanduser("~/android-sdk"),
        ]

    else:
        return None

    for p in ADK_SEARCH_PATH:
        if os.path.exists(p):
            return p

    return None


def get_prop(name):
    return subprocess.check_output(["adb", "shell", "getprop", name]).decode().strip()


def setup_jdk(jdk_version=None, env=None):
    if env is None:
        env = os.environ

    def find_jdk(patterns, jdk_version=None):
        jdk_paths = []
        for pattern in patterns:
            paths = glob.glob(pattern)
            if len(paths) == 0:
                continue
            if jdk_version:
                jdk_paths += [
                    p
                    for p in paths
                    if re.match(r"^\D*" + re.escape(jdk_version), os.path.basename(p))
                ]
            else:
                jdk_paths += paths
        jdk_paths = sorted(jdk_paths)
        return jdk_paths[-1]  # Choose latest JDK

    if sys.platform == "win32":
        java_home = find_jdk(
            [
                r"C:\Program Files\Java\jdk*",
                r"C:\Program Files (x86)\Android\openjdk\jdk-*",
                r"C:\Program Files\Eclipse Adoptium\jdk*",
            ],
            jdk_version=jdk_version,
        )
    elif sys.platform == "linux":
        javac_path = os.popen("which javac").read().strip()
        javac_abs_path = os.path.realpath(javac_path)
        javac_dir = os.path.dirname(javac_abs_path)
        java_home = os.path.dirname(javac_dir)
    else:
        raise Exception("Unsupported os: %s" % sys.platform)

    if java_home is None:
        raise Exception("Cannot find JDK")

    env["JAVA_HOME"] = java_home
    logging.info("JAVA_HOME: %s" % java_home)

    jdk_bin = os.path.join(java_home, "bin")
    prepend_to_path(jdk_bin, env=env)


def setup_android_env(
    env=None,
    ndk_version=None,
    jdk_version=None,
    build_tools_version=None,
    android_home=None,
):
    if env is None:
        env = os.environ

    path = []

    # ANDROID_HOME
    if android_home is None:
        android_home = os.environ.get("ANDROID_HOME")
    if android_home is None:
        android_home = get_adk_path()
    if android_home is None:
        raise Exception("Cannot find ANDROID_HOME")
    logging.info("ANDROID_HOME: %s" % android_home)
    env["ANDROID_HOME"] = android_home
    path += [
        env["ANDROID_HOME"] + "/platform-tools",
        env["ANDROID_HOME"] + "/tools",
        env["ANDROID_HOME"] + "/tools/bin",
        env["ANDROID_HOME"] + "/ndk-bundle",
    ]

    # # Android build tools (latest)
    build_tools_search_pattern = os.path.join(env["ANDROID_HOME"], "build-tools")
    if build_tools_version:
        build_tools_search_pattern = os.path.join(
            build_tools_search_pattern, build_tools_version
        )
    else:
        build_tools_search_pattern = os.path.join(build_tools_search_pattern, "*")
    build_tools_dir = sorted(glob.glob(build_tools_search_pattern))
    if len(build_tools_dir) > 0:
        path.append(build_tools_dir[-1])  # choose the latest version
        logging.info("Android SDK: build-tools: " + build_tools_dir[-1])

    # NDK
    ndk_path = None
    if (android_home is not None) and (ndk_path is None):
        if ndk_path is None:
            found = sorted(
                glob.glob(
                    os.path.join(
                        android_home, "ndk", ndk_version + "*" if ndk_version else "*"
                    )
                )
            )
            if found:
                ndk_path = found[-1]

        if ndk_path is None:
            found = sorted(
                list(
                    glob.glob(
                        os.path.join(
                            android_home,
                            "ndk",
                            ndk_version + "*" if ndk_version else "*",
                        )
                    )
                )
            )
            if found:
                ndk_path = found[-1]

        if ndk_path is None:
            ndk_bundle = os.path.join(android_home, "ndk-bundle")
            if os.path.exists(ndk_bundle):
                ndk_path = ndk_bundle

    if ndk_path:
        logging.info("ANDROID_NDK_ROOT: %s" % ndk_path)
        env["ANDROID_NDK_ROOT"] = ndk_path
        env["ANDROID_NDK_HOME"] = ndk_path
        env["ANDROID_NDK"] = ndk_path
        env["NDKROOT"] = ndk_path
        env["NDK_ROOT"] = ndk_path
        path.append(ndk_path)

    setup_jdk(jdk_version=jdk_version, env=env)

    prepend_to_path(path, env=env)


def adb_shell(command, check=True, check_output=False, echo=False, **kwargs):
    if isinstance(command, list):
        args = ["adb", "shell"] + command
    else:
        args = ["adb", "shell", command]

    if echo:
        print2("> " + " ".join(args))

    if check_output:
        return subprocess.check_output(args, universal_newlines=True)
    else:
        return subprocess.run(args, check=check, **kwargs)


def wait_for_device():
    subprocess.check_call(["adb", "wait-for-device"])


def wait_until_boot_complete():
    wait_for_device()
    while True:
        try:
            if (
                subprocess.check_output(
                    ["adb", "shell", "getprop", "sys.boot_completed"],
                    universal_newlines=True,
                ).strip()
                == "1"
            ):
                break

            print(".", end="", flush=True)
            time.sleep(2)

        except Exception as ex:
            logging.error(ex)
            time.sleep(2)


def adb_shell2(command, check=True, root=True):
    if root and not hasattr(adb_shell2, "super_su"):
        # Check root permission
        adb_shell2.super_su = subprocess.call(["adb", "shell", "type", "su"]) == 0
        if not adb_shell2.super_su:
            subprocess.check_call(["adb", "root"])

    if isinstance(command, list):
        command = " ".join(command)

    args = ["adb", "shell"]
    if adb_shell2.super_su:
        args += ["su", "-c", command]
    else:
        args.append(command)

    subprocess.run(args, check=check)


def pm_list_packages():
    s = check_output(["adb", "shell", "pm", "list", "packages"]).decode()
    s = s.replace("package:", "")
    lines = s.splitlines()
    lines = sorted(lines)
    return lines


class AdbInstallResult:
    def __init__(self, pkg: str, installed: bool):
        self.pkg = pkg
        self.installed = installed


def adb_install(
    apk,
    force_reinstall=False,
    grant_permissions=False,
    skip_install_if_exist=True,
) -> AdbInstallResult:
    # Get package name
    out = subprocess.check_output(
        ["aapt", "dump", "badging", apk], universal_newlines=True
    )
    match = re.search(r"package: name='(.+?)'", out)
    if match is None:
        raise Exception(f"Failed to find app package name from: {out}")
    pkg_name = match.group(1)
    logger.debug("apk package name: %s" % pkg_name)

    if not force_reinstall:
        should_install = False
        if not app_is_installed(pkg_name):
            logger.info("App does not exist on device, installing")
            should_install = True

        if not should_install and not skip_install_if_exist:
            # Get local apk size in bytes
            local_file_size = os.path.getsize(apk)

            # Get file size in bytes
            apk_path_device = get_apk_path(pkg_name)
            file_size = int(
                subprocess.check_output(
                    ["adb", "shell", "wc -c %s | awk '{print $1}'" % apk_path_device],
                    universal_newlines=True,
                )
            )

            if local_file_size != file_size:
                logger.info(
                    "Installed APK size does not match with local file %d != %d, reinstalling..."
                    % (file_size, local_file_size)
                )
                should_install = True
    else:
        should_install = True

    if force_reinstall or should_install:
        logger.info("Install %s" % apk)
        try:
            adb_install_cmd = [
                "adb",
                "install",
                "-r",  # Replace existing apps without clearing data
                "-d",  # Allow downgrade
            ]
            args = adb_install_cmd + [apk]
            logging.debug("%s" % args)
            out = subprocess.check_output(
                args, stderr=subprocess.STDOUT, universal_newlines=True
            )
            logging.debug(out)
        except subprocess.CalledProcessError as ex:
            msg = ex.output
            logging.warning(msg)

            if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in msg:
                pkg = re.findall("[Pp]ackage ([a-z0-9A-Z.]+)", msg)[0]
                logging.warning("Uninstalling %s..." % pkg)
                subprocess.check_call(["adb", "uninstall", pkg])
                subprocess.check_call(adb_install_cmd + [apk])
            elif "INSTALL_FAILED_CONFLICTING_PROVIDE" in msg:
                pkg = re.findall("already used by ([a-z0-9A-Z.]+)", msg)[0]
                logging.warning("Uninstalling %s..." % pkg)
                subprocess.check_call(["adb", "uninstall", pkg])
                subprocess.check_call(adb_install_cmd + [apk])
            else:
                raise ex

        if grant_permissions:
            apk_info = get_apk_info(apk)
            with open(os.devnull, "w") as fnull:
                for permission in apk_info.permissions:
                    ret_code = subprocess.call(
                        [
                            "adb",
                            "shell",
                            "pm",
                            "grant",
                            apk_info.pkg_name,
                            permission,
                        ],
                        stderr=fnull,
                        stdout=fnull,
                    )
                    if ret_code != 0:
                        logger.warning("Failed to grant permission: %s" % permission)

    else:
        logger.info("App already installed, skipping")

    return AdbInstallResult(pkg=pkg_name, installed=should_install)


def adb_install2(
    file,
    force_reinstall=False,
    grant_permissions=False,
    skip_install_if_exist=True,
) -> AdbInstallResult:
    """
    Install + restore app data.
    """
    result = adb_install(
        file,
        force_reinstall=force_reinstall,
        grant_permissions=grant_permissions,
        skip_install_if_exist=skip_install_if_exist,
    )

    if result.installed:
        # Push data
        tar_file = os.path.splitext(file)[0] + ".tar"
        pkg = os.path.splitext(os.path.basename(file))[0]
        if os.path.exists(tar_file):
            logger.info("Restoring app data")
            subprocess.check_call(["adb", "push", tar_file, "/data/local/tmp/"])
            adb_shell2(["tar", "-xf", f"/data/local/tmp/{pkg}.tar"], root=True)

            out = check_output(
                ["adb", "shell", f"dumpsys package {pkg} | grep userId"]
            ).strip()

            userId = re.findall(r"userId=(\d+)", out)[0]
            logger.info(f"Changing owner of {pkg} => {userId}")
            adb_shell2(
                ["chown", "-R", f"{userId}:{userId}", f"/data/data/{pkg}"], root=True
            )

            logger.info("Resetting SELinux permisions")
            adb_shell2(["restorecon", "-R", f"/data/data/{pkg}"], root=True)

        # Push obb file
        file = os.path.abspath(file)
        obb_dir = os.path.join(
            os.path.dirname(file), "obb", os.path.splitext(os.path.basename(file))[0]
        )
        if os.path.isdir(obb_dir):
            logger.info(f"Push obb: {obb_dir} => /sdcard/android/obb/")
            subprocess.check_call(
                ["adb", "push", "-p", obb_dir, "/sdcard/android/obb/"]
            )

    return result


def sample_proc_stat():
    adb_shell(
        """
    rm /data/local/tmp/proc_stat.txt
    total_secs=60
    while [ $total_secs -gt 0 ]; do
        cat /proc/stat >> /data/local/tmp/proc_stat.txt
        echo --- >> /data/local/tmp/proc_stat.txt
        echo $total_secs

        let total_secs=$total_secs-1
        sleep 1
    done
    """
    )

    call2(["adb", "pull", "/data/local/tmp/proc_stat.txt"])


def get_pkg_name_apk(file):
    setup_android_env()
    logger.info("Starting the app")
    out = subprocess.check_output(["aapt", "dump", "badging", file]).decode()
    match = re.search("package: name='(.*?)'", out)
    if match is None:
        raise Exception(f"Failed to find app package name from: {out}")
    package_name = match.group(1)
    logger.debug("PackageName=%s" % package_name)
    # activity_name = re.search("launchable-activity: name='(.*?)'", out).group(1)
    # logger.debug('LaunchableActivity: %s' % activity_name)
    return package_name


ApkInfo = namedtuple("ApkInfo", "pkg_name permissions")


def get_apk_info(file):
    out = subprocess.check_output(["aapt", "dump", "badging", file]).decode()
    match = re.search("package: name='(.*?)'", out)
    if match is None:
        raise Exception(f"Failed to find app package name from: {out}")
    pkg_name = match.group(1)
    permissions = re.findall("uses-permission: name='(.*?)'", out)
    return ApkInfo(pkg_name, permissions)


def unlock_device(pin):
    out = subprocess.check_output(
        ["adb", "shell", 'dumpsys power | grep "mWakefulness="'],
        universal_newlines=True,
    )

    if "Dozing" in out:
        adb_shell(["input", "keyevent", "82"])
        time.sleep(1)

        # Swipe up
        adb_shell(["input", "touchscreen", "swipe", "930", "880", "930", "380"])
        time.sleep(1)

        # Type pin
        adb_shell(["input", "text", pin])
        adb_shell(["input", "keyevent", "KEYCODE_ENTER"])


def is_locked():
    patt = re.compile("(?:mShowingLockscreen|isStatusBarKeyguard|showing)=(true|false)")
    m = patt.search(adb_shell("dumpsys window policy", check_output=True))
    if not m:
        raise Exception("Couldn't determine screen lock state")
    return m.group(1) == "true"


def app_is_installed(pkg_name):
    try:
        subprocess.check_output(
            ["adb", "shell", "pm", "path", pkg_name],
            universal_newlines=True,
        )
    except Exception:
        return False
    return True


def logcat_bg(patt):
    """Show filtered logcat in a background thread."""

    if type(patt) != str:
        raise Exception("patt must be a string")

    patt = re.compile(patt)

    def logcat_thread():
        while True:
            print("logcat begin.", end="\r\n")

            for line in read_proc_lines(
                [
                    "adb",
                    "logcat",
                ]
            ):
                if re.search(patt, line):
                    print2(line, end="\r\n", color="gray")

            print("logcat end.", end="\r\n")
            time.sleep(1)

    threading.Thread(
        target=logcat_thread,
        daemon=True,  # daemon threads will terminate as main thread exits
    ).start()


def toggle_prop(name, values=("0", "1")):
    cur_val = subprocess.check_output(
        ["adb", "shell", "getprop", name], universal_newlines=True
    ).strip()

    # Find next value
    try:
        i = values.index(cur_val)
    except ValueError:
        i = 0
    new_val = values[(i + 1) % len(values)]

    logger.debug("setprop %s %s" % (name, new_val))
    subprocess.check_call(["adb", "shell", "setprop", name, new_val])


def run_apk(
    apk, grant_permissions=False, force_reinstall=False, skip_install_if_exist=True
) -> AdbInstallResult:
    result = adb_install2(
        apk,
        grant_permissions=grant_permissions,
        force_reinstall=force_reinstall,
        skip_install_if_exist=skip_install_if_exist,
    )
    restart_app(result.pkg)
    return result


def find_device_by_product_name_adb(product) -> Optional[str]:
    lines = subprocess.check_output(["adb", "devices"], universal_newlines=True).split(
        "\n"
    )[1:]

    for line in lines:
        if not line.strip():
            continue

        serial = line.split("\t")[0]
        prod = subprocess.check_output(
            ["adb", "-s", serial, "shell", "getprop", "ro.build.product"],
            universal_newlines=True,
        ).strip()

        if prod == product:
            return serial

    return None


def find_device_by_product_name_fastboot(product) -> Optional[str]:
    lines = subprocess.check_output(
        ["fastboot", "devices"], universal_newlines=True
    ).splitlines()
    for line in lines:
        if not line.strip():
            continue

        serial = line.split("\t")[0]
        out = subprocess.check_output(
            ["fastboot", "-s", serial, "getvar", "product"],
            universal_newlines=True,
            stderr=subprocess.STDOUT,
        )
        match = re.findall(r"product\s*:\s*(\w+)", out)
        prod = match[0]
        if prod == product:
            return serial

    return None


def find_device_by_product_name(product: str) -> Optional[str]:
    serial = find_device_by_product_name_adb(product)
    if serial:
        return serial
    serial = find_device_by_product_name_fastboot(product)
    if serial:
        return serial
    return None


def setprop(prop):
    """Set all system properities in a single shell command."""

    shell = ""
    for k, v in prop.items():
        if not v:
            v = "''"
        shell += "setprop {} {};".format(k, v)
    adb_shell(shell)


def install_cmdline_tools(version="8.0"):
    if version == "8.0":
        # Download command line tools 8.0
        cmdline_tools_path = os.path.join(
            ANDROID_SDK_INSTALL_DIR, "cmdline-tools", "8.0"
        )
        if not os.path.exists(cmdline_tools_path):
            os.makedirs(os.path.dirname(cmdline_tools_path), exist_ok=True)
            cmdline_tools_zip = download(
                "https://dl.google.com/android/repository/commandlinetools-win-9123335_latest.zip",
                save_to_tmp=True,
            )
            unzip(
                cmdline_tools_zip,
                os.path.join(ANDROID_SDK_INSTALL_DIR, "cmdline-tools"),
            )
            os.rename(
                os.path.join(ANDROID_SDK_INSTALL_DIR, "cmdline-tools", "cmdline-tools"),
                cmdline_tools_path,
            )
        else:
            logging.info(
                "Android Sdk: cmdline-tools version=8.0 already installed, skip."
            )
    else:
        raise Exception(f"install_cmdline_tools(): invalid version: {version}")

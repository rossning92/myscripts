# https://android.googlesource.com/platform/system/extras/+/master/simpleperf/doc/README.md
# https://perf.wiki.kernel.org/index.php/Main_Page

unset MSYS_NO_PATHCONV
set -e

if [[ -z "${ANDROID_NDK_HOME}" ]]; then
    echo 'Cannot find android ndk, please install first.'
    exit 1
fi

cd "${ANDROID_NDK_HOME}/simpleperf"

if [[ "${SIMPLEPERF_CLEAN_BINARY_CACHE}" == "1" ]]; then
    echo "Cleaning binary_cache..."
    rm -rf binary_cache
    echo "Done."
fi

duration="${SIMPLEPERF_DURATION_SEC}"
if [[ -z "$duration" ]]; then
    duration=5
fi

# python run_simpleperf_on_device.py stat -a --duration 1
# python run_simpleperf_on_device.py record -a -e cpu-clock --duration 3

args=''
if [[ -n "${SIMPLEPERF_NATIVE_PROGRAM}" ]]; then
    args+="--native_program ${SIMPLEPERF_NATIVE_PROGRAM}"
elif [[ -n "${_APP}" ]]; then
    args+="--app ${_APP}"
else
    args+="--app $(run_script r/android/get_active_package.sh)"
fi

python app_profiler.py $args -r "-e task-clock:u -f 1000 -g --duration ${duration}"
if [[ -n "${SIMPLEPERF_REPORT_OUTPUT}" ]]; then
    report="${SIMPLEPERF_REPORT_OUTPUT}"
else
    device=$(adb shell getprop ro.product.device | tr -d '\r')
    timestamp=$(date +'%Y%m%d%H%M%S')
    report="$HOME/Desktop/simpleperf-report-$device-$timestamp.html"
fi
python report_html.py -o "$report"

# adb pull /data/local/tmp/perf.data
# inferno.bat -sc --record_file perf.data

import argparse
import importlib.util
import inspect
import mimetypes
import os
import sys
import time

from build123d import BuildPart


def load_module(path):
    spec = importlib.util.spec_from_file_location("_cad_model", os.path.abspath(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def to_cad(value):
    if isinstance(value, BuildPart):
        return value.part
    if inspect.isclass(value) or inspect.ismodule(value) or inspect.isroutine(value):
        return None
    if getattr(value, "wrapped", None) is not None:
        return value
    return None


def discover_parts(module):
    parts = []
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        cad = to_cad(value)
        if cad is not None:
            parts.append((name, cad))
    return parts


def main():
    parser = argparse.ArgumentParser(description="Live browser viewer for build123d scripts (yacv).")
    parser.add_argument("model")
    args = parser.parse_args()

    if not os.path.isfile(args.model):
        sys.exit(f"model script not found: {args.model}")

    # yacv reads its config from these env vars (override them to change host/port).
    os.environ.setdefault("YACV_HOST", "127.0.0.1")
    os.environ.setdefault("YACV_PORT", "32323")
    os.environ.setdefault("YACV_GRACEFUL_SECS_CONNECT", "300")

    # Windows maps .js -> text/plain, which browsers reject for ES modules.
    mimetypes.init()
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("application/wasm", ".wasm")

    from yacv_server import show  # importing starts the server

    def reshow():
        parts = discover_parts(load_module(args.model))
        if not parts:
            print(f"no build123d parts found in {args.model}", file=sys.stderr)
            return None
        names = [n for n, _ in parts]
        objs = [obj for _, obj in parts]
        show(*objs, names=names)
        return names

    if reshow() is None:
        sys.exit(1)

    url = f"http://{os.environ['YACV_HOST']}:{os.environ['YACV_PORT']}"
    print(f"YACV serving at {url}, watching {os.path.basename(args.model)} (Ctrl-C to stop)", flush=True)

    # Block to keep the server alive, hot-reloading whenever the model file changes.
    last = os.path.getmtime(args.model)
    try:
        while True:
            time.sleep(0.3)
            try:
                mtime = os.path.getmtime(args.model)
            except OSError:
                continue  # file briefly missing mid-save
            if mtime == last:
                continue
            last = mtime
            time.sleep(0.1)  # debounce so we read a fully-written file
            try:
                names = reshow()
                if names is not None:
                    print(f"Reloaded: {names}", flush=True)
            except Exception as exc:
                print(f"Reload failed: {exc}", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

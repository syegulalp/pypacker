from re import L
import sys
from pathlib import Path, PureWindowsPath
import shutil
import zipfile
import py_compile
import os
import json
import site
import subprocess


class IniFileMissing(Exception):
    pass


if len(sys.argv) == 1:
    print(
        """
usage: pypacker
    -a <module> -- analyze module
    -f <function> -- function to run in module for entry point
    -v -- for verbose output

    -ta -- treeshake application
    -tl -- treeshake libraries    
    -t -- treeshake all (implies -ta and -tl)
    
    -tli <libname> -- treeshake library <libname>
    -tlx <libname> -- exclude library <libname> from treeshaking (implies -tl)
    (-tli/tlx can be specified more than once)

    -cp <wildcard> -- copy in files matching a given glob wildcard
    -cx <wildcard> -- exclude files matching a given glob wildcard
    (-cx can be specified more than once; does not yet support
    suppressing file copies from libraries, only app tree)

    -o [1/2] -- specify optimization level for .pyc files, default is 0
    (some modules will object if you remove docstrings)

    -ax -- retain analysis scripts (for debugging)
"""
    )

verbose = "-v" in sys.argv

vprint = lambda *a: None
if verbose:
    vprint = lambda *a: print(*a)

treeshake_app = "-ta" in sys.argv or "-t" in sys.argv
treeshake_libs = "-tl" in sys.argv or "-t" in sys.argv
retain_analysis = "-ax" in sys.argv

treeshake_exclude = set()
treeshake_include = set()
file_exclusions = set()

pyc_opt_level = 0

entry_function = None

BUILD_ARTIFACT_DIR = "dist"
TARGET_BIN_PATH = ".bin"

PY_VERSION = f"python{sys.version_info[0]}{sys.version_info[1]}"
PATH_TO_ORIGINAL_EXECUTABLE = Path(sys.base_prefix)
PATH_TO_ORIGINAL_LIBS = PATH_TO_ORIGINAL_EXECUTABLE / "Lib"
PATH_TO_VENV_LIBS = Path(sys.prefix, "Lib", "site-packages")


copy_files_cmdline = []

for idx, a in enumerate(sys.argv):
    id = idx + 1
    if a == "-tlx":
        treeshake_exclude.add(sys.argv[id])
        treeshake_include = None
        treeshake_libs = True

    elif a == "-tli":
        treeshake_include.add(sys.argv[id])
        treeshake_exclude = None
        treeshake_libs = True

    elif a == "-o":
        try:
            level = int(sys.argv[id])
        except ValueError:
            print("Invalid optimization level supplied; defaulting to 0")
        else:
            level = max(0, min(level, 2))
        pyc_opt_level = level

    elif a == "-f":
        entry_function = sys.argv[id]

    elif a == "-od":
        BUILD_ARTIFACT_DIR = sys.argv[id]

    elif a == "-cp":
        copy_files_cmdline.append([sys.argv[id], "."])

    elif a == "-cx":
        file_exclusions.add(sys.argv[id])


class Analysis:
    def __init__(self, app_name):
        self.app_name = app_name
        self.analyze()

    def generate_analysis_script(self):
        self.app_exec = [f"import {self.app_import_name}"]
        print("E:", entry_function)
        if entry_function:
            self.app_exec.append(f"{self.app_import_name}.{entry_function}()")

        app_exec_temp = "\n    ".join(self.app_exec)

        temp = f"""
try:
    {app_exec_temp}
except BaseException:
    pass

import sys

run_modules = set(sys.modules.keys()) #-original_modules

import json
import types

final_modules = []

for m in run_modules:
    if m == "{self.app_name}":
        continue
    if isinstance(sys.modules[m], type):
        continue
    if m in sys.builtin_module_names:
        continue
    if getattr(sys.modules[m], "__file__", None) is None:
        continue
    final_modules.append([m, sys.modules[m].__file__])
    
with open("{self.app_name}.tmp","w") as f:
    json.dump(sorted(final_modules), f)
        """

        with open(f"{self.app_name}_analysis.py", "w") as f:
            f.write(temp)

    def delete_analysis_script(self):
        Path(f"{self.app_name}_analysis.py").unlink()

    def delete_tempdata(self):
        Path(f"{self.app_name}.tmp").unlink()

    def analyze(self):
        self.standalone_file = None

        as_module = Path(self.app_name)

        print("Looking for", as_module.absolute())

        self.app_import_name = self.app_name

        if as_module.is_dir():
            self.standalone_file = False
        elif as_module.is_file():
            self.standalone_file = True
            self.app_import_name = as_module.stem

        if self.standalone_file is None:
            raise Exception("Couldn't determine what to import")

        print(
            f"Importing {self.app_name} as {'file' if self.standalone_file else 'module'}"
        )

        print(f"Starting run for {self.app_name}")

        self.generate_analysis_script()

        subprocess.run(["py", f"{self.app_name}_analysis.py"])

        site_pkgs = site.getsitepackages()
        lib_dir = Path(subprocess.__file__).parent

        print(f"Starting analysis for {self.app_name}")

        root_app_dir = Path(f"{self.app_name}.tmp").parent.absolute()

        with open(f"{self.app_name}.tmp") as f:
            loaded_modules = json.load(f)

        std_lib = []
        app_lib = []
        binaries = []
        app_modules = []

        # BUG: lib folder for venv has case sensitivity issues
        # why?

        for m, mn in loaded_modules:
            if mn.endswith(".pyd") or mn.endswith(".dll"):
                binaries.append(mn)
            elif mn.startswith(f"{lib_dir}\\"):
                t = mn.replace(f"{lib_dir}\\", "")
                std_lib.append(t)
            else:
                for p in site_pkgs[1:]:
                    if mn.startswith(p + "\\"):
                        t = mn.replace(p + "\\", "")
                        app_lib.append(t)
                    elif mn.startswith(f"{PATH_TO_ORIGINAL_LIBS}\\"):
                        t = mn.replace(f"{PATH_TO_ORIGINAL_LIBS}\\", "")
                        app_modules.append(t)
                    else:
                        if str(root_app_dir) in mn:
                            t = mn.replace(f"{root_app_dir}\\", "")
                            app_modules.append(t)

        if not retain_analysis:
            self.delete_tempdata()
            self.delete_analysis_script()

        output = {
            "app": self.app_name,
            "app_exec": self.app_exec,
            "std_lib": sorted(set(std_lib)),
            "app_lib": sorted(set(app_lib)),
            "app_modules": sorted(set(app_modules)),
            "binaries": sorted(set(binaries)),
            "copy": copy_files_cmdline,
            "lib_exclude": [],
            "app_exclude": [],
            "file_exclude": sorted(set(file_exclusions)),
            "entry_function": entry_function,
        }

        # TODO:
        # migrate copyfile information from old json

        filename = f"tracefile.json"

        with open(filename, "w") as f:
            json.dump(output, f, indent=4)

        print("Analysis done")

        return filename


class AppInfo:
    def __init__(self, config_file=None):

        if config_file is None:
            self.setup_no_config()
        else:
            self.setup(config_file)

    def setup_no_config(self):
        raise NotImplementedError

    def setup(self, config_file: dict):

        self.use_tk = False
        self.use_sqlite3 = False

        self.standalone = False

        self.appdir = config_file["app"]
        if self.appdir.endswith(".py"):
            self.app_title = self.appdir.rsplit(".py", 1)[0]
            self.standalone = True
        else:
            self.app_title = self.appdir

        self.abs_root_path = Path(".").absolute()

        self.stdlib = config_file["std_lib"]
        self.app_lib = config_file["app_lib"]
        self.app_exec = config_file["app_exec"]
        self.app_modules = config_file["app_modules"]
        self.lib_dirs = config_file.get("lib_dirs", [])
        self.binaries = config_file.get("binaries", [])

        self.copy_files = config_file.get("copy", [])
        self.lib_exclude = set(config_file.get("lib_exclude", []))
        self.app_exclude = set(config_file.get("app_exclude", []))
        self.file_exclude_glob = set(config_file.get("file_exclude", []))

        self.file_exclude = set()
        for n in self.file_exclude_glob:
            for nn in Path().glob(n):
                self.file_exclude.add(str(Path(BUILD_ARTIFACT_DIR / nn)))

        print("EXCLUSIONS", self.file_exclude)

        app_exec = "\n".join(self.app_exec)
        if self.standalone:
            self.boot = f"{app_exec}\nimport os\nos._exit(0)"
        else:
            self.boot = app_exec

    def create_dirs(self):

        self.build_path = Path(BUILD_ARTIFACT_DIR)

        print(f"Creating build directory {self.build_path}")

        if self.build_path.exists():
            shutil.rmtree(self.build_path)
        self.build_path.mkdir(parents=True)

        self.lib_target_path = Path(self.build_path, TARGET_BIN_PATH)
        if self.lib_target_path.exists():
            shutil.rmtree(self.lib_target_path)
        self.lib_target_path.mkdir(parents=True)

    def copy_base_files(self):

        print("Copying base files")

        base_files = ["python.exe", "pythonw.exe", f"{PY_VERSION}.dll"]

        for file in base_files:
            shutil.copy(Path(PATH_TO_ORIGINAL_EXECUTABLE, file), self.build_path)

        target_path_for_base_files = self.lib_target_path.parts[-1]

        output = [
            ".",
            f"{target_path_for_base_files}",
            f"{target_path_for_base_files}\\{PY_VERSION}.zip",
            f"{target_path_for_base_files}\\pkg.zip",
            f"{target_path_for_base_files}\\app.zip",
            "",
            "import site",
        ]

        with open(self.build_path / f"{PY_VERSION}._pth", "w") as f:
            for line in output:
                f.write(line)
                f.write("\n")

    def create_stdlib_archive(self):

        print("Creating stdlib archive")

        self.stdlib_zip = zipfile.ZipFile(
            self.lib_target_path / f"{PY_VERSION}.zip",
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        )

        self.stdlib.extend(self.binaries)
        self.stdlib.extend(
            [
                str(Path(PATH_TO_ORIGINAL_EXECUTABLE, "DLLS", "libffi-7.dll")),
                str(Path(PATH_TO_ORIGINAL_EXECUTABLE, "DLLS", "libffi-8.dll")),
                "encodings/cp437.py",
            ]
        )
        all_libs = set(self.stdlib)

        vpath = PureWindowsPath(PATH_TO_VENV_LIBS)

        for lib in all_libs:

            lp = PureWindowsPath(lib)
            llp = None
            try:
                llp = lp.relative_to(vpath)
            except ValueError:
                pass

            if not (PATH_TO_ORIGINAL_LIBS / lib).exists():
                print(f"\tWarning: {lib} not found")
                continue
            if lib in self.lib_exclude:
                vprint("\tExcluding", lib)
                continue

            if lib.endswith(".dll"):
                shutil.copy(PATH_TO_ORIGINAL_LIBS / lib, self.lib_target_path)
            elif lib.endswith(".pyd"):
                if lib.endswith("_tkinter.pyd"):
                    self.use_tk = True
                elif lib.endswith("_sqlite3.pyd"):
                    self.use_sqlite3 = True

                # make sure this lib isn't in the installed packages
                # if so, copy it to the right location

                if llp:
                    target_directory = self.build_path / str(llp.parent)
                    if not target_directory.exists():
                        target_directory.mkdir(parents=True)
                    shutil.copy(lib, target_directory)

                elif lib.startswith(str(self.abs_root_path)):
                    target_path = Path(lib.replace(str(self.abs_root_path), ""))
                    target_directory = self.build_path / str(target_path.parent.name)
                    if not target_directory.exists():
                        target_directory.mkdir(parents=True)
                    shutil.copy(lib, target_directory)

                else:
                    shutil.copy(lib, self.lib_target_path)
            else:
                compiled = py_compile.compile(
                    PATH_TO_ORIGINAL_LIBS / lib, optimize=pyc_opt_level
                )
                self.stdlib_zip.write(
                    compiled,
                    lib + "c",
                )

    def add_libraries(self):

        print("Adding libraries")

        self.pkgzip = zipfile.ZipFile(
            self.lib_target_path / "pkg.zip", mode="w", compression=zipfile.ZIP_DEFLATED
        )

        all_libs = set()

        if treeshake_libs:

            print("Treeshaking")

            for file in self.app_lib:
                all_libs.add(Path(PATH_TO_VENV_LIBS, file.split("\\", 1)[0]))
                outfile = Path(PATH_TO_VENV_LIBS, file)
                compiled = py_compile.compile(outfile, optimize=pyc_opt_level)
                vprint(outfile)
                self.pkgzip.write(
                    compiled,
                    Path(file + "c"),
                )

            self.pkgzip.close()

            print("Creating libpath copies")

            for libpath in all_libs:
                ts = True

                if treeshake_exclude and Path(libpath).stem in treeshake_exclude:
                    ts = False
                elif treeshake_include:
                    ts = False
                    if Path(libpath).stem in treeshake_include:
                        ts = True

                for path, _, files in os.walk(libpath):
                    if "__pycache__" in path:
                        continue
                    for f in files:
                        if not ts:
                            fpath = path.replace(str(libpath), "")
                            outpath = Path(libpath).stem
                            t = (self.build_path, outpath, str(fpath).lstrip("\\"))
                            target_directory = Path(*t)
                            if not target_directory.exists():
                                target_directory.mkdir(parents=True)
                            vprint(f, ">>", target_directory)
                            shutil.copy(Path(path, f), target_directory)
                            continue

                        if not f.endswith((".py", ".pyc")):
                            path_parent = Path(libpath).parent
                            # XXX
                            ppath = path.replace(str(path_parent) + "\\", "")
                            target_directory = Path(self.build_path, ppath)
                            if not target_directory.exists():
                                target_directory.mkdir(parents=True)
                            vprint(f, ">>", target_directory)
                            shutil.copy(Path(path, f), target_directory)

        else:

            print("All libs")

            for file in self.app_lib:
                all_libs.add(Path(PATH_TO_VENV_LIBS, file.split("\\", 1)[0]))

            for libpath in all_libs:
                for path, _, files in os.walk(libpath):
                    if "__pycache__" in path:
                        continue
                    outpath = Path(libpath).stem
                    fpath = path.replace(str(libpath), "")
                    for f in files:
                        outpath = Path(libpath).stem
                        t = (self.build_path, outpath, str(fpath).lstrip("\\"))
                        target_directory = Path(*t)
                        if not target_directory.exists():
                            target_directory.mkdir(parents=True)
                        if f.endswith(".py"):
                            outfile = Path(target_directory, str(f) + "c")
                            compiled = py_compile.compile(
                                Path(path, f), optimize=pyc_opt_level
                            )
                            vprint(outfile)
                            shutil.copy(compiled, outfile)
                        else:
                            vprint(f, ">>", target_directory)
                            shutil.copy(Path(path, f), target_directory)

            self.pkgzip.close()

    def add_app_libraries(self):

        print("Adding app libraries")

        self.app_zip = zipfile.ZipFile(
            self.lib_target_path / "app.zip", "w", compression=zipfile.ZIP_DEFLATED
        )

        all_paths = set()

        if treeshake_app:

            print("Treeshaking app")

            for file in self.app_modules:
                if any(file.startswith(x) for x in self.app_exclude):
                    vprint("Excluding", file)
                path_to_file = Path(file)
                if str(path_to_file.parent) != ".":
                    all_paths.add(path_to_file.parent)
                if not path_to_file.exists():
                    continue
                compiled = py_compile.compile(
                    str(path_to_file.absolute()), optimize=pyc_opt_level
                )
                self.app_zip.write(compiled, f"{file}c")

            ap2 = set()
            for p in all_paths:
                for path, _, files in os.walk(p):
                    if "__pycache__" in path:
                        continue
                    ap2.add(path)

            for dir in ap2:
                for file in Path(dir).glob("*"):
                    if file.is_file():
                        if not file.suffix == ".py":
                            target = Path(self.build_path, dir)
                            if not target.exists():
                                target.mkdir(parents=True)
                            shutil.copy(file, target)

            self.app_zip.close()

        else:

            print("All app")

            toplevel = set()

            for file in self.app_modules:
                p = Path(file)
                if p.exists() and str(p.parent) == ".":
                    toplevel.add(file)
                    continue
                if any(file.startswith(x) for x in self.app_exclude):
                    vprint("Excluding", file)
                path_to_file = Path(file)
                if str(path_to_file.parent) != ".":
                    all_paths.add(path_to_file.parent)
                if not path_to_file.exists():
                    continue

            ap2 = set()

            for p in all_paths:
                for path, _, files in os.walk(p):
                    if "__pycache__" in path:
                        continue
                    p2 = Path(path).parts[0]
                    ap2.add(p2)

            pyc_in_dir = False

            for dir in ap2:
                for path, _, files in os.walk(dir):
                    if any(f.endswith("pyd") for f in files):
                        pyc_in_dir = True

            for f in toplevel:
                compiled = py_compile.compile(
                    str(Path(f).absolute()), optimize=pyc_opt_level
                )
                self.app_zip.write(compiled, f"{f}c")

            # future optimization:
            # create set ahead of time, perform set intersection?
            
            for dir in ap2:
                for path, _, files in os.walk(dir):
                    if "__pycache__" in path:
                        continue
                    for file in files:
                        py_file = False
                        if file.endswith(".py"):
                            py_file = True
                            out_file = py_compile.compile(
                                str(Path(path, file).absolute()),
                                optimize=pyc_opt_level,
                            )
                            out_file_name = f"{file}c"
                        else:
                            out_file = Path(path, file)
                            out_file_name = file
                        if pyc_in_dir or not py_file:
                            target = Path(self.build_path, path)
                            if (
                                str(target / out_file_name) in self.file_exclude
                                or str(target) in self.file_exclude
                            ):
                                continue
                            if not target.exists():
                                target.mkdir(parents=True)
                            shutil.copy(out_file, target / out_file_name)
                        else:
                            self.app_zip.write(out_file, f"{path}\\{out_file_name}")

            self.app_zip.close()

    def add_site_customization(self):

        print("Adding site customization")

        self.stdlib_zip.writestr("sitecustomize.py", self.boot)
        self.stdlib_zip.close()

        if self.copy_files:
            print("Copying any additional files")
            # TODO: path replacement
            for src_path, dest in self.copy_files:
                srcs = Path().glob(src_path)
                for src in srcs:
                    if str(self.build_path / src) in self.file_exclude:
                        continue
                    if src.is_dir():
                        shutil.copytree(src, self.build_path / src)
                    else:
                        shutil.copy(src, self.build_path / src)

    def rename_execs(self):

        for exe, extension in (("pythonw.exe", ".exe"), ("python.exe", "_console.exe")):
            Path(self.build_path, exe).rename(
                self.build_path / f"{self.app_title}{extension}"
            )

    def make_dist_zipfile(self):

        print("Creating distribution zip file")

        self.dist_zip = zipfile.ZipFile(
            f"{self.app_title}.zip", "w", compression=zipfile.ZIP_DEFLATED
        )

        for path, _, files in os.walk(self.build_path):
            p = Path(path).parts[1:]
            for f in files:
                self.dist_zip.write(Path(path, f), Path(*p, f))

    def add_special_libs(self):

        if self.use_sqlite3:
            sqlite_src = Path(PATH_TO_ORIGINAL_EXECUTABLE, "DLLs", "sqlite3.dll")
            shutil.copy(sqlite_src, self.lib_target_path)

        if self.use_tk:
            tk_src = Path(PATH_TO_ORIGINAL_EXECUTABLE, "tcl")
            tk_dest = Path(self.build_path, "Lib")
            shutil.copytree(tk_src, tk_dest)
            dll_src = Path(PATH_TO_ORIGINAL_EXECUTABLE, "DLLs")
            for f in dll_src.glob("t*.dll"):
                shutil.copy(f, self.lib_target_path)
            unneeded_lib = tk_dest.glob("*.lib")
            for f in unneeded_lib:
                f.unlink()


def main():

    analyze = None
    try:
        analyze = sys.argv.index("-a")
    except ValueError:
        pass

    if analyze:
        analysis = Analysis(sys.argv[analyze + 1])

    config_file = "tracefile.json"

    try:
        c_index = sys.argv.index("-c")
        config_file = sys.argv[c_index + 1]
    except ValueError:
        pass

    print(f"Reading config file {config_file}")

    config_file_obj = Path(config_file)

    if not config_file_obj.exists():
        raise IniFileMissing(
            f"{config_file} not found in application directory, run with -a <module> to start analysis"
        )

    with open(config_file_obj) as f:
        config = json.load(f)

    appinfo = AppInfo(config)

    print(f"App title: {appinfo.app_title}")
    print(f"App dir: {appinfo.appdir}")
    print(f"Entry script: {appinfo.boot}")
    print(f"Lib dirs: {appinfo.lib_dirs}")
    vprint(f"Stdlib items:")
    for item in appinfo.stdlib:
        vprint("\t", item)
    vprint(f"Exclude items:")
    for item in appinfo.lib_exclude:
        vprint("\t", item)

    print("Starting build process ...")

    appinfo.create_dirs()
    appinfo.copy_base_files()
    appinfo.create_stdlib_archive()
    appinfo.add_libraries()
    appinfo.add_app_libraries()
    appinfo.add_site_customization()
    appinfo.add_special_libs()
    appinfo.rename_execs()
    appinfo.make_dist_zipfile()

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except IniFileMissing as e:
        print(e)

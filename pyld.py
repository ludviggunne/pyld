
from __future__ import annotations
import os, subprocess, enum, time

# Global Data
c_compiler: str = "gcc"
_targets: dict[str, Target] = {}
_external_dependencies: dict[str, ExtDep] = {}

_object_ext  = ".o"
_dynamic_ext = ".so"
_static_ext = ".a"

_do_print_commands = True

_color_codes: dict[str, int] = {
    "reset":   0,
    "grey":   90,
    "red":    91,
    "green":  92,
    "yellow": 93,
    "white":  97
}

def _color_str(c: str) -> str:
    return f"\033[{_color_codes[c]}m"



# Utility Functions
def _strip_extension(path):
    return path.split(".")[0]

def _get_extension(path: str) -> str:
    return path.split(".")[-1]

def _change_extension(path: str, ext: str) -> str:
    return _strip_extension(path) + ext

def _target_type_to_extension(type: TargetType) -> str:
    match type:
        case TargetType.EXECUTABLE:
            return ""
        case TargetType.STATIC_LIB:
            return _static_ext
        case TargetType.DYNAMIC_LIB:
            return _dynamic_ext
        case _:
            assert False, "Unknown Target Type"

def _get_opt_mod_time(path: str) -> float:
    if os.path.exists(path):
        return os.path.getmtime(path)
    return -1.0

def _cmp_timestamp(t1: float, t2: float) -> bool:
    return t1 < 0.0 or t1 > t2

def _print_elapsed_time(t: float):
    msg: str = "Elapsed time: "
    if t < 1.0:
        msg += "< 1s"
    else:
        s = int(t) % 60
        m = s / 60
        msg += f"{m}m {s}s" if m > 0 else f"{s}s"
    
    print(msg)

def _output_str(msg: str, indent: int = 0, color: str = "reset") -> str:
    return "\t" * indent + _color_str(color) + msg + _color_str("reset")

def _print_commands(indent: int, args: str):
    if _do_print_commands:
        print(_output_str(" ".join(args), indent, "grey"))

def _error(msg: str, indent: int = 0):
    assert False, _output_str(str, indent, "red")

class TargetType(enum.Enum):
    EXECUTABLE       = 0
    STATIC_LIB       = 1
    DYNAMIC_LIB      = 2

class ExtDepType(enum.Enum):
    STATIC_LIB  = 0
    DYNAMIC_LIB = 1
    SYSTEM_LIB  = 2

class ExtDep:
    def __init__(self, name: str, type: ExtDepType, path: str = ""):
        self.name: str               = name
        self.type: ExtDepType        = type
        self.path: str               = path
        _external_dependencies[name] = self

class Target:
    def __init__(self, name: str, type: TargetType):
        self.name: str          = name
        self.type: TargetType   = type
        self.output_dir: str    = ""
        self.deps: list[str]    = []
        self.sources: list[str] = []
        self.flags: list[str]   = []
        self.incdirs: list[str] = []
        _targets[name]          = self

    def add_dependencies(self, deps: list[str]):
        self.deps += deps

    def add_source_files(self, sources: list[str]):
        self.sources += sources

    def add_include_directories(self, dirs: list[str]):
        self.incdirs += dirs

    def get_out_path(self) -> str:
        if len(self.output_dir) > 0:
            return self.output_dir + "/" + self.name + _target_type_to_extension(self.type)
        else:
            return self.name + _target_type_to_extension(self.type)

    def run(self, args: list[str] = []):
        subprocess.run([f"./{self.get_out_path()}"] + args)

    def clean(self):
        print(f"Cleaning target {self.name}")
        args: list[str] = []
        args.append("rm")
        args.append("-f")
        args.append(self.get_out_path())
        args += [_change_extension(s, _object_ext) for s in self.sources]
        _print_commands(0, args)
        subprocess.run(args)
        for dep_name in self.deps:
            if  dep_name in _targets:
                dep: Target = _targets[dep_name]
                dep.clean()

    def build(self, force: bool = False):
        t0: float = time.perf_counter()
        self._opt_build(force, _get_opt_mod_time(self.get_out_path()), 0)
        t1: float = time.perf_counter()
        _print_elapsed_time(t1 - t0)

    # Build target if not up to date
    # Returns True if rebuilt
    def _opt_build(self, force: bool, timestamp: float, indent: int) -> bool:
        rebuild = False
        target_timestamp = _get_opt_mod_time(self.get_out_path())

        if target_timestamp < 0.0:
            rebuild = True

        # Update Dependencies
        for dep_name in self.deps:
            if dep_name in _targets:
                dep = _targets[dep_name]
                print(_output_str(f"Checking dependency {dep_name}...", indent))
                dep_rebuild = dep._opt_build(force, target_timestamp, indent + 1)
                rebuild |= dep_rebuild

            elif dep_name in _external_dependencies:
                pass

            else:
                _error(f"Unknown Dependency: {dep_name}", indent)

        # Update Object Files
        for source in self.sources:
            obj = _change_extension(source, _object_ext)
            if not os.path.exists(source):
                _error(f"Could not find source file {source}")

            if _cmp_timestamp(_get_opt_mod_time(source), target_timestamp) or not os.path.exists(obj) or force:
                rebuild = True
                print(_output_str(f"Compiling source file {source}", indent))
                args: list[str] = []
                args.append(c_compiler)
                if self.type == TargetType.DYNAMIC_LIB:
                    args.append("-fPIC")
                args.append("-c")
                args.append(source)
                args += self.flags
                args += [f"-I{I}" for I in self.incdirs]
                args.append("-o")
                args.append(obj)
                _print_commands(indent, args)
                subprocess.run(args)
            else:
                print(_output_str(f"Source file {source} is up to date", indent))
        
        if rebuild or force:
            print(_output_str(f"Building target {self.name}...", indent))
            args: list[str] = []
            args.append(c_compiler)
            args += self.flags

            objs: list[str] = [_change_extension(s, ".o") for s in self.sources]
            links: list[str] = []

            for dep_name in self.deps:
                if dep_name in _targets:
                    dep: Target = _targets[dep_name]
                    match dep.type:
                        case TargetType.EXECUTABLE:
                            _error("Can't have executable as dependency", indent)

                        case TargetType.STATIC_LIB:
                            objs.append(dep.get_out_path())

                        case TargetType.DYNAMIC_LIB:
                            _error("Using TargetType.DYNAMIC_LIB as dependency is not supported yet", indent)

                        case _:
                            _error("Unknown target type {dep.type}", indent)
                        
                elif dep_name in _external_dependencies:
                    dep: ExtDep = _external_dependencies[dep_name]
                    match dep.type:
                        case ExtDepType.STATIC_LIB:
                            objs.append(f"{dep.path}/{dep.name}{_static_ext}")
                        
                        case ExtDepType.SYSTEM_LIB:
                            links.append(f"-l{dep.name}")

                        case _:
                            _error(f"Unknown external dependency type {dep.type}", indent)
                else:
                    _error(f"Unknown dependency: {dep_name}")

            args += objs

            match self.type:
                case TargetType.EXECUTABLE:
                    args.append("-o")
                    args.append(self.get_out_path())
                    args += links
                
                case TargetType.STATIC_LIB:
                    args = []
                    args.append("ar")
                    args.append("rcs")
                    args.append(self.get_out_path())
                    args += objs

                case TargetType.DYNAMIC_LIB:
                    args.append("-shared")
                    args.append("-o")
                    args.append("-fPIC")
                    args.append(self.get_out_path())

            _print_commands(indent, args)
            subprocess.run(args)
            print(_output_str("Completed!", indent, "green"))
        else:
            print(_output_str(f"Target {self.name} is up to date", indent))
        
        return rebuild
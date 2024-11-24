import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Thread

# Directories
BIN_DIR = "bin"
OBJ_DIR = "obj"
ANDROID_BIN_DIR = "android_bin"
ANDROID_OBJ_DIR = "android_obj"

# Architectures
ARCHITECTURES = {
    "armv7": {
        "target": "armv7a-linux-androideabi",
        "api": "21",
        "subdir": "armv7"
    },
    "aarch64": {
        "target": "aarch64-linux-android",
        "api": "21",
        "subdir": "aarch64"
    }
}

# Source files for pycxx library
PYCXX_FILES = [
    "bytecode.cpp", "data.cpp", "pyc_code.cpp", "pyc_module.cpp",
    "pyc_numeric.cpp", "pyc_object.cpp", "pyc_sequence.cpp", "pyc_string.cpp"
]

# Python version-specific files
PYTHON_VERSION_FILES = [
    f"bytes/python_{major}_{minor}.cpp"
    for major in range(1, 4)
    for minor in range(0, 14)
]

# Compiler and flags for desktop
DESKTOP_CXX = "g++"
DESKTOP_CXX_FLAGS = "-std=c++11 -Wall -Wextra -Wno-error=shadow -Werror"
DESKTOP_INCLUDE_FLAGS = "-I."

# Android NDK configuration
ANDROID_NDK_PATH = r"C:\Android\ndk\27.2.12479018"
ANDROID_TOOLCHAIN = os.path.join(ANDROID_NDK_PATH, "toolchains", "llvm", "prebuilt", "windows-x86_64")

# Thread-safe logging
log_queue = Queue()


def log(message, level="INFO"):
    """Thread-safe logging."""
    levels = {
        "INFO": "\033[94m[INFO]\033[0m",
        "WARNING": "\033[93m[WARNING]\033[0m",
        "ERROR": "\033[91m[ERROR]\033[0m",
    }
    log_queue.put(f"{levels.get(level, '')} {message}")


def log_worker():
    """Log worker to process queue."""
    while True:
        message = log_queue.get()
        if message == "STOP":
            break
        print(message)
    log_queue.task_done()


def compile_source(compiler, cxx_flags, include_flags, source_file, output_file):
    """Compile a single source file into an object file."""
    if not os.path.exists(source_file):
        log(f"Skipping missing file: {source_file}", level="WARNING")
        return
    command = f"{compiler} {cxx_flags} {include_flags} -c {source_file} -o {output_file}"
    log(f"Compiling {source_file}...")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        log(f"Failed to compile {source_file}", level="ERROR")
        raise RuntimeError(f"Failed to compile {source_file}")


def create_archive(output_archive, object_files):
    """Create a static library archive from object files."""
    command = f"ar rcs {output_archive} {' '.join(object_files)}"
    log("Creating archive...")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        log("Failed to create archive", level="ERROR")
        raise RuntimeError("Failed to create archive")


def compile_executable(compiler, cxx_flags, include_flags, output_executable, source_files, libraries):
    """Compile and link an executable."""
    command = f"{compiler} {cxx_flags} {include_flags} {' '.join(source_files)} {libraries} -o {output_executable}"
    log(f"Linking {output_executable}...")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        log(f"Failed to link {output_executable}", level="ERROR")
        raise RuntimeError(f"Failed to link {output_executable}")


def build_android_architecture(arch, target, api, output_subdir):
    """Build for a specific Android architecture."""
    arch_bin_dir = os.path.join(ANDROID_BIN_DIR, output_subdir)
    arch_obj_dir = os.path.join(ANDROID_OBJ_DIR, output_subdir)

    os.makedirs(arch_bin_dir, exist_ok=True)
    os.makedirs(arch_obj_dir, exist_ok=True)

    compiler = os.path.join(ANDROID_TOOLCHAIN, "bin", f"{target}{api}-clang++")
    include_flags = f"-I. -I{os.path.join(ANDROID_NDK_PATH, 'sources', 'android')}"
    cxx_flags = "-std=c++11 -Wall -Wextra"

    object_files = []
    with ThreadPoolExecutor() as executor:
        futures = []

        for src in PYCXX_FILES + PYTHON_VERSION_FILES:
            obj = os.path.join(arch_obj_dir, os.path.splitext(os.path.basename(src))[0] + ".o")
            futures.append(executor.submit(compile_source, compiler, cxx_flags, include_flags, src, obj))
            object_files.append(obj)

        for future in futures:
            future.result()

    library = os.path.join(arch_obj_dir, "libpycxx.a")
    create_archive(library, [obj for obj in object_files if os.path.exists(obj)])

    compile_executable(compiler, cxx_flags, include_flags, os.path.join(arch_bin_dir, "pycdas"), ["pycdas.cpp"], library)
    compile_executable(compiler, cxx_flags, include_flags, os.path.join(arch_bin_dir, "pycdc"), ["pycdc.cpp", "ASTree.cpp", "ASTNode.cpp"], library)


if __name__ == "__main__":
    os.system('cls')
    print("\033[92m" + "=" * 50)
    print("            PYTHON ANDROID BUILDER")
    print("         Build for Desktop & Android")
    print("=" * 50 + "\033[0m")

    log_thread = Thread(target=log_worker, daemon=True)
    log_thread.start()

    # Desktop build
    log("Starting desktop build...")
    os.makedirs(BIN_DIR, exist_ok=True)
    os.makedirs(OBJ_DIR, exist_ok=True)

    desktop_object_files = []
    with ThreadPoolExecutor() as executor:
        futures = []

        for src in PYCXX_FILES + PYTHON_VERSION_FILES:
            obj = os.path.join(OBJ_DIR, os.path.splitext(os.path.basename(src))[0] + ".o")
            futures.append(executor.submit(compile_source, DESKTOP_CXX, DESKTOP_CXX_FLAGS, DESKTOP_INCLUDE_FLAGS, src, obj))
            desktop_object_files.append(obj)

        for future in futures:
            future.result()

    desktop_library = os.path.join(OBJ_DIR, "libpycxx.a")
    create_archive(desktop_library, [obj for obj in desktop_object_files if os.path.exists(obj)])

    compile_executable(DESKTOP_CXX, DESKTOP_CXX_FLAGS, DESKTOP_INCLUDE_FLAGS, os.path.join(BIN_DIR, "pycdas.exe"), ["pycdas.cpp"], desktop_library)
    compile_executable(DESKTOP_CXX, DESKTOP_CXX_FLAGS, DESKTOP_INCLUDE_FLAGS, os.path.join(BIN_DIR, "pycdc.exe"), ["pycdc.cpp", "ASTree.cpp", "ASTNode.cpp"], desktop_library)
    log("Desktop build complete.\n")

    # Android build
    for arch, config in ARCHITECTURES.items():
        log(f"Building for Android {arch}...\n")
        build_android_architecture(config["target"], config["target"], config["api"], config["subdir"])

    log_queue.put("STOP")
    log_thread.join()

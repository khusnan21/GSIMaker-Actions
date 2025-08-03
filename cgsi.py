#!/bin/env python3
r"""
  __  __ ___ ____ ___ ____  _____
 |  \/  |_ _/ ___|_ _|  _ \| ____|
 | |\/| || |\___ \| || | | |  _|
 | |  | || | ___) | || |_| | |___
 |_|  |_|___|____/___|____/|_____|
       Love & You
"""
import os
import platform
import subprocess
import sys
import zipfile

from src import imgextractor
from src.downloader import download
from src.gettype import gettype
from src.payload_extract import extract_partitions_from_payload
from src.posix import readlink, symlink
from src.sdat2img import Sdat2img
from shutil import rmtree, move, copy, copytree, which
from src.fspatch import main as fspatch
from src.contextpatch import main as contextpatch
if os.name == 'nt':
    import ctypes

    ctypes.windll.kernel32.SetConsoleTitleW("OEM Generic System Image Maker")
else:
    sys.stdout.write("\x1b]2;OEM Generic System Image Maker\x07")
    sys.stdout.flush()
__author__ = ["ColdWindScholar", "Child I"]
__version__ = "1.0.0"
if os.name == 'nt':
    prog_path = os.getcwd()
else:
    prog_path = os.path.normpath(os.path.abspath(os.path.dirname(sys.argv[0])))
    if platform.system() == 'Darwin':
        path_frags = prog_path.split(os.path.sep)
        if path_frags[-3:] == ['tool.app', 'Contents', 'MacOS']:
            path_frags = path_frags[:-3]
            prog_path = os.path.sep.join(path_frags)

BASE_DIR = prog_path
IMG_DIR = os.path.join(BASE_DIR, 'IMG')
EXTRACT_DIR = os.path.join(BASE_DIR, 'EXTRACT')
tool_bin = os.path.join(prog_path, 'bin', platform.system(), platform.machine())
BIN_DIR = os.path.join(prog_path, 'bin')
img_files_list = ['my_bigball', 'my_carrier', 'my_engineering', 'my_heytap', 'my_manifest', 'my_product',
                  'my_region', 'my_stock', 'product', 'system', 'system_ext', 'mi_ext']


def call(exe, extra_path=True, out_=None) -> int:
    if not out_:
        out_ = True

    def output(inp: subprocess.CalledProcessError | subprocess.Popen[bytes]):
        for i in iter(inp.stdout.readline, b""):
            try:
                out_put = i.decode("utf-8").strip()
            except (Exception, BaseException):
                out_put = i.decode("gbk").strip()
            if out_:
                print(out_put)

    if isinstance(exe, list):
        cmd = exe
        if extra_path:
            cmd[0] = f"{tool_bin}/{exe[0]}"
        cmd = [i for i in cmd if i]
    else:
        cmd = f'{tool_bin}/{exe}' if extra_path else exe
        if os.name == 'posix':
            cmd = cmd.split()
    conf = subprocess.CREATE_NO_WINDOW if os.name != 'posix' else 0
    try:
        ret = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, creationflags=conf)
        output(ret)
    except subprocess.CalledProcessError as e:
        output(e)
        return 2
    except FileNotFoundError:
        return 2
    ret.wait()
    return ret.returncode


def check_tools():
    print("Checking necessary tools...")
    if not os.path.exists(tool_bin):
        print(f"BIN_DIR {tool_bin} not found.")
        return 1
    print("Done.")
    return 0


def select_file():
    projects = {}
    pro = 0
    print("Select file...")
    for pros in os.listdir(prog_path):
        if pros in ['bin', 'src'] or pros.startswith('.'):
            continue
        if os.path.isfile(os.path.join(prog_path, pros)) and pros.endswith('.zip'):
            pro += 1
            print(f"[{pro}]  {pros}\n")
            projects[str(pro)] = pros
    choice = input("Select project: ")
    if not choice or not choice in projects:
        return ""
    return projects[choice]


def extract_rom(path: str):
    if not zipfile.is_zipfile(path):
        print(f"[{path}] is not a ZIP file")
        return 1
    with zipfile.ZipFile(path) as zip_file:
        if "payload.bin" in zip_file.namelist():
            print(f"正在从 {path} 提取 payload.bin...")
            zip_file.extract("payload.bin", EXTRACT_DIR)
        else:
            print(f"正在从 {path} 提取文件...")
            zip_file.extractall(EXTRACT_DIR)
    return 0


def extract_images():
    print("正在从 payload.bin 提取指定的img文件...")

    if os.path.exists(os.path.join(EXTRACT_DIR, 'payload.bin')):
        with open(os.path.join(EXTRACT_DIR, 'payload.bin'), "rb") as f:
            extract_partitions_from_payload(f, img_files_list, EXTRACT_DIR, os.cpu_count() or 2)
    else:
        for partition in img_files_list:
            if os.path.exists(os.path.join(EXTRACT_DIR, f"{partition}.new.dat.br")):
                if call(["brotli", "-d", f"{EXTRACT_DIR}/{partition}.new.dat.br"]): return 1
            if os.path.exists(os.path.join(EXTRACT_DIR, f"{partition}.new.dat.1")):
                with open(os.path.join(EXTRACT_DIR, f"{partition}.new.dat"), 'wb') as f:
                    for i in range(1000):
                        if os.path.exists(os.path.join(EXTRACT_DIR, f"{partition}.new.dat.{i}")):
                            with open(os.path.join(EXTRACT_DIR, f"{partition}.new.dat.{i}"), "rb") as split_dat:
                                f.write(split_dat.read())
            if os.path.exists(os.path.join(EXTRACT_DIR, f"{partition}.new.dat")):
                Sdat2img(os.path.join(EXTRACT_DIR, f"{partition}.transfer.list"),
                         os.path.join(EXTRACT_DIR, f"{partition}.new.dat"),
                         os.path.join(EXTRACT_DIR, f"{partition}.img"))
    print("Checking extracted images...：")
    extracted_count = 0
    for img in img_files_list:
        if os.path.exists(os.path.join(EXTRACT_DIR, f"{img}.img")):
            print(f"✓ {img}")
            extracted_count += 1
        else:
            print(f"✗ {img} (Not Found)")
    print(f"{extracted_count} Images extracted.")
    return 0


def decompose_images():
    print("正在分解提取的img文件...")
    for name in img_files_list:
        img_path = os.path.join(EXTRACT_DIR, f"{name}.img")
        if os.path.exists(img_path):
            print(f"Processing {name}...")
            file_type = gettype(img_path)
            if file_type == 'sparse':
                if call(["simg2img", f"{img_path}", f"{EXTRACT_DIR}/{name}_unsparse.img"]): return 1
                os.remove(img_path)
                os.rename(f"{EXTRACT_DIR}/{name}_unsparse.img", img_path)
            if file_type == 'ext':
                imgextractor.Extractor().main(img_path, f'{IMG_DIR}/{name}', IMG_DIR)
            if file_type == 'erofs':
                if call(["extract.erofs", "-i", f"{img_path}", "-o", f"{IMG_DIR}", "-x"], out_=False): return 1
            if not os.path.exists(f'{IMG_DIR}/{name}'):
                print(f"{name} 未能成功分解或分解目录为空。可能需要手动处理或使用其他工具。")
                return 1
            else:
                print(f"{name}[{file_type}]分解成功到{IMG_DIR}/{name}")
    return 0


def rm_rf(path: str):
    if os.path.isfile(path) or readlink(path):
        os.remove(path)
    if os.path.isdir(path):
        rmtree(path)


def get_prop(file: str, name: str):
    if os.path.isfile(file):
        with open(file, "r", encoding='utf-8') as f:
            for i in f.readlines():
                if i.startswith(f"{name}="):
                    _, value = i.split("=", 1)
                    return value.strip()
    return ""


def modify_parts():
    systemdir = f"{IMG_DIR}/system"
    if readlink(f"{systemdir}/cache"):
        rm_rf(f"{systemdir}/cache")
        os.makedirs(f"{systemdir}/cache")
    rm_rf(f"{IMG_DIR}/system_ext/etc/selinux/mapping")
    os.makedirs(f"{IMG_DIR}/system_ext/etc/selinux/mapping", exist_ok=True)
    rm_rf(f"{IMG_DIR}/product/etc/selinux/mapping")
    os.makedirs(f"{IMG_DIR}/product/etc/selinux/mapping", exist_ok=True)
    with open(f"{IMG_DIR}/system_ext/etc/init/init.gsi.rc", 'w', encoding='utf-8') as f:
        f.write("\n")
    vndk = get_prop(f"{systemdir}/system/build.prop", "ro.system.build.version.sdk")
    manufacturer = get_prop(f"{systemdir}/system/build.prop", "ro.product.system.manufacturer")
    with open(f"{systemdir}/system/build.prop", 'r+', encoding='utf-8') as f:
        lines = f.readlines()
        lines = [i for i in lines if "media.settings.xml=/vendor/etc/media_profiles_vendor.xml" not in i]
        f.seek(0)
        f.truncate()
        lines.append("persist.sys.usb.config=adb,mtp\n")
        lines.append("ro.adb.secure=0\n")
        lines.append("ro.secure=0\n")
        lines.append("ro.debuggable=1\n")
        f.writelines(lines)
    if os.path.isdir(f"{BIN_DIR}/init/v{vndk}"):
        copy(f"{BIN_DIR}/init/v{vndk}/init", f"{systemdir}/system/bin/init")
        if os.path.exists(f"{BIN_DIR}/init/v{vndk}/libfs_mgr.so"): copy(f"{BIN_DIR}/init/v{vndk}/libfs_mgr.so",
                                                                        f"{systemdir}/system/lib64/libfs_mgr.so")
        if os.path.exists(f"{BIN_DIR}/init/v{vndk}/libfs_mgr_binder.so"): copy(
            f"{BIN_DIR}/init/v{vndk}/libfs_mgr_binder.so", f"{systemdir}/system/lib64/libfs_mgr_binder.so")
    else:
        print("suitable init not found")
    if manufacturer == "Xiaomi":
        print("ROM:Xiaomi")
        with open(f"{systemdir}/system/build.prop", 'a+', encoding='utf-8') as f, open(
                f"{BIN_DIR}/build/miui/system.prop", 'r', encoding='utf-8') as o:
            f.write("\n")
            f.writelines(o.readlines())
        with open(f"{IMG_DIR}/product/etc/build.prop", "a+", encoding='utf-8') as f, open(
                f"{BIN_DIR}/build/miui/product.prop", 'r', encoding='utf-8') as o:
            f.write("\n")
            f.writelines(o.readlines())
    if manufacturer in ["meizu", 'vivo'] and vndk == '34':
        print("ROM:Flyme")
        copytree(f"{BIN_DIR}/files/flyme/system/apex", f"{systemdir}/system/apex", dirs_exist_ok=True)
        copytree(f"{BIN_DIR}/files/flyme/product/overlay", f"{IMG_DIR}/product/overlay", dirs_exist_ok=True)
    copytree(f"{BIN_DIR}/apex", f"{systemdir}/system/apex", dirs_exist_ok=True)
    rm_rf(f"{IMG_DIR}/system_ext/apex")
    return 0


def merge_my():
    systemdir = os.path.join(IMG_DIR, "system")
    configdir = os.path.join(IMG_DIR, "config")
    dynamic_fs_dir = os.path.join(IMG_DIR, "dynamic_fs")
    target_fs = os.path.join(configdir, "system_fs_config")
    target_contexts = os.path.join(configdir, "system_file_contexts")
    if not os.path.exists(dynamic_fs_dir):
        os.makedirs(dynamic_fs_dir)
    for partition in os.listdir(IMG_DIR):
        if not partition.startswith('my_'):
            if partition != 'mi_ext':
                continue
        if not os.path.exists(systemdir):
            print("system.img is not unpacked，please continue after unpacking it.")
            return 1
        if not os.path.exists(os.path.join(IMG_DIR, partition)):
            print(f"{partition}.img is not unpacked，please continue after unpacking it.")
            return 1
        print(f"- Merging {partition} Partition")
        if os.path.isdir(os.path.join(IMG_DIR, partition)):
            rm_rf(os.path.join(systemdir, partition))
            rm_rf(os.path.join(IMG_DIR, partition, "lost+found"))
            move(os.path.join(IMG_DIR, partition), systemdir)
        if os.path.isfile(os.path.join(configdir, f"{partition}_file_contexts")):
            move(os.path.join(configdir, f"{partition}_file_contexts"), dynamic_fs_dir)
        fs_file = os.path.join(configdir, f"{partition}_fs_config")
        if os.path.exists(fs_file):
            move(fs_file, dynamic_fs_dir)
            rm_rf(os.path.join(configdir, f"{partition}_info"))
        if os.path.exists(os.path.join(dynamic_fs_dir, f"{partition}_file_contexts")):
            with open(os.path.join(dynamic_fs_dir, f"{partition}_file_contexts"), 'r+', encoding='utf-8') as f:
                lines = [i for i in f.readlines() if not i.startswith('/ u:')]
                lines = lines[1:]
                lines = [f"/system{i}" for i in lines if not "?" in i]
                lines.append(f"/system/{partition} u:object_r:system_file:s0\n")
            with open(target_contexts, 'r+', encoding='utf-8') as f:
                lines2 = f.readlines()
                f.seek(0)
                f.truncate()
                f.writelines([i for i in lines2 if not f"system/{partition} " in i])
                f.writelines(lines)
        if os.path.exists(os.path.join(dynamic_fs_dir, f"{partition}_fs_config")):
            with open(os.path.join(dynamic_fs_dir, f"{partition}_fs_config"), 'r+', encoding='utf-8') as f:
                lines = [i for i in f.readlines() if not i.startswith('/ 0')]
                lines = lines[1:]
                lines = [f"system/{i}" for i in lines]
                lines = lines[1:]
                if not lines[len(lines) - 1].endswith("\n"):
                    lines.append("\n")
                lines.append(f"system/{partition} 0 0 0755\n")
            with open(target_fs, 'r+', encoding='utf-8') as f:
                lines2 = f.readlines()
                lines2 = [i for i in lines2 if not f"system/{partition} " in i]
                f.seek(0)
                f.truncate()
                f.writelines(lines2)
                f.writelines(lines)

        print(f"Merged {partition}")
        with open(f"{systemdir}/system/build.prop", "a", encoding='utf-8', newline='\n') as f:
            f.write("\n")
            f.write(f"import /{partition}/build.prop")
    rm_rf(dynamic_fs_dir)
    return 0


def merge_parts_inside(parts: list):
    systemdir = f"{IMG_DIR}/system/system"
    configdir = f"{IMG_DIR}/config"
    dynamic_fs_dir = f"{IMG_DIR}/dynamic_fs"
    target_fs = f"{configdir}/system_fs_config"
    target_contexts = f"{configdir}/system_file_contexts"
    rm_rf(dynamic_fs_dir)
    os.makedirs(dynamic_fs_dir, exist_ok=True)
    for partition in parts:
        if not os.path.exists(systemdir):
            print("system.img is not unpacked，please continue after unpacking it.")
            return 1
        if not os.path.exists(os.path.join(IMG_DIR, partition)):
            print(f"{partition}.img is not unpacked，please continue after unpacking it.")
            return 1
        print(f"- Merging {partition} partition.")
        if os.path.isdir(os.path.join(IMG_DIR, partition)):
            rm_rf(os.path.join(systemdir, partition))
            rm_rf(os.path.join(IMG_DIR, partition, "lost+found"))
            move(os.path.join(IMG_DIR, partition), systemdir)
            rm_rf(os.path.join(IMG_DIR, 'system', partition))
            symlink(f"/system/{partition}", os.path.join(IMG_DIR, 'system', partition))

        if os.path.isfile(os.path.join(configdir, f"{partition}_file_contexts")):
            copy(os.path.join(configdir, f"{partition}_file_contexts"), dynamic_fs_dir)
        fs_file = os.path.join(configdir, f"{partition}_fs_config")
        if os.path.exists(fs_file):
            copy(fs_file, dynamic_fs_dir)
        if not os.path.isdir(f"{systemdir}/etc/init/config"):
            os.makedirs(f"{systemdir}/etc/init/config", exist_ok=True)
        skip_mount_file = f"{systemdir}/etc/init/config/skip_mount.cfg"
        if not os.path.exists(skip_mount_file):
            with open(skip_mount_file, 'w', encoding='utf-8'):
                ...
        with open(skip_mount_file, 'a+', encoding='utf-8') as f:
            f.write(f"/{partition}\n")
        if os.path.exists(os.path.join(dynamic_fs_dir, f"{partition}_file_contexts")):
            with open(os.path.join(dynamic_fs_dir, f"{partition}_file_contexts"), 'r+', encoding='utf-8') as f:
                lines = [i for i in f.readlines() if not i.startswith('/ u:')]
                lines = [f"/system/system{i}" for i in lines if not "?" in i]
                lines.append(f"/system/{partition} u:object_r:system_file:s0\n")
            with open(target_contexts, 'r+', encoding='utf-8') as f:
                lines2 = f.readlines()
                f.seek(0)
                f.truncate()
                f.writelines([i for i in lines2 if not f"system/{partition} " in i])
                f.writelines(lines)
        if os.path.exists(os.path.join(dynamic_fs_dir, f"{partition}_fs_config")):
            with open(os.path.join(dynamic_fs_dir, f"{partition}_fs_config"), 'r+', encoding='utf-8') as f:
                lines = [i for i in f.readlines() if not i.startswith('/ 0')]
                lines = [f"system/system/{i}" for i in lines]
                lines.append(f"system/{partition} 0 0 0644 /system/{partition}\n")
            with open(target_fs, 'r+', encoding='utf-8') as f:
                lines2 = f.readlines()
                lines2 = [i for i in lines2 if not f"system/{partition} " in i]
                f.seek(0)
                f.truncate()
                f.writelines(lines2)
                f.writelines(lines)
        print(f"Merged {partition}.")
    rm_rf(dynamic_fs_dir)
    return 0

def get_dir_size(path) -> int:
    size = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                file_path = os.path.join(root, name)
                if not os.path.isfile(file_path):
                    size += len(name)
                size += os.path.getsize(file_path)
            except (PermissionError, BaseException, Exception):
                size += 1
    return size

def repack_image():
    systemdir = f"{IMG_DIR}/system"
    fs = f"{IMG_DIR}/config/system_fs_config"
    con = f"{IMG_DIR}/config/system_file_contexts"
    fspatch(systemdir, fs)
    contextpatch(systemdir, con)
    os.makedirs(f"{IMG_DIR}/out", exist_ok=True)
    choice = input("Choose a FileSystem to Repack:[ext(default)/erofs]")
    if choice == "erofs":
        return call(["mkfs.erofs", "-zlz4hc,9", "--mount-point", f"/system", "--fs-config-file", f"{IMG_DIR}/config/system_fs_config",
                     "--file-contexts", f"{IMG_DIR}/config/system_file_contexts", f"{IMG_DIR}/out/system.img", f"{IMG_DIR}/system"], out_=False)
    else:
        size = get_dir_size(systemdir)
        size2 = int(size / 4096 + 4096*10)
        if call(['mke2fs', '-O', '^has_journal', '-t', 'ext4', '-b', '4096', '-L', 'system', '-I', '256', '-M', '/system', f'{IMG_DIR}/out/system.img', f'{size2}']):
            return 1
        if call(
                ['e2fsdroid', '-e', '-T', '1230768000', '-C', f'{IMG_DIR}/config/system_fs_config', '-S',
                 f'{IMG_DIR}/config/system_file_contexts', '-f', f'{IMG_DIR}/system', '-a', f'/system',
                 f'{IMG_DIR}/out/system.img']
        ):
            return 1
        if which("resize2fs"):
            if call(["resize2fs","-M", f'{IMG_DIR}/out/system.img'], extra_path=False):
                return 1
    return 0

def clean_up():
    print("Cleaning up...")
    rm_rf(EXTRACT_DIR)
    rm_rf(os.path.join(IMG_DIR, "system"))
    rm_rf(os.path.join(IMG_DIR, "config"))
    print("Done.")
    return 0

def main() -> int:
    if check_tools():
        return 1
    clean_up()
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)
    if not os.path.exists(EXTRACT_DIR):
        os.makedirs(EXTRACT_DIR)
    dest_path = None
    print("========================================")
    print("    OEM Generic System Image Maker")
    print("========================================")
    print(f"  Version:{__version__}")
    print(f"  Provided by {'|'.join(__author__)}")
    print("========================================")
    print()
    print("Please Select Operation：")
    print("1. Download and process")
    print("2. Process local roms")
    print("3. Exit")
    mode = input("Select (1/2/3):")
    if mode == "3":
        return 0
    elif mode == '1':
        url = input("Enter download url([q] to exit):")
        if url:
            filename = url.split("/")[-1].split('?')[0]
            dest_path = os.path.join(prog_path, filename)
            download([url], prog_path)
    else:
        dest_path = select_file()
    if not dest_path:
        print(f"[{dest_path}] not found.")
        return 1
    if extract_rom(dest_path):
        return 1
    if extract_images():
        return 1
    if decompose_images():
        return 1
    if modify_parts():
        return 1
    if merge_my():
        return 1
    if merge_parts_inside(["system_ext", "product"]):
        return 1
    if repack_image():
        return 1
    if clean_up():
        return 1
    print(f"Done!The GSi File is {IMG_DIR}/out/system.img.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

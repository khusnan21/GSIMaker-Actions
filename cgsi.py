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

from src import imgextractor, ozipdecrypt
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
__version__ = "1.0.1"
if os.name == 'nt':
    prog_path = os.getcwd()
else:
    prog_path = os.path.normpath(os.path.abspath(os.path.dirname(sys.argv[0])))
    if platform.system() == 'Darwin':
        path_frags = prog_path.split(os.path.sep)
        if path_frags[-3:] == ['tool.app', 'Contents', 'MacOS']:
            path_frags = path_frags[:-3]
            prog_path = os.path.sep.join(path_frags)

IMG_DIR = os.path.join(prog_path, 'IMG')
EXTRACT_DIR = os.path.join(prog_path, 'EXTRACT')
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
    if gettype(path) == 'ozip':
        ozipdecrypt.main(path)
        decrypted = os.path.dirname(path) + os.sep + os.path.basename(path)[:-4] + "zip"
        path = decrypted
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
    if os.name == 'posix':
        if readlink(path):
            os.remove(path)
    if not os.path.exists(path):
        return
    if os.path.isfile(path) or readlink(path):
        os.remove(path)
    if os.path.isdir(path):
        rmtree(path)


def get_prop(file: str, name: str) -> str:
    if os.path.isfile(file):
        with open(file, "r", encoding='utf-8') as f:
            for i in f.readlines():
                if i.startswith(f"{name}="):
                    _, value = i.split("=", 1)
                    return value.strip()
    return ""


def replace(file: str, origin: str, repl: str) -> int:
    with open(file, "r+", encoding='utf-8') as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        for i in lines:
            if i == origin:
                f.write(repl)
            else:
                f.write(i)
    return 0


def modify_parts() -> int:
    systemdir = f"{IMG_DIR}/system"
    # Avoid flashing wrong rec
    rm_rf(f"{systemdir}/init.recovery.hardware.rc")
    rm_rf(f"{systemdir}/cache")
    os.makedirs(f"{systemdir}/cache")
    for i in ["bt_firmware", "dsp", "firmware", "lost+found", "persist"]:
        if not os.path.exists(f"{systemdir}/{i}"):
            os.makedirs(f"{systemdir}/{i}", exist_ok=True)
    for i in ["update_engine", "update_verifier"]:
        rm_rf(f"{systemdir}/system/bin/{i}")
    rm_rf(f"{IMG_DIR}/system_ext/etc/selinux/mapping")
    os.makedirs(f"{IMG_DIR}/system_ext/etc/selinux/mapping", exist_ok=True)
    rm_rf(f"{IMG_DIR}/product/etc/selinux/mapping")
    os.makedirs(f"{IMG_DIR}/product/etc/selinux/mapping", exist_ok=True)
    with open(f"{IMG_DIR}/system_ext/etc/init/init.gsi.rc", 'w', encoding='utf-8') as f:
        f.write("\n")
    for i in [
        'persist.vendor.camera.selfie.unfold u:object_r:exported_system_prop:s0 exact int',
        'persist.vendor.camera.3rdhighResolutionBlob.scenes u:object_r:exported_system_prop:s0',
        'persist.vendor.camera.3rdvideocall.scenes u:object_r:exported_system_prop:s0',
        'persist.vendor.camera.3rdvideo.scenes u:object_r:exported_system_prop:s0',
        'persist.vendor.camera.3rdlive.scenes u:object_r:exported_system_prop:s0',
        'persist.vendor.camera.cloud.    u:object_r:exported_system_prop:s0',
        'persist.vendor.camera.traceGroupsEnable u:object_r:exported_system_prop:s0 exact string',
        'persist.vendor.camera.gadget       u:object_r:exported_system_prop:s0',
        'ro.vendor.camera.interpolation.mialgo.support        u:object_r:exported_system_prop:s0',
        'vendor.camera.sensor.logsystem.unrelease u:object_r:exported_system_prop:s0 exact string',
        'persist.vendor.camera.facetracker.active   u:object_r:exported_system_prop:s0 exact int',
        'persist.vendor.camera.facetracker.enable   u:object_r:exported_system_prop:s0 exact int',
        'persist.vendor.camera.facetracker.fpsrange u:object_r:exported_system_prop:s0 exact string',
        'persist.vendor.camera.facetracker.rrzosize u:object_r:exported_system_prop:s0 exact string',
        'persist.vendor.camera.logentry      u:object_r:exported_system_prop:s0',
        'persist.vendor.camera.gesture.emoji.support u:object_r:exported_system_prop:s0 exact int',
        'persist.vendor.camera.gesture.emoji.enable u:object_r:exported_system_prop:s0 exact int',
        'persist.vendor.camera.gesture.emoji.active u:object_r:exported_system_prop:s0 exact int',
        'persist.vendor.cameraopt.loglevel u:object_r:exported_system_prop:s0',
        'persist.vendor.camera.IsStreetModeSupported u:object_r:camera_config_prop:s0 exact bool',
        'persist.vendor.camera.facetracker.support  u:object_r:camera_config_prop:s0 exact int', ]:
        replace(f"{IMG_DIR}/system_ext/etc/selinux/system_ext_property_contexts", i + "\n", '')
    vndk = get_prop(f"{systemdir}/system/build.prop", "ro.system.build.version.sdk")
    manufacturer = get_prop(f"{systemdir}/system/build.prop", "ro.product.system.manufacturer")
    is_hyper_os = get_prop(f"{systemdir}/system/build.prop", "ro.build.version.incremental")
    replace(f"{systemdir}/system/etc/init/apexd.rc", "    reboot_on_failure reboot,apexd-failed\n", "    #Removed\n")
    replace(f"{systemdir}/system/etc/init/apexd.rc", "    reboot_on_failure reboot,bootloader,bootstrap-apexd-failed\n",
            "    #Removed\n")
    replace(f"{systemdir}/system/etc/init/hw/init.rc", "    reboot_on_failure reboot,boringssl-self-check-failed\n",
            "    #Removed\n")
    replace(f"{systemdir}/system/etc/init/vold.rc", "    group root reserved_disk\n", "    #Removed\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "/system/bin/logcat	--	u:object_r:logcat_exec:s0",
            "/system/bin/logcat	--	u:object_r:logd_exec:s0")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "/system/bin/logcatd	--	u:object_r:logcat_exec:s0",
            "/system/bin/logcatd	--	u:object_r:logd_exec:s0")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "# ro.build.fingerprint is either set in /system/build.prop, or is\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "ro.build.fingerprint    u:object_r:fingerprint_prop:s0 exact string\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "ro.product.ab_ota_partitions u:object_r:ota_prop:s0 exact string\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "ro.vendor.build.ab_ota_partitions u:object_r:ota_build_prop:s0 exact string\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "ro.vendor.camera.extensions.package u:object_r:camera2_extensions_prop:s0 exact string\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "ro.vendor.camera.extensions.service u:object_r:camera2_extensions_prop:s0 exact string\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "sys.usb.config     u:object_r:usb_control_prop:s0 exact string\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "sys.usb.configfs   u:object_r:usb_control_prop:s0 exact int\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "sys.usb.controller u:object_r:usb_control_prop:s0 exact string\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts", "sys.usb.config. u:object_r:usb_prop:s0\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "ro.actionable_compatible_property.enabled u:object_r:build_prop:s0 exact bool\n", "\n")
    replace(f"{systemdir}/system/etc/selinux/plat_file_contexts",
            "ro.opengles.version u:object_r:graphics_config_prop:s0 exact int\n", "\n")
    replace(f"{IMG_DIR}/product/etc/build.prop", "ro.product.ab_ota_partitions=boot,product,system,system_ext,vendor\n",
            "\n")
    for i in [
        '(genfscon binder "/binder_logs/proc_transaction/" (u object_r binderfs_logs_proc ((s0) (s0))))',
        '(genfscon binder "/binder_logs/proc_transaction" (u object_r binderfs_logs_proc ((s0) (s0))))',
        '(genfscon bpf "/miui" (u object_r fs_bpf_miui ((s0) (s0))))',
        '(genfscon cifs "/" (u object_r cifs ((s0) (s0))))',
        '(genfscon proc "/trace_package/package_runtime_disable" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/sys/kernel/sched_min_granularity_ns" (u object_r proc_sched ((s0) (s0))))',
        '(genfscon proc "/trace_package/top_package_on_bcore" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/trace_package/top_package_on_lcore" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/trace_package/show_traced_package" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/trace_package/show_traced_window" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/package/stat/reset_traced_window" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/trace_package/show_windowsize" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/trace_package/show_tracestat" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/trace_package/develop_mode" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/trace_package/top_package" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/trace_package/show_all" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/dynamic_debug/control" (u object_r proc_dynamic_debug_control ((s0) (s0))))',
        '(genfscon proc "/package/pkg/show_all" (u object_r trace_package_file ((s0) (s0))))',
        '(genfscon proc "/driver/cl_cam_status" (u object_r proc_cl_cam_status ((s0) (s0))))',
        '(genfscon proc "/mi_trace/enabled" (u object_r mitrace_enabled ((s0) (s0))))',
        '(genfscon proc "/fs/cifs/ConnStat" (u object_r samba_stat ((s0) (s0))))',
        '(genfscon proc "/sys/binder_prio" (u object_r proc_binder_prio ((s0) (s0))))',
        '(genfscon proc "/mtk_battery_cmd" (u object_r proc_battery_cmd ((s0) (s0))))',
        '(genfscon proc "/fs/f2fs/status" (u object_r proc_f2fs_status ((s0) (s0))))',
        '(genfscon proc "/mi_stack/stack" (u object_r mistack_stack ((s0) (s0))))',
        '(genfscon proc "/mi_mem_engine" (u object_r proc_mi_mem ((s0) (s0))))',
        '(genfscon proc "/mi_stack/pid" (u object_r mistack_pid ((s0) (s0))))',
        '(genfscon proc "/sys/mi_asap" (u object_r proc_ioturbo ((s0) (s0))))',
        '(genfscon proc "/ccci_lp_mem" (u object_r proc_ccci_lp_mem ((s0) (s0))))',
        '(genfscon proc "/cpumaxfreq" (u object_r proc_deviceinfo ((s0) (s0))))',
        '(genfscon proc "/unionpower" (u object_r proc_union_power ((s0) (s0))))',
        '(genfscon proc "/partitions" (u object_r proc_partition ((s0) (s0))))',
        '(genfscon proc "/powersave" (u object_r proc_power_save ((s0) (s0))))',
        '(genfscon proc "/mi_log" (u object_r proc_mi_log ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11cb1000.i2c/i2c-9/9-0034/11cb1000.i2c:mt6375@34:mt6375_gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk_gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk_gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge2/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge2/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk_gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk_gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk_gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11f01000.i2c/i2c-5/5-0034/11f01000.i2c:mt6375@34:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11d02000.i2c/i2c-5/5-0034/11d02000.i2c:mt6375@34:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6359-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11cb1000.i2c/i2c-9/9-0034/11cb1000.i2c:mt6375@34:mt6375_gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/10026000.pwrap/10026000.pwrap:mt6366/mt6358-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11cb1000.i2c/i2c-9/9-0034/11cb1000.i2c:mt6375@34:mt6375_gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11cb1000.i2c/i2c-9/9-0034/11cb1000.i2c:mt6375@34:mt6375_gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6357-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk_gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk_gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11cb1000.i2c/i2c-9/9-0034/11cb1000.i2c:mt6375@34:mt6375_gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10027000.spmi/spmi-0/0-03/10027000.spmi:mt6315@3:mt6315_3_regulator/extbuck_access" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10027000.spmi/spmi-0/0-06/10027000.spmi:mt6315@6:mt6315_6_regulator/extbuck_access" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10027000.spmi/spmi-0/0-07/10027000.spmi:mt6315@7:mt6315_7_regulator/extbuck_access" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10026000.pwrap/10026000.pwrap:mt6359p/mt6359p-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk_gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk_gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk_gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk_gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk_gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk_gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge2/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge2/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk_gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk_gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk_gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11cb1000.i2c/i2c-9/9-0034/11cb1000.i2c:mt6375@34:mt6375_gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11f01000.i2c/i2c-5/5-0034/11f01000.i2c:mt6375@34:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11d02000.i2c/i2c-5/5-0034/11d02000.i2c:mt6375@34:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge2/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge2/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge2/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge2/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10027000.spmi/spmi-0/0-03/10027000.spmi:mt6315@3:extbuck_debug/extbuck_access" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10027000.spmi/spmi-0/0-06/10027000.spmi:mt6315@6:extbuck_debug/extbuck_access" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10027000.spmi/spmi-0/0-07/10027000.spmi:mt6315@7:extbuck_debug/extbuck_access" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6359-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk_gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk_gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk_gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk_gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk_gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk_gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11f01000.i2c/i2c-5/5-0034/11f01000.i2c:mt6375@34:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11f01000.i2c/i2c-5/5-0034/11f01000.i2c:mt6375@34:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11d02000.i2c/i2c-5/5-0034/11d02000.i2c:mt6375@34:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11d02000.i2c/i2c-5/5-0034/11d02000.i2c:mt6375@34:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge2/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge2/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk_gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk_gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/11280000.i2c:mt6375@34:mtk_gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk_gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11b21000.i2c/i2c-5/5-0034/11b21000.i2c:mt6375@34:mtk_gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11f01000.i2c/i2c-5/5-0034/11f01000.i2c:mt6375@34:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11d02000.i2c/i2c-5/5-0034/11d02000.i2c:mt6375@34:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6359-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6359-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6359-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/10026000.pwrap/10026000.pwrap:mt6366/mt6358-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge2/BatteryNotify" (u object_r sysfs_battery_warning ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge2/BatteryNotify" (u object_r sysfs_battery_warning ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6357-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1c804000.spmi/spmi-0/0-04/mt6377-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge/BatteryNotify" (u object_r sysfs_battery_warning ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge2/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge/BatteryNotify" (u object_r sysfs_battery_warning ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge2/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10026000.pwrap/10026000.pwrap:mt6359p/mt6359p-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/11e01000.i2c:mt6375@34:mtk_gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11ed1000.i2c/i2c-5/5-0034/11ed1000.i2c:mt6375@34:mtk_gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/10026000.pwrap/10026000.pwrap:mt6366/mt6358-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/10026000.pwrap/10026000.pwrap:mt6366/mt6358-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/11b20000.i2c:mt6375@34:mtk_gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11f01000.i2c/i2c-5/5-0034/11f01000.i2c:mt6375@34:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11d02000.i2c/i2c-5/5-0034/11d02000.i2c:mt6375@34:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1cc04000.spmi/spmi-0/0-03/1cc04000.spmi:mt6379@3:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:mtk-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6357-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6357-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/10026000.pwrap/10026000.pwrap:mt6366/mt6358-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6357-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6359-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10026000.pwrap/10026000.pwrap:mt6359p/mt6359p-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10026000.pwrap/10026000.pwrap:mt6359p/mt6359p-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10026000.pwrap/10026000.pwrap:mt6359p/mt6359p-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c015000.spmi/spmi-0/0-04/mt6363-gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/10026000.pwrap/10026000.pwrap:mt6366/mt6358-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:main_pmic/mt6357-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10026000.pwrap/10026000.pwrap:mt6359p/mt6359p-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1c804000.spmi/spmi-0/0-04/mt6377-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1c804000.spmi/spmi-0/0-04/mt6377-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1c804000.spmi/spmi-0/0-04/mt6377-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1c804000.spmi/spmi-0/0-04/mt6377-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c015000.spmi/spmi-0/0-04/mt6363-gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c015000.spmi/spmi-0/0-04/mt6363-gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c015000.spmi/spmi-0/0-04/mt6363-gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c015000.spmi/spmi-0/0-04/mt6363-gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1c804000.spmi/spmi-0/0-04/mt6377-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11cb1000.i2c/i2c-9/9-0034/extdev_io/MT6375.9-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0018/extdev_io/MT6375.5-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11280000.i2c/i2c-5/5-0034/extdev_io/MT6375.5-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11017000.i2c/i2c-5/5-0034/extdev_io/MT6375.5-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11f01000.i2c/i2c-5/5-0034/extdev_io/MT6375.5-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/11d02000.i2c/i2c-5/5-0034/extdev_io/MT6375.5-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c015000.spmi/spmi-0/0-04/mt6363-gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:mt6358-pmic/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:mt6359-pmic/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10026000.pwrap/10026000.pwrap:mt6359-pmic/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11e01000.i2c/i2c-5/5-0034/extdev_io/MT6375.5-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b20000.i2c/i2c-5/5-0034/extdev_io/MT6375.5-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11b21000.i2c/i2c-5/5-0034/extdev_io/MT6375.5-0034" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/10026000.pwrap/10026000.pwrap:mt6366/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/1000d000.pwrap:main_pmic/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/odm/odm:extcon-usb2/extcon/extcon2/cable.1/name" (u object_r sysfs_extcon ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/odm/odm:extcon-usb2/extcon/extcon2/cable.0/name" (u object_r sysfs_extcon ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/odm/odm:extcon-usb1/extcon/extcon1/cable.1/name" (u object_r sysfs_extcon ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/odm/odm:extcon-usb1/extcon/extcon1/cable.0/name" (u object_r sysfs_extcon ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/10026000.pwrap/10026000.pwrap:mt6359p/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/battery/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/1c804000.spmi/spmi-0/0-04/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/mhl@0/extcon/HDMI_audio_extcon/state" (u object_r sysfs_HDMI_audio_extcon_state ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c015000.spmi/spmi-0/0-04/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1c804000.spmi/spmi-0/0-04/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/musb-mtu3d/musb-hdrc/portmode" (u object_r sysfs_usb_plat ((s0) (s0))))',
        '(genfscon sysfs "/bus/platform/drivers/pmic-codec-accdet/state" (u object_r sysfs_headset ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/charger/ADC_Charger_Voltage" (u object_r sysfs_vbus ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/battery/ADC_Charger_Voltage" (u object_r sysfs_vbus ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/battery/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/CONNAC/net/wlan0/operstate" (u object_r sysfs_thermald ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/battery/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/battery/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/vibrator@0/leds/vibrator" (u object_r sysfs_vibrator ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/11201000.mtu3_0/portmode" (u object_r sysfs_usb_plat ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/mt-battery/BatteryNotify" (u object_r sysfs_battery_warning ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/battery/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/bus/platform/drivers/Accdet_Driver/state" (u object_r sysfs_headset ((s0) (s0))))',
        '(genfscon sysfs "/bus/platform/devices/musb-hdrc/portmode" (u object_r sysfs_usb_plat ((s0) (s0))))',
        '(genfscon sysfs "/dev/gauge/FG_Battery_CurrentConsumption" (u object_r sysfs_battery_consumption ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/1000d000.pwrap/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/charger/BatteryNotify" (u object_r sysfs_battery_warning ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/battery/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/kernel/smart_cache/debug_log_enable" (u object_r sysfs_smartcache ((s0) (s0))))',
        '(genfscon sysfs "/kernel/smart_cache/refault_distance" (u object_r sysfs_smartcache ((s0) (s0))))',
        '(genfscon sysfs "/class/udc/musb-hdrc/device/portmode" (u object_r sysfs_usb_plat ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/bp-thl/bp_thl_stop" (u object_r sysfs_pt_enable_file ((s0) (s0))))',
        '(genfscon sysfs "/devices/virtual/net/p2p0/operstate" (u object_r sysfs_thermald ((s0) (s0))))',
        '(genfscon sysfs "/devices/virtual/net/ap0/operstate" (u object_r sysfs_thermald ((s0) (s0))))',
        '(genfscon sysfs "/class/udc/musb-hdrc/device/comde" (u object_r sysfs_usb_plat ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/mt_usb/portmode" (u object_r sysfs_usb_plat ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/mt_usb/cmode" (u object_r sysfs_usb_plat ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/soc/usb-phy0" (u object_r sysfs_usb_plat ((s0) (s0))))',
        '(genfscon sysfs "/dev/gauge/Battery_Temperature" (u object_r sysfs_battery_temp ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/mt6333-user" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/mt6311-user" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/dev/gauge/Power_Off_Voltage" (u object_r sysfs_power_off_vol ((s0) (s0))))',
        '(genfscon sysfs "/dev/gauge/FG_daemon_disable" (u object_r sysfs_fg_disable ((s0) (s0))))',
        '(genfscon sysfs "/devices/virtual/usb_rawbulk" (u object_r sys_usb_rawbulk ((s0) (s0))))',
        '(genfscon sysfs "/class/android_usb/android0" (u object_r sysfs_android0_usb ((s0) (s0))))',
        '(genfscon sysfs "/dev/gauge/Power_On_Voltage" (u object_r sysfs_power_on_vol ((s0) (s0))))',
        '(genfscon sysfs "/kernel/smart_cache/enable" (u object_r sysfs_smartcache ((s0) (s0))))',
        '(genfscon sysfs "/kernel/smart_cache/ratio" (u object_r sysfs_smartcache ((s0) (s0))))',
        '(genfscon sysfs "/devices/platform/mt-pmic" (u object_r sysfs_pmu ((s0) (s0))))',
        '(genfscon sysfs "/kernel/smart_cache/file" (u object_r sysfs_smartcache ((s0) (s0))))',
        '(genfscon sysfs "/block/mmcblk0rpmb/size" (u object_r access_sys_file ((s0) (s0))))',
        '(genfscon sysfs "/dev/gauge/disable_nafg" (u object_r sysfs_dis_nafg ((s0) (s0))))',
        '(genfscon sysfs "/module/unionpower" (u object_r sysfs_union_power ((s0) (s0))))',
        '(genfscon sysfs "/module/powersave" (u object_r sysfs_power_save ((s0) (s0))))',
        '(genfscon sysfs "/devices/kprobe" (u object_r fs_sys_miui ((s0) (s0))))',
        '(genfscon sysfs "/kernel/metis" (u object_r proc_mi_mem ((s0) (s0))))',
        '(genfscon sysfs "/unionpower" (u object_r sysfs_union_power ((s0) (s0))))',
        '(genfscon sysfs "/powersave" (u object_r sysfs_power_save ((s0) (s0))))',
        '(genfscon sysfs "/bootinfo" (u object_r sysfs_bootinfo ((s0) (s0))))',
        '(genfscon sysfs "/hwconf" (u object_r hwconf_data_file ((s0) (s0))))',
        '(genfscon tracefs "/events/scheduler/sched_big_task_rotation/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/scheduler/sched_select_task_rq_rt/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/scheduler/sched_frequency_limits/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/scheduler/sched_select_task_rq/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/scheduler/sched_force_migrate/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/scheduler/sched_task_uclamp/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_bio_frontmerge/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/scheduler/sched_queue_task/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_bio_backmerge/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/fpsgo/fpsgo_main_systrace/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/sched/sched_process_fork/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_bio_complete/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_dirty_buffer/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_touch_buffer/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/sched/sched_migrate_task/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/sched/sched_stat_blocked/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/scheduler/sugov_ext_util/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_bio_bounce/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_rq_requeue/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/fpsgo/fpsgo_main_trace/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_bio_queue/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_bio_remap/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_rq_insert/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/ged/gpu_frequency_mtk/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/sched/sched_wait_task/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_rq_remap/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/fpsgo/fstb_systrace/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_unplug/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/fpsgo/fbt_systrace/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_getrq/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_split/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/block/block_plug/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/workqueue/" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/kprobes" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/events/uprobes" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/kprobe_events" (u object_r debugfs_tracing ((s0) (s0))))',
        '(genfscon tracefs "/uprobe_events" (u object_r debugfs_tracing ((s0) (s0))))', ]:
        replace(f"{IMG_DIR}/system_ext/etc/selinux/system_ext_sepolicy.cil", i + "\n", "")
    with open(f"{IMG_DIR}/product/etc/build.prop", 'a+', encoding='utf-8') as f:
        for i in [
            'ro.cp_system_other_odex=0',
            'ro.nnapi.extensions.deny_on_product=true',
            'ro.lmk.kill_heaviest_task=true',
            'ro.lmk.kill_timeout_ms=100',
            'ro.lmk.use_minfree_levels=true',
            'ro.surface_flinger.vsync_event_phase_offset_ns=-1',
            'ro.surface_flinger.vsync_sf_event_phase_offset_ns=-1',
            'debug.sf.high_fps_late_app_phase_offset_ns=',
            'debug.sf.early_phase_offset_ns=',
            'debug.sf.early_gl_phase_offset_ns=',
            'debug.sf.early_app_phase_offset_ns=',
            'debug.sf.early_gl_app_phase_offset_ns=',
            'debug.sf.high_fps_late_sf_phase_offset_ns=',
            'debug.sf.high_fps_early_phase_offset_ns=',
            'debug.sf.high_fps_early_gl_phase_offset_ns=',
            'debug.sf.high_fps_early_app_phase_offset_ns=',
            'debug.sf.high_fps_early_gl_app_phase_offset_ns=',
            'qemu.hw.mainkeys=0',
            'ro.opa.eligible_device=true',
            'ro.setupwizard.mode=OPTIONAL',
            'ro.vndk.lite=false',
            'persist.sys.disable_rescue=true',
            'ro.control_privapp_permissions=disable', ]:
            f.write(i + '\n')
    rm_rf(f"{systemdir}/system/etc/init/config")
    rm_rf(f"{systemdir}/system/etc/init/cppreopts.rc")
    rm_rf(f"{systemdir}/system/etc/init/otapreopt.rc")
    rm_rf(f"{systemdir}/system/etc/init/update_verifier.rc")
    rm_rf(f"{systemdir}/system/etc/init/update_engine.rc")
    rm_rf(f"{systemdir}/system/etc/init/recovery-refresh.rc")
    rm_rf(f"{systemdir}/system/etc/init/recovery-persist.rc")
    rm_rf(f"{systemdir}/system/priv-app/LocalTransport")
    rm_rf(f"{systemdir}/system/priv-app/ONS")
    rm_rf(f"{systemdir}/system/priv-app/Tag")
    with open(f"{systemdir}/system/build.prop", 'r+', encoding='utf-8') as f:
        lines = f.readlines()
        lines = [i for i in lines if "media.settings.xml=/vendor/etc/media_profiles_vendor.xml" not in i]
        lines = [i for i in lines if "ro.actionable_compatible_property.enabled=true" not in i]
        lines = [i for i in lines if "ro.secure=1" not in i]
        lines = [i for i in lines if "ro.debuggable=0" not in i]
        lines = [i for i in lines if "ro.apex.updatable=false" not in i]
        f.seek(0)
        f.truncate()
        lines.append("ro.build.system_root_image=true\n")
        lines.append("ro.support_one_handed_mode=true\n")
        lines.append("persist.sys.binary_xml=false\n")
        lines.append("persist.logd.logpersistd.buffer=0\n")
        lines.append("ro.opengles.version=196610\n")
        lines.append("persist.sys.disable_rescue=true\n")
        lines.append("ro.control_privapp_permissions=disable\n")
        lines.append("ro.cp_system_other_odex=0\n")
        lines.append("ro.nnapi.extensions.deny_on_product=true\n")
        lines.append("\n")
        lines.append("# Start adbd\n")
        lines.append("persist.service.adb.enable=1\n")
        lines.append("persist.service.debuggable=1\n")
        lines.append("persist.sys.usb.config=mtp,adb\n")
        lines.append("ro.adb.secure=0\n")
        lines.append("ro.secure=0\n")
        lines.append("ro.debuggable=1\n")
        for p in ['# Some devices have sdcardfs kernel panicing on 8.0, Disable for everyone for the moment',
                  'ro.sys.sdcardfs=0persist.bluetooth.system_audio_hal.enabled=1',
                  'bluetooth.profile.asha.central.enabled=true',
                  'bluetooth.profile.a2dp.source.enabled=true',
                  'bluetooth.profile.avrcp.target.enabled=true',
                  'bluetooth.profile.bas.client.enabled=true',
                  'bluetooth.profile.gatt.enabled=true',
                  'bluetooth.profile.hfp.ag.enabled=true',
                  'bluetooth.profile.hid.device.enabled=true',
                  'bluetooth.profile.hid.host.enabled=true',
                  'bluetooth.profile.map.server.enabled=true',
                  'bluetooth.profile.opp.enabled=true',
                  'bluetooth.profile.pan.nap.enabled=true',
                  'bluetooth.profile.pan.panu.enabled=true',
                  'bluetooth.profile.pbap.server.enabled=true',
                  'bluetooth.profile.sap.server.enabled=true',
                  '# Force triple frame buffers', '# ro.surface_flinger.max_frame_buffer_acquired_buffers=3',
                  '# Fix developer settings', 'ro.oem_unlock_supported=1', '# BT Fix',
                  '# BT Fix',
                  'persist.bluetooth.a2dp_offload.cap=sbc-aac-aptx-aptxhd-ldac',
                  'persist.bluetooth.a2dp_offload.disabled=false',
                  'persist.vendor.qcom.bluetooth.a2dp_offload_cap=sbc-aptx-aptxtws-aptxhd-aac-ldac',
                  'persist.vendor.qcom.bluetooth.aac_vbr_ctl.enabled=false',
                  'persist.vendor.qcom.bluetooth.enable.splita2dp=true',
                  'persist.vendor.qcom.bluetooth.scram.enabled=true',
                  'persist.vendor.qcom.bluetooth.soc=cherokee',
                  'persist.vendor.qcom.bluetooth.twsp_state.enabled=false',
                  'ro.bluetooth.a2dp_offload.supported=true',
                  'ro.vendor.bluetooth.wipower=false',
                  'vendor.qcom.bluetooth.soc=cherokee',
                  'persist.bluetooth.bluetooth_audio_hal.disabled=false',
                  'persist.bluetooth.bluetooth_audio_hal.enabled=true',
                  '# SIM Fix',
                  'ro.multisim.simslotcount=2',
                  'ro.vendor.multisim.simslotcount=2',
                  'persist.radio.multisim.config=dsds',
                  'persist.vendor.radio.msimode=dsds',
                  "ro.apex.updatable=true"
                  ]:
            lines.append(p + "\n")
        f.writelines(lines)
    if os.path.isdir(f"{BIN_DIR}/init/v{vndk}"):
        copy(f"{BIN_DIR}/init/v{vndk}/init", f"{systemdir}/system/bin/init")
        if os.path.exists(f"{BIN_DIR}/init/v{vndk}/libfs_mgr.so"): copy(f"{BIN_DIR}/init/v{vndk}/libfs_mgr.so",
                                                                        f"{systemdir}/system/lib64/libfs_mgr.so")
        if os.path.exists(f"{BIN_DIR}/init/v{vndk}/libfs_mgr_binder.so"): copy(
            f"{BIN_DIR}/init/v{vndk}/libfs_mgr_binder.so", f"{systemdir}/system/lib64/libfs_mgr_binder.so")
    else:
        print("suitable init not found")
    with open(f"{systemdir}/system/etc/selinux/plat_file_contexts", 'a+', encoding="utf-8") as f:
        for i in ["/system/bin/vndk-detect			u:object_r:update_engine_exec:s0",
                  "/system/etc/usb_audio_policy_configuration.xml	u:object_r:vendor_configs_file:s0",
                  "/system/bin/rw-system.sh u:object_r:update_engine_exec:s0",
                  "/system/bin/phh-on-boot.sh u:object_r:update_engine_exec:s0",
                  "/system/bin/phh-on-data.sh u:object_r:update_engine_exec:s0",
                  "/system/bin/phh-prop-handler.sh u:object_r:update_engine_exec:s0",
                  "/system/bin/phh-remotectl.sh u:object_r:update_engine_exec:s0",
                  "/system/bin/wificonf u:object_r:wificond_exec:s0",
                  "/system/bin/permissiver.sh			u:object_r:update_engine_exec:s0",
                  "/system/bin/hdrfix_post-data.sh			u:object_r:update_engine_exec:s0",

                  ]:
            f.write(i + "\n")
    if manufacturer == "Xiaomi":
        print("ROM:Xiaomi")
        for i in ["Polaris", "MiuiDaemon"]:
            if os.path.exists(f"{IMG_DIR}/system_ext/app/{i}"):
                rm_rf(f"{IMG_DIR}/system_ext/app/{i}")
        copytree(f"{BIN_DIR}/files/miui/product/device_features", f"{IMG_DIR}/product/device_features",
                 dirs_exist_ok=True)
        copytree(f"{BIN_DIR}/phh/system_ext/priv-app", f"{IMG_DIR}/system_ext/priv-app", dirs_exist_ok=True)
        if is_hyper_os.startswith("OS2"):
            copytree(f"{BIN_DIR}/files/miui/product/etc", f"{IMG_DIR}/product/etc", dirs_exist_ok=True)
        with open(f"{systemdir}/system/build.prop", 'a+', encoding='utf-8') as f, open(
                f"{BIN_DIR}/build/miui/system.prop", 'r', encoding='utf-8') as o:
            f.write("\n")
            f.writelines(o.readlines())
        with open(f"{IMG_DIR}/product/etc/build.prop", "a+", encoding='utf-8') as f, open(
                f"{BIN_DIR}/build/miui/product.prop", 'r', encoding='utf-8') as o:
            f.write("\n")
            f.writelines(o.readlines())
        with open(f"{IMG_DIR}/product/etc/build.prop", "a+", encoding='utf-8') as f:
            f.write("\n")
            f.writelines([i + "\n" for i in [
                "# You can nuke this if necessary", "sys.miui.ndcd=off",
                "# MIUI CN bpfloader-failed fix (by romashkagene heh)", "ro.miui.region=gb",
                "# MIUI launcher fix", "ro.miui.product.home=com.miui.home",
            ]])
    if manufacturer in ["meizu", 'vivo'] and vndk == '34':
        print("ROM:Flyme")
        copytree(f"{BIN_DIR}/files/flyme/system/apex", f"{systemdir}/system/apex", dirs_exist_ok=True)
        copytree(f"{BIN_DIR}/files/flyme/product/overlay", f"{IMG_DIR}/product/overlay", dirs_exist_ok=True)
    copytree(f"{BIN_DIR}/apex", f"{systemdir}/system/apex", dirs_exist_ok=True)
    copytree(f"{BIN_DIR}/phh/system", f"{systemdir}/system/system", dirs_exist_ok=True)
    copytree(f"{BIN_DIR}/phh/product/app", f"{IMG_DIR}/product/app", dirs_exist_ok=True)
    rm_rf(f"{IMG_DIR}/system_ext/apex")
    return 0

def generate_markdown(mark_down_file: str):
    if not os.path.exists(os.path.dirname(mark_down_file)):
        os.makedirs(os.path.dirname(mark_down_file), exist_ok=True)
    build_file = f"{IMG_DIR}/system/system/build.prop"
    build_file_vendor = f"{IMG_DIR}/vendor/build.prop"
    vndk = get_prop(build_file, "ro.system.build.version.sdk")
    manufacturer = get_prop(build_file, "ro.product.system.manufacturer")
    is_hyper_os = get_prop(build_file, "ro.build.version.incremental")
    oem_os_dict = {
        "Xiaomi":"MIUI","meizu":"Flyme","vivo":"OriginOS","BLUEFOX":"FoxOS"
    }
    with open(mark_down_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f"## {f"HyperOS{is_hyper_os[2:]}" if is_hyper_os else oem_os_dict.get(manufacturer, manufacturer + "OS")}\n")
        f.write(f"## Ported from {get_prop(build_file, 'ro.product.system.model')}({get_prop(build_file, 'ro.product.system.device')})\n")
        f.write('\n')
        f.write('## Info\n')
        f.write("```\n")
        f.write(f"Device brand: {get_prop(build_file, 'ro.product.system.brand')}\n")
        f.write(f"Device manufacturer: {manufacturer}\n")
        f.write(f"Device model: {get_prop(build_file, 'ro.product.system.model')}\n")
        f.write(f"Device codename: {get_prop(build_file, 'ro.product.system.device')}\n")
        f.write(f"Device board: {get_prop(build_file_vendor, 'ro.board.platform')}\n")
        f.write(f"Android version: {get_prop(build_file, 'ro.system.build.version.release')}\n")
        f.write(f"Android API: {vndk}\n")
        f.write(f"Build fingerprint: {get_prop(build_file, 'ro.system.build.fingerprint')}\n")
        f.write(f"Build type: {get_prop(build_file, 'ro.build.type')}\n")
        f.write(f"Build tags: {get_prop(build_file, 'ro.build.tags')}\n")
        f.write(f"Build ID: {get_prop(build_file, 'ro.build.id')}\n")
        f.write(f"Security patch: {get_prop(build_file, 'ro.build.version.security_patch')}\n")
        f.write(f"#Raw Image Size#\n")
        f.write("```\n")

def merge_my() -> int:
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
            f.write(f"import /{partition}/build.prop\n")
    rm_rf(dynamic_fs_dir)
    return 0


def merge_parts_inside(parts: list) -> int:
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
            f.write(f"/{partition}/*\n")
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


def repack_image() -> int:
    systemdir = f"{IMG_DIR}/system"
    fs = f"{IMG_DIR}/config/system_fs_config"
    con = f"{IMG_DIR}/config/system_file_contexts"
    with open(fs, 'a+', encoding='utf-8') as f:
        for i in ['system/system/bin/bootctl 0 2000 0755',
                  'system/system/bin/busybox_phh 0 2000 0755',
                  'system/system/bin/getSPL 0 2000 0755',
                  'system/system/bin/gsid 0 2000 0755',
                  'system/system/bin/objdump 0 2000 0755',
                  'system/system/bin/phh-on-boot.sh 0 2000 0755',
                  'system/system/bin/rw-system.sh 0 2000 0755',
                  'system/system/bin/vintf 0 2000 0755',
                  'system/system/bin/vndk-detect 0 2000 0755',
                  'system/system/bin/wificonf 0 2000 0755',
                  'system/system/etc/init/config 0 0 0755',
                  'system/system/etc/init/config/skip_mount.cfg 0 0 0644',
                  'system/system/system_ext/etc/init 0 0 0755',
                  'system/system/system_ext/etc/init/config 0 0 0755',
                  'system/system/system_ext/etc/init/config/skip_mount.cfg 0 0 0644',
                  'system/system/etc/init/gsid.rc 0 0 0644',
                  'system/system/etc/init/vndk.rc 0 0 0644',
                  'system/system/etc/init/wificonf.rc 0 0 0644',
                  'system/system/etc/usb_audio_policy_configuration.xml 0 0 0644']:
            f.write(i + '\n')
    with open(con, 'a+', encoding='utf-8') as f:
        for i in [
            '/system/system/bin/bootctl u:object_r:system_file:s0',
            '/system/system/bin/busybox_phh u:object_r:system_file:s0',
            '/system/system/bin/getSPL u:object_r:system_file:s0',
            '/system/system/bin/gsid u:object_r:gsid_exec:s0',
            '/system/system/bin/vintf u:object_r:system_file:s0',
            '/system/system/bin/vndk-detect u:object_r:update_engine_exec:s0',
            '/system/system/bin/wificonf u:object_r:wificond_exec:s0',
            '/system/system/etc/init/config u:object_r:system_file:s0',
            r'/system/system/etc/init/config/skip_mount\.cfg u:object_r:system_file:s0',
            '/system/system/system_ext/etc/init u:object_r:system_file:s0',
            '/system/system/system_ext/etc/init/config u:object_r:system_file:s0',
            r'/system/system/system_ext/etc/init/config/skip_mount\.cfg u:object_r:system_file:s0',
            r'/system/system/etc/init/vndk\.rc u:object_r:system_file:s0',
            r'/system/system/etc/init/wificonf\.rc u:object_r:system_file:s0',
            r'/system/system/etc/usb_audio_policy_configuration\.xml u:object_r:vendor_configs_file:s0',
            r'/system/system/bin/phh-on-boot\.sh u:object_r:update_engine_exec:s0',
            r'/system/system/bin/rw-system\.sh u:object_r:update_engine_exec:s0',
        ]:
            f.write(i + '\n')
    fspatch(systemdir, fs)
    contextpatch(systemdir, con)
    os.makedirs(f"{IMG_DIR}/out", exist_ok=True)
    choice = "ext4"
    if choice == "erofs":
        return call(["mkfs.erofs", "-zlz4hc,9", "--mount-point", f"/system", "--fs-config-file",
                     f"{IMG_DIR}/config/system_fs_config",
                     "--file-contexts", f"{IMG_DIR}/config/system_file_contexts", f"{IMG_DIR}/out/system.img",
                     f"{IMG_DIR}/system"], out_=False)
    else:
        size = get_dir_size(systemdir)
        size2 = int(size / 4096 + 4096 * 10)
        if call(['mke2fs', '-O', '^has_journal', '-t', 'ext4', '-b', '4096', '-L', 'system', '-I', '256', '-M',
                 '/system', f'{IMG_DIR}/out/system.img', f'{size2}']):
            return 1
        if call(
                ['e2fsdroid', '-e', '-T', '1230768000', '-C', f'{IMG_DIR}/config/system_fs_config', '-S',
                 f'{IMG_DIR}/config/system_file_contexts', '-f', f'{IMG_DIR}/system', '-a', f'/system',
                 f'{IMG_DIR}/out/system.img']
        ):
            return 1
        if which("resize2fs"):
            if call(["resize2fs", "-M", f'{IMG_DIR}/out/system.img'], extra_path=False):
                return 1
    return 0


def clean_up(clean_img_dir=False) -> int:
    print("Cleaning up...")
    rm_rf(EXTRACT_DIR)
    if clean_img_dir:
        rm_rf(IMG_DIR)
    rm_rf(os.path.join(IMG_DIR, "system"))
    rm_rf(os.path.join(IMG_DIR, "config"))
    print("Done.")
    return 0


def main() -> int:
    if check_tools():
        return 1
    clean_up(True)
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)
    if not os.path.exists(EXTRACT_DIR):
        os.makedirs(EXTRACT_DIR)
    dest_path = os.path.join(prog_path, "roms", "rom.zip")
    print("========================================")
    print("    OEM Generic System Image Maker")
    print("========================================")
    print(f"  Version:{__version__}")
    print(f"  Provided by {'|'.join(__author__)}")
    print("========================================")
    print()
    if not os.path.exists(dest_path):
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
    if generate_markdown(f"{IMG_DIR}/out/info.md"):
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
    replace(f"{IMG_DIR}/out/info.md", "#Raw Image Size#\n", f"Raw Image Size: {round(os.path.getsize(f'{IMG_DIR}/out/system.img')/1024**3, 2)} GB\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

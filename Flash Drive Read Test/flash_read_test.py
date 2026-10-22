# v1.6

import os
import sys
import time
import platform
import string
import datetime
import curses
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

BLOCK_SIZE = 1024 * 1024  # Read in 1MB chunks
UI_REFRESH_INTERVAL = 0.05  # Refresh display at 20 FPS (every 50ms)

@dataclass
class FileResult:
    path: str
    size_bytes: int
    read_time_sec: float
    speed_mbps: float
    error: Optional[str] = None

@dataclass
class BenchmarkStats:
    results: List[FileResult] = field(default_factory=list)
    total_bytes_read: int = 0
    total_time_sec: float = 0.0
    failed_files: List[FileResult] = field(default_factory=list)

def detect_removable_drives() -> List[str]:
    system = platform.system()
    drives = []

    if system == "Windows":
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_path = f"{letter}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(drive_path) == 2:
                    drives.append(drive_path)
            bitmask >>= 1
            
    elif system == "Darwin":
        volumes = "/Volumes"
        if os.path.exists(volumes):
            for entry in os.listdir(volumes):
                full_path = os.path.join(volumes, entry)
                if os.path.islink(full_path) or entry == "Macintosh HD":
                    continue
                if os.path.ismount(full_path):
                    drives.append(full_path)

    elif system == "Linux":
        media_paths = ["/media", f"/media/{os.getenv('USER')}", "/run/media"]
        for base in media_paths:
            if os.path.exists(base):
                for root, dirs, _ in os.walk(base):
                    for d in dirs:
                        p = os.path.join(root, d)
                        if os.path.ismount(p):
                            drives.append(p)
    return drives

def select_drive() -> str:
    drives = detect_removable_drives()
    
    if not drives:
        print("No removable drives automatically detected.")
        path = input("Please manually enter drive path (e.g., E:\\ or /Volumes/USB): ").strip()
        if not os.path.exists(path):
            print("Error: Invalid path. Exiting.")
            sys.exit(1)
        return path

    print("\n--- Detected Flash Drives ---")
    for idx, drive in enumerate(drives, 1):
        print(f"[{idx}] {drive}")

    choice = input(f"\nSelect drive (1-{len(drives)}) or enter custom path: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(drives):
        return drives[int(choice) - 1]
    elif os.path.exists(choice):
        return choice
    else:
        print("Invalid selection. Exiting.")
        sys.exit(1)

def format_bytes(size: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def format_time(seconds: float) -> str:
    if seconds < 0 or seconds == float('inf'):
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def make_bar(pct: float, width: int = 10) -> str:
    filled = int(round(width * pct / 100))
    return "█" * filled + "░" * (width - filled)

def open_uncached_file(filepath: str) -> Tuple[int, Optional[str]]:
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            GENERIC_READ = 0x80000000
            FILE_SHARE_READ = 0x00000001
            OPEN_EXISTING = 3
            FILE_FLAG_NO_BUFFERING = 0x20000000

            handle = ctypes.windll.kernel32.CreateFileW(
                filepath, GENERIC_READ, FILE_SHARE_READ, None,
                OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
            )
            if handle == -1 or handle == 0:
                raise OSError(f"Win32 API error: {ctypes.GetLastError()}")
            
            import msvcrt
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
            return fd, None

        elif system == "Linux":
            flags = os.O_RDONLY
            if hasattr(os, 'O_DIRECT'):
                flags |= os.O_DIRECT
            return os.open(filepath, flags), None

        elif system == "Darwin":
            import fcntl
            fd = os.open(filepath, os.O_RDONLY)
            try:
                fcntl.fcntl(fd, 48, 1)
            except Exception:
                pass
            return fd, None
        else:
            return os.open(filepath, os.O_RDONLY), None

    except Exception as e:
        return -1, str(e)

def update_ui(stdscr, idx: int, total_files: int, filename: str, size: int,
              bytes_processed: int, total_bytes: int, file_bytes: int,
              current_speed: float, benchmark_start: float):
    """Encapsulated rendering function for stable terminal refresh rates."""
    try:
        # Handle non-blocking key checks (e.g. window resizes)
        ch = stdscr.getch()
        if ch == curses.KEY_RESIZE:
            curses.update_lines_cols()
            stdscr.clear()

        now = time.time()
        elapsed_total = now - benchmark_start
        total_pct = (bytes_processed / total_bytes) * 100 if total_bytes > 0 else 0
        file_pct = (file_bytes / size) * 100 if size > 0 else 100.0

        avg_speed = (bytes_processed / (1024 * 1024)) / elapsed_total if elapsed_total > 0 else 0
        remaining_bytes = max(0, total_bytes - bytes_processed)
        avg_bytes_per_sec = bytes_processed / elapsed_total if elapsed_total > 0 else 0
        eta_sec = (remaining_bytes / avg_bytes_per_sec) if avg_bytes_per_sec > 0 else 0

        max_y, max_x = stdscr.getmaxyx()

        if max_y >= 2 and max_x > 10:
            raw_line1 = f"File [{idx}/{total_files}]: {filename} ({format_bytes(size)})"
            raw_line2 = (
                f"ALL [{make_bar(total_pct)}] {total_pct:4.0f}% | "
                f"FILE [{make_bar(file_pct)}] {file_pct:4.0f}% | "
                f"Cur: {current_speed:5.1f}MB/s | Avg: {avg_speed:5.1f}MB/s | ETA: {format_time(eta_sec)}"
            )

            line1 = raw_line1[:max_x - 1].ljust(max_x - 1)
            line2 = raw_line2[:max_x - 1].ljust(max_x - 1)

            stdscr.addstr(0, 0, line1)
            stdscr.addstr(1, 0, line2)
            stdscr.refresh()
    except curses.error:
        pass

def run_benchmark_ui(stdscr, drive_path: str, file_list: list, total_drive_bytes: int):
    try:
        curses.curs_set(0)
    except Exception:
        pass
        
    stdscr.nodelay(True)
    stdscr.clear()

    stats = BenchmarkStats()
    bytes_processed_so_far = 0
    benchmark_start = time.time()
    last_ui_update = 0.0
    total_files = len(file_list)

    for idx, (path, size) in enumerate(file_list, 1):
        filename = os.path.basename(path)
        file_start = time.perf_counter()
        file_bytes_read = 0
        read_error = None

        # Force UI update at start of every file if timer elapsed (prevents skip-lags on small files)
        now_time = time.time()
        if now_time - last_ui_update >= UI_REFRESH_INTERVAL:
            update_ui(
                stdscr, idx, total_files, filename, size,
                bytes_processed_so_far, total_drive_bytes, 0,
                0.0, benchmark_start
            )
            last_ui_update = now_time

        fd, err = open_uncached_file(path)
        if err:
            stats.failed_files.append(FileResult(path, size, 0.0, 0.0, error=err))
            bytes_processed_so_far += size
            continue

        last_chunk_time = file_start
        last_chunk_bytes = 0
        current_speed_mbps = 0.0

        try:
            while True:
                chunk = os.read(fd, BLOCK_SIZE)
                if not chunk:
                    break

                chunk_len = len(chunk)
                file_bytes_read += chunk_len
                bytes_processed_so_far += chunk_len

                now = time.perf_counter()
                time_diff = now - last_chunk_time

                # Refresh metrics calculations and render screen UI on timer
                if time_diff >= UI_REFRESH_INTERVAL:
                    bytes_diff = file_bytes_read - last_chunk_bytes
                    current_speed_mbps = (bytes_diff / (1024 * 1024)) / time_diff

                    last_chunk_time = now
                    last_chunk_bytes = file_bytes_read

                    update_ui(
                        stdscr, idx, total_files, filename, size,
                        bytes_processed_so_far, total_drive_bytes, file_bytes_read,
                        current_speed_mbps, benchmark_start
                    )
                    last_ui_update = time.time()

        except Exception as e:
            read_error = str(e)
            bytes_processed_so_far += (size - file_bytes_read)
        finally:
            os.close(fd)

        file_duration = time.perf_counter() - file_start

        if read_error or file_duration == 0:
            if read_error:
                res = FileResult(path, size, file_duration, 0.0, error=read_error)
                stats.failed_files.append(res)
            continue

        file_avg_speed = (file_bytes_read / (1024 * 1024)) / file_duration
        res = FileResult(path, file_bytes_read, file_duration, file_avg_speed)
        stats.results.append(res)
        stats.total_bytes_read += file_bytes_read

    stats.total_time_sec = time.time() - benchmark_start
    return stats

def benchmark_drive(drive_path: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(script_dir, "flash_drive_benchmark.log")

    print(f"\nIndexing files on {drive_path}...")
    file_list = []
    total_drive_bytes = 0

    for root, _, files in os.walk(drive_path):
        for f in files:
            full_path = os.path.join(root, f)
            try:
                size = os.path.getsize(full_path)
                file_list.append((full_path, size))
                total_drive_bytes += size
            except Exception:
                pass

    total_files = len(file_list)
    if total_files == 0:
        print("No readable files found on the drive.")
        return

    print(f"Found {total_files} files ({format_bytes(total_drive_bytes)} total).\n")
    print("Starting read benchmark (OS Cache Bypass Active)...")
    time.sleep(1)

    stats = curses.wrapper(lambda stdscr: run_benchmark_ui(stdscr, drive_path, file_list, total_drive_bytes))

    # --- BENCHMARK REPORT DISPLAY ---
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append(f"       FLASH DRIVE BENCHMARK REPORT - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 80)

    valid_results = stats.results
    if not valid_results:
        report_lines.append("No files were read successfully.")
        if stats.failed_files:
            report_lines.append(f"Total read errors encountered: {len(stats.failed_files)}")
    else:
        overall_avg_speed = (stats.total_bytes_read / (1024 * 1024)) / stats.total_time_sec if stats.total_time_sec > 0 else 0

        report_lines.append(f"Target Drive:        {drive_path}")
        report_lines.append(f"Total Files Scanned: {total_files}")
        report_lines.append(f"Total Data Read:     {format_bytes(stats.total_bytes_read)}")
        report_lines.append(f"Total Elapsed Time:  {format_time(stats.total_time_sec)} ({stats.total_time_sec:.2f}s)")
        report_lines.append(f"\n--- Read Performance ---")
        report_lines.append(f"Average Speed:       {overall_avg_speed:.2f} MB/s")

        if valid_results:
            min_result = min(valid_results, key=lambda x: x.speed_mbps)
            max_result = max(valid_results, key=lambda x: x.speed_mbps)
            report_lines.append(f"Minimum Speed:       {min_result.speed_mbps:.2f} MB/s ({os.path.basename(min_result.path)})")
            report_lines.append(f"Maximum Speed:       {max_result.speed_mbps:.2f} MB/s ({os.path.basename(max_result.path)})")

        threshold = overall_avg_speed * 0.5
        underperforming = [
            r for r in valid_results 
            if r.speed_mbps < threshold and r.size_bytes >= 1024 * 1024
        ]

        if underperforming:
            report_lines.append(f"\n--- Underperforming Files (< {threshold:.2f} MB/s, Size >= 1MB) ---")
            report_lines.append(f"{'File Name':<45} | {'Size':<10} | {'Speed':<10}")
            report_lines.append("-" * 75)
            for r in sorted(underperforming, key=lambda x: x.speed_mbps):
                fname = os.path.basename(r.path)
                if len(fname) > 42:
                    fname = fname[:39] + "..."
                report_lines.append(f"{fname:<45} | {format_bytes(r.size_bytes):<10} | {r.speed_mbps:.2f} MB/s")

        if stats.failed_files:
            report_lines.append(f"\n--- Read Errors ({len(stats.failed_files)} file(s)) ---")
            for f in stats.failed_files:
                report_lines.append(f"FAILED: {f.path} -> Error: {f.error}")

    full_report = "\n".join(report_lines)
    print("\n" + full_report)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f_log:
            f_log.write(full_report + "\n")
        print(f"\n[+] Log saved to: {log_file_path}")
    except Exception as log_err:
        print(f"\n[-] Failed to write log file: {log_err}")

if __name__ == "__main__":
    try:
        benchmark_drive(select_drive())
        print("\n" + "="*80)
        input("Benchmark Complete. Press Enter to close this terminal window...")
    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled by user.")
        sys.exit(0)
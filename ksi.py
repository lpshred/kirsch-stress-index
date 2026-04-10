import os
import sys
import subprocess
import argparse
import platform
import time
import re
import threading
import shutil
import atexit
import glob
from datetime import datetime

# --- NEW: Bulletproof Pathing ---
# Dynamically find the root directory and the src directory
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
# --------------------------------

# Global list to keep track of running background processes
active_processes = []

def cleanup_processes():
    """Ensures all child processes are killed if the master script dies."""
    for p in active_processes:
        try:
            p.terminate()
        except:
            pass

# Register the cleanup function to run even if the script crashes
atexit.register(cleanup_processes)

def open_file_in_default_app(filepath):
    """Opens a file using the OS's default application."""
    if not os.path.exists(filepath):
        return
    try:
        if platform.system() == 'Windows':
            os.startfile(filepath)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', filepath], check=True)
        else:  # Linux
            subprocess.run(['xdg-open', filepath], check=True)
    except Exception as e:
        print(f"[\033[91mWARNING\033[0m] Could not automatically open storyboard: {e}")

def get_pgn_headers(pgn_path):
    """Parses a PGN file to extract White and Black player names safely."""
    white, black = "Unknown", "Unknown"
    if os.path.exists(pgn_path):
        with open(pgn_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            w_match = re.search(r'\[White\s+"([^"]+)"\]', content)
            b_match = re.search(r'\[Black\s+"([^"]+)"\]', content)
            
            # Added comma (,) to the regex strip list
            if w_match: white = re.sub(r'[\\/*?:"<>|,]', "", w_match.group(1)).strip()
            if b_match: black = re.sub(r'[\\/*?:"<>|,]', "", b_match.group(1)).strip()

    return white, black

def archive_latest_folder():
    """Renames the latest folder and all files inside to a permanent timestamped base name."""
    latest_dir = os.path.join("games", "latest")
    if not os.path.exists(latest_dir):
        return
        
    pgn_path = os.path.join(latest_dir, "chess.pgn")
    if not os.path.exists(pgn_path):
        shutil.rmtree(latest_dir, ignore_errors=True)
        return
        
    white, black = get_pgn_headers(pgn_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{white}_vs_{black}_{timestamp}"
    archive_dir = os.path.join("games", base_name)
    
    # Rename the directory
    for _ in range(3):
        try:
            os.rename(latest_dir, archive_dir)
            break
        except PermissionError:
            time.sleep(1)
    else:
        print(f"\n[\033[91mWARNING\033[0m] Could not rename {latest_dir}. Archive manually.")
        return

    # Rename the files inside the new directory to match the base name
    file_mappings = {
        "chess.pgn": f"{base_name}.pgn",
        "chess.csv": f"{base_name}.csv",
        "ksi_log.txt": f"{base_name}_log.txt"
    }
    
    for old_name, new_name in file_mappings.items():
        old_path = os.path.join(archive_dir, old_name)
        new_path = os.path.join(archive_dir, new_name)
        if os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
            except Exception as e:
                pass # Fail silently on file renames if locked

    print(f"\n[\033[92mSUCCESS\033[0m] Game archived safely to: {archive_dir}")

def stream_reader(pipe, prefix, color_code):
    """Reads lines from a subprocess pipe and prints them with a color-coded prefix."""
    reset_code = "\033[0m"
    for line in iter(pipe.readline, ''):
        if line:
            print(f"{color_code}[{prefix}]{reset_code} {line.strip()}")
    pipe.close()

def launch_daemon(cmd, prefix, color_code):
    """Launches a subprocess in the background and attaches threaded stdout readers."""
    cmd.insert(1, "-u") 
    p = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        bufsize=1, 
        encoding="utf-8",      # Forces Python to read the pipe as UTF-8
        errors="replace"       # Prevents crashes by replacing bad bytes with a '?'
    )
    active_processes.append(p)
    
    t = threading.Thread(target=stream_reader, args=(p.stdout, prefix, color_code), daemon=True)
    t.start()
    return p

def main():
    parser = argparse.ArgumentParser(description="Kirsch Stress Index (KSI) - Master Pipeline Wrapper")
    
    parser.add_argument("--mode", choices=["live", "full", "archive"], default="live", help="Run mode: 'live', 'full' batch analysis, or 'archive' viewer.")
    parser.add_argument("--url", help="The full URL of the live PGN file (Required for LIVE mode).")
    parser.add_argument("--pgn", help="Path to the local PGN file (Required for FULL mode).")
    parser.add_argument("--dir", help="Path to the evaluated game directory (Required for ARCHIVE mode).")
    
    parser.add_argument("--tc", choices=["auto", "classical", "rapid", "blitz"], default="auto", help="Time control mode.")
    parser.add_argument("--fast", action="store_true", help="Skip Chaos Move simulations for faster processing.")
    parser.add_argument("--no-ff", action="store_true", help="Disable fast-forwarding in live mode.")
    parser.add_argument("--sf", default=os.path.join(ROOT_DIR, "engines", "stockfish", "stockfish-windows-x86-64-avx2.exe"), help="Path to Stockfish.")
    parser.add_argument("--lc0", default=os.path.join(ROOT_DIR, "engines", "lc0", "lc0.exe"), help="Path to Lc0.")
    parser.add_argument("--weights", default=os.path.join(ROOT_DIR, "engines", "lc0", "maia-2200.pb.gz"), help="Path to Maia weights.")
    parser.add_argument("--threads", type=int, default=8, help="Number of CPU threads for Stockfish.")
    parser.add_argument("--poll", type=int, default=3, help="Live mode polling interval in seconds.")

    args = parser.parse_args()
    os.makedirs(os.path.join(ROOT_DIR, "games"), exist_ok=True)

    try:
        if args.mode == "live":
            if not args.url:
                print("[\033[91mERROR\033[0m] --url is required when running in 'live' mode.")
                sys.exit(1)
                
            archive_latest_folder()
            latest_dir = os.path.join(ROOT_DIR, "games", "latest")
            os.makedirs(latest_dir, exist_ok=True)
            
            pgn_file = os.path.join(latest_dir, "chess.pgn")
            csv_file = os.path.join(latest_dir, "chess.csv")
            log_file = os.path.join(latest_dir, "ksi_log.txt")
            
            print("=" * 60)
            print(" KSI MASTER PIPELINE: LIVE MODE INITIALIZED")
            print(f" Output Directory: {latest_dir}")
            print("=" * 60)
            
            # --- UPDATED PATHS HERE ---
            fetcher_cmd = [sys.executable, os.path.join(SRC_DIR, "ksi_fetcher.py"), args.url, "--output", pgn_file, "--poll", str(args.poll)]
            eval_cmd = [sys.executable, os.path.join(SRC_DIR, "ksi_evaluator.py"), "--mode", "live", "--pgn", pgn_file, "--csv", csv_file, 
                        "--output", log_file, "--sf", args.sf, "--lc0", args.lc0, "--weights", args.weights, 
                        "--threads", str(args.threads), "--poll", str(args.poll), "--tc", args.tc]
            if args.fast: eval_cmd.append("--fast")
            if args.no_ff: eval_cmd.append("--no-ff")
            
            vis_cmd = [sys.executable, os.path.join(SRC_DIR, "ksi_visualizer.py"), "--mode", "live", "--csv", csv_file, 
                       "--log", log_file, "--poll", str(args.poll)]
            # --------------------------
            
            launch_daemon(fetcher_cmd, "FETCHER", "\033[96m")
            time.sleep(1) 
            launch_daemon(eval_cmd, "EVALUATOR", "\033[92m")
            launch_daemon(vis_cmd, "VISUALIZER", "\033[95m")
            
            while True:
                time.sleep(1)

        elif args.mode == "full":
            if not args.pgn or not os.path.exists(args.pgn):
                print("[\033[91mERROR\033[0m] A valid --pgn file path is required when running in 'full' mode.")
                sys.exit(1)
                
            white, black = get_pgn_headers(args.pgn)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"{white}_vs_{black}_{timestamp}"
            archive_dir = os.path.join(ROOT_DIR, "games", base_name)
            os.makedirs(archive_dir, exist_ok=True)
            
            pgn_file = os.path.join(archive_dir, f"{base_name}.pgn")
            csv_file = os.path.join(archive_dir, f"{base_name}.csv")
            log_file = os.path.join(archive_dir, f"{base_name}_log.txt")
            md_file  = os.path.join(archive_dir, f"{base_name}_storyboard.md")
            
            shutil.copy2(args.pgn, pgn_file)
            
            print("=" * 60)
            print(" KSI MASTER PIPELINE: FULL MODE INITIALIZED")
            print(f" Match: {white} vs {black}")
            print(f" Output Directory: {archive_dir}")
            print("=" * 60)
            
            # --- UPDATED PATHS HERE ---
            eval_cmd = [sys.executable, "-u", os.path.join(SRC_DIR, "ksi_evaluator.py"), "--mode", "full", "--pgn", pgn_file, "--csv", csv_file, 
                        "--output", log_file, "--sf", args.sf, "--lc0", args.lc0, "--weights", args.weights, "--threads", str(args.threads), "--tc", args.tc]
            if args.fast: eval_cmd.append("--fast")
            
            story_cmd = [sys.executable, "-u", os.path.join(SRC_DIR, "ksi_storyboard.py"), csv_file, "--out", md_file]
            vis_cmd = [sys.executable, os.path.join(SRC_DIR, "ksi_visualizer.py"), "--mode", "live", "--csv", csv_file, "--log", log_file, "--poll", "5"]
            # --------------------------
            
            print("\n[\033[92mPHASE 1\033[0m] Running Evaluator...")
            p_eval = subprocess.Popen(eval_cmd)
            active_processes.append(p_eval)
            p_eval.wait() 
            active_processes.remove(p_eval)
            
            print("\n[\033[93mPHASE 2\033[0m] Generating Storyboard...")
            p_story = subprocess.Popen(story_cmd)
            active_processes.append(p_story)
            p_story.wait()
            active_processes.remove(p_story)

            print("[\033[94mSYSTEM\033[0m] Opening Storyboard...")
            open_file_in_default_app(md_file)
            
            print("\n[\033[95mPHASE 3\033[0m] Launching Interactive Visualizer...")
            print("[\033[95mINFO\033[0m] Dashboard is running. Press Ctrl+C to exit when finished.")
            
            launch_daemon(vis_cmd, "VISUALIZER", "\033[95m")
            
            while True:
                time.sleep(1)

        elif args.mode == "archive":
            if not args.dir or not os.path.isdir(args.dir):
                print("[\033[91mERROR\033[0m] A valid directory path (--dir) is required when running in 'archive' mode.")
                sys.exit(1)
                
            print("=" * 60)
            print(" KSI MASTER PIPELINE: ARCHIVE VIEWER")
            print(f" Target Directory: {args.dir}")
            print("=" * 60)

            # Auto-discover the CSV and Log files in the directory
            csv_files = glob.glob(os.path.join(args.dir, "*.csv"))
            log_files = glob.glob(os.path.join(args.dir, "*_log.txt")) + glob.glob(os.path.join(args.dir, "ksi_log.txt"))
            md_files  = glob.glob(os.path.join(args.dir, "*.md"))

            if not csv_files:
                print(f"[\033[91mERROR\033[0m] Could not find a .csv file in {args.dir}")
                sys.exit(1)

            csv_file = csv_files[0]
            log_file = log_files[0] if log_files else None

            print(f"[\033[94mSYSTEM\033[0m] Found CSV: {os.path.basename(csv_file)}")
            if log_file:
                print(f"[\033[94mSYSTEM\033[0m] Found Log: {os.path.basename(log_file)}")
                
            if md_files:
                print(f"[\033[94mSYSTEM\033[0m] Found Storyboard: {os.path.basename(md_files[0])}")
                open_file_in_default_app(md_files[0])

            # --- UPDATED PATH HERE ---
            vis_cmd = [sys.executable, os.path.join(SRC_DIR, "ksi_visualizer.py"), "--mode", "live", "--csv", csv_file, "--poll", "5"]
            if log_file:
                vis_cmd.extend(["--log", log_file])
            # -------------------------

            print("\n[\033[95mINFO\033[0m] Dashboard is running. Press Ctrl+C to exit when finished.")
            launch_daemon(vis_cmd, "VISUALIZER", "\033[95m")
            
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n[\033[93mSYSTEM\033[0m] KeyboardInterrupt detected. Shutting down gracefully...")
        
    finally:
        cleanup_processes()
        time.sleep(1.5) 
        
        if args.mode == "live":
            archive_latest_folder()
            
        print("[\033[93mSYSTEM\033[0m] Shutdown complete.")

if __name__ == "__main__":
    main()
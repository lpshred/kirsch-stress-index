import urllib.request
import time
import argparse
from datetime import datetime

def download_pgn(url, output_file):
    # Lichess prefers bots/scripts to identify themselves
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'KSILiveFetcher/1.0'
        }
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            pgn_data = response.read().decode('utf-8')
            
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(pgn_data)
            
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Successfully updated {output_file}")
        
    except Exception as e:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Error fetching PGN: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live PGN Fetcher for the Kirsch Stress Index")
    
    # The URL is a required positional argument
    parser.add_argument("url", help="The full URL of the live PGN file to fetch.")
    
    # Optional arguments with defaults
    parser.add_argument("--output", default="../chess.pgn", help="Output filename (default: chess.pgn)")
    parser.add_argument("--poll", type=int, default=10, help="Polling interval in seconds (default: 10)")
    
    args = parser.parse_args()

    print(f"[*] Starting live PGN fetcher...")
    print(f"[*] Target: {args.url}")
    print(f"[*] Output: {args.output}")
    print(f"[*] Interval: {args.poll} seconds")
    print("-" * 40)
    
    while True:
        download_pgn(args.url, args.output)
        time.sleep(args.poll)
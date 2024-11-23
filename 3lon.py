import time
import requests
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('memecoin_monitor.log'),
        logging.StreamHandler()
    ]
)

USAGE = """
Memecoin Market Monitor - Track potential memecoin opportunities

Usage:
    python script.py           Run the monitor with default settings
    python script.py clean     Start fresh by removing existing data files
    python script.py help      Show this help message

The script will:
    - Monitor DexScreener for new memecoins
    - Track tokens across multiple chains
    - Save findings to memecoin_data.csv
    - Log all activities to memecoin_monitor.log

Data files:
    - memecoin_data.csv       Token data and metrics
    - memecoin_watchlist.json Configuration and tracked tokens
    - memecoin_monitor.log    Activity log

Press Ctrl+C to stop monitoring
"""

class MemecoinMonitor:
    def __init__(self, watchlist_file: str = 'memecoin_watchlist.json'):
        self.watchlist_file = watchlist_file
        self.watchlist = self.load_watchlist()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def load_watchlist(self) -> Dict:
        """Load or create watchlist of memecoins to track."""
        try:
            if Path(self.watchlist_file).exists():
                with open(self.watchlist_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error loading watchlist: {e}")
        
        # Default watchlist if file doesn't exist
        default_watchlist = {
            "keywords": [
                "pepe", "wojak", "doge", "shib", "floki", "inu", "elon",
                "moon", "safe", "chad", "based", "wojak", "meme"
            ],
            "trending_tokens": {},
            "blacklisted_tokens": [],  # Changed from set to list
            "chains": [
                "ethereum", "bsc", "arbitrum", "polygon"
            ]
        }
        self.save_watchlist(default_watchlist)
        return default_watchlist

    def save_watchlist(self, watchlist: Dict):
        """Save watchlist to file."""
        try:
            # Ensure blacklisted_tokens is a list before saving
            if isinstance(watchlist.get('blacklisted_tokens'), set):
                watchlist['blacklisted_tokens'] = list(watchlist['blacklisted_tokens'])
            
            with open(self.watchlist_file, 'w') as f:
                json.dump(watchlist, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving watchlist: {e}")

    def search_dexscreener(self, query: str) -> Optional[Dict]:
        """Search DexScreener API for a given query."""
        url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error searching DexScreener for {query}: {e}")
            return None

    def get_token_info(self, pair: Dict) -> Dict:
        """Extract relevant token information from a pair."""
        return {
            'timestamp': datetime.now().isoformat(),
            'token_name': pair.get('baseToken', {}).get('name'),
            'token_symbol': pair.get('baseToken', {}).get('symbol'),
            'token_address': pair.get('baseToken', {}).get('address'),
            'chain': pair.get('chainId'),
            'dex': pair.get('dexId'),
            'price_usd': pair.get('priceUsd'),
            'price_change_24h': pair.get('priceChange', {}).get('h24'),
            'volume_24h': pair.get('volume', {}).get('h24'),
            'liquidity_usd': pair.get('liquidity', {}).get('usd'),
            'pair_address': pair.get('pairAddress'),
            'created_at': pair.get('pairCreatedAt')
        }

    def analyze_token(self, token_info: Dict) -> bool:
        """Analyze if a token is worth tracking based on criteria."""
        try:
            # Skip if token is blacklisted
            if token_info['token_address'] in self.watchlist.get('blacklisted_tokens', []):
                return False

            # Basic criteria for tracking
            if all([
                token_info['liquidity_usd'] and float(token_info['liquidity_usd']) > 10000,  # Min $10k liquidity
                token_info['volume_24h'] and float(token_info['volume_24h']) > 5000,  # Min $5k daily volume
                token_info['chain'] in self.watchlist['chains']  # Supported chain
            ]):
                return True
        except Exception as e:
            logging.error(f"Error analyzing token: {e}")
        return False

    def scan_new_tokens(self):
        """Scan for new potential memecoin tokens."""
        all_tokens = []
        
        for keyword in self.watchlist['keywords']:
            logging.info(f"Searching for tokens with keyword: {keyword}")
            
            results = self.search_dexscreener(keyword)
            if not results or 'pairs' not in results:
                continue
                
            for pair in results['pairs']:
                token_info = self.get_token_info(pair)
                if self.analyze_token(token_info):
                    all_tokens.append(token_info)
                    
            time.sleep(1)  # Rate limiting
        
        return all_tokens

    def save_results(self, tokens: List[Dict], filename: str = 'memecoin_data.csv'):
        """Save token data to CSV file."""
        if not tokens:
            return
            
        df = pd.DataFrame(tokens)
        mode = 'a' if Path(filename).exists() else 'w'
        df.to_csv(filename, mode=mode, header=(mode == 'w'), index=False)
        logging.info(f"Saved {len(tokens)} tokens to {filename}")

    def clean_data_files(self):
        """Remove all data files to start fresh."""
        files = ['memecoin_data.csv', 'memecoin_watchlist.json', 'memecoin_monitor.log']
        for file in files:
            try:
                Path(file).unlink(missing_ok=True)
            except Exception as e:
                logging.error(f"Error removing {file}: {e}")
        logging.info("All data files cleaned")

def main():
    # Show usage if no arguments or help requested
    if len(sys.argv) > 1:
        if sys.argv[1] in ['help', '-h', '--help']:
            print(USAGE)
            sys.exit(0)
        elif sys.argv[1] == 'clean':
            monitor = MemecoinMonitor()
            monitor.clean_data_files()
            print("Data files cleaned. Starting fresh...")
        else:
            print(USAGE)
            sys.exit(1)
    else:
        print(USAGE)
    
    monitor = MemecoinMonitor()
    
    print("\nStarting memecoin monitor... Press Ctrl+C to stop.\n")
    
    while True:
        try:
            logging.info("Starting new scan...")
            tokens = monitor.scan_new_tokens()
            monitor.save_results(tokens)
            
            # Update trending tokens in watchlist
            monitor.watchlist['trending_tokens'] = {
                token['token_address']: {
                    'symbol': token['token_symbol'],
                    'last_seen': datetime.now().isoformat()
                }
                for token in tokens
            }
            monitor.save_watchlist(monitor.watchlist)
            
            logging.info(f"Scan complete. Found {len(tokens)} potential tokens.")
            logging.info("Waiting 5 minutes before next scan...")
            time.sleep(300)  # Wait 5 minutes between scans
            
        except KeyboardInterrupt:
            logging.info("Monitoring stopped by user.")
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main()

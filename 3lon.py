import time
import requests
import pandas as pd
import json
import curses
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import sys

# Keep your existing logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('memecoin_monitor.log'),
        logging.StreamHandler()
    ]
)

class PatternAnalyzer:
    # Your existing PatternAnalyzer class remains unchanged
    def __init__(self, buy_threshold: float = 1.1, sell_threshold: float = 0.8):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def detect_pump_and_dump(self, volume_data: pd.Series) -> bool:
        avg_volume = volume_data.mean()
        max_volume = volume_data.max()
        min_volume = volume_data.min()
        pump_detected = max_volume > 3 * avg_volume
        dump_detected = min_volume < 0.5 * avg_volume
        return pump_detected and dump_detected

    def detect_steady_growth(self, volume_data: pd.Series) -> bool:
        changes = volume_data.pct_change()
        return all(-0.05 < change < 0.10 for change in changes[1:])

    def detect_whale_accumulation(self, volume_data: pd.Series) -> bool:
        avg_volume = volume_data.mean()
        return volume_data.max() > 2 * avg_volume

    def analyze(self, volume_data: pd.Series) -> str:
        if self.detect_pump_and_dump(volume_data):
            return "Pump and Dump"
        elif self.detect_whale_accumulation(volume_data):
            return "Whale Accumulation"
        elif self.detect_steady_growth(volume_data):
            return "Steady Growth"
        return "No Pattern"

    def should_buy(self, volume_data: pd.Series) -> bool:
        avg_volume = volume_data.mean()
        current_volume = volume_data.iloc[-1]
        return current_volume > self.buy_threshold * avg_volume

    def should_sell(self, volume_data: pd.Series, avg_pump_volume: float) -> bool:
        current_volume = volume_data.iloc[-1]
        return current_volume < self.sell_threshold * avg_pump_volume

class PaperTraderUI:
    def __init__(self, initial_capital=10000):
        self.capital = initial_capital
        self.positions = {}
        self.trade_history = []
        self.current_page = 'main'
        self.selected_token = None
        self.message = ""
        self.message_timeout = 0
        self.monitor = None
        self.pattern_analyzer = PatternAnalyzer()
        self.current_token_data = {}
        # Input handling attributes
        self.input_mode = False
        self.current_input = ""
        self.input_prompt = ""
        self.input_callback = None
        self.trade_input_state = {
            'token_address': '',
            'amount': '',
            'side': ''
        }

    def set_monitor(self, monitor):
        """Set reference to MemecoinMonitor instance"""
        self.monitor = monitor

    def display_main_menu(self, stdscr, height, width):
        """Display main menu screen"""
        menu_items = [
            "1. View Portfolio",
            "2. Execute Trade",
            "3. View Trade History",
            "4. Token Scanner",
            "5. Risk Calculator"
        ]
        
        stdscr.addstr(3, 0, "=== Main Menu ===", curses.A_BOLD)
        
        for i, item in enumerate(menu_items, start=5):
            stdscr.addstr(i, 2, item)
        
        # Instructions
        stdscr.addstr(12, 2, "Use keyboard to navigate:")
        stdscr.addstr(13, 4, "[p] Portfolio")
        stdscr.addstr(14, 4, "[t] Trade")
        stdscr.addstr(15, 4, "[h] History")
        stdscr.addstr(16, 4, "[s] Scanner")
        stdscr.addstr(17, 4, "[q] Quit")

    def display_portfolio(self, stdscr, height, width):
        """Display portfolio screen"""
        stdscr.addstr(3, 0, "=== Portfolio ===", curses.A_BOLD)
        if not self.positions:
            stdscr.addstr(5, 2, "No positions open")
            return
            
        headers = ["Token", "Amount", "Avg Price", "Current Price", "P&L"]
        stdscr.addstr(5, 2, " | ".join(headers))
        
        row = 7
        for token, amount in self.positions.items():
            if self.update_token_data(token):
                current_price = float(self.current_token_data['price_usd'])
                trades = [t for t in self.trade_history if t['token_address'] == token]
                avg_price = sum(t['price'] * t['amount'] for t in trades) / sum(t['amount'] for t in trades)
                pnl = (current_price - avg_price) * amount
                
                position_str = (f"{token[:10]} | {amount:.4f} | ${avg_price:.8f} | "
                              f"${current_price:.8f} | ${pnl:.2f}")
                color = curses.color_pair(1) if pnl >= 0 else curses.color_pair(2)
                stdscr.addstr(row, 2, position_str, color)
                row += 1

        def display_trade_screen(self, stdscr, height, width):
         """Display trading screen with input handling"""
        stdscr.addstr(3, 0, "=== Execute Trade ===", curses.A_BOLD)
        
        # Show current token info if selected
        if self.selected_token and self.current_token_data:
            stdscr.addstr(5, 2, f"Selected Token: {self.current_token_data['token_symbol']}")
            stdscr.addstr(6, 2, f"Current Price: ${float(self.current_token_data['price_usd']):.8f}")
            stdscr.addstr(7, 2, f"24h Change: {self.current_token_data['price_change_24h']}%")
            stdscr.addstr(8, 2, f"Pattern: {self.current_token_data.get('pattern', 'Unknown')}")
        
        # Trade input form
        start_row = 10
        stdscr.addstr(start_row, 2, "Token address: " + self.trade_input_state['token_address'])
        stdscr.addstr(start_row + 1, 2, "Amount: " + self.trade_input_state['amount'])
        stdscr.addstr(start_row + 2, 2, "Side (buy/sell): " + self.trade_input_state['side'])
        
        # Show input instructions
        stdscr.addstr(start_row + 4, 2, "Press: [1] Enter token [2] Enter amount [3] Enter side [Enter] Execute trade")
        
        # Show current input if in input mode
        if self.input_mode:
            stdscr.addstr(height-3, 0, f"{self.input_prompt}: {self.current_input}")

    def display_trade_history(self, stdscr, height, width):
        """Display trade history screen"""
        stdscr.addstr(3, 0, "=== Trade History ===", curses.A_BOLD)
        if not self.trade_history:
            stdscr.addstr(5, 2, "No trades executed")
            return
            
        headers = ["Time", "Token", "Side", "Amount", "Price", "Slippage"]
        stdscr.addstr(5, 2, " | ".join(headers))
        
        for i, trade in enumerate(reversed(self.trade_history[-10:]), start=7):
            row = (f"{trade['timestamp'].strftime('%H:%M:%S')} | "
                  f"{trade['token_address'][:8]} | "
                  f"{trade['side'].upper()} | "
                  f"{trade['amount']:.4f} | "
                  f"${trade['price']:.8f} | "
                  f"{(trade['slippage']/trade['price'])*100:.2f}%")
            color = curses.color_pair(1) if trade['side'] == 'buy' else curses.color_pair(2)
            stdscr.addstr(i, 2, row, color)

    def display_scanner(self, stdscr, height, width):
        """Display token scanner screen"""
        stdscr.addstr(3, 0, "=== Token Scanner ===", curses.A_BOLD)
        if self.monitor:
            tokens = self.monitor.scan_new_tokens()
            if tokens:
                headers = ["Token", "Price", "24h Change", "Pattern"]
                stdscr.addstr(5, 2, " | ".join(headers))
                for i, token in enumerate(tokens[:10], start=7):
                    volume_data = pd.Series([float(token['volume_24h']) * (1 + 0.1 * i) for i in range(5)])
                    pattern = self.pattern_analyzer.analyze(volume_data)
                    row = f"{token['token_symbol'][:10]} | ${float(token['price_usd']):.8f} | {token['price_change_24h']}% | {pattern}"
                    color = curses.color_pair(1) if float(token['price_change_24h']) >= 0 else curses.color_pair(2)
                    stdscr.addstr(i, 2, row, color)
            else:
                stdscr.addstr(5, 2, "No tokens found")

    def update_token_data(self, token_address: str) -> bool:
        """Update current token data from API"""
        if self.monitor:
            results = self.monitor.search_dexscreener(token_address)
            if results and 'pairs' in results and results['pairs']:
                pair = results['pairs'][0]
                self.current_token_data = self.monitor.get_token_info(pair)
                volume_data = pd.Series([float(pair['volume']['h24']) for _ in range(5)])
                pattern = self.pattern_analyzer.analyze(volume_data)
                self.current_token_data['pattern'] = pattern
                return True
        return False



    def get_user_input(self, stdscr, prompt: str, callback):
        """Start input mode with a prompt and callback"""
        self.input_mode = True
        self.input_prompt = prompt
        self.current_input = ""
        self.input_callback = callback
        
    def handle_input_mode(self, stdscr, key):
        """Handle input when in input mode"""
        if key == 27:  # ESC
            self.input_mode = False
            self.current_input = ""
            return
        
        if key == 10:  # Enter
            if self.input_callback:
                self.input_callback(self.current_input)
            self.input_mode = False
            self.current_input = ""
            return
            
        if key == curses.KEY_BACKSPACE or key == 127:  # Backspace
            self.current_input = self.current_input[:-1]
        elif 32 <= key <= 126:  # Printable characters
            self.current_input += chr(key)

    def display_trade_screen(self, stdscr, height, width):
        """Display trading screen with input handling"""
        stdscr.addstr(3, 0, "=== Execute Trade ===", curses.A_BOLD)
        
        # Show current token info if selected
        if self.selected_token and self.current_token_data:
            stdscr.addstr(5, 2, f"Selected Token: {self.current_token_data['token_symbol']}")
            stdscr.addstr(6, 2, f"Current Price: ${float(self.current_token_data['price_usd']):.8f}")
            stdscr.addstr(7, 2, f"24h Change: {self.current_token_data['price_change_24h']}%")
            stdscr.addstr(8, 2, f"Pattern: {self.current_token_data.get('pattern', 'Unknown')}")
        
        # Trade input form
        start_row = 10
        stdscr.addstr(start_row, 2, "Token address: " + self.trade_input_state['token_address'])
        stdscr.addstr(start_row + 1, 2, "Amount: " + self.trade_input_state['amount'])
        stdscr.addstr(start_row + 2, 2, "Side (buy/sell): " + self.trade_input_state['side'])
        
        # Show input instructions
        stdscr.addstr(start_row + 4, 2, "Press: [1] Enter token [2] Enter amount [3] Enter side [Enter] Execute trade")
        
        # Show current input if in input mode
        if self.input_mode:
            stdscr.addstr(height-3, 0, f"{self.input_prompt}: {self.current_input}")

    def handle_trade_input(self, key):
        """Handle input specifically for the trade screen"""
        if self.current_page == 'trade':
            if key == ord('1'):
                self.get_user_input(None, "Enter token address", 
                    lambda x: setattr(self, 'trade_input_state', {**self.trade_input_state, 'token_address': x}))
            elif key == ord('2'):
                self.get_user_input(None, "Enter amount", 
                    lambda x: setattr(self, 'trade_input_state', {**self.trade_input_state, 'amount': x}))
            elif key == ord('3'):
                self.get_user_input(None, "Enter side (buy/sell)", 
                    lambda x: setattr(self, 'trade_input_state', {**self.trade_input_state, 'side': x}))
            elif key == 10:  # Enter key
                self.execute_trade_from_input()

    def execute_trade_from_input(self):
        """Execute trade based on input state"""
        try:
            if all(self.trade_input_state.values()):
                amount = float(self.trade_input_state['amount'])
                token = self.trade_input_state['token_address']
                side = self.trade_input_state['side'].lower()
                
                if self.monitor:
                    api_data = self.monitor.search_dexscreener(token)
                    if api_data and 'pairs' in api_data and api_data['pairs']:
                        price = float(api_data['pairs'][0]['priceUsd'])
                        self.execute_trade(token, price, amount, side)
                        # Clear input state after successful trade
                        self.trade_input_state = {'token_address': '', 'amount': '', 'side': ''}
                    else:
                        self.set_message("Error: Could not fetch token price")
                else:
                    self.set_message("Error: Monitor not initialized")
        except ValueError:
            self.set_message("Error: Invalid amount")
        except Exception as e:
            self.set_message(f"Error executing trade: {str(e)}")

    def handle_input(self, key):
        """Handle user input"""
        if self.input_mode:
            self.handle_input_mode(None, key)
            return

        if key == ord('m'):
            self.current_page = 'main'
        elif key == ord('p'):
            self.current_page = 'portfolio'
        elif key == ord('t'):
            self.current_page = 'trade'
        elif key == ord('h'):
            self.current_page = 'history'
        elif key == ord('s'):
            self.current_page = 'scanner'
        
        # Handle trade-specific inputs
        self.handle_trade_input(key)

    def run_ui(self, stdscr):
        """Main UI loop"""
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.curs_set(1)  # Show cursor
        stdscr.nodelay(0)   # Make getch() blocking
        
        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            
            # Header
            stdscr.addstr(0, 0, "=== Memecoin Paper Trading Terminal ===", curses.A_BOLD)
            stdscr.addstr(1, 0, f"Capital: ${self.capital:.2f}", curses.color_pair(1))
            
            # Display current page content
            if self.current_page == 'main':
                self.display_main_menu(stdscr, height, width)
            elif self.current_page == 'portfolio':
                self.display_portfolio(stdscr, height, width)
            elif self.current_page == 'trade':
                self.display_trade_screen(stdscr, height, width)
            elif self.current_page == 'history':
                self.display_trade_history(stdscr, height, width)
            elif self.current_page == 'scanner':
                self.display_scanner(stdscr, height, width)
            
            # Footer
            if time.time() < self.message_timeout:
                stdscr.addstr(height-2, 0, self.message, curses.color_pair(3))
            stdscr.addstr(height-1, 0, "Commands: [q]uit [m]ain [p]ortfolio [t]rade [h]istory [s]canner")
            
            # Handle input
            key = stdscr.getch()
            if key == ord('q'):
                break
                
            self.handle_input(key)
            stdscr.refresh()

class MemecoinMonitor:
    def __init__(self, watchlist_file: str = 'memecoin_watchlist.json'):
        self.watchlist_file = watchlist_file
        self.watchlist = self.load_watchlist()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.pattern_analyzer = PatternAnalyzer()
        self.paper_trader = PaperTraderUI()

    def load_watchlist(self) -> Dict:
        try:
            if Path(self.watchlist_file).exists():
                with open(self.watchlist_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error loading watchlist: {e}")

        default_watchlist = {
            "keywords": ["pepe", "wojak", "doge", "shib", "floki", "inu", "elon", "moon", "safe", "chad", "based", "wojak", "meme"],
            "trending_tokens": {},
            "blacklisted_tokens": [],
            "chains": ["ethereum", "bsc", "arbitrum", "polygon"]
        }
        self.save_watchlist(default_watchlist)
        return default_watchlist

    def save_watchlist(self, watchlist: Dict):
        try:
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

    def scan_new_tokens(self):
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
            time.sleep(1)
        return all_tokens

    def save_results(self, tokens: List[Dict], filename: str = 'memecoin_data.csv'):
        if not tokens:
            return

        results = []
        for token in tokens:
            volume_data = pd.Series([float(token['volume_24h']) * (1 + 0.1 * i) for i in range(5)])
            token['pattern'] = self.pattern_analyzer.analyze(volume_data)
            if self.pattern_analyzer.should_buy(volume_data):
                token['decision'] = 'Buy'
                self.paper_trader.execute_trade(token['token_address'], float(token['price_usd']), 1, side='buy')
            elif self.pattern_analyzer.should_sell(volume_data, volume_data.mean() * 1.5):
                token['decision'] = 'Sell'
                self.paper_trader.execute_trade(token['token_address'], float(token['price_usd']), 1, side='sell')
            else:
                token['decision'] = 'Hold'
            results.append(token)

        df = pd.DataFrame(results)
        mode = 'a' if Path(filename).exists() else 'w'
        df.to_csv(filename, mode=mode, header=(mode == 'w'), index=False)
        logging.info(f"Saved {len(tokens)} tokens to {filename}")

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
            if token_info['token_address'] in self.watchlist.get('blacklisted_tokens', []):
                return False
            if all([
                token_info['liquidity_usd'] and float(token_info['liquidity_usd']) > 10000,
                token_info['volume_24h'] and float(token_info['volume_24h']) > 5000,
                token_info['price_usd'] and float(token_info['price_usd']) > 0.000001
            ]):
                return True
        except Exception as e:
            logging.error(f"Error analyzing token: {e}")
        return False


def main():
    monitor = MemecoinMonitor()
    print("\nStarting memecoin monitor and UI... Press Ctrl+C to stop.\n")

    # Set up the paper trader UI
    monitor.paper_trader.set_monitor(monitor)
    
    try:
        # Start curses UI
        curses.wrapper(monitor.paper_trader.run_ui)
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user.")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        # Cleanup curses
        curses.endwin()

if __name__ == "__main__":
    main()
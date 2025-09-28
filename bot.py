from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account
from aiohttp import ClientResponseError, ClientSession, ClientTimeout, BasicAuth
from aiohttp_socks import ProxyConnector
from datetime import datetime
from colorama import *
import asyncio, random, json, re, os, pytz

wib = pytz.timezone('Asia/Jakarta')

class Ekox:
    def __init__(self) -> None:
        self.RPC_URL = "https://ethereum-holesky-rpc.publicnode.com/"
        self.EXPLORER = "https://holesky.etherscan.io/tx/"
        self.ETH_CONTRACT_ADDRESS = "0x0000000000000000000000000000000000000000"
        self.WETH_CONTRACT_ADDRESS = "0x94373a4919B3240D86eA41593D5eBa789FEF3848"
        self.exETH_CONTRACT_ADDRESS = "0xDD1ec7e2c5408aB7199302d481a1b77FdA0267A3"
        self.RESTAKE_CONTRACT_ADDRESS = "0x0c6A085e9d17A51DEA2A7e954ACcAb1429213B75"
        self.WITHDRAW_CONTRACT_ADDRESS = "0x3Cc99498dea7a164C9d6D02C7710FF63f36A60ed"
        self.WRAP_CONTRACT_ABI = json.loads('''[
            {"type":"function","name":"deposit","stateMutability":"payable","inputs":[],"outputs":[]},
            {"type":"function","name":"withdraw","stateMutability":"nonpayable","inputs":[{"name":"wad","type":"uint256"}],"outputs":[]}
        ]''')
        self.ERC20_CONTRACT_ABI = json.loads('''[
            {"type":"function","name":"balanceOf","stateMutability":"view","inputs":[{"name":"address","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"allowance","stateMutability":"view","inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"approve","stateMutability":"nonpayable","inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
            {"type":"function","name":"getOutstandingWithdrawRequests","stateMutability":"view","inputs":[{"internalType":"address","name":"user","type":"address"}],"outputs":[{"internalType":"uint256","name":"","type":"uint256"}]},
            {"type":"function","name":"deposit","stateMutability":"nonpayable","inputs":[{"internalType":"address","name":"_collateralToken","type":"address"},{"internalType":"uint256","name":"_amount","type":"uint256"}],"outputs":[]},
            {"type":"function","name":"withdraw","stateMutability":"nonpayable","inputs":[{"internalType":"uint256","name":"_amount","type":"uint256"},{"internalType":"address","name":"_assetOut","type":"address"}],"outputs":[]},
            {"type":"function","name":"claim","stateMutability":"nonpayable","inputs":[{"internalType":"uint256","name":"withdrawRequestIndex","type":"uint256"},{"internalType":"address","name":"user","type":"address"}],"outputs":[]}
        ]''')
        self.proxies = []
        self.proxy_index = 0
        self.account_proxies = {}
        self.used_nonce = {}
        self.make_transfer = False
        self.recepients = []
        self.transfer_amount = 0
        self.wrap_option = 0
        self.wrap_amount = 0
        self.restake_count = 0
        self.restake_amount = 0
        self.withdraw_count = 0
        self.withdraw_amount = 0
        self.min_delay = 0
        self.max_delay = 0

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message):
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}{message}",
            flush=True
        )

    def welcome(self):
        print(
            f"""
        {Fore.GREEN + Style.BRIGHT}Ekox{Fore.BLUE + Style.BRIGHT} Auto BOT
            """
            f"""
        {Fore.GREEN + Style.BRIGHT}Rey? {Fore.YELLOW + Style.BRIGHT}<INI WATERMARK>
            """
        )

    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    
    async def load_proxies(self):
        filename = "proxy.txt"
        try:
            if not os.path.exists(filename):
                self.log(f"{Fore.RED + Style.BRIGHT}File {filename} Not Found.{Style.RESET_ALL}")
                return
            with open(filename, 'r') as f:
                self.proxies = [line.strip() for line in f.read().splitlines() if line.strip()]
            
            if not self.proxies:
                self.log(f"{Fore.RED + Style.BRIGHT}No Proxies Found.{Style.RESET_ALL}")
                return

            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Proxies Total  : {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(self.proxies)}{Style.RESET_ALL}"
            )
        
        except Exception as e:
            self.log(f"{Fore.RED + Style.BRIGHT}Failed To Load Proxies: {e}{Style.RESET_ALL}")
            self.proxies = []

    def check_proxy_schemes(self, proxies):
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxies.startswith(scheme) for scheme in schemes):
            return proxies
        return f"http://{proxies}"

    def get_next_proxy_for_account(self, token):
        if token not in self.account_proxies:
            if not self.proxies:
                return None
            proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
            self.account_proxies[token] = proxy
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return self.account_proxies[token]

    def rotate_proxy_for_account(self, token):
        if not self.proxies:
            return None
        proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
        self.account_proxies[token] = proxy
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return proxy
    
    def build_proxy_config(self, proxy=None):
        if not proxy:
            return None, None, None

        if proxy.startswith("socks"):
            connector = ProxyConnector.from_url(proxy)
            return connector, None, None

        elif proxy.startswith("http"):
            match = re.match(r"http://(.*?):(.*?)@(.*)", proxy)
            if match:
                username, password, host_port = match.groups()
                clean_url = f"http://{host_port}"
                auth = BasicAuth(username, password)
                return None, clean_url, auth
            else:
                return None, proxy, None

        raise Exception("Unsupported Proxy Type.")
    
    def generate_address(self, account: str):
        try:
            account = Account.from_key(account)
            address = account.address
            
            return address
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Status    :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Generate Address Failed {Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}                  "
            )
            return None
        
    def mask_account(self, account):
        try:
            mask_account = account[:6] + '*' * 6 + account[-6:]
            return mask_account
        except Exception as e:
            return None

    async def get_web3_with_check(self, address: str, use_proxy: bool, retries=3, timeout=60):
        request_kwargs = {"timeout": timeout}

        proxy = self.get_next_proxy_for_account(address) if use_proxy else None

        if use_proxy and proxy:
            request_kwargs["proxies"] = {"http": proxy, "https": proxy}

        for attempt in range(retries):
            try:
                web3 = Web3(Web3.HTTPProvider(self.RPC_URL, request_kwargs=request_kwargs))
                web3.eth.get_block_number()
                return web3
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                    continue
                raise Exception(f"Failed to Connect to RPC: {str(e)}")
            
    async def send_raw_transaction_with_retries(self, account, web3, tx, retries=5):
        for attempt in range(retries):
            try:
                signed_tx = web3.eth.account.sign_transaction(tx, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                return tx_hash
            except TransactionNotFound:
                pass
            except Exception as e:
                self.log(
                    f"{Fore.CYAN + Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                    f"{Fore.YELLOW + Style.BRIGHT} [Attempt {attempt + 1}] Send TX Error: {str(e)} {Style.RESET_ALL}"
                )
            await asyncio.sleep(2 ** attempt)
        raise Exception("Transaction Hash Not Found After Maximum Retries")

    async def wait_for_receipt_with_retries(self, web3, tx_hash, retries=5):
        for attempt in range(retries):
            try:
                receipt = await asyncio.to_thread(web3.eth.wait_for_transaction_receipt, tx_hash, timeout=300)
                return receipt
            except TransactionNotFound:
                pass
            except Exception as e:
                self.log(
                    f"{Fore.CYAN + Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                    f"{Fore.YELLOW + Style.BRIGHT} [Attempt {attempt + 1}] Wait for Receipt Error: {str(e)} {Style.RESET_ALL}"
                )
            await asyncio.sleep(2 ** attempt)
        raise Exception("Transaction Receipt Not Found After Maximum Retries")
        
    async def get_token_balance(self, address: str, contract_address: str, use_proxy: bool, retries=5):
        for attempt in range(retries):
            try:
                web3 = await self.get_web3_with_check(address, use_proxy)

                if contract_address == self.ETH_CONTRACT_ADDRESS:
                    balance = web3.eth.get_balance(address)
                else:
                    token_contract = web3.eth.contract(address=web3.to_checksum_address(contract_address), abi=self.ERC20_CONTRACT_ABI)
                    balance = token_contract.functions.balanceOf(address).call()

                token_balance = balance / (10**18)

                return token_balance
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )
                return None
        
    async def get_outstanding_withdraw(self, address: str, use_proxy: bool, retries=5):
        for attempt in range(retries):
            try:
                web3 = await self.get_web3_with_check(address, use_proxy)

                contract_address = web3.to_checksum_address(self.WITHDRAW_CONTRACT_ADDRESS)
                token_contract = web3.eth.contract(address=contract_address, abi=self.ERC20_CONTRACT_ABI)
                index = token_contract.functions.getOutstandingWithdrawRequests(address).call()

                return index
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )
                return None
            
    async def perform_transfer(self, account: str, address: str, recepient: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)

            amount_to_wei = web3.to_wei(self.transfer_amount, "ether")

            max_priority_fee = web3.to_wei(1, "gwei")
            max_fee = max_priority_fee

            transfer_tx = {
                "from": web3.to_checksum_address(address),
                "to": web3.to_checksum_address(recepient),
                "value": amount_to_wei,
                "gas": 21000,
                "maxFeePerGas": int(max_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": self.used_nonce[address],
                "chainId": web3.eth.chain_id,
            }

            tx_hash = await self.send_raw_transaction_with_retries(account, web3, transfer_tx)
            receipt = await self.wait_for_receipt_with_retries(web3, tx_hash)

            block_number = receipt.blockNumber
            self.used_nonce[address] += 1

            return tx_hash, block_number
        except Exception as e:
            self.log(
                f"{Fore.CYAN + Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                f"{Fore.RED + Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None, None
        
    async def perform_wrapped(self, account: str, address: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)

            asset_address = web3.to_checksum_address(self.WETH_CONTRACT_ADDRESS)
            amount_to_wei = web3.to_wei(self.wrap_amount, "ether")

            token_contract = web3.eth.contract(address=asset_address, abi=self.WRAP_CONTRACT_ABI)
            wrap_data = token_contract.functions.deposit()

            estimated_gas = wrap_data.estimate_gas({"from":address, "value":amount_to_wei})
            max_priority_fee = web3.to_wei(1, "gwei")
            max_fee = max_priority_fee

            wrap_tx = wrap_data.build_transaction({
                "from": address,
                "value": amount_to_wei,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": self.used_nonce[address],
                "chainId": web3.eth.chain_id,
            })

            tx_hash = await self.send_raw_transaction_with_retries(account, web3, wrap_tx)
            receipt = await self.wait_for_receipt_with_retries(web3, tx_hash)
            block_number = receipt.blockNumber
            self.used_nonce[address] += 1

            return tx_hash, block_number
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None, None
        
    async def perform_unwrapped(self, account: str, address: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)

            asset_address = web3.to_checksum_address(self.WETH_CONTRACT_ADDRESS)
            amount_to_wei = web3.to_wei(self.wrap_amount, "ether")

            token_contract = web3.eth.contract(address=asset_address, abi=self.WRAP_CONTRACT_ABI)
            unwrap_data = token_contract.functions.withdraw(amount_to_wei)

            estimated_gas = unwrap_data.estimate_gas({"from":address})
            max_priority_fee = web3.to_wei(1, "gwei")
            max_fee = max_priority_fee

            unwrap_tx = unwrap_data.build_transaction({
                "from": address,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": self.used_nonce[address],
                "chainId": web3.eth.chain_id,
            })

            tx_hash = await self.send_raw_transaction_with_retries(account, web3, unwrap_tx)
            receipt = await self.wait_for_receipt_with_retries(web3, tx_hash)
            block_number = receipt.blockNumber
            self.used_nonce[address] += 1

            return tx_hash, block_number
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None, None
        
    async def approving_token(self, account: str, address: str, router_address: str, asset_address: str, amount_to_wei: int, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)
            
            token_contract = web3.eth.contract(address=asset_address, abi=self.ERC20_CONTRACT_ABI)
            allowance = token_contract.functions.allowance(address, router_address).call()

            if allowance < amount_to_wei:
                approve_data = token_contract.functions.approve(router_address, amount_to_wei)
                estimated_gas = approve_data.estimate_gas({"from": address})

                max_priority_fee = web3.to_wei(1, "gwei")
                max_fee = max_priority_fee

                approve_tx = approve_data.build_transaction({
                    "from": address,
                    "gas": int(estimated_gas * 1.2),
                    "maxFeePerGas": int(max_fee),
                    "maxPriorityFeePerGas": int(max_priority_fee),
                    "nonce": self.used_nonce[address],
                    "chainId": web3.eth.chain_id,
                })

                tx_hash = await self.send_raw_transaction_with_retries(account, web3, approve_tx)
                receipt = await self.wait_for_receipt_with_retries(web3, tx_hash)
                block_number = receipt.blockNumber
                self.used_nonce[address] += 1

                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Approve  :{Style.RESET_ALL}"
                    f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}                      "
                )
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Block    :{Style.RESET_ALL}"
                    f"{Fore.WHITE+Style.BRIGHT} {block_number} {Style.RESET_ALL}"
                )
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Tx Hash  :{Style.RESET_ALL}"
                    f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
                )
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Explorer :{Style.RESET_ALL}"
                    f"{Fore.WHITE+Style.BRIGHT} {self.EXPLORER}{tx_hash} {Style.RESET_ALL}"
                )
                await self.print_timer()

            return True
        except Exception as e:
            raise Exception(f"Approving Token Contract Failed: {str(e)}")
        
    async def perform_restake(self, account: str, address: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)

            router_address = web3.to_checksum_address(self.RESTAKE_CONTRACT_ADDRESS)
            asset_address = web3.to_checksum_address(self.WETH_CONTRACT_ADDRESS)

            amount_to_wei = web3.to_wei(self.restake_amount, "ether")

            await self.approving_token(account, address, router_address, asset_address, amount_to_wei, use_proxy)

            token_contract = web3.eth.contract(address=router_address, abi=self.ERC20_CONTRACT_ABI)
            restake_data = token_contract.functions.deposit(asset_address, amount_to_wei)
            
            estimated_gas = restake_data.estimate_gas({"from":address})
            max_priority_fee = web3.to_wei(1, "gwei")
            max_fee = max_priority_fee

            restake_tx = restake_data.build_transaction({
                "from": address,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": self.used_nonce[address],
                "chainId": web3.eth.chain_id,
            })

            tx_hash = await self.send_raw_transaction_with_retries(account, web3, restake_tx)
            receipt = await self.wait_for_receipt_with_retries(web3, tx_hash)
            block_number = receipt.blockNumber
            self.used_nonce[address] += 1

            return tx_hash, block_number
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None, None
        
    async def perform_withdraw(self, account: str, address: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)

            router_address = web3.to_checksum_address(self.WITHDRAW_CONTRACT_ADDRESS)
            asset_address = web3.to_checksum_address(self.exETH_CONTRACT_ADDRESS)
            asset_out_address = web3.to_checksum_address(self.WETH_CONTRACT_ADDRESS)

            amount_to_wei = web3.to_wei(self.withdraw_amount, "ether")

            await self.approving_token(account, address, router_address, asset_address, amount_to_wei, use_proxy)

            token_contract = web3.eth.contract(address=router_address, abi=self.ERC20_CONTRACT_ABI)
            withdraw_data = token_contract.functions.withdraw(amount_to_wei, asset_out_address)
            
            estimated_gas = withdraw_data.estimate_gas({"from":address})
            max_priority_fee = web3.to_wei(1, "gwei")
            max_fee = max_priority_fee

            withdraw_tx = withdraw_data.build_transaction({
                "from": address,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": self.used_nonce[address],
                "chainId": web3.eth.chain_id,
            })

            tx_hash = await self.send_raw_transaction_with_retries(account, web3, withdraw_tx)
            receipt = await self.wait_for_receipt_with_retries(web3, tx_hash)
            block_number = receipt.blockNumber
            self.used_nonce[address] += 1

            return tx_hash, block_number
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None, None
        
    async def perform_claim(self, account: str, address: str, index: int, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)

            router_address = web3.to_checksum_address(self.WITHDRAW_CONTRACT_ADDRESS)

            token_contract = web3.eth.contract(address=router_address, abi=self.ERC20_CONTRACT_ABI)
            claim_data = token_contract.functions.claim(index, address)
            
            estimated_gas = claim_data.estimate_gas({"from":address})
            max_priority_fee = web3.to_wei(1, "gwei")
            max_fee = max_priority_fee

            claim_tx = claim_data.build_transaction({
                "from": address,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": self.used_nonce[address],
                "chainId": web3.eth.chain_id,
            })

            tx_hash = await self.send_raw_transaction_with_retries(account, web3, claim_tx)
            receipt = await self.wait_for_receipt_with_retries(web3, tx_hash)
            block_number = receipt.blockNumber
            self.used_nonce[address] += 1

            return tx_hash, block_number
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Message  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None, None
        
    def print_make_transfer_question(self):
        while True:
            make_transfer = input(f"{Fore.YELLOW + Style.BRIGHT}Do U Want to Make a Transfer [y/n] -> {Style.RESET_ALL}")
            if make_transfer in ["y", "n"]:
                make_transfer = make_transfer == "y"
                if make_transfer:
                    self.print_transfer_question()

                self.make_transfer = make_transfer
                break
            else:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter 'y' or 'n.{Style.RESET_ALL}")
        
    def print_transfer_question(self):
        print(f"{Fore.YELLOW + Style.BRIGHT}Enter Recepients Address [type 'z' to finish]:{Style.RESET_ALL}")
        while True:
            addr = input(f"{Fore.BLUE + Style.BRIGHT}Address -> {Style.RESET_ALL}").strip()
            if addr.lower() == "z":
                if not self.recepients:
                    print(f"{Fore.RED + Style.BRIGHT}No Recepients Address Entered.{Style.RESET_ALL}")
                    continue
                break

            if addr:
                self.recepients.append(addr)

        while True:
            try:
                transfer_amount = float(input(f"{Fore.YELLOW + Style.BRIGHT}Enter Transfer Amount [ETH] -> {Style.RESET_ALL}").strip())
                if transfer_amount > 0:
                    self.transfer_amount = transfer_amount
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}WETH amount must be > 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a float or decimal number.{Style.RESET_ALL}")
        
    def print_wrap_question(self):
        while True:
            try:
                wrap_amount = float(input(f"{Fore.YELLOW + Style.BRIGHT}Enter Wrap Amount [ETH] -> {Style.RESET_ALL}").strip())
                if wrap_amount > 0:
                    self.wrap_amount = wrap_amount
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}ETH amount must be > 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a float or decimal number.{Style.RESET_ALL}")
    
    def print_unwrap_question(self):
        while True:
            try:
                wrap_amount = float(input(f"{Fore.YELLOW + Style.BRIGHT}Enter Unwrap Amount [WETH] -> {Style.RESET_ALL}").strip())
                if wrap_amount > 0:
                    self.wrap_amount = wrap_amount
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}WETH amount must be > 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a float or decimal number.{Style.RESET_ALL}")

    def print_wrap_or_unwarp_option(self):
        while True:
            try:
                print(f"{Fore.GREEN + Style.BRIGHT}Select Option:{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}1. Wrap ETH to WETH{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}2. Unwrap WETH to ETH{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}3. Skipped{Style.RESET_ALL}")
                wrap_option = int(input(f"{Fore.BLUE + Style.BRIGHT}Choose [1/2/3] -> {Style.RESET_ALL}").strip())

                if wrap_option in [1, 2, 3]:
                    wrap_type = (
                        "Wrap ETH to WETH" if wrap_option == 1 else 
                        "Unwrap WETH to ETH" if wrap_option == 2 else 
                        "Skipped"
                    )
                    print(f"{Fore.GREEN + Style.BRIGHT}{wrap_type} Selected.{Style.RESET_ALL}")
                    self.wrap_option = wrap_option

                    if self.wrap_option == 1:
                        self.print_wrap_question()
                    elif self.wrap_option == 2:
                        self.print_unwrap_question()

                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Please enter either 1 or 2.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number (1 or 2).{Style.RESET_ALL}")

    def print_restake_question(self):
        while True:
            try:
                restake_count = int(input(f"{Fore.YELLOW + Style.BRIGHT}Enter Restake Count -> {Style.RESET_ALL}").strip())
                if restake_count > 0:
                    self.restake_count = restake_count
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Restake count must be > 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number.{Style.RESET_ALL}")

        while True:
            try:
                restake_amount = float(input(f"{Fore.YELLOW + Style.BRIGHT}Enter Restake Amount [WETH] -> {Style.RESET_ALL}").strip())
                if restake_amount > 0:
                    self.restake_amount = restake_amount
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}WETH amount must be > 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a float or decimal number.{Style.RESET_ALL}")

    def print_withdraw_question(self):
        while True:
            try:
                withdraw_count = int(input(f"{Fore.YELLOW + Style.BRIGHT}Enter Withdraw Count -> {Style.RESET_ALL}").strip())
                if withdraw_count > 0:
                    self.withdraw_count = withdraw_count
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Withdraw count must be > 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number.{Style.RESET_ALL}")

        while True:
            try:
                withdraw_amount = float(input(f"{Fore.YELLOW + Style.BRIGHT}Enter Withdraw Amount [exETH] -> {Style.RESET_ALL}").strip())
                if withdraw_amount > 0:
                    self.withdraw_amount = withdraw_amount
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}exETH amount must be > 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a float or decimal number.{Style.RESET_ALL}")

    def print_delay_question(self):
        while True:
            try:
                min_delay = int(input(f"{Fore.YELLOW + Style.BRIGHT}Min Delay For Each Tx -> {Style.RESET_ALL}").strip())
                if min_delay >= 0:
                    self.min_delay = min_delay
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Min Delay must be >= 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number.{Style.RESET_ALL}")

        while True:
            try:
                max_delay = int(input(f"{Fore.YELLOW + Style.BRIGHT}Max Delay For Each Tx -> {Style.RESET_ALL}").strip())
                if max_delay >= min_delay:
                    self.max_delay = max_delay
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Max Delay must be >= Min Delay.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number.{Style.RESET_ALL}")
         
    async def print_timer(self):
        for remaining in range(random.randint(self.min_delay, self.max_delay), 0, -1):
            print(
                f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
                f"{Fore.BLUE + Style.BRIGHT}Wait For{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} {remaining} {Style.RESET_ALL}"
                f"{Fore.BLUE + Style.BRIGHT}Seconds For Next Tx...{Style.RESET_ALL}",
                end="\r",
                flush=True
            )
            await asyncio.sleep(1)

    def print_question(self):
        while True:
            try:
                print(f"{Fore.GREEN + Style.BRIGHT}Select Option:{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}1. Transfer ETH to Friends{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}2. Wrap ETH to WETH{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}3. Unwrap WETH to ETH{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}4. Restake WETH to exETH{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}5. Withdraw exETH to WETH{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}6. Claim Rewards{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}7. Run All Features{Style.RESET_ALL}")
                option = int(input(f"{Fore.BLUE + Style.BRIGHT}Choose [1/2/3/4/5/6/7] -> {Style.RESET_ALL}").strip())

                if option in [1, 2, 3, 4, 5, 6, 7]:
                    option_type = (
                        "Send ETH to Friends" if option == 1 else 
                        "Wrap ETH to WETH" if option == 2 else 
                        "Unwrap WETH to ETH" if option == 3 else 
                        "Restake WETH to exETH" if option == 4 else
                        "Withdraw exETH to WETH" if option == 5 else
                        "Claim Rewards" if option == 6 else
                        "Run All Features"
                    )
                    print(f"{Fore.GREEN + Style.BRIGHT}{option_type} Selected.{Style.RESET_ALL}")
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Please enter either 1, 2, 3, 4, 5, 6, or 7.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number (1, 2, 3, 4, 5, 6, or 7).{Style.RESET_ALL}")

        if option == 1:
            self.print_transfer_question()
            self.print_delay_question()

        if option == 2:
            self.print_wrap_question()
            self.print_delay_question()

        elif option == 3:
            self.print_unwrap_question()
            self.print_delay_question()

        elif option == 4:
            self.print_restake_question()
            self.print_delay_question()

        elif option == 5:
            self.print_withdraw_question()
            self.print_delay_question()

        elif option == 6:
            self.print_delay_question()

        elif option == 7:
            self.print_make_transfer_question()
            self.print_wrap_or_unwarp_option()
            self.print_restake_question()
            self.print_withdraw_question()
            self.print_delay_question()

        while True:
            try:
                print(f"{Fore.WHITE + Style.BRIGHT}1. Run With Proxy{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}2. Run Without Proxy{Style.RESET_ALL}")
                proxy_choice = int(input(f"{Fore.BLUE + Style.BRIGHT}Choose [1/2] -> {Style.RESET_ALL}").strip())

                if proxy_choice in [1, 2]:
                    proxy_type = (
                        "With" if proxy_choice == 2 else 
                        "Without"
                    )
                    print(f"{Fore.GREEN + Style.BRIGHT}Run {proxy_type} Proxy Selected.{Style.RESET_ALL}")
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Please enter either 1 or 2.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number (1 or 2).{Style.RESET_ALL}")

        rotate_proxy = False
        if proxy_choice == 1:
            while True:
                rotate_proxy = input(f"{Fore.BLUE + Style.BRIGHT}Rotate Invalid Proxy? [y/n] -> {Style.RESET_ALL}").strip()

                if rotate_proxy in ["y", "n"]:
                    rotate_proxy = rotate_proxy == "y"
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter 'y' or 'n'.{Style.RESET_ALL}")

        return option, proxy_choice, rotate_proxy
    
    async def check_connection(self, proxy_url=None):
        connector, proxy, proxy_auth = self.build_proxy_config(proxy_url)
        try:
            async with ClientSession(connector=connector, timeout=ClientTimeout(total=10)) as session:
                async with session.get(url="https://api.ipify.org?format=json", proxy=proxy, proxy_auth=proxy_auth) as response:
                    response.raise_for_status()
                    return True
        except (Exception, ClientResponseError) as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Status    :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Connection Not 200 OK {Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None
    
    async def process_check_connection(self, address: str, use_proxy: bool, rotate_proxy: bool):
        while True:
            proxy = self.get_next_proxy_for_account(address) if use_proxy else None
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Proxy     :{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} {proxy} {Style.RESET_ALL}"
            )

            is_valid = await self.check_connection(proxy)
            if not is_valid:
                if rotate_proxy:
                    proxy = self.rotate_proxy_for_account(address)
                    await asyncio.sleep(1)
                    continue

                return False
            
            return True
        
    async def process_perform_transfer(self, account: str, address: str, recepient: str, use_proxy: bool):
        tx_hash, block_number = await self.perform_transfer(account, address, recepient, use_proxy)
        if tx_hash and block_number:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}                      "
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Block    :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {block_number} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Tx Hash  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Explorer :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.EXPLORER}{tx_hash} {Style.RESET_ALL}"
            )
        else:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Perform On-Chain Failed {Style.RESET_ALL}"
            )
        
    async def process_perform_wrapped(self, account: str, address: str, use_proxy: bool):
        tx_hash, block_number = await self.perform_wrapped(account, address, use_proxy)
        if tx_hash and block_number:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}                      "
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Block    :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {block_number} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Tx Hash  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Explorer :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.EXPLORER}{tx_hash} {Style.RESET_ALL}"
            )
        else:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Perform On-Chain Failed {Style.RESET_ALL}"
            )

    async def process_perform_unwrapped(self, account: str, address: str, use_proxy: bool):
        tx_hash, block_number = await self.perform_unwrapped(account, address, use_proxy)
        if tx_hash and block_number:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}                      "
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Block    :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {block_number} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Tx Hash  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Explorer :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.EXPLORER}{tx_hash} {Style.RESET_ALL}"
            )
        else:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Perform On-Chain Failed {Style.RESET_ALL}"
            )

    async def process_perform_restake(self, account: str, address: str, use_proxy: bool):
        tx_hash, block_number = await self.perform_restake(account, address, use_proxy)
        if tx_hash and block_number:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}                      "
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Block    :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {block_number} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Tx Hash  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Explorer :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.EXPLORER}{tx_hash} {Style.RESET_ALL}"
            )
        else:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Perform On-Chain Failed {Style.RESET_ALL}"
            )

    async def process_perform_withdraw(self, account: str, address: str, use_proxy: bool):
        tx_hash, block_number = await self.perform_withdraw(account, address, use_proxy)
        if tx_hash and block_number:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}                      "
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Block    :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {block_number} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Tx Hash  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Explorer :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.EXPLORER}{tx_hash} {Style.RESET_ALL}"
            )
        else:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Perform On-Chain Failed {Style.RESET_ALL}"
            )

    async def process_perform_claim(self, account: str, address: str, index: int, use_proxy: bool):
        tx_hash, block_number = await self.perform_claim(account, address, index, use_proxy)
        if tx_hash and block_number:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}                      "
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Block    :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {block_number} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Tx Hash  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Explorer :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.EXPLORER}{tx_hash} {Style.RESET_ALL}"
            )
        else:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Perform On-Chain Failed {Style.RESET_ALL}"
            )

    async def process_option_1(self, account: str, address: str, use_proxy):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Transfer  :{Style.RESET_ALL}                      ")

        for i, recepient in enumerate(self.recepients, start=1):
            self.log(
                f"{Fore.GREEN+Style.BRIGHT} ● {Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT}Transfer{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {i} {Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT}Of{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {len(self.recepients)} {Style.RESET_ALL}                                   "
            )

            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Recepinet:{Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT} {address} {Style.RESET_ALL}"
            )

            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Amount   :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.transfer_amount} ETH {Style.RESET_ALL}"
            )

            balance = await self.get_token_balance(address, self.ETH_CONTRACT_ADDRESS, use_proxy)
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Balance  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance} ETH {Style.RESET_ALL}"
            )

            if balance is None:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Fecth ETH Token Balance Failed {Style.RESET_ALL}"
                )
                continue

            if balance < self.transfer_amount:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Insufficient ETH Token Balance {Style.RESET_ALL}"
                )
                return
            
            await self.process_perform_transfer(account, address, recepient, use_proxy)
            await self.print_timer()

    async def process_option_2(self, account: str, address: str, use_proxy):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Wrapped   :{Style.RESET_ALL}                      ")

        self.log(
            f"{Fore.CYAN+Style.BRIGHT}   Amount   :{Style.RESET_ALL}"
            f"{Fore.WHITE+Style.BRIGHT} {self.wrap_amount} ETH {Style.RESET_ALL}"
        )

        balance = await self.get_token_balance(address, self.ETH_CONTRACT_ADDRESS, use_proxy)
        self.log(
            f"{Fore.CYAN+Style.BRIGHT}   Balance  :{Style.RESET_ALL}"
            f"{Fore.WHITE+Style.BRIGHT} {balance} ETH {Style.RESET_ALL}"
        )

        if balance is None:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Fecth ETH Token Balance Failed {Style.RESET_ALL}"
            )
            return

        if balance <= self.wrap_amount:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} Insufficient ETH Token Balance {Style.RESET_ALL}"
            )
            return
        
        await self.process_perform_wrapped(account, address, use_proxy)

    async def process_option_3(self, account: str, address: str, use_proxy):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Unwrapped :{Style.RESET_ALL}                      ")

        self.log(
            f"{Fore.CYAN+Style.BRIGHT}   Amount   :{Style.RESET_ALL}"
            f"{Fore.WHITE+Style.BRIGHT} {self.wrap_amount} WETH {Style.RESET_ALL}"
        )

        balance = await self.get_token_balance(address, self.WETH_CONTRACT_ADDRESS, use_proxy)
        self.log(
            f"{Fore.CYAN+Style.BRIGHT}   Balance  :{Style.RESET_ALL}"
            f"{Fore.WHITE+Style.BRIGHT} {balance} WETH {Style.RESET_ALL}"
        )

        if balance is None:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Fecth WETH Token Balance Failed {Style.RESET_ALL}"
            )
            return

        if balance < self.wrap_amount:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} Insufficient WETH Token Balance {Style.RESET_ALL}"
            )
            return
        
        await self.process_perform_unwrapped(account, address, use_proxy)

    async def process_option_4(self, account: str, address: str, use_proxy):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Restake   :{Style.RESET_ALL}                      ")

        for i in range(self.restake_count):
            self.log(
                f"{Fore.GREEN+Style.BRIGHT} ● {Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT}Restake{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {i+1} {Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT}Of{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.restake_count} {Style.RESET_ALL}                                   "
            )

            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Amount   :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.restake_amount} WETH {Style.RESET_ALL}"
            )

            balance = await self.get_token_balance(address, self.WETH_CONTRACT_ADDRESS, use_proxy)
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Balance  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance} WETH {Style.RESET_ALL}"
            )

            if balance is None:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Fecth WETH Token Balance Failed {Style.RESET_ALL}"
                )
                continue

            if balance < self.restake_amount:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Insufficient WETH Token Balance {Style.RESET_ALL}"
                )
                return
            
            await self.process_perform_restake(account, address, use_proxy)
            await self.print_timer()

    async def process_option_5(self, account: str, address: str, use_proxy):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Withdraw  :{Style.RESET_ALL}                      ")

        for i in range(self.withdraw_count):
            self.log(
                f"{Fore.GREEN+Style.BRIGHT} ● {Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT}Withdraw{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {i+1} {Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT}Of{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.withdraw_count} {Style.RESET_ALL}                                   "
            )

            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Amount   :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.withdraw_amount} exETH {Style.RESET_ALL}"
            )

            balance = await self.get_token_balance(address, self.exETH_CONTRACT_ADDRESS, use_proxy)
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Balance  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance} exETH {Style.RESET_ALL}"
            )

            if balance is None:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Fecth exETH Token Balance Failed {Style.RESET_ALL}"
                )
                continue

            if balance < self.withdraw_amount:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Insufficient exETH Token Balance {Style.RESET_ALL}"
                )
                return
            
            await self.process_perform_withdraw(account, address, use_proxy)
            await self.print_timer()

    async def process_option_6(self, account: str, address: str, use_proxy):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Claims    :{Style.RESET_ALL}                      ")

        index_totals = await self.get_outstanding_withdraw(address, use_proxy)
        if index_totals is None:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Fecth Outstanding Withdraw Requests Failed {Style.RESET_ALL}"
            )
            return
        
        if index_totals == 0:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}   Status   :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} No Available Outstanding Withdraw Requests {Style.RESET_ALL}"
            )
            return

        for index in range(index_totals - 1):
            self.log(
                f"{Fore.GREEN+Style.BRIGHT} ● {Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT}Claim{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {index+1} {Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT}Of{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {index_totals - 1} {Style.RESET_ALL}                                   "
            )

            await self.process_perform_claim(account, address, index, use_proxy)
            await self.print_timer()

    async def process_accounts(self, account: str, address: str, option: int, use_proxy: bool, rotate_proxy: bool):
        is_valid = await self.process_check_connection(address, use_proxy, rotate_proxy)
        if is_valid:
            try:
                web3 = await self.get_web3_with_check(address, use_proxy)
            except Exception as e:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Status  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Web3 Not Connected {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )
                return
            
            self.used_nonce[address] = web3.eth.get_transaction_count(address, "pending")
            
            if option == 1:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Option    :{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} Transfer ETH to Friends {Style.RESET_ALL}"
                )
                await self.process_option_1(account, address, use_proxy)
            
            if option == 2:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Option    :{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} Wrap ETH to WETH {Style.RESET_ALL}"
                )
                await self.process_option_2(account, address, use_proxy)

            elif option == 3:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Option    :{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} Unwrap WETH to ETH {Style.RESET_ALL}"
                )
                await self.process_option_3(account, address, use_proxy)

            elif option == 4:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Option    :{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} Restake WETH to exETH {Style.RESET_ALL}"
                )
                await self.process_option_4(account, address, use_proxy)

            elif option == 5:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Option    :{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} Withdraw exETH to WETH {Style.RESET_ALL}"
                )
                await self.process_option_5(account, address, use_proxy)

            elif option == 6:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Option    :{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} Claim Rewards {Style.RESET_ALL}"
                )
                await self.process_option_6(account, address, use_proxy)

            elif option == 7:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Option    :{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} Run All Features {Style.RESET_ALL}"
                )

                if self.make_transfer:
                    await self.process_option_1(account, address, use_proxy)

                if self.wrap_option == 1:
                    await self.process_option_2(account, address, use_proxy)
                elif self.wrap_option == 2:
                    await self.process_option_3(account, address, use_proxy)
                
                await self.process_option_4(account, address, use_proxy)
                await self.process_option_5(account, address, use_proxy)
                await self.process_option_6(account, address, use_proxy)

    async def main(self):
        try:
            with open('accounts.txt', 'r') as file:
                accounts = [line.strip() for line in file if line.strip()]

            option, proxy_choice, rotate_proxy = self.print_question()

            use_proxy = True if proxy_choice == 1 else False

            while True:
                self.clear_terminal()
                self.welcome()
                self.log(
                    f"{Fore.GREEN + Style.BRIGHT}Account's Total: {Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}"
                )

                if use_proxy:
                    await self.load_proxies()
                
                separator = "=" * 25
                for account in accounts:
                    if account:
                        address = self.generate_address(account)

                        self.log(
                            f"{Fore.CYAN + Style.BRIGHT}{separator}[{Style.RESET_ALL}"
                            f"{Fore.WHITE + Style.BRIGHT} {self.mask_account(address)} {Style.RESET_ALL}"
                            f"{Fore.CYAN + Style.BRIGHT}]{separator}{Style.RESET_ALL}"
                        )

                        if not address:
                            self.log(
                                f"{Fore.CYAN + Style.BRIGHT}Status    :{Style.RESET_ALL}"
                                f"{Fore.RED + Style.BRIGHT} Invalid Private Key or Library Version Not Supported {Style.RESET_ALL}"
                            )
                            continue

                        await self.process_accounts(account, address, option, use_proxy, rotate_proxy)
                        await asyncio.sleep(3)

                self.log(f"{Fore.CYAN + Style.BRIGHT}={Style.RESET_ALL}"*72)
                seconds = 24 * 60 * 60
                while seconds > 0:
                    formatted_time = self.format_seconds(seconds)
                    print(
                        f"{Fore.CYAN+Style.BRIGHT}[ Wait for{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} {formatted_time} {Style.RESET_ALL}"
                        f"{Fore.CYAN+Style.BRIGHT}... ]{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} | {Style.RESET_ALL}"
                        f"{Fore.BLUE+Style.BRIGHT}All Accounts Have Been Processed.{Style.RESET_ALL}",
                        end="\r"
                    )
                    await asyncio.sleep(1)
                    seconds -= 1

        except FileNotFoundError:
            self.log(f"{Fore.RED}File 'accounts.txt' Not Found.{Style.RESET_ALL}")
            return
        except Exception as e:
            self.log(f"{Fore.RED+Style.BRIGHT}Error: {e}{Style.RESET_ALL}")
            raise e

if __name__ == "__main__":
    try:
        bot = Ekox()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ EXIT ] Ekox - BOT{Style.RESET_ALL}                                       "                              
        )
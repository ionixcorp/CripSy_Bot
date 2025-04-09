
# Archivos __init__.py presentes en cada módulo
#
# Este archivo contiene todos los módulos de un bot modular completo.
# Este no es un solo archivo, cada archivo tiene su ruta específica.
# Encontrarás la ruta exacta de cada módulo al inicio del separador.
#


#██████████ INICIO - .gitignore ██████████
# Ruta del módulo: .gitignore

.venv
error.log
logs.log
#██████████ FIN - .gitignore ██████████


#██████████ INICIO - check_win.py ██████████
# Ruta del módulo: async\check_win.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync


import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    (buy_id, _) = await api.buy(asset="EURUSD_otc", amount=1.0, time=15, check_win=False)
    (sell_id, _) = await api.sell(asset="EURUSD_otc", amount=1.0, time=300, check_win=False)
    print(buy_id, sell_id)
    # This is the same as setting checkw_win to true on the api.buy and api.sell functions
    buy_data = await api.check_win(buy_id)
    print(f"Buy trade result: {buy_data['result']}\nBuy trade data: {buy_data}")
    sell_data = await api.check_win(sell_id)
    print(f"Sell trade result: {sell_data['result']}\nSell trade data: {sell_data}")


    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - check_win.py ██████████


#██████████ INICIO - create_raw_iterator.py ██████████
# Ruta del módulo: async\create_raw_iterator.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from BinaryOptionsToolsV2.validator import Validator
from datetime import timedelta

import asyncio

async def main(ssid: str):
    # Initialize the API client
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)  # Wait for connection to establish
    
    # Create a validator for price updates
    validator = Validator.regex(r'{"price":\d+\.\d+}')
    
    # Create an iterator with 5 minute timeout
    stream = await api.create_raw_iterator(
        '42["price/subscribe"]',  # WebSocket subscription message
        validator,
        timeout=timedelta(minutes=5)
    )
    
    try:
        # Process messages as they arrive
        async for message in stream:
            print(f"Received message: {message}")
    except TimeoutError:
        print("Stream timed out after 5 minutes")
    except Exception as e:
        print(f"Error processing stream: {e}")

if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
#██████████ FIN - create_raw_iterator.py ██████████


#██████████ INICIO - create_raw_order.py ██████████
# Ruta del módulo: async\create_raw_order.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from BinaryOptionsToolsV2.validator import Validator
from datetime import timedelta

import asyncio

async def main(ssid: str):
    # Initialize the API client
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)  # Wait for connection to establish
    
    # Basic raw order example
    try:
        validator = Validator.contains('"status":"success"')
        response = await api.create_raw_order(
            '42["signals/subscribe"]',
            validator
        )
        print(f"Basic raw order response: {response}")
    except Exception as e:
        print(f"Basic raw order failed: {e}")

    # Raw order with timeout example
    try:
        validator = Validator.regex(r'{"type":"signal","data":.*}')
        response = await api.create_raw_order_with_timout(
            '42["signals/load"]',
            validator,
            timeout=timedelta(seconds=5)
        )
        print(f"Raw order with timeout response: {response}")
    except TimeoutError:
        print("Order timed out after 5 seconds")
    except Exception as e:
        print(f"Order with timeout failed: {e}")

    # Raw order with timeout and retry example
    try:
        # Create a validator that checks for both conditions
        validator = Validator.all([
            Validator.contains('"type":"trade"'),
            Validator.contains('"status":"completed"')
        ])
        
        response = await api.create_raw_order_with_timeout_and_retry(
            '42["trade/subscribe"]',
            validator,
            timeout=timedelta(seconds=10)
        )
        print(f"Raw order with retry response: {response}")
    except Exception as e:
        print(f"Order with retry failed: {e}")

if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
#██████████ FIN - create_raw_order.py ██████████


#██████████ INICIO - get_balance.py ██████████
# Ruta del módulo: async\get_balance.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    await asyncio.sleep(5)
    
    balance = await api.balance()
    print(f"Balance: {balance}")
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - get_balance.py ██████████


#██████████ INICIO - get_candles.py ██████████
# Ruta del módulo: async\get_candles.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import pandas as pd
import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)
    
    # Candñes are returned in the format of a list of dictionaries
    times = [ 3600 * i for i in range(1, 11)]
    time_frames = [ 1, 5, 15, 30, 60, 300]
    for time in times:
        for frame in time_frames:
            
            candles = await api.get_candles("EURUSD_otc", 60, time)
            # print(f"Raw Candles: {candles}")
            candles_pd = pd.DataFrame.from_dict(candles)
            print(f"Candles: {candles_pd}")
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - get_candles.py ██████████


#██████████ INICIO - get_open_and_close_trades.py ██████████
# Ruta del módulo: async\get_open_and_close_trades.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    _ = await api.buy(asset="EURUSD_otc", amount=1.0, time=60, check_win=False)
    _ = await api.sell(asset="EURUSD_otc", amount=1.0, time=60, check_win=False)
    # This is the same as setting checkw_win to true on the api.buy and api.sell functions
    opened_deals = await api.opened_deals()
    print(f"Opened deals: {opened_deals}\nNumber of opened deals: {len(opened_deals)} (should be at least 2)")
    await asyncio.sleep(62) # Wait for the trades to complete
    closed_deals = await api.closed_deals()
    print(f"Closed deals: {closed_deals}\nNumber of closed deals: {len(closed_deals)} (should be at least 2)")

    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - get_open_and_close_trades.py ██████████


#██████████ INICIO - history.py ██████████
# Ruta del módulo: async\history.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import pandas as pd
import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)
    
    # Candles are returned in the format of a list of dictionaries
    candles = await api.history("EURUSD_otc", 3600)
    print(f"Raw Candles: {candles}")
    candles_pd = pd.DataFrame.from_dict(candles)
    print(f"Candles: {candles_pd}")
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - history.py ██████████


#██████████ INICIO - log_iterator.py ██████████
# Ruta del módulo: async\log_iterator.py

# Import necessary modules
from BinaryOptionsToolsV2.tracing import Logger, LogBuilder
from datetime import timedelta
import asyncio

async def main():
    """
    Main asynchronous function demonstrating the usage of logging system.
    """
    
    # Create a Logger instance
    logger = Logger()
    
    # Create a LogBuilder instance
    log_builder = LogBuilder()
    
    # Create a new logs iterator with INFO level and 10-second timeout
    log_iterator = log_builder.create_logs_iterator(level="INFO", timeout=timedelta(seconds=10))

    # Configure logging to write to a file
    # This will create or append to 'logs.log' file with INFO level logs
    log_builder.log_file(path="app_logs.txt", level="INFO")

    # Configure terminal logging for DEBUG level
    log_builder.terminal(level="DEBUG")

    # Build and initialize the logging configuration
    log_builder.build()

    # Create a Logger instance with the built configuration
    logger = Logger()

    # Log some messages at different levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warn("This is a warning message")
    logger.error("This is an error message")

    # Example of logging with variables
    asset = "EURUSD"
    amount = 100
    logger.info(f"Bought {amount} units of {asset}")

    # Demonstrate async usage
    async def log_async():
        """
        Asynchronous logging function demonstrating async usage.
        """
        logger.debug("This is an asynchronous debug message")
        await asyncio.sleep(5)  # Simulate some work
        logger.info("Async operation completed")

    # Run the async function
    task1 = asyncio.create_task(log_async())

    # Example of using LogBuilder for creating iterators
    async def process_logs(log_iterator):
        """
        Function demonstrating the use of LogSubscription.
        """
        
        try:
            async for log in log_iterator:
                print(f"Received log: {log}")
                # Each log is a dict so we can access the message
                print(f"Log message: {log['message']}")
        except Exception as e:
            print(f"Error processing logs: {e}")

    # Run the logs processing function
    task2 = asyncio.create_task(process_logs(log_iterator))
    
    # Execute both tasks at the same time
    await asyncio.gather(task1, task2)

    

if __name__ == "__main__":
    asyncio.run(main())
#██████████ FIN - log_iterator.py ██████████


#██████████ INICIO - logs.py ██████████
# Ruta del módulo: async\logs.py

from BinaryOptionsToolsV2.tracing import start_logs
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # Start logs, it works perfectly on async code
    start_logs(path=".", level="DEBUG", terminal=True) # If false then the logs will only be written to the log files
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    (buy_id, _) = await api.buy(asset="EURUSD_otc", amount=1.0, time=300, check_win=False)
    (sell_id, _) = await api.sell(asset="EURUSD_otc", amount=1.0, time=300, check_win=False)
    print(buy_id, sell_id)
    # This is the same as setting checkw_win to true on the api.buy and api.sell functions
    buy_data = await api.check_win(buy_id)
    sell_data = await api.check_win(sell_id)
    print(f"Buy trade result: {buy_data['result']}\nBuy trade data: {buy_data}")
    print(f"Sell trade result: {sell_data['result']}\nSell trade data: {sell_data}")


    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - logs.py ██████████


#██████████ INICIO - payout.py ██████████
# Ruta del módulo: async\payout.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)
    
    # Candñes are returned in the format of a list of dictionaries
    full_payout = await api.payout() # Returns a dictionary asset: payout
    print(f"Full Payout: {full_payout}")
    partial_payout = await api.payout(["EURUSD_otc", "EURUSD", "AEX25"]) # Returns a list of the payout for each of the passed assets in order
    print(f"Partial Payout: {partial_payout}")
    single_payout = await api.payout("EURUSD_otc") # Returns the payout for the specified asset
    print(f"Single Payout: {single_payout}")
    
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - payout.py ██████████


#██████████ INICIO - raw_send.py ██████████
# Ruta del módulo: async\raw_send.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
import asyncio

async def main(ssid: str):
    # Initialize the API client
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)  # Wait for connection to establish
    
    # Example of sending a raw message
    try:
        # Subscribe to signals
        await api.send_raw_message('42["signals/subscribe"]')
        print("Sent signals subscription message")
        
        # Subscribe to price updates
        await api.send_raw_message('42["price/subscribe"]')
        print("Sent price subscription message")
        
        # Custom message example
        custom_message = '42["custom/event",{"param":"value"}]'
        await api.send_raw_message(custom_message)
        print(f"Sent custom message: {custom_message}")
        
        # Multiple messages in sequence
        messages = [
            '42["chart/subscribe",{"asset":"EURUSD"}]',
            '42["trades/subscribe"]',
            '42["notifications/subscribe"]'
        ]
        
        for msg in messages:
            await api.send_raw_message(msg)
            print(f"Sent message: {msg}")
            await asyncio.sleep(1)  # Small delay between messages
            
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')


#██████████ FIN - raw_send.py ██████████


#██████████ INICIO - subscribe_symbol.py ██████████
# Ruta del módulo: async\subscribe_symbol.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    stream = await api.subscribe_symbol("EURUSD_otc")
    
    # This should run forever so you will need to force close the program
    async for candle in stream:
        print(f"Candle: {candle}") # Each candle is in format of a dictionary 
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - subscribe_symbol.py ██████████


#██████████ INICIO - subscribe_symbol_chuncked.py ██████████
# Ruta del módulo: async\subscribe_symbol_chuncked.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    stream = await api.subscribe_symbol_chuncked("EURUSD_otc", 15) # Returns a candle obtained from combining 15 (chunk_size) candles
    
    # This should run forever so you will need to force close the program
    async for candle in stream:
        print(f"Candle: {candle}") # Each candle is in format of a dictionary 
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - subscribe_symbol_chuncked.py ██████████


#██████████ INICIO - subscribe_symbol_timed.py ██████████
# Ruta del módulo: async\subscribe_symbol_timed.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from BinaryOptionsToolsV2.tracing import start_logs
from datetime import timedelta

import asyncio

# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    start_logs(".", "INFO")
    api = PocketOptionAsync(ssid)    
    stream = await api.subscribe_symbol_timed("EURUSD_otc", timedelta(seconds=5)) # Returns a candle obtained from combining candles that are inside a specific time range
    
    # This should run forever so you will need to force close the program
    async for candle in stream:
        print(f"Candle: {candle}") # Each candle is in format of a dictionary 
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - subscribe_symbol_timed.py ██████████


#██████████ INICIO - trade.py ██████████
# Ruta del módulo: async\trade.py

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    
    (buy_id, buy) = await api.buy(asset="EURUSD_otc", amount=1.0, time=60, check_win=False)
    print(f"Buy trade id: {buy_id}\nBuy trade data: {buy}")
    (sell_id, sell) = await api.sell(asset="EURUSD_otc", amount=1.0, time=60, check_win=False)
    print(f"Sell trade id: {sell_id}\nSell trade data: {sell}")
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    
#██████████ FIN - trade.py ██████████


#██████████ INICIO - validator.py ██████████
# Ruta del módulo: async\validator.py

from BinaryOptionsToolsV2.validator import Validator

if __name__ == "__main__":
    none = Validator()
    regex = Validator.regex("([A-Z])\w+")
    start = Validator.starts_with("Hello")
    end = Validator.ends_with("Bye")
    contains = Validator.contains("World")
    rnot = Validator.ne(contains)
    custom = Validator.custom(lambda x: x.startswith("Hello") and x.endswith("World"))

    # Modified for better testing - smaller groups with predictable outcomes
    rall = Validator.all([regex, start])  # Will need both capital letter and "Hello" at start
    rany = Validator.any([contains, end])  # Will need either "World" or end with "Bye"

    print(f"None validator: {none.check('hello')} (Expected: True)")
    print(f"Regex validator: {regex.check('Hello')} (Expected: True)")
    print(f"Regex validator: {regex.check('hello')} (Expected: False)")
    print(f"Starts_with validator: {start.check('Hello World')} (Expected: True)")
    print(f"Starts_with validator: {start.check('hi World')} (Expected: False)")
    print(f"Ends_with validator: {end.check('Hello Bye')} (Expected: True)")
    print(f"Ends_with validator: {end.check('Hello there')} (Expected: False)")
    print(f"Contains validator: {contains.check('Hello World')} (Expected: True)")
    print(f"Contains validator: {contains.check('Hello there')} (Expected: False)")
    print(f"Not validator: {rnot.check('Hello World')} (Expected: False)")
    print(f"Not validator: {rnot.check('Hello there')} (Expected: True)")
    try:
        print(f"Custom validator: {custom.check('Hello World')}, (Expected: True)")
        print(f"Custom validator: {custom.check('Hello there')}, (Expected: False)")
    except Exception as e:
        print(f"Error: {e}")        
    # Testing the all validator
    print(f"All validator: {rall.check('Hello World')} (Expected: True)")  # Starts with "Hello" and has capital
    print(f"All validator: {rall.check('hello World')} (Expected: False)")  # No capital at start
    print(f"All validator: {rall.check('Hey there')} (Expected: False)")  # Has capital but doesn't start with "Hello"

    # Testing the any validator
    print(f"Any validator: {rany.check('Hello World')} (Expected: True)")  # Contains "World"
    print(f"Any validator: {rany.check('Hello Bye')} (Expected: True)")  # Ends with "Bye"
    print(f"Any validator: {rany.check('Hello there')} (Expected: False)")  # Neither contains "World" nor ends with "Bye"
#██████████ FIN - validator.py ██████████

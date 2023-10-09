### EMA STRATEGY

## Steps:
# Create a contract in contract folder
example: 
```json
{
    "contract" : {
        "symbol" : "ES",
        "secType" : "CONTFUT",  (security type Stock, Futures, Options etc.)
        "exchange" : "CME",
        "currency" : "USD"
    },
    "no_contract" : 1,
    "action" : "BUY",
    "take_profit_pct" : 2,  (provide % value of profit taking)
    "trailing_stop_pct" : 1,  (provide % value of trailing stop)
    "ema_interval" : "1 min",  (use intervals as given in ib_insync documentation)
    "emas" : [9,20]  (EMAS provide first number who's EMA you want to be greater)
}
```
# Run main.py

# Every time an Order will be created in the Order folder for a contract
example:
(example of a stock bought)
```json
{
    "contract": "Contract(secType='STK', conId=265598, symbol='AAPL', exchange='SMART', primaryExchange='NASDAQ', currency='USD', localSymbol='AAPL', tradingClass='NMS')",
    "entry_timestamp": "2023-10-10 01:11:21.286851",
    "entry_price": 178.9,
    "long/short": "long",
    "quantity": 1.0
}
```
(example of closing a position)
```json
{
    "contract": "Contract(secType='STK', conId=265598, symbol='AAPL', exchange='SMART', primaryExchange='NASDAQ', currency='USD', localSymbol='AAPL', tradingClass='NMS')",
    "entry_timestamp": "2023-10-10 01:11:21.286851",
    "entry_price": 178.9,
    "long/short": "long",
    "quantity": 1.0,
    "exit_timestamp" :  "2023-10-10 01:50:21.286851",
    "exit_price" : 179.9
}
```

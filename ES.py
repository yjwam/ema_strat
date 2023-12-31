import datetime
import yfinance as yf
from ib_insync import *
import json
import os
import schedule
import pytz

def create_ib_contract(contract,ib):
    contract = Contract(symbol=contract['symbol'], secType=contract['secType'], exchange=contract['exchange'], currency=contract['currency'], includeExpired=True)
    contract = ib.qualifyContracts(contract)[0]
    return contract

def get_historical_data(ib,contract,barsize,trading_hours,debugging = False):
    # function to get historical data to calculate EMA used Yahoo finacne in debugging
    if debugging:
        sym = contract.symbol
        data = yf.download(tickers=sym,interval='1m')['Adj Close']
    else:
        try:
            RTH = True if trading_hours == "RTH" else False
            bars = ib.reqHistoricalData(
                contract=contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting=barsize,
                whatToShow='TRADES',
                useRTH=RTH)
            data = util.df(bars)['close']
        except Exception as e:
            print("Error:",e)
            ib.sleep(1)
            print("Retrying to get historical data")
            data = get_historical_data(ib,contract,barsize,trading_hours,debugging = False)
    return data

def ema(data,number):
    return data.rolling(window=number).mean().iloc[-1],data.rolling(window=number).mean().iloc[-2]

def live_data(contract,ib,debugging=False):
    # function to fecth live data from ib tws using input for debugging
    if not debugging:
        ib.reqMktData(contract)
        ib.sleep(2)
        bar = ib.ticker(contract)
        price = bar.marketPrice()
        return price
    else:
        return float(input("Enter current price: "))

def place_order(contract,ib,action,quantity):
    order = MarketOrder(action, quantity)
    trade = ib.placeOrder(contract, order)
    while not trade.isDone():
        ib.waitOnUpdate()
    return trade

def update_results(path,contract,trade,first = False):
    # function to write order placed and update order 
    trade = trade.fills[0]
    st = "long" if trade.execution.side == 'BOT' else "short"
    cId = str(contract.conId)+".json"
    path = os.path.join(path,cId)
    if first:
        temp = {"contract":str(trade.contract),"entry_timestamp":str(datetime.datetime.now()),"entry_price":trade.execution.price,'long/short':st,'quantity':trade.execution.shares}
        with open(path, 'w') as f:
            json.dump(temp, f, indent=4)
    else:
        with open(path) as f:
            temp = json.load(f)
        temp["exit_timestamp"] = str(datetime.datetime.now())
        temp['exit_price'] = trade.execution.price
        with open(path, 'w') as f:
            json.dump(temp, f, indent=4)
    return None

def trade_time(contract_info,ib,debugging=False):
    path = "orders"
    contract = create_ib_contract(contract_info['contract'],ib)
    # check any open positions
    print("Checking Open Position")
    open_pos,open_pos_dict = check_open_orders(path,contract)
    if not open_pos:
        print("No Open Position Found")

    trailing_stop = contract_info['trailing_stop_pct']
    taking_profit = contract_info["take_profit_pct"]
    quantity = contract_info['no_contract']
    if not open_pos:

        hist_data = get_historical_data(ib,contract,contract_info['ema_interval'],contract_info["trading_hours"],debugging)
        print("Calculating EMAs")
        emas = contract_info['emas']
        emas = sorted(emas)
        low_ema, low_ema_pre = ema(hist_data,emas[0])
        high_ema, high_ema_pre = ema(hist_data,emas[1])
        print(f" current EMAs : {emas[0]} -> {round(low_ema,5)} , {emas[1]} -> {round(high_ema,5)}")
        print(f" previous EMAs : {emas[0]} -> {round(low_ema_pre,5)} , {emas[1]} -> {round(high_ema_pre,5)}")

        if (low_ema > high_ema and low_ema_pre <= high_ema_pre) and contract_info['action'] == "BUY":
            position = 1
            trade = place_order(contract,ib,"BUY",quantity)
            traded_price = trade.fills[0].execution.price
            stop_loss = (1-trailing_stop/100)*traded_price
            update_results(path,contract,trade,True)
            print("Taking Long Position")

        elif (low_ema < high_ema and low_ema_pre >= high_ema_pre) and contract_info['action'] == "SELL":
            position = -1
            trade = place_order(contract,ib,"SELL",quantity)
            traded_price = trade.fills[0].execution.price
            stop_loss = (1+trailing_stop/100)*traded_price
            update_results(path,contract,trade,True)
            print("Taking Short Position")

        else:
            print("No Position Taken")
            position = 0
    else:
        print("Open Position Found")
        traded_price = open_pos_dict['entry_price']
        position = 1 if open_pos_dict["long/short"] == "long" else -1
        stop_loss = (1-trailing_stop/100)*traded_price if position == 1 else (1+trailing_stop/100)*traded_price

    while position != 0:
        current_price = live_data(contract,ib,debugging)
        print(datetime.datetime.now()," Current Price :",current_price)
        if position*(current_price/traded_price-1)*100 >= taking_profit:
            if position > 0:
                position = 0
                print("Taking Profit")
                trade = place_order(contract,ib,"SELL",quantity)
                update_results(path,contract,trade)
                continue
            else:
                position = 0
                print("Taking Profit")
                trade = place_order(contract,ib,"BUY",quantity)
                update_results(path,contract,trade)
                continue
        if (current_price - stop_loss)*position < 0:
            if position > 0:
                position = 0
                print("Stop Loss Hit")
                trade = place_order(contract,ib,"SELL",quantity)
                update_results(path,contract,trade)
                continue
            else:
                position = 0
                print("Stop Loss Hit")
                trade = place_order(contract,ib,"BUY",quantity)
                update_results(path,contract,trade)
                continue
        new_stop = (1-position*contract_info['trailing_stop_pct']/100)*current_price
        if  (new_stop - stop_loss)*position >= 0:
            stop_loss = new_stop
            print('Trailing Stop Loss',stop_loss)
    return False

def check_open_orders(path,contract):
    cId = str(contract.conId)+".json"
    path = os.path.join(path,cId)
    try:
        with open(path) as f:
            temp = json.load(f)
            if "exit_price" in list(temp.keys()):
                return False, {}
            else:
                return True, temp
    except:
        return False,{}

def main(ib,i):
    print("Starting Algorithm")
    with open(r'contracts\ES.json') as f:
        contract_info = json.load(f)
    job = schedule.every().minute.at(":00").do(trade_time, contract_info = contract_info, ib = ib, debugging = debugging)
    while True:
        now = datetime.datetime.now()
        est_time = now.astimezone(est).time()
        try:
            schedule.run_pending()
            continue
        except Exception as e:
            print("Error:", e)
            ib.disconnect()
            ib = IB()   
            while not ib.isConnected():
                try:
                    ib.connect('127.0.0.1', 7497, clientId=i)
                    schedule.cancel_job(job)
                    job = schedule.every().minute.at(":00").do(trade_time, contract_info = contract_info, ib = ib, debugging = debugging)
                except Exception as e:
                    print("Error:",e)
                    print("Trying to reconnect with TWS")
                    ib.sleep(1)
            print("Reconnect with TWS")
            if debugging:
                raise e
            continue
    return None

debugging = False
ib = IB()
for i in range(1,51):
    try:
        ib.connect('127.0.0.1', 7497, clientId=i)
        print(f"Connected with client ID {i}")
        ib_open = True
        break
    except ConnectionRefusedError:
        ib_open = False
        print("Please open TWS and run code again")
        break
    except:
        ib_open = False
        print(f"Client ID {i} in use")
        continue
est = pytz.timezone('US/Eastern')
if ib_open:
    main(ib,i)
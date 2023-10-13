import datetime
import yfinance as yf
from ib_insync import *
import json
import os
import schedule
import time

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

def create_ib_contract(contract,ib):
    contract = Contract(symbol=contract['symbol'], secType=contract['secType'], exchange=contract['exchange'], currency=contract['currency'], includeExpired=True)
    contract = ib.qualifyContracts(contract)[0]
    return contract

def get_historical_data(contract,barsize,debugging = False):
    # function to get historical data to calculate EMA used Yahoo finacne in debugging
    if debugging:
        sym = contract.symbol
        data = yf.download(tickers=sym,interval='1m')['Adj Close']
    else:
        bars = ib.reqHistoricalData(
            contract=contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting=barsize,
            whatToShow='TRADES',
            useRTH=True)
        data = util.df(bars)['close']
    return data

def ema(data,number):
    return data.rolling(window=number).mean().iloc[-1]

def live_data(contract,ib,debugging=False):
    # function to fecth live data from ib tws using input for debugging
    if not debugging:
        return ib.reqMktData(contract).marketPrice()
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
    print("Start Algo")
    path = "orders"
    contract = create_ib_contract(contract_info['contract'],ib)
    trailing_stop = contract_info['trailing_stop_pct']
    taking_profit = contract_info["take_profit_pct"]
    quantity = contract_info['no_contract']
    hist_data = get_historical_data(contract,contract_info['ema_interval'],debugging)  #yahoo finacnce need to repalce with ib one
    emas = contract_info['emas']
    low_ema = ema(hist_data,emas[0])
    high_ema = ema(hist_data,emas[1])
    print("low ema :",low_ema)
    print("high ema :",high_ema)
    # check any open positions
    open_pos,open_pos_dict = check_open_orders(path,contract)
    if not open_pos:
        if (low_ema > high_ema or True) and contract_info['action'] == "BUY":
            position = 1
            trade = place_order(contract,ib,"BUY",quantity)
            traded_price = trade.fills[0].execution.price
            stop_loss = (1-trailing_stop/100)*traded_price
            update_results(path,contract,trade,True)

        elif low_ema > high_ema and contract_info['action'] == "SELL":
            position = -1
            trade = place_order(contract,ib,"SELL",quantity)
            traded_price = trade.fills[0].execution.price
            stop_loss = (1+trailing_stop/100)*traded_price
            update_results(path,contract,trade,True)

        else:
            position = 0
    else:
        traded_price = open_pos_dict['entry_price']
        position = 1 if open_pos_dict["long/short"] == "long" else -1
        stop_loss = (1-trailing_stop/100)*traded_price if position == 1 else (1+trailing_stop/100)*traded_price


    current_price = live_data(contract,ib,debugging)
    print(datetime.datetime.now()," Current Price :",current_price)
    while position != 0:
        current_price = live_data(contract,ib,debugging)
        print(datetime.datetime.now()," Current Price :",current_price)
        if (current_price/traded_price-1)*100 >= taking_profit:
            if position > 0:
                position = 0
                print("taking profit")
                trade = place_order(contract,ib,"SELL",quantity)
                update_results(path,contract,trade)
                continue
            else:
                position = 0
                print("taking profit")
                trade = place_order(contract,ib,"BUY",quantity)
                update_results(path,contract,trade)
                continue
        if (current_price - stop_loss)*position < 0:
            if position > 0:
                position = 0
                print("stop loss hit")
                trade = place_order(contract,ib,"SELL",quantity)
                update_results(path,contract,trade)
                continue
            else:
                position = 0
                print("stop loss hit")
                trade = place_order(contract,ib,"BUY",quantity)
                update_results(path,contract,trade)
                continue
        new_stop = (1-position*contract_info['trailing_stop_pct']/100)*current_price
        if  (new_stop - stop_loss)*position >= 0:
            stop_loss = new_stop
            print('trailing stop',stop_loss)
        time.sleep(2)
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

def main():
    with open('contracts\AAPL.json') as f:
        contract_info = json.load(f)
    schedule.every().minute.at(":00").do(trade_time, contract_info = contract_info, ib = ib, debugging = debugging)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            if debugging:
                raise e
            continue
    return None

if __name__ == "__main__":
    debugging = False
    main()
# 1、获取市场的订单列表
# 2、获取钱包当前拥有的position，判断是否有利润，如果有就挂单卖出，
#     如果position为[]，代表当前没有持仓，获取最有赚头的市场进行挂单买入
#     如果有持仓，判断当前市场金额是否有赚，有赚就卖出，没赚就挂单当前金额挂单卖出
#     获取当前的挂单，挂单时间超过4小时，则取消当前订单

import math
import os
import random
import time
import httpx
from agents.polymarket.polymarket import Polymarket
from py_clob_client.clob_types import (
    OrderArgs,
    MarketOrderArgs,
    OrderType,
    OrderBookSummary,
    TradeParams,
)
from py_clob_client.order_builder.constants import (
    BUY,
    SELL,
)
from concurrent.futures import ThreadPoolExecutor, as_completed

amount_info = [] ##没有优先级高的就随意取条按最高限额去下单吧
good_amount_info = [] ##优先级高，期望为正的

def get_position(addr:str):
    response = httpx.get("https://data-api.polymarket.com/positions", params={
            'user': addr,
            'limit': 100,
            'offset': 0,
            'sortBy': 'TOKENS',
            'sortDirection' : 'DESC',
        })
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Error {addr} response returned from api: HTTP {response.status_code}:{response.content}")
        return False
    
def get_best_market_amount(addr:str,market_info,market_config):
    if len(amount_info) == 0:
        for item in market_config :
            info = market_info[item["id"]]
            token = info['tokens'][item['outcomeIndex']]
            if token['outcome'] != item['outcome']:
                raise Exception(f"获取token失败:{token}")
            #判断金额
            index = round((item['max_buy_price'] - token['price']),4) ##优先级
            buy_price = item['max_buy_price']
            if buy_price > token['price']:
                buy_price = token['price']
                
            temp = {
                'token_id' : token['token_id'],
                'price' : token['price'],
                'index' : index,
                'buy_price' : buy_price,
            }
            amount_info.append(temp)
     
            if index >= 0:
                good_amount_info.append(temp)

    ##在正的优先级中随机取出一个去下单
    if len(good_amount_info) > 0:
        return random.choice(good_amount_info)

    return random.choice(amount_info)

def get_size(balance,price):
    return math.floor(balance/price)
    
def process_key(private_key,market_info,market_config):
    addr = ""
    try:
        #获取挂单
        polymarket = Polymarket(private_key)
        addr = polymarket.get_address_for_private_key()
        order_infos =  polymarket.client.get_orders()
        i = len(order_infos) - 1
        while i >= 0:
            order = order_infos[i]
            if order['side'] == "Buy":
                max_limit_time = 2*3600
            else:
                max_limit_time = 4*3600
            if (time.time() - order['created_at']) >= max_limit_time:
                polymarket.client.cancel(order['id'])
                print("订单超过限定时间，取消订单")
                del order_infos[i]
            i = i-1
        
        if (len(order_infos) > 0):
            print(f"{addr} 钱包存在合理挂单")
            return True


        cur_position = get_position(addr)
        if cur_position == False:
            print(f"{addr} 获取持仓异常")
            return True
        if len(cur_position) == 0:
            balance = polymarket.get_usdc_balance()
            #没有持仓，获取最划算的市场金额来下单
            amount_info = get_best_market_amount(addr,market_info,market_config)
            size =  math.floor(balance/amount_info['buy_price'])
            order_args = OrderArgs(
                token_id=amount_info['token_id'],
                price=amount_info['buy_price'],
                size=size,
                side=BUY,
            )
            print(f"{addr} 准备下单:{order_args},amount_info:{amount_info}")
            resp = polymarket.client.create_and_post_order(order_args)
            print(f"{addr} 下单结果:{resp}")
        else:
            #有持仓，挂卖单
            #获取这个market的trade，如果持仓时间超过了4小时，就按原价卖，否则就按加一步距卖
            for item in cur_position:
                trade_arg = TradeParams(
                        maker_address=addr,
                        market=item['conditionId'],
                        asset_id=item['asset'],
                        after=int(time.time() - 4*3600),
                )
                trade_info = polymarket.client.get_trades(trade_arg)
                issetTrade = False
                for trade in trade_info:
                    if trade['side'] == "BUY":
                        issetTrade = True

                cur_price = item['avgPrice']
                if issetTrade :
                    cur_price = cur_price+0.001

                if item['curPrice'] > cur_price:
                    cur_price = item['curPrice']

                ##判断是否有限制最小卖出
                cur_config = [config for config in market_config if config["id"] == item['conditionId']]
                if (cur_config[0]['min_sell_price'] != 0)  & (cur_config[0]['min_sell_price'] > cur_price):
                    cur_price = cur_config[0]['min_sell_price']

                order_args = OrderArgs( 
                    token_id=item['asset'],
                    price=cur_price,
                    size=item['size'],
                    side=SELL,
                )
                print(f"{addr} 准备下单:{order_args},amount_info:{item}")
                resp = polymarket.client.create_and_post_order(order_args)
                print(f"{addr} 下单结果:{resp}")
        return True
    except Exception as e:
        print(f"{addr} 处理失败: {private_key}, 错误: {str(e)}")
        return False
            
# 读取私钥列表
def load_keys(path):
    with open(path, 'r') as file:
        return [line.strip() for line in file]

def main():
    pythonpath = os.getenv('PYTHONPATH')
    # 加载所有私钥
    wallets = load_keys(pythonpath+'/autoOrder.txt')
    if not wallets:
        print("没有需要处理的私钥.")
        return

    market_config = [
        {
            'id' :"0x4150752d0efc99377d7388908724cb79e8423768414af7e4a4ee857ac28ef8e3",
            'title' : "Election certified on January 6?",
            "outcome" : "Yes",
            "outcomeIndex" : 0,
            "max_buy_price" : 0.95,
            "min_sell_price" : 0,  #为0则说明最低按照原价出 
        },
        {
            'id' :"0xfa5b660a1366853b220f0420cf8f2367ce618c854d25cfe3451dab9b415ad2a7",
            'title' : "Will China unban Bitcoin by March 31?",
            "outcome" : "No",
            "outcomeIndex" : 1,
            "max_buy_price" : 0.96,
            "min_sell_price" : 0.961,  #为0则说明最低按照原价出 
        },
        {
            'id':"0xc3d4155148681756bfe67bb41d8d0882a8a122e7d3762b3591bf6598c9bd198b",
            'title':"will-donald-trump-be-inaugurated",
            "outcome" : "Yes",
            "outcomeIndex" : 0,
            "max_buy_price" : 0.99,
            "min_sell_price" : 0.99,  #为0则说明最低按照原价出 
        },
        {
            "id":"0xd1e760f57415093db2e8378b79fe37ec8dc9ad09ee57f6f0cdc2468ae29fea23",
            'title':"Will Biden finish his term?",
            "outcome" : "Yes",
            "outcomeIndex" : 0,
            "max_buy_price" : 0.99,
            "min_sell_price" : 0,  #为0则说明最低按照原价出 
        },
    ]

    polymarket = Polymarket()
    market_info = {}

    for item in market_config:
        info = polymarket.client.get_market(item['id'])
        for token in info['tokens']:
            book_info = polymarket.client.get_order_book(token['token_id'])
            book_info = book_info.__dict__
            if len(book_info['bids']) >= 3:
                book_info['bids'] = book_info['bids'][-3:]
            if len(book_info['asks']) >= 3:
                book_info['asks'] = book_info['asks'][-3:]
            token['book'] = book_info
        market_info[item['id']] = info


     # 使用线程池管理
    max_threads = 5
    timeout = 30
    results = []

    with ThreadPoolExecutor(max_threads) as executor:
        results = list(executor.map(lambda w: process_key(w, market_info, market_config), wallets))

    success_count = sum(results)
    total_count = len(results)
    print(f"任务全部完成! 成功: {success_count}/{total_count}")

        

if __name__ == '__main__':
    main()




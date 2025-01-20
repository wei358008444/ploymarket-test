#下1￥的川普限价单，到时mint

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

#市场配置
market_config = {
    'id':"0xc3d4155148681756bfe67bb41d8d0882a8a122e7d3762b3591bf6598c9bd198b",
    'title':"will-donald-trump-be-inaugurated",
    "outcome" : "Yes",
    "outcomeIndex" : 0,
    "buy_price" : 0.995,
    "sell_price" : 0.994,
}
market_info = {}

#母账号,转账过去的账号
pre_pri_key = ""

def retry_on_exception(retries=3, delay=2, exceptions=(Exception,), match_message=None):
    """
    重试装饰器：
    - retries: 最大重试次数
    - delay: 重试间隔时间（秒）
    - exceptions: 捕获的异常类型
    - match_message: 字符串或列表，用于匹配异常消息内容
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < retries:
                try:
                    # 尝试执行函数
                    return func(*args, **kwargs)
                except exceptions as e:
                    # 检查异常消息匹配条件
                    if match_message:
                        error_message = str(e)  # 获取异常消息
                        if isinstance(match_message, str):
                            # 单字符串匹配
                            if match_message not in error_message:
                                raise  e
                        elif isinstance(match_message, (list, tuple)):
                            # 多字符串匹配
                            if not any(msg in error_message for msg in match_message):
                                raise  e

                    # 打印重试信息
                    attempts += 1
                    print(f"第 {attempts} 次重试，异常: {e}")
                    time.sleep(delay)  # 等待指定时间后重试

            # 重试用尽后抛出最后的异常
            raise e
        return wrapper
    return decorator

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

def transfer(to_addr):
    polymarket = Polymarket(pre_pri_key)
    addr = polymarket.get_address_for_private_key()
    try:
        balance_res = polymarket.usdc.functions.balanceOf(
            addr
        ).call()
        print(balance_res)
        if balance_res < 1026113: #1$
            raise Exception("余额不足")
        
        nonce = polymarket.web3.eth.get_transaction_count(addr)
        gas_estimate = polymarket.usdc.functions.transfer(to_addr, 1000000).estimate_gas({"from": addr})
        raw_usdc_approve_txn = polymarket.usdc.functions.transfer(
                to_addr, 1000000
            ).build_transaction({
                "chainId": polymarket.chain_id,
                  "from": addr, 
                  "nonce": nonce,
                  "gas": int(gas_estimate * 1.2),  # 增加 20% 作为缓冲
                  })
        signed_usdc_approve_tx = polymarket.web3.eth.account.sign_transaction(
            raw_usdc_approve_txn, private_key=polymarket.private_key
        )
        send_usdc_approve_tx = polymarket.web3.eth.send_raw_transaction(
            signed_usdc_approve_tx.raw_transaction
        )
        usdc_approve_tx_receipt = polymarket.web3.eth.wait_for_transaction_receipt(
            send_usdc_approve_tx, 600
        )
        print(usdc_approve_tx_receipt)
        return True
    except Exception as e:
        raise Exception(f"转账失败: {addr}, 错误: {str(e)}")
        return False
    
##发送pol
def transferPol(to_addr):
    polymarket = Polymarket(pre_pri_key)
    addr = polymarket.get_address_for_private_key()
    # 获取发送账户的 nonce
    nonce = polymarket.web3.eth.get_transaction_count(addr)

    balance_pol = round(polymarket.web3.eth.get_balance(addr)/10**18,4) 
    print(f"{addr} 的pol余额:{balance_pol}")
    amount = 0.01
    # 构造交易
    transaction = {
        'nonce': nonce,
        'to': to_addr,
        'value': polymarket.web3.to_wei(amount,'ether'),
        'gas': 21000,  # 标准转账的 gas 限制
        'gasPrice': polymarket.web3.eth.gas_price,  # 获取当前 gas 价格
        'chainId': polymarket.chain_id  # Polygon 主网 Chain ID
    }
    # 使用私钥对交易进行签名
    signed_txn = polymarket.web3.eth.account.sign_transaction(transaction, polymarket.private_key)
    # 发送交易
    tx_hash = polymarket.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
    # 等待交易确认
    receipt = polymarket.web3.eth.wait_for_transaction_receipt(tx_hash,600)
    # 输出交易哈希
    print(f'转账pol: {receipt}')

@retry_on_exception(
    retries=2,
    delay=10,
)       
def process_key(private_key):
    polymarket = Polymarket(private_key)
    addr = polymarket.get_address_for_private_key()
    #获取持仓
    cur_position = get_position(addr)
    if cur_position == False:
        raise Exception(f"{addr} 获取持仓异常")
    if len(cur_position) == 0:
        #判断是否要授权
        polymarket._init_approvals(True)
        #获取挂单
        order_infos =  polymarket.client.get_orders()
        i = len(order_infos) - 1
        while i >= 0:
            order = order_infos[i]
            polymarket.client.cancel(order['id'])
        #获取余额，没有统一由一个账号转过来
        balance = polymarket.get_usdc_balance()
        if balance < 1:
            transfer(addr)
            time.sleep(15)
        balance_pol = round(polymarket.web3.eth.get_balance(addr)/10**18,4) 
        if balance < 0.002:
            transferPol(addr)
            time.sleep(15)
        #下单
        token = market_info['tokens'][market_config['outcomeIndex']]
        if token['outcome'] != market_config['outcome']:
            raise Exception(f"获取token失败:{token}")
        order_args = MarketOrderArgs(
                token_id=token['token_id'],
                price=market_config['buy_price'],
                amount=1,
            )
        print(f"{addr} 准备下单:{order_args}")
        signed_order = polymarket.client.create_market_order(order_args)
        resp = polymarket.client.post_order(signed_order, orderType=OrderType.FOK)
        print(f"{addr} 下单结果:{resp}")
        if resp['success'] != True:
            raise Exception(f"下单结果异常")
    else:
        for item in cur_position:
            if item['conditionId'] != market_config['id']:
                raise Exception(f"{addr} 有特殊持仓！！")
    return True
            
# 读取私钥列表
def load_keys(path):
    with open(path, 'r') as file:
        return [line.strip() for line in file]
    
# 更新文件，移除已完成的私钥
def remove_key_from_file(path,key_to_remove):
    with open(path, 'r') as file:
        keys = [line.strip() for line in file]

    keys_to_keep = [key for key in keys if key != key_to_remove]

    with open(path, 'w') as file:
        file.write('\n'.join(keys_to_keep) + '\n')

def main():
    global market_config
    global market_info
    pythonpath = os.getenv('PYTHONPATH')
    path = pythonpath+'/brushOrder.txt'
    # 加载所有私钥
    wallets = load_keys(path)
    if not wallets:
        print("没有需要处理的私钥.")
        return


    polymarket = Polymarket()

    info = polymarket.client.get_market(market_config['id'])
    for token in info['tokens']:
        book_info = polymarket.client.get_order_book(token['token_id'])
        book_info = book_info.__dict__
        if len(book_info['bids']) >= 3:
            book_info['bids'] = book_info['bids'][-3:]
        if len(book_info['asks']) >= 3:
            book_info['asks'] = book_info['asks'][-3:]
        token['book'] = book_info
    market_info = info
    print(market_info)

    for i in range(len(wallets)):
        current_line = wallets[i]
        result = process_key(current_line)
        if result :
            remove_key_from_file(path=path,key_to_remove=current_line)

    # 使用线程池管理
    # max_threads = 5
    # timeout = 30
    # results = []

    # with ThreadPoolExecutor(max_threads) as executor:
    #     results = list(executor.map(lambda w: process_key(w), wallets))

    # success_count = sum(results)
    # total_count = len(results)
    # print(f"任务全部完成! 成功: {success_count}/{total_count}")

        

if __name__ == '__main__':
    main()




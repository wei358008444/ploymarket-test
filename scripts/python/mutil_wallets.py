import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from agents.polymarket.polymarket import Polymarket

# 文件路径
FILE_PATH = '1.txt'


# 读取私钥列表
def load_keys():
    with open(FILE_PATH, 'r') as file:
        return [line.strip() for line in file]

# 更新文件，移除已完成的私钥
def remove_key_from_file(key_to_remove):
    with open(FILE_PATH, 'r') as file:
        keys = [line.strip() for line in file]

    keys_to_keep = [key for key in keys if key != key_to_remove]

    with open(FILE_PATH, 'w') as file:
        file.write('\n'.join(keys_to_keep) + '\n')
        
# 模拟处理任务
def process_key(private_key):
    try:
        polymarket = Polymarket(private_key)
        addr = polymarket.get_address_for_private_key()
        print(addr)
        balance = polymarket.get_usdc_balance()
        print(balance)
        polymarket._init_approvals(True)
        remove_key_from_file(private_key)
        print(f"私钥处理完成: {private_key}")
        return True
    except Exception as e:
        print(f"处理失败: {private_key}, 错误: {str(e)}")
        return False

# 主函数
def main():
    # 加载所有私钥
    private_keys = load_keys()
    if not private_keys:
        print("没有需要处理的私钥.")
        return

    # 使用线程池管理
    max_threads = 10
    timeout = 30
    results = []

    with ThreadPoolExecutor(max_threads) as executor:
        results = list(executor.map(process_key, private_keys))


    print("任务全部完成!")


if __name__ == '__main__':
    main()

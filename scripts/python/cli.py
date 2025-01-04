import typer
from devtools import pprint
import httpx

from agents.polymarket.polymarket import Polymarket
from agents.connectors.chroma import PolymarketRAG
from agents.connectors.news import News
from agents.application.trade import Trader
from agents.application.executor import Executor
from agents.application.creator import Creator
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

app = typer.Typer()
polymarket = Polymarket()
newsapi_client = News()
polymarket_rag = PolymarketRAG()


@app.command()
def get_all_markets(limit: int = 5, sort_by: str = "spread") -> None:
    """
    Query Polymarket's markets
    """
    print(f"limit: int = {limit}, sort_by: str = {sort_by}")
    markets = polymarket.get_all_markets()
    markets = polymarket.filter_markets_for_trading(markets)
    if sort_by == "spread":
        markets = sorted(markets, key=lambda x: x.spread, reverse=True)
    markets = markets[:limit]
    pprint(markets)


@app.command()
def get_relevant_news(keywords: str) -> None:
    """
    Use NewsAPI to query the internet
    """
    articles = newsapi_client.get_articles_for_cli_keywords(keywords)
    pprint(articles)


@app.command()
def get_all_events(limit: int = 5, sort_by: str = "number_of_markets") -> None:
    """
    Query Polymarket's events
    """
    print(f"limit: int = {limit}, sort_by: str = {sort_by}")
    events = polymarket.get_all_events()
    events = polymarket.filter_events_for_trading(events)
    if sort_by == "number_of_markets":
        events = sorted(events, key=lambda x: len(x.markets), reverse=True)
    events = events[:limit]
    pprint(events)


@app.command()
def create_local_markets_rag(local_directory: str) -> None:
    """
    Create a local markets database for RAG
    """
    polymarket_rag.create_local_markets_rag(local_directory=local_directory)


@app.command()
def query_local_markets_rag(vector_db_directory: str, query: str) -> None:
    """
    RAG over a local database of Polymarket's events
    """
    response = polymarket_rag.query_local_markets_rag(
        local_directory=vector_db_directory, query=query
    )
    pprint(response)


@app.command()
def ask_superforecaster(event_title: str, market_question: str, outcome: str) -> None:
    """
    Ask a superforecaster about a trade
    """
    print(
        f"event: str = {event_title}, question: str = {market_question}, outcome (usually yes or no): str = {outcome}"
    )
    executor = Executor()
    response = executor.get_superforecast(
        event_title=event_title, market_question=market_question, outcome=outcome
    )
    print(f"Response:{response}")


@app.command()
def create_market() -> None:
    """
    Format a request to create a market on Polymarket
    """
    c = Creator()
    market_description = c.one_best_market()
    print(f"market_description: str = {market_description}")


@app.command()
def ask_llm(user_input: str) -> None:
    """
    Ask a question to the LLM and get a response.
    """
    executor = Executor()
    response = executor.get_llm_response(user_input)
    print(f"LLM Response: {response}")


@app.command()
def ask_polymarket_llm(user_input: str) -> None:
    """
    What types of markets do you want trade?
    """
    executor = Executor()
    response = executor.get_polymarket_llm(user_input=user_input)
    print(f"LLM + current markets&events response: {response}")


@app.command()
def run_autonomous_trader() -> None:
    """
    Let an autonomous system trade for you.
    """
    trader = Trader()
    trader.one_best_trade()

@app.command()
def get_balance()-> None:
    balance = polymarket.get_usdc_balance()
    pprint(balance)

@app.command()
def get_order()-> None:
    info = polymarket.client.get_order()
    pprint(info)

@app.command()
def create_test_order()-> None:
    balance = polymarket.get_usdc_balance()
    pprint(balance)
    order_args = OrderArgs(
            token_id='24635636911615866092589652362670811323984202357282728474473612545495782013438',
            price=0.32,
            size=5,
            side=SELL,
        )
    signed_order = polymarket.client.create_order(order_args)
    print("Execute market order... signed_order ", signed_order)
    resp = polymarket.client.post_order(signed_order, orderType=OrderType.GTC)
    print(resp)
    print("Done!")
    return resp

@app.command()
def get_trades()->None:
    print(polymarket.client.get_address())
    balance = polymarket.get_usdc_balance()
    pprint(balance)
    trades_params = TradeParams(
        # maker_address='0x5327D641188F211D9846A91639665C8D0E5EC5Ab',
        maker_address=polymarket.client.get_address(),
        after=1735574400
    )
    trades_info = polymarket.client.get_trades(trades_params)
    for info in trades_info:
        market_info = polymarket.client.get_market(info['market'])
        info['market_info'] = {
           'question' :  market_info['question'],
           'tokens' :  market_info['tokens'],
        }
    pprint(trades_info)

@app.command()
def get_order()->None:
    order_info = polymarket.client.get_orders()
    #补全order
    for info in order_info:
        market_info = polymarket.client.get_market(info['market'])
        info['market_info'] = {
           'question' :  market_info['question'],
           'tokens' :  market_info['tokens'],
        }
    pprint(order_info)

@app.command()
def cancel_all_order()->None:
    order_info = polymarket.client.cancel_all() 
    pprint(order_info)

@app.command()
def cancel_order()->None:
    order_info = polymarket.client.cancel("0xd98ff22d11f29833c37c7d551b79a6bd13abff12f70ca3d830515f4087559e32")
    pprint(order_info)
   
@app.command()
def get_market()->None:
    #tiktok-banned-in-the-us-in-2024
    #yes
    #92183702303563122069416277238283804483148544865270859128510579897460690048203
    #no
    #56146919834196908404256110241417464069562619059315782848423172398245672612969
    info = polymarket.client.get_market("0xd1e760f57415093db2e8378b79fe37ec8dc9ad09ee57f6f0cdc2468ae29fea23") 
    #把订单也整合上去
    for token in info['tokens']:
        book_info = polymarket.client.get_order_book(token['token_id'])
        book_info = book_info.__dict__
        if len(book_info['bids']) >= 3:
            book_info['bids'] = book_info['bids'][-3:]
        if len(book_info['asks']) >= 3:
            book_info['asks'] = book_info['asks'][-3:]
        token['book'] = book_info
    pprint(info)

@app.command()
def get_book()->None:
    info = polymarket.client.get_order_book("54782008865575348694327270605889335720485919569869265118387677130571469723915")
    pprint(info)

@app.command()
def get_position(addr :str = "")->None:
    if addr == "":
        addr = polymarket.client.get_address()
    pprint(addr)
    response = httpx.get("https://data-api.polymarket.com/positions", params={
         'user': addr,
         'limit': 100,
         'offset': 0,
         'sortBy': 'TOKENS',
         'sortDirection' : 'DESC',
     })
    if response.status_code == 200:
        data = response.json()
        pprint(data)
    else:
        print(f"Error response returned from api: HTTP {response.status_code}:{response.content}")
        raise Exception()


@app.command()
def mutil_wallet()->None:
    wallets = [
    ]

    #批量去授权
    i = 1
    for pri in wallets:
        polymarket = Polymarket(pri)
        addr = polymarket.get_address_for_private_key()
        print(addr)
        # balance = polymarket.get_usdc_balance()
        # print(balance)

        # info = polymarket.client.get_orders()
        # print(info)

        # get_position(addr)

        order_args = OrderArgs(
            token_id='5690379412844472378491285614065764289522424365063615941331551001296177725370',
            price=0.993,
            size=40,
            side=SELL,
        )
        signed_order = polymarket.client.create_order(order_args)
        print("Execute market order... signed_order ", signed_order)
        resp = polymarket.client.post_order(signed_order, orderType=OrderType.GTC)
        print(resp)

        print("Done!")
        print(f"{i}钱包成功")
        i = i+1


if __name__ == "__main__":
    app()

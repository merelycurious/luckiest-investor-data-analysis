# Script to download all daily stock prices for 2018 from IEX.
# To run: TODO

import datetime
import json
import urllib.request

# Downloads a list of stock symbols available at IEX.
# Returns a list of (symbol, name) pairs.
def download_symbol_names():
	request_url = "https://api.iextrading.com/1.0/ref-data/symbols"
	
	request = urllib.request.urlopen(request_url)
	response = request.read().decode('utf-8')
	parsed_response = json.loads(response)

	return list(map(lambda x: (x['symbol'], x['name']), parsed_response))


def parse_date_string(date_string):
	return datetime.datetime.strptime(date_string, '%Y-%m-%d')

max_batch_size = 100
# Downloads one batch of daily prices from 2018 for given symbols (at most 100).
def download_one_batch_prices(symbols_list):
	assert len(symbols_list) <= max_batch_size

	raw_request_url = "https://api.iextrading.com/1.0/stock/market/batch?types=chart&range={}&{}"
	timerange = "2y"
	
	symbols_str = ",".join(symbols_list)
	symbols_param = urllib.parse.urlencode({"symbols": symbols_str})
	request_url = raw_request_url.format(timerange, symbols_param)
	request = urllib.request.urlopen(request_url)
	response = request.read().decode('utf-8')
	parsed_response = json.loads(response)
	
	daily_prices = {}
	for symbol in symbols_list:
		raw_data = parsed_response[symbol]['chart']
		daily_symbol_prices = map(
			(lambda x:
				(x.get('date'),
				 x.get('volume'),
				 x.get('low', None),
				 x.get('high', None),
				 x.get('open', None),
				 x.get('close', None))
			), raw_data);

		daily_symbol_prices = list(filter(
			lambda x: parse_date_string(x[0]).year == 2018, daily_symbol_prices))

		daily_prices[symbol] = daily_symbol_prices

	return daily_prices

# Downloads daily prices from 2018 for given symbols.
def download_prices(symbols_list):
	daily_prices = {}

	batches = [symbols_list[i:i+max_batch_size] for i in range(0, len(symbols_list), max_batch_size)]
	for batch in batches:
		batch_daily_prices = download_one_batch_prices(batch)
		daily_prices.update(batch_daily_prices)

	return daily_prices

def main():
	symbol_names = download_symbol_names()
	with open("symbol_names.json", "w") as f:
		f.write(json.dumps(symbol_names))

	symbols = list(map(lambda x: x[0], symbol_names))
	daily_prices = download_prices(symbols)
	with open("daily_prices.json", "w") as f:
		f.write(json.dumps(daily_prices))

if __name__ == "__main__":
	main()
# Script to calculate the best investment sequence.
# See the list of dependencies below.

# To run: python3 optimize.py

import json
import logging
import datetime
import copy

# Dependencies:
daily_prices_filepath = "daily_prices.json"
s_p_500_constituents_filepath = "constituents_json.json"

cash_symbol_id = 0
cash_symbol = "USD_cash"

start_cash_amount = 1000

# Reads daily prices as a dictionary <symbol> -> <price point list>,
# where each price point consinsts of:
# - date string e.g. '2018-12-31'
# - traded volume
# - low
# - high
# - open
# - close
# Absent prices are denoted as None.
def read_daily_prices():
	with open(daily_prices_filepath, "r") as f:
		return json.loads(f.read())

# Reads constituents of S&P 500 index as a list of symbols.
def read_s_p_500():
	with open(s_p_500_constituents_filepath, "r") as f:
		return list(map(lambda x: x['Symbol'], json.loads(f.read())))

# Prepares the raw data for the optimization.
# Selects only prices for dates in [start_date, end_date).
# If selected_symbols is given, only these symbols will be processed.
# It is forbidden to buy symbols with price lower than lowest_allowed_price_to_buy,
# this is achieved by artifically setting such buying prices to infinity.
# Returns
# - sell_prices - a matrix with prices at which a given symbol could
#   have been sold at that date.
# - buy_prices - same, but for buying.
# - mappings - mappings between matrices rows/columns and dates/symbols.
def preprocess_data(daily_prices, start_date, end_date, lowest_allowed_price_to_buy=0, selected_symbols=None):
	# Working with numeric ids is simples, so let's map all symbols
	# and dates to numbers.

	# Add special value for cash manually.
	symbol_to_id = {cash_symbol: cash_symbol_id}
	id_to_symbol = [cash_symbol]
	for symbol in daily_prices.keys():
		symbol_to_id[symbol] = len(symbol_to_id)
		id_to_symbol.append(symbol)

	date_to_id = {}
	id_to_date = []
	date = start_date
	while(date != end_date):
		date_string = datetime.datetime.strftime(date, "%Y-%m-%d")
		date_to_id[date_string] = len(date_to_id)
		id_to_date.append(date_string)

		date = date + datetime.timedelta(days=1)

	# Let's prepate two matrices for the optimization:
	# - sell_prices[date_id][symbol_id] - price at which a given symbol could
	#   have been sold at that date.
	# - buy_prices[date_id][symbol_id] - same, but for buying.
	# None denotes that it was impossible (e.g. not a trading day).
	sell_prices = [[None] * len(symbol_to_id) for i in range(len(date_to_id))]
	buy_prices = copy.deepcopy(sell_prices)

	# Some stats to make sure that we don't drop too much data.
	symbols_dropped = 0
	price_points_dropped = 0
	price_points_forbidden_to_buy = 0
	overall_price_points = 0
	for symbol, price_points in daily_prices.items():
		# If only some symbols should be selected, drop all others.
		if selected_symbols and symbol not in selected_symbols:
			symbols_dropped = symbols_dropped + 1
			continue

		symbol_id = symbol_to_id[symbol]
		for price_point in price_points:
			overall_price_points = overall_price_points + 1

			date_id = date_to_id[price_point[0]]
			volume = price_point[1]
			prices = price_point[2:]
			# Ignore items with missing prices, because they can be weird (e.g. "price" jump
			# from 0.9 to 87359.95 in 1 day for ZAZZT on 2018-05-31).
			if None in prices:
				price_points_dropped = price_points_dropped + 1
				continue
			# Ignore items with all 4 price values being equal.
			if max(prices) == min(prices):
				price_points_dropped = price_points_dropped + 1
				continue
			# Ignore items with too large of a price jump (10x) in one day.
			if max(prices) / min(prices) > 10:
				price_points_dropped = price_points_dropped + 1
				continue
			# Ignore items with low trading volume.
			if volume <= 1000:
				price_points_dropped = price_points_dropped + 1
				continue

			# We assume the best case, i.e. selling at the highest price and
			# buying at the lowest.
			sell_prices[date_id][symbol_id] = max(prices)
			buy_prices[date_id][symbol_id] = min(prices)

			if buy_prices[date_id][symbol_id] < lowest_allowed_price_to_buy:
				price_points_forbidden_to_buy = price_points_forbidden_to_buy + 1
				buy_prices[date_id][symbol_id] = 1e9
	logging.info("symbols dropped: {} (out of {})".format(
		symbols_dropped, len(daily_prices)))
	logging.info("price points dropped: {} (out of {})".format(
		price_points_dropped, overall_price_points))
	logging.info("price points forbidden to buy: {} (out of {})".format(
		price_points_forbidden_to_buy, overall_price_points - price_points_dropped))

	mappings = (symbol_to_id, id_to_symbol, date_to_id, id_to_date)
	return (sell_prices, buy_prices, mappings)

# Calculates the best stock sequence to get the largest return.
# Returns two matrices:
# - best_quantity[date_id][symbol_id] - what is the max quantity of a given symbol
#   we can own at a given date evening (i.e. after performing an action).
# - best_move[date_id][symbol_id] - which symbol we should have owned yesterday
# 	to be able to get best_quantity[date_id][symbol_id] today (i.e. this implicitly
# 	denotes the last optimal action).
def optimize(sell_prices, buy_prices):
	date_quantity = len(sell_prices)
	symbol_quantity = len(sell_prices[0])

	# best_quantity[date_id][symbol_id] - what is the max quantity of a given symbol
	# we can own at a given date (evening, i.e. after performing an action).
	best_quantity = [[0] * symbol_quantity for i in range(date_quantity)]
	# best_move[date_id][symbol_id] - which symbol we should have owned yesterday
	# to be able to get best_quantity[date_id][symbol_id] today (i.e. this implicitly
	# denotes the last optimal action).
	best_move = [[None] * symbol_quantity for i in range(date_quantity)]

	# On the evening of the first day, we just have some USD and nothing else.
	best_quantity[0][cash_symbol_id] = start_cash_amount

	for date_id in range(1, date_quantity):
		# Perform all possible actions:
		# 1) Just hold what we had yesterday.
		for symbol_id in range(0, symbol_quantity):
			best_quantity[date_id][symbol_id] = best_quantity[date_id-1][symbol_id]
			best_move[date_id][symbol_id] = symbol_id

		for symbol_id in range(0, symbol_quantity):
			if symbol_id == cash_symbol_id:
				continue

			# 2) Sell.
			sell_price = sell_prices[date_id][symbol_id]
			if sell_price:
				yesterday_evening_quantity = best_quantity[date_id-1][symbol_id]
				proceeds = yesterday_evening_quantity * sell_price
				if proceeds > best_quantity[date_id][cash_symbol_id]:
					best_quantity[date_id][cash_symbol_id] = proceeds
					best_move[date_id][cash_symbol_id] = symbol_id

			# 3) Buy.
			buy_price = buy_prices[date_id][symbol_id]
			if buy_price:
				cash_yesterday_evening = best_quantity[date_id-1][cash_symbol_id]
				quantity_bought = cash_yesterday_evening / buy_price
				if quantity_bought > best_quantity[date_id][symbol_id]:
					best_quantity[date_id][symbol_id] = quantity_bought
					best_move[date_id][symbol_id] = 0

	return (best_quantity, best_move)

# Takes optimization result and returns the optimal sequence of symbols to achieve
# that result. The first date is ommited (when we have only cash).
def restore_solution(best_move):
	date_quantity = len(best_move)

	owned_symbol_id = cash_symbol_id
	solution = []
	for date_id in reversed(range(1, date_quantity)):
		solution.append(owned_symbol_id)
		owned_symbol_id = best_move[date_id][owned_symbol_id]

	return list(reversed(solution))

# Returns whether explicitly replaying a given solution leads to the optimal final
# amount of cash (i.e. matches optimization results).
def verify_solution(solution, best_quantity, sell_prices, buy_prices):
	best_cash = best_quantity[-1][cash_symbol_id]

	current_quantity = start_cash_amount
	current_symbol_id = cash_symbol_id

	for i, next_symbol_id in enumerate(solution):
		# Solution does not contain the first day when we have only cash.
		date_id = i + 1

		if next_symbol_id != current_symbol_id:
			if current_symbol_id == 0:
				price = buy_prices[date_id][next_symbol_id]
				current_quantity = current_quantity / price
			else:
				price = sell_prices[date_id][current_symbol_id]
				current_quantity = current_quantity * price
			current_symbol_id = next_symbol_id

	return best_cash == current_quantity

# Calculates returns on investment (overall, daily and yearly).
# Returns ratios, not percentages.
def calculate_return_on_investment(value_now, initial_value, days):
	overall_return_on_investment = (value_now - initial_value) / initial_value
	daily_return_on_investment = (overall_return_on_investment + 1) ** (1 / days) - 1 
	return (overall_return_on_investment,
			daily_return_on_investment)

# Returns a given solution as a human readable string.
def get_pretty_solution_string(solution, best_quantity, sell_prices, buy_prices, id_to_date, id_to_symbol):
	best_cash = best_quantity[-1][cash_symbol_id]

	s = "cash in the end (scientific): {:.2g}\n".format(best_cash)
	s = s + "cash in the end (full number): {:.2f}\n".format(best_cash)
	overall_roi, daily_roi = calculate_return_on_investment(
		best_cash, start_cash_amount, days = 365)
	s = s + "ROI {overall:.2g}%, daily {daily:.2f}%\n\n".format(
		overall = overall_roi * 100,
		daily = daily_roi * 100)


	current_quantity = start_cash_amount
	current_symbol_id = cash_symbol_id
	bought_at_price = None
	bought_at_date_id = None

	for i, next_symbol_id in enumerate(solution):
		# Solution does not contain the first day when we have only cash.
		date_id = i + 1
		date = id_to_date[date_id]

		if next_symbol_id == current_symbol_id:
			continue
	
		if current_symbol_id == 0:
			action_string = "buy"
			target_symbol = id_to_symbol[next_symbol_id]
			price = buy_prices[date_id][next_symbol_id]
			current_quantity = current_quantity / price

			bought_at_price = price
			bought_at_date_id = date_id
		else:
			action_string = "sell"
			target_symbol = id_to_symbol[current_symbol_id]
			price = sell_prices[date_id][current_symbol_id]
			current_quantity = current_quantity * price
		current_symbol_id = next_symbol_id

		s = s + "{date} {action} {symbol} @ {price}".format(
			date = date,
			action = action_string,
			symbol = target_symbol,
			price = price)

		if action_string == "sell":
			overall_roi, daily_roi = calculate_return_on_investment(
				price, bought_at_price, days = date_id - bought_at_date_id)

			s = s + " => ${money:.2g}, ROI {overall:.2f}%, daily {daily:.2f}%".format(
				money = current_quantity,
				overall = overall_roi * 100,
				daily = daily_roi * 100)

		s = s + "\n"
		
	return s

# Runs the optimization and outputs results.
def optimize_and_output_results(sell_prices, buy_prices, mappings):
	best_quantity, best_move = optimize(sell_prices, buy_prices)
	solution = restore_solution(best_move)

	is_correct = verify_solution(solution, best_quantity, sell_prices, buy_prices)

	print("Passed verification: ", is_correct)
	
	symbol_to_id, id_to_symbol, date_to_id, id_to_date = mappings
	
	solution_string = get_pretty_solution_string(solution, best_quantity, 
												sell_prices, buy_prices, 
												id_to_date, id_to_symbol)
	print (solution_string)

def main():
	logging.basicConfig(level="INFO")
	
	daily_prices = read_daily_prices()

	# First, let's optimize without price limitations (i.e. allowing penny stocks).
	print("== with penny stocks ==")
	sell_prices, buy_prices, mappings = preprocess_data(
		daily_prices,
		start_date = datetime.datetime(year=2017, month=12, day=31),
		end_date = datetime.datetime(year=2019, month=1, day=1),
		lowest_allowed_price_to_buy = 0)

	optimize_and_output_results(sell_prices, buy_prices, mappings)
	
	# Then no penny stocks.
	print("== without penny stocks ==")
	sell_prices, buy_prices, mappings = preprocess_data(
		daily_prices,
		start_date = datetime.datetime(year=2017, month=12, day=31),
		end_date = datetime.datetime(year=2019, month=1, day=1),
		lowest_allowed_price_to_buy = 5)

	optimize_and_output_results(sell_prices, buy_prices, mappings)
	
	# Then no penny stocks and only S&P 500.
	print("== only S&P 500 and without penny stocks ==")
	s_p_500 = read_s_p_500()
	sell_prices, buy_prices, mappings = preprocess_data(
		daily_prices,
		start_date = datetime.datetime(year=2017, month=12, day=31),
		end_date = datetime.datetime(year=2019, month=1, day=1),
		lowest_allowed_price_to_buy = 5,
		selected_symbols=s_p_500)

	optimize_and_output_results(sell_prices, buy_prices, mappings)

if __name__ == "__main__":
	main()

This is the code I used for [my post about the luckiest investor](https://merelycurious.me/post/luckiest-investor-or-investing-when-knowing-the-future) (i.e. investing performance when knowing the future). Please see the blog post for the
assumptions, results as well as the optimization approach description.

To run:
1)  Start with 

	```bash
 	python3 download_data.py
  	```

  	This will download the data from IEX and save it in `daily_prices.json` in
  	the same folder. The resulting file is ~100 MB, but the download itself will
  	take 1 GB.


2)  Run the analysis itself

	```bash
 	python3 optimize.py
  	```
    
    This will write results into `results.txt`.
    
There are no dependencies (except IEX providing the data itself).
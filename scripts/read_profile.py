import pstats

# Create a Stats object
p = pstats.Stats("profile.out")

# Sort the statistics by cumulative time and print the top 20
p.sort_stats("cumulative").print_stats(20)

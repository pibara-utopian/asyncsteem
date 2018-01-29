#!/usr/bin/python3
import steem
import time
nodes = nodes=["https://rpc.buildteam.io/",
               "https://steemd.minnowsupportproject.org/",
               "https://steemd.pevo.science/",
               "https://rpc.steemviz.com/",
               "https://seed.bitcoiner.me/",
               "https://rpc.steemliberator.com/",
               "https://api.steemit.com/",
               "https://steemd.privex.io/"]
steemd = steem.steemd.Steemd(nodes)
blockchain = steem.blockchain.Blockchain(steemd)
last_block = 19273700
ltime = time.time()
for entry in slockchain.stream_from(last_block):
    block_no = entry["block"]
    if block_no != last_block:
        last_block = block_no
        if last_block % 100 == 0:
            now = time.time()
            duration = now - ltime
            ltime = now
            print("* 100 blocks processed in",duration,"seconds")


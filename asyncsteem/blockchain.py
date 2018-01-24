import jsonrpc

class ActiveBlockChain:
    def __init__(self,reactor,nodes=["rpc.buildteam.io",
                                        "steemd.minnowsupportproject.org",
                                        "steemd.pevo.science",
                                        "rpc.steemviz.com",
                                        "seed.bitcoiner.me",
                                        "rpc.steemliberator.com",
                                        "api.steemit.com",
                                        "steemd.privex.io"]):
        self.reactor = reactor
        self.nodes=nodes
        self.bots = dict()
        self.blk = 18888888
        self.rpc = jsonrpc.Client(reactor,nodes,self)
    def register_bot(self,bot,botname, persistence = False, blockchain_timers = {"hour" : 3600, "day" : 86400, "week" : 604800},rich_events = ["vote"]):
        newbot = dict()
        newbot["code"] = bot
        self.bots[botname] = newbot
    def start(self):
        self.rpc.get_block(self.blk)
    def __call__(self,blk):
        ts = blk["timestamp"]
        print "=== BLOCK " + str(self.blk) + " " + ts + " ==="
        for transaction in blk["transactions"]:
            for operation in transaction["operations"]:
                et = operation[0]
                obj = operation[1]
                #print ts, et, obj
        self.blk = self.blk + 1
        self.start()


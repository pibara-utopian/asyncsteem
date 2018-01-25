import jsonrpc

class VotesEnhancer:
    def __init__(self,abc,block):
        self.abc = abc
        self.block = block
    def start(self):
        self.abc.start()

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
        self.blk = 19273700
        self.rpc = jsonrpc.Client(reactor,nodes,self)
    def register_bot(self,bot,botname, persistence = False, blockchain_timers = {"hour" : 3600, "day" : 86400, "week" : 604800},rich_events = ["vote"]):
        newbot = dict()
        newbot["code"] = bot
        self.bots[botname] = newbot
    def start(self):
        self.rpc.get_block(self.blk)
    def __call__(self,blk):
        if blk != None and "timestamp" in blk:
            ts = blk["timestamp"]
            print "=== BLOCK " + str(self.blk) + " " + ts + " ==="
            veh = VotesEnhancer(self,blk)
            self.blk = self.blk + 1
            veh.start()
        else:
            print("-spin")
            self.start()


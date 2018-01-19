
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
    def register_bot(self,bot,botname, persistence = False, blockchain_timers = {"hour" : 3600, "day" : 86400, "week" : 604800},rich_events = ["vote"]):
        newbot = dict()
        newbot["code"] = bot
        self.bots[botname] = newbot
    def start(self):
        pass


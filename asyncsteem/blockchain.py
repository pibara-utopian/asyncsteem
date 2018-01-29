import jsonrpc
import copy
import dateutil.parser

class Continue:
    def __init__(self,abc,bot):
        self.abc=abc
        self.bot=bot
    def __call__(self):
        self.abc._cont(self.bot)

class ActiveBlockChain:
    def __init__(self,reactor,nodes=["rpc.buildteam.io",
                                     "steemd.minnowsupportproject.org",
                                     "steemd.pevo.science",
                                     "rpc.steemviz.com",
                                     "seed.bitcoiner.me",
                                     "rpc.steemliberator.com",
                                     "api.steemit.com",
                                     "steemd.privex.io"],parallel = 8):
        self.reactor = reactor #Twisted reactor to use
        self.nodes=nodes       #List of steemit full API nodes
        self.blk = 19273700    #FIXME: block number, should not be a static number.
        self.rpc = jsonrpc.Client(reactor,nodes,self) 
        self.throttle_info = set() #Set of bots that currently want the block streem to throttle.
        self.throttled = False #Start off unthrottled.
        self.active_events = dict() #The list of events the active bots are subscribed to.
        self.ddt = None
        self.count = 0
        self.parallel = parallel
    def register_bot(self,bot,botname):
        #Each method of the object not starting with an underscore is a handler of operation events
        for key in dir(bot):
            if key[0] != "_":
                #Create a new dict if no bots are yet registered for this event.
                if not key in self.active_events:
                    self.active_events[key] = dict()
                #Add handler by bot name.
                self.active_events[key][botname] = getattr(bot,key)
    def start(self):
        #Start of by fetching a clock of operations
        while self.count < self.parallel:
            self.count = self.count + 1
            self.rpc.get_block(self.blk)
            if self.count < self.parallel:
                self.blk = self.blk + 1
    def _cont(self,botname):
        if botname in self.throttle_info:
            self.throttle_info.remove(botname)
        #If no 'other' bots desire throttling to continue, go and fetch the next block of operations.
        if len(self.throttle_info) == 0 and self.throttled:
            self.start()
    #The __call__ method is to be called only by the jsonrpc client!
    def __call__(self,blk):
        self.count = self.count - 1
        if blk != None and "timestamp" in blk:
            ts = blk["timestamp"]
            ddt = None
            try:
                ddt = dateutil.parser.parse(ts)
            except:
                pass
            if ddt !=None:
                if self.ddt == None:
                    self.ddt = ddt
                else:
                    if ddt > self.ddt and ddt.hour != self.ddt.hour:
                        self.ddt = ddt
                        obj = dict()
                        obj["year"] = ddt.year
                        obj["month"] = ddt.month
                        obj["day"] = ddt.day
                        obj["weekday"] = ddt.weekday()
                        obj["hour"] = ddt.hour
                        if "hour" in self.active_events:
                            for bot in self.active_events["hour"].keys():
                                try:
                                    self.active_events["hour"][bot](ts,obj,Continue(self,bot))
                                except:
                                    print("Error in bot '"+bot+"' processing 'hour' event.")
                        if ddt.hour == 0 and "day" in self.active_events:
                            for bot in self.active_events["day"].keys():
                                try:
                                    self.active_events["day"][bot](ts,obj,Continue(self,bot))
                                except:
                                    print("Error in bot '"+bot+"' processing 'day' event.")
                        if ddt.hour == 0 and ddt.weekday == 0 and "week" in self.active_events:
                            for bot in self.active_events["week"].keys():
                                try:
                                    self.active_events["week"][bot](ts,obj,Continue(self,bot))
                                except:
                                    print("Error in bot '"+bot+"' processing 'week' event.")
            blk_meta = dict()
            for k in ["witness_signature",
                      "block_id",
                      "signing_key",
                      "transaction_merkle_root",
                      "witness","previous"]:
                if k in blk:
                    blk_meta[k] = blk[k]
            if "block" in self.active_events:
                for bot in self.active_events["block"].keys():
                    try:
                        self.active_events["block"][bot](ts,blk_meta,Continue(self,bot))
                    except:
                        print("Error in bot '"+bot+"' processing 'block' event.")
            if "transactions" in blk and isinstance(blk["transactions"],list):
                for index in range(0,len(blk["transactions"])):
                    transaction_meta = dict()
                    transaction_meta["block_meta"] = copy.copy(blk_meta)
                    if "transaction_ids" in blk and isinstance(blk["transaction_ids"],list) and len(blk["transaction_ids"]) > index:
                        transaction_meta["id"] = blk["transaction_ids"][index]
                    for k in ["ref_block_prefix","ref_block_num","expiration"]:
                        if k in blk["transactions"][index]:
                            transaction_meta[k] = blk["transactions"][index][k] 
                    if "transaction" in self.active_events:
                        for bot in self.active_events["transaction"].keys():
                            try:
                                self.active_events["transaction"][bot](ts,transaction_meta,Continue(self,bot))
                            except:
                                print("Error in bot '"+bot+"' processing 'transaction' event.")
                    if "operations" in blk["transactions"][index] and isinstance(blk["transactions"][index]["operations"],list):
                        for oindex in range(0,len(blk["transactions"][index]["operations"])):
                            operation = blk["transactions"][index]["operations"][oindex]
                            if isinstance(operation,list) and \
                               len(operation) == 2 and \
                               (isinstance(operation[0],str) or isinstance(operation[0],unicode)) and \
                               isinstance(operation[1],object) and \
                               operation[0] in self.active_events:
                                op = copy.copy(operation[1])
                                op["operation_no"] = oindex
                                op["transaction_meta"] = copy.copy(transaction_meta)
                                for bot in self.active_events[operation[0]].keys():
                                    try:
                                        self.active_events[operation[0]][bot](ts,op,Continue(self,bot))
                                    except:
                                        print("Error in bot '"+bot+"' processing '" + operation[0] + "' event.")
            self.blk = self.blk + 1
            if "throttle" in self.active_events:
                for bot in self.active_events["throttle"].keys():
                    needstrottle = False
                    try:
                        needstrottle = self.active_events["throttle"][bot]()
                    except:
                        print("Error in bot '"+bot+"' processing 'throttle' hook.")
                    if needstrottle:
                        self.throttle_info.add(bot)

            if len(self.throttle_info) == 0:
                self.start()
            else:
                self.throttled = True
        else:
            #We got an error, probably because the block didn't exist yet.
            #print("-spin")
            self.start()

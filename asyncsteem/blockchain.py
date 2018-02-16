#!/usr/bin/python
from jsonrpc import RpcClient
from blockfinder import DateFinder
import copy
import dateutil.parser
import time
from datetime import date
from datetime import datetime as dt
from dateutil import relativedelta
from termcolor import colored


class ActiveBlockChain:
    def __init__(self,reactor,log,nodelist=None,nodes=None,rewind_days=None):
        self.log = log
        self.reactor = reactor #Twisted reactor to use
        self.last_block = 1    #Not the block we are looking for.
        if nodelist==None:
            if nodes == None:
                self.rpc = RpcClient(reactor,log)
            else:
                self.rpc = RpcClient(reactor,log,nodes=nodes)
        else:
            self.rpc = RpcClient(reactor,log,nodelist=nodelist)
        datefinder = DateFinder(self.rpc,log)
        if rewind_days == None:
            datefinder(self._bootstrap,None)
        else:
            ddt = date.today() - relativedelta.relativedelta(hour=0,days=rewind_days)
            datefinder(self._bootstrap,ddt)
        self.active_events = dict() #The list of events the active bots are subscribed to.
        self.ddt = None
        self.last_ddt = None
        self.synced = False
        self.count = 0
        self.eventtypes = set()
        self.sync_block = None
        self.active_block_queries = 0
        self.rpc()
    def register_bot(self,bot,botname):
        #Each method of the object not starting with an underscore is a handler of operation events
        for key in dir(bot):
            if key[0] != "_":
                #Create a new dict if no bots are yet registered for this event.
                if not key in self.active_events:
                    self.active_events[key] = dict()
                #Add handler by bot name.
                self.active_events[key][botname] = getattr(bot,key)
    def _get_block(self,blockno):
        def process_block_event(event,client):
            self.active_block_queries = self.active_block_queries - 1
            if event == None:
                if self.sync_block == None or blockno <= self.sync_block:
                    self.sync_block = blockno
                    self._get_block(blockno)
                else:
                    if self.active_block_queries == 0:
                        self._get_block(blockno)
                    else:
                        self.log.info("Synced, reducing number of parallel get_block queries to {count!r}",count=self.active_block_queries)
            else:
                if self.sync_block != None and blockno >= self.sync_block:
                    self.sync_block = None
                self._process_block(event)
                self._get_block(self.last_block+1)
                if self.active_block_queries < 8:
                    treshold = self.active_block_queries * 20
                    behind = (dt.utcnow() - dateutil.parser.parse(event["timestamp"])).seconds
                    if behind >= treshold:
                        self._get_block(self.last_block+1)
                        self.log.info("Lost synchonysation, spinning up an extra parallel get_block query to {count!r}",count=self.active_block_queries)
        if self.last_block < blockno:
            self.last_block = blockno
        cmd = self.rpc.get_block(blockno)
        cmd.on_result(process_block_event)
        self.active_block_queries = self.active_block_queries + 1
    def _bootstrap(self,block):
        self.log.info("Starting at block {block!r}",block=block)
        #Start up eight paralel https queries so we can catch up with the blockchain.
        for index in range(0,64):
            self._get_block(block+index)
    #The __call__ method is to be called only by the jsonrpc client!
    def _process_block(self,blk):
        self.count = self.count - 1
        if blk != None and "timestamp" in blk:
            ts = blk["timestamp"]
            ddt = None
            try:
                ddt = dateutil.parser.parse(ts)
            except:
                pass
            if ddt !=None:
                if self.last_ddt == None or self.last_ddt < ddt:
                    self.last_ddt = ddt
                    if self.synced == False and (dt.now() - self.last_ddt).seconds < 240:
                        self.synced  = True
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
                                    self.active_events["hour"][bot](ts,obj,self.rpc)
                                except Exception,e:
                                    self.log.failure("Error in bot '{bot!r}' processing 'hour' event.",bot=bot)
                        if ddt.hour == 0 and "day" in self.active_events:
                            for bot in self.active_events["day"].keys():
                                try:
                                    self.active_events["day"][bot](ts,obj,self.rpc)
                                except Exception,e:
                                    self.log.failure("Error in bot '{bot!r}' processing 'day' event.",bot=bot)
                        if ddt.hour == 0 and ddt.weekday == 0 and "week" in self.active_events:
                            for bot in self.active_events["week"].keys():
                                try:
                                    self.active_events["week"][bot](ts,obj,self.rpc)
                                except Exception,e:
                                    self.log.failure("Error in bot '{bot!r}' processing 'week' event.",bot=bot)
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
                        self.active_events["block"][bot](ts,blk_meta,self.rpc)
                    except Exception,e:
                        self.log.failure("Error in bot '{bot!r}' processing 'block' event.",bot=bot)
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
                                self.active_events["transaction"][bot](ts,transaction_meta,self.rpc)
                            except Exception,e:
                                self.log.failure("Error in bot '{bot!r}' processing 'transaction' event.",bot=bot)
                    if "operations" in blk["transactions"][index] and isinstance(blk["transactions"][index]["operations"],list):
                        for oindex in range(0,len(blk["transactions"][index]["operations"])):
                            operation = blk["transactions"][index]["operations"][oindex]
                            if not operation[0] in self.eventtypes:
                                self.eventtypes.add(operation[0])
                                if not operation[0] in self.active_events:
                                    self.log.info("Received an operation not implemented by any bot: {op!r}",op=operation[0])
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
                                        self.active_events[operation[0]][bot](ts,op,self.rpc)
                                    except Exception, e:
                                        self.log.failure("Error in bot '{bot!r}' processing '{op!r}' event.",bot=bot, op=operation[0])

if __name__ == "__main__":
    import sys
    from twisted.internet import reactor
    from twisted.logger import Logger, textFileLogObserver
    class Bot:
        def vote(self,tm,vote_event,client):
            opp = client.get_content(vote_event["author"],vote_event["permlink"])
            def process_vote_content(event, client):
                start_rshares = 0.0
                for vote in  event["active_votes"]:
                    if vote["voter"] == vote_event["voter"] and vote["rshares"] < 0:
                        if start_rshares + float(vote["rshares"]) < 0:
                            print vote["time"],\
                                    "FLAG",\
                                    vote["voter"],"=>",vote_event["author"],\
                                    vote["rshares"]," rshares (",\
                                    start_rshares , "->", start_rshares + float(vote["rshares"]) , ")"
                        else:
                            print vote["time"],\
                                    "DOWNVOTE",\
                                    vote["voter"],"=>",vote_event["author"],\
                                    vote["rshares"],"(",\
                                    start_rshares , "->" , start_rshares + float(vote["rshares"]) , ")"
                    start_rshares = start_rshares + float(vote["rshares"])
            opp.on_result(process_vote_content)
    obs = textFileLogObserver(sys.stdout)
    log = Logger(observer=obs,namespace="blockchain_test")
    bc = ActiveBlockChain(reactor,log)
    bot=Bot()
    bc.register_bot(bot,"testbot")
    reactor.run()

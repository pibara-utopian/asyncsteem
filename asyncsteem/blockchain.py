#!/usr/bin/python
from jsonrpc import RpcClient
from blockfinder import DateFinder
import copy
import dateutil.parser
import time
from datetime import date
from datetime import datetime as dt
from dateutil import relativedelta


class ActiveBlockChain:
    """Class for following the blockchain as it grows, or processing it from a given block in the past"""
    def __init__(self,
                 reactor,
                 log,
                 rewind_days=None,
                 day_limit=None,
                 nodes=None,
                 max_batch_size=None,
                 nodelist="default",
                 parallel=16,
                 rpc_timeout=15,
                 initial_batch_size = None,
                 stop_when_empty= False):
        """Constructor

        Args:
            reactor : The Twisted reactor.
            log      : The Twisted asynchonous logger.
            rewind_days : Start n days in the past or None for now.
            day_limit : Stop processing new blocks after n days. Meant to be used in conjunction with rewind_days.
            nodes    : List of API nodes, you normally should NOT use this, if you use this variable, also use max_batch_size!
            max_batch_size : The max batch size to use for JSON-RPC batched calls. Only use with nodes that support batched RPC calls!
            nodelist : Name of the nodelist to use. "default" and "stage" are currently valid values for this field.
            parallel : Maximum number of paralel outstanding HTTPS JSON-RPC at any point in time.
            rpc_timeout : Timeout (in seconds) for a single HTTPS JSON-RPC query.
            initial_batch_size : The initial number of 'get_block' commands to start the command queue off with.
            stop_when_empty : Boolean indicating if reactor should be stopped when the command queue is empty and no active HTTPS sessions remain.
        """
        try:
            self.log = log
            self.daycount = 0
            self.halt = False
            self.day_limit = day_limit
            self.reactor = reactor #Twisted reactor to use
            self.last_block = 1    #Not the block we are looking for.
            self.rpc = RpcClient(reactor,log,
                                 nodes=nodes,
                                 max_batch_size=max_batch_size,
                                 nodelist=nodelist,
                                 parallel=parallel,
                                 rpc_timeout=rpc_timeout,
                                 stop_when_empty=stop_when_empty)
            #Start at the apropriate block.
            datefinder = DateFinder(self.rpc,log)
            if rewind_days == None:
                #If no date is given, use now
                datefinder(self._bootstrap,None)
            else:
                ddt = date.today() - relativedelta.relativedelta(hour=0,days=rewind_days)
                datefinder(self._bootstrap,ddt)
            self.active_events = dict() #The list of events the active bots are subscribed to.
            self.ddt = None
            self.last_ddt = None
            self.synced = False
            self.eventtypes = set()
            self.sync_block = None
            self.active_block_queries = 0
            if initial_batch_size != None:
                self.initial_batch_size = initial_batch_size
            else:
                if rewind_days != None and rewind_days > 0:
                    self.initial_batch_size = 32
                else:
                    self.initial_batch_size = 2
            #Wake up the RpcClient
            self.rpc()
        except Exception,ex:
            self.log.failure("Error in ActiveBlockChain constructor: {err!r}",err=str(ex))
    def register_bot(self,bot,botname):
        """Register a bot with the active blockchain.

        Args:
            bot: The bot object to register
            botname: A unique name for this bot.
        """
        try:
            #Each method of the object not starting with an underscore is a handler of operation events
            for key in dir(bot):
                if key[0] != "_":
                    #Create a new dict if no bots are yet registered for this event.
                    if not key in self.active_events:
                        self.active_events[key] = dict()
                    #Add handler by bot name.
                    self.active_events[key][botname] = getattr(bot,key)
        except Exception,ex:
            self.log.failure("Error in ActiveBlockChain::register_bot : {err!r}",err=str(ex))
    def _get_block(self,blockno):
        try:
            def process_block_error(errno, msg, rpcclient):
                self.log.error(msg + " while trying to fetch block " + str(blockno))
                self._get_block(blockno)
            def process_block_event(event,client):
                try:
                    self.active_block_queries = self.active_block_queries - 1
                    if event == None:
                        #The requested block does not exist yet
                        if self.sync_block == None or blockno <= self.sync_block:
                            #If this is the lowest numbered non existing block so far, set it as sync_block and try again.
                            self.sync_block = blockno
                            self._get_block(blockno)
                        else:
                            if self.active_block_queries == 0:
                                self._process_behind(0,dt.utcnow())
                                #If it isn't, but this is the last query remaining, try the sync_block once more.
                                self._get_block(self.sync_block)
                            else:
                                #Otherwise, given that we are synced or close to synced, reduce the number of requested blocks in the queue.
                                self.log.info("Synced, reducing number of parallel get_block queries to {count!r}",count=self.active_block_queries)
                    else:
                        #Clear the sync_block if needed
                        if self.sync_block != None and blockno >= self.sync_block:
                            self.sync_block = None
                        #Process this whole block
                        self._process_block(event)
                        #Add a new block getting command to the queue
                        if self.halt == False:
                            self._get_block(self.last_block+1)
                        if self.active_block_queries < self.initial_batch_size:
                            #We may want to scale up the number of get_block commands in the queue again.
                            if self.active_block_queries < 7:
                                #Slowly scale up when we first start tu run a bit behind
                                treshold = self.active_block_queries * 20
                            else:
                                #If we still end up running more than two minutes behind, keep scaling untill we don't
                                treshold = 120
                            behind = (dt.utcnow() - dateutil.parser.parse(event["timestamp"])).seconds
                            if behind >= treshold and self.active_block_queries < 20:
                                #Do an extra get_block if we are behind to far.
                                if self.halt == False:
                                    self._get_block(self.last_block+1)
                                    self.log.info("Lost synchonysation, spinning up an extra parallel get_block query to {count!r}",count=self.active_block_queries)
                            self._process_behind(behind,dateutil.parser.parse(event["timestamp"]))
                except Exception,ex:
                    self.log.failure("Error in process_block_event : {err!r}",err=str(ex))
            if self.last_block < blockno:
                self.last_block = blockno
            if self.halt == False:
                cmd = self.rpc.get_block(blockno)
                cmd.on_result(process_block_event)
                cmd.on_error(process_block_error)
                self.active_block_queries = self.active_block_queries + 1
        except Exception,ex:
            self.log.failure("Error in ActiveBlockChain::_get_block : {err!r}",err=str(ex))
    def _bootstrap(self,block):
        try:
            self.log.info("Starting at block {block!r}",block=block)
            #Start up eight paralel https queries so we can catch up with the blockchain.
            for index in range(0,self.initial_batch_size):
                self._get_block(block+index)
        except Exception,ex:
            self.log.failure("Error in ActiveBlockChain::_bootstrap : {err!r}",err=str(ex))
    def _process_behind(self,seconds,ts):
        if "behind" in self.active_events:
            #Invoke behind eventon all bots that implement the behind method
            for bot in self.active_events["behind"].keys():
                try:
                    behind_obj = dict()
                    behind_obj["seconds"] = seconds
                    self.active_events["behind"][bot](ts,behind_obj,self.rpc)
                except Exception,e:
                    self.log.failure("Error in bot '{bot!r}' processing 'behind' event: {err!r}",bot=bot,err=str(e))
    def _process_block(self,blk):
        try:
            if blk != None and "timestamp" in blk:
                ts = blk["timestamp"]
                ddt = None
                try:
                    #Parse the time from the block
                    ddt = dateutil.parser.parse(ts)
                except:
                    pass
                if ddt !=None:
                    #If this is a valid block with a valid time, check if we are synced yet
                    if self.last_ddt == None or self.last_ddt < ddt:
                        self.last_ddt = ddt
                        #We consider ourselves synced if we are behind no more than two minutes
                        if self.synced == False and (dt.now() - self.last_ddt).seconds < 120:
                            self.synced  = True
                    if self.ddt == None:
                        self.ddt = ddt
                    else:
                        if ddt > self.ddt and ddt.hour != self.ddt.hour:
                            #Hour event
                            self.ddt = ddt
                            obj = dict()
                            obj["year"] = ddt.year
                            obj["month"] = ddt.month
                            obj["day"] = ddt.day
                            obj["weekday"] = ddt.weekday()
                            obj["hour"] = ddt.hour
                            self.log.info("Blockchain time mark: {ts!r}",ts=str(ts))
                            if "hour" in self.active_events:
                                #Invoke hour event on all bots that implement the hour method
                                for bot in self.active_events["hour"].keys():
                                    try:
                                        self.active_events["hour"][bot](ddt,obj,self.rpc)
                                    except Exception,e:
                                        self.log.failure("Error in bot '{bot!r}' processing 'hour' event.",bot=bot)
                            if ddt.hour == 0:
                                self.daycount += 1
                                if self.day_limit != None:
                                    if self.daycount >= self.day_limit:
                                        self.halt = True
                                        self.log.info("Notice: day_limit reached, halting block fetching.")
                                    else:
                                        self.log.info("Info: day_limit not yet reached.")
                                else:
                                    self.log.info("A brand new day.")
                            if ddt.hour == 0 and "day" in self.active_events:
                                #Invoke day event on all bots that implement the day method
                                for bot in self.active_events["day"].keys():
                                    try:
                                        self.active_events["day"][bot](ddt,obj,self.rpc)
                                    except Exception,e:
                                        self.log.failure("Error in bot '{bot!r}' processing 'day' event.",bot=bot)
                            if ddt.hour == 0 and ddt.weekday == 0 and "week" in self.active_events:
                                #Invoke week event on all bots that implement the week method
                                for bot in self.active_events["week"].keys():
                                    try:
                                        self.active_events["week"][bot](ddt,obj,self.rpc)
                                    except Exception,e:
                                        self.log.failure("Error in bot '{bot!r}' processing 'week' event.",bot=bot)
                blk_meta = dict()
                #Copy relevant keys to block level meta.
                for k in ["witness_signature",
                          "block_id",
                          "signing_key",
                          "transaction_merkle_root",
                          "witness","previous"]:
                    if k in blk:
                        blk_meta[k] = blk[k]
                if "block" in self.active_events:
                    #Invoke block event  on all bots that implement the block method
                    for bot in self.active_events["block"].keys():
                        try:
                            self.active_events["block"][bot](ddt,blk_meta,self.rpc)
                        except Exception,e:
                            self.log.failure("Error in bot '{bot!r}' processing 'block' event.",bot=bot)
                if "transactions" in blk and isinstance(blk["transactions"],list):
                    for index in range(0,len(blk["transactions"])):
                        transaction_meta = dict()
                        #Start off transaction meta with our block level meta.
                        transaction_meta["block_meta"] = copy.copy(blk_meta)
                        #Copy the transaction id
                        if "transaction_ids" in blk and isinstance(blk["transaction_ids"],list) and len(blk["transaction_ids"]) > index:
                            transaction_meta["id"] = blk["transaction_ids"][index]
                        #And copy some relevant transaction meta
                        for k in ["ref_block_prefix","ref_block_num","expiration"]:
                            if k in blk["transactions"][index]:
                                transaction_meta[k] = blk["transactions"][index][k] 
                        if "transaction" in self.active_events:
                            #Invoke transaction event  on all bots that implement the transaction method
                            for bot in self.active_events["transaction"].keys():
                                try:
                                    self.active_events["transaction"][bot](ddt,transaction_meta,self.rpc)
                                except Exception,e:
                                    self.log.failure("Error in bot '{bot!r}' processing 'transaction' event.",bot=bot)
                        if "operations" in blk["transactions"][index] and isinstance(blk["transactions"][index]["operations"],list):
                            for oindex in range(0,len(blk["transactions"][index]["operations"])):
                                #Get the name of the operation.
                                operation = blk["transactions"][index]["operations"][oindex]
                                #Do some logging of unimplemented methods on first occurance.
                                if not operation[0] in self.eventtypes:
                                    self.eventtypes.add(operation[0])
                                    if not operation[0] in self.active_events:
                                        self.log.info("Received an operation not implemented by any bot: {op!r}",op=operation[0])
                                if isinstance(operation,list) and \
                                   len(operation) == 2 and \
                                   (isinstance(operation[0],str) or isinstance(operation[0],unicode)) and \
                                   isinstance(operation[1],object) and \
                                   operation[0] in self.active_events:
                                    #Start off with operation meta copied from the operation.
                                    op = copy.copy(operation[1])
                                    op["operation_no"] = oindex
                                    #Copy in thansaction (and block) level meta.
                                    op["transaction_meta"] = copy.copy(transaction_meta)
                                    #Invoke specific operation event  on all bots that implement the specific operation method
                                    for bot in self.active_events[operation[0]].keys():
                                        try:
                                            self.active_events[operation[0]][bot](ddt,op,self.rpc)
                                        except Exception, e:
                                            self.log.failure("Error in bot '{bot!r}' processing '{op!r}' event.",bot=bot, op=operation[0])
        except Exception,ex:
            self.log.failure("Error in ActiveBlockChain::_process_block : {err!r}",err=str(ex))

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
    bc = ActiveBlockChain(reactor,log,rewind_days=1,nodelist="stage")
    bot=Bot()
    bc.register_bot(bot,"testbot")
    reactor.run()

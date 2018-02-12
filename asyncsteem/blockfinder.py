#!/usr/bin/python
import dateutil.parser

class DateFinder(object):
    def __init__(self,client,log):
        self.rpc = client
        self.log = log
        self.active_queries = 0
    def __call__(self,on_found,trigger_time=None,best_guess=5000000):
        def process_global_config(config_event,cclient):
            on_found(config_event["last_irreversible_block_num"])
        if trigger_time == None:
            cmd = self.rpc.get_dynamic_global_properties()
            cmd.on_result(process_global_config)
            return
        self.lower_limit = 0
        self.upper_limit = -1
        self.found = False
        def get_block(blk,ndx):
            def process_block(event, client):
                if not self.found:
                    self.active_queries = self.active_queries - 1
                    if event != None and "timestamp" in event:
                        ddt = dateutil.parser.parse(event["timestamp"])
                        if ddt < trigger_time:
                            #Our guess was to early
                            if blk > self.lower_limit: 
                                if self.upper_limit > 0 and self.upper_limit - blk < 2:
                                    self.found = True
                                    on_found(blk)
                                else:
                                    self.lower_limit =blk
                                    if self.upper_limit == -1:
                                        self.log.info("Looking for block in range {rng!r}",rng=[self.lower_limit,"?"])
                                    else:

                                        self.log.info("Looking for block in range {rng!r}",rng=[self.lower_limit,self.upper_limit])
                        else:
                            #Our best guess was either to late or spot on.
                            if self.upper_limit == -1 or blk <= self.upper_limit: 
                                if blk - self.lower_limit < 2:
                                    self.found = True
                                    on_found(blk)
                                else:
                                    self.upper_limit = blk
                                    self.log.info("Looking for block in range {rng!r}",rng=[self.lower_limit,self.upper_limit])
                    else:
                        if self.upper_limit > blk or self.upper_limit == -1:
                            self.upper_limit = blk
                            self.log.info("Looking for block in range {rng!r}",rng=[self.lower_limit,self.upper_limit])
                    if not self.found:
                        if self.upper_limit != -1:
                            nexttry = self.lower_limit + (self.upper_limit - self.lower_limit)*(ndx+1)/4
                            get_block(nexttry,ndx)
                        else:
                            nexttry = int(self.lower_limit * (0.75*ndx + 1.75))
                            get_block(nexttry,ndx)
            opp = self.rpc.get_block(blk)
            self.active_queries = self.active_queries + 1
            opp.on_result(process_block)
        get_block(5000000,0)
        get_block(10000000,1)
        get_block(15000000,2)

if __name__ == "__main__":
    import sys
    from twisted.internet import reactor
    from jsonrpc import RpcClient
    from datetime import date
    from dateutil import relativedelta
    from twisted.logger import Logger, textFileLogObserver
    def process_blockno(bno):
        print "BLOCK: ",bno
    obs = textFileLogObserver(sys.stdout)
    log = Logger(observer=obs,namespace="blockfinder_test")
    rpcclient = RpcClient(reactor,log)
    datefinder = DateFinder(rpcclient,log)
    ddt = date.today() - relativedelta.relativedelta(hour=0,days=1)
    datefinder(process_blockno,ddt)
    rpcclient()
    reactor.run()

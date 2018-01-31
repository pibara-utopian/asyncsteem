#!/usr/bin/python
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain, AsyncQueue
from datetime import timedelta
import time
from termcolor import colored

class WatchingTheWatchersBot:
    def __init__(self):
        self.blocks = 0
        self.hourcount = 0
        self.start = time.time()
        self.last = time.time()
        self.queue = AsyncQueue(reactor)
    def _comment(self,obj):
        print "OBJ:", obj #FIXME: process the comment
    def vote(self,tm,event,cont):
        if event["weight"] < 0:
            print colored(str(tm),"cyan"),colored("@" + event["voter"],"yellow"),"=> "+colored("@"+event["author"],"green") + "/" + event["permlink"]
            self.queue.get_comment(event["author"],event["permlink"])(self._comment)
    def day(self,tm,event,cont):
        print colored("* HOUR mark: Processed "+str(self.hourcount)+ " blockchain hours in "+ total_duration,"green")
        reactor.stop() #FIXME, we shouldn't stop the reacor just yet, but ActiveBlockChain should sop emitting events and
                       #       after teh queue is completely empty and all pending queries answered, the reactor should stop

bc = ActiveBlockChain(reactor,rewind_days=1,parallel = 8)
tb = WatchingTheWatchersBot()
bc.register_bot(tb,"watchingthewatchers")
bc.start()
reactor.run()

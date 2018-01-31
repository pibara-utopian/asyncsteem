#!/usr/bin/python
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain
from datetime import timedelta
import time
from termcolor import colored

class WatchingTheWatchersBot:
    def __init__(self):
        self.blocks = 0
        self.hourcount = 0
        self.start = time.time()
        self.last = time.time()
    def vote(self,tm,event,cont):
        if event["weight"] < 0:
            print colored(str(tm),"cyan"),colored("@" + event["voter"],"yellow"),"=> "+colored("@"+event["author"],"green") + "/" + event["permlink"]
    def hour(self,tm,event,cont):
        self.hourcount = self.hourcount + 1
        now = time.time()
        total_duration = str(timedelta(seconds=now-self.start))
        print colored("* HOUR mark: Processed "+str(self.hourcount)+ " blockchain hours in "+ total_duration,"green")
        if self.hourcount == 24: 
            print "Ending eventloop"
            reactor.stop()

print "Constructing ActiveBlockChain"
bc = ActiveBlockChain(reactor,rewind_days=1,parallel = 8)
print "Constructing bot"
tb = WatchingTheWatchersBot()
print "Regestering bot"
bc.register_bot(tb,"watchingthewatchers")
print "Starting bot"
bc.start()
print "Starting main event loop"
reactor.run()
print "Done"

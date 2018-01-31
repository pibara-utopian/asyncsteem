#!/usr/bin/python
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain
from datetime import timedelta
import time
from termcolor import colored

class TestBot:
    def __init__(self):
        self.blocks = 0
        self.daycount = 0
        self.start = time.time()
        self.last = time.time()
    def block(self,tm,event,cont):
        chunk = 1000
        self.blocks = self.blocks + 1
        if self.blocks % chunk == 0:
            now = time.time()
            duration = now - self.last
            total_duration = now - self.start
            speed = int(chunk*1000.0/duration)*1.0/1000
            avspeed = int(self.blocks*1000/total_duration)*1.0/1000
            print colored("* "+str(chunk)+" blocks processed in "+str(duration)+" seconds. Speed "+ str(speed) + " blocks per second. Avg:"+ str(avspeed),"green")
            self.last = now
    def day(self,tm,event,cont):
        self.daycount = self.daycount + 1
        now = time.time()
        total_duration = str(timedelta(seconds=now-self.start))
        print colored("* DAY mark: Processed "+str(self.daycount)+ "blockchain days in "+ total_duration,"green")
        if self.daycount == 7: 
            print "Ending eventloop"
            reactor.stop()

print "Constructing ActiveBlockChain"
bc = ActiveBlockChain(reactor,rewind_days=7,parallel = 8)
print "Constructing bot"
tb = TestBot()
print "Regestering bot"
bc.register_bot(tb,"benchmark")
print "Starting bot"
bc.start()
print "Starting main event loop"
reactor.run()
print "Done"

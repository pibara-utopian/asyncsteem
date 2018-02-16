#!/usr/bin/python
import sys
from datetime import timedelta
import time
import io
from termcolor import colored
from twisted.internet import reactor
from twisted.logger import Logger, textFileLogObserver
from asyncsteem import ActiveBlockChain

class TestBot:
    def __init__(self):
        self.blocks = 0
        self.hourcount = 0
        self.start = time.time()
        self.last = time.time()
    def block(self,tm,event,client):
        chunk = 100
        self.blocks = self.blocks + 1
        if self.blocks % chunk == 0:
            now = time.time()
            duration = now - self.last
            total_duration = now - self.start
            speed = int(chunk*1000.0/duration)*1.0/1000
            avspeed = int(self.blocks*1000/total_duration)*1.0/1000
            print colored("* "+str(chunk)+" blocks processed in "+str(duration)+" seconds. Speed "+ str(speed) + " blocks per second. Avg:"+ str(avspeed),"green"),tm
            self.last = now
    def hour(self,tm,event,client):
        self.hourcount = self.hourcount + 1
        now = time.time()
        total_duration = str(timedelta(seconds=now-self.start))
        print colored("* HOUR mark: Processed "+str(self.hourcount)+ " blockchain hours in "+ total_duration,"green")
        if self.hourcount == 7*24: 
            print "Ending eventloop"
            reactor.stop()

obs = textFileLogObserver(io.open("benchmark_asyncsteem.log", "a"))
print "NOTE: asyncsteem logging to benchmark_asyncsteem.log"
log = Logger(observer=obs,namespace="asyncsteem")
print "Constructing ActiveBlockChain"
bc = ActiveBlockChain(reactor,log=log,rewind_days=7)
print "Constructing bot"
tb = TestBot()
print "Regestering bot"
bc.register_bot(tb,"benchmark")
print "Starting main event loop"
reactor.run()
print "Done"

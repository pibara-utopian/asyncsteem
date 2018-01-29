#!/usr/bin/python
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain
import time

class TestBot:
    def __init__(self):
        self.blocks = 0
        self.start = time.time()
        self.last = time.time()
    def block(self,tm,event,cont):
        self.blocks = self.blocks + 1
        if self.blocks % 100 == 0:
            now = time.time()
            duration = now - self.last
            total_duration = now - self.start
            speed = int(100000.0/duration)*1.0/1000
            avspeed = int(self.blocks*1000/total_duration)*1.0/1000
            print "* 100 blocks processed in",duration,"seconds. Speed",speed,"blocks per second. Avg:",avspeed
            self.last = now

print "Constructing ActiveBlockChain"
bc = ActiveBlockChain(reactor)
print "Constructing bot"
tb = TestBot()
print "Regestering bot"
bc.register_bot(tb,"testbot")
print "Starting bot"
bc.start()
print "Starting main event loop"
reactor.run()

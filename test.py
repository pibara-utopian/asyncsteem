#!/usr/bin/python
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain
import time

class TestBot:
    def __init__(self):
        self.count = 0
        self.blocks = 0
        self.last = time.time()
    def block(self,tm,event,cont):
        self.blocks = self.blocks + 1
        if self.blocks % 1000 == 0:
            now = time.time()
            duration = now - self.last
            print "* 1000 blocks processed in",duration,"seconds."
            self.last = now
#    def hour(self,tm,event,cont):
#        print event
    def vote(self,tm,event,cont):
        self.count = self.count + 1
        cont()
    def throttle(self):
        self.count = 0
        return False

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

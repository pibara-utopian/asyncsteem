#!/usr/bin/python
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain

class TestBot:
    def vote(self,time,event):
        print time, event

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

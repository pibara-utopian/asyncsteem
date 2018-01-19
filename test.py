#!/usr/bin/python
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain

class TestBot:
    def vote(self,time,event):
        print time, event

nodes = []
bc = ActiveBlockChain(reactor,nodes)
tb = TestBot()
bc.register_bot(tb,"testbot")
bc.start()

reactor.run()

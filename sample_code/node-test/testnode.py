#!/usr/bin/python
import sys
import json
import socket
from twisted.internet import reactor
from twisted.logger import Logger, textFileLogObserver
from asyncsteem import RpcClient

def process_block(event,client):
    print "OK"

class Test:
    def __init__(self,test):
        self.test = test
        self.okcount = 0
        self.failcount = 0
        self.querycount = 0
    def report(self):
        print self.test, ":", self.okcount , "(", self.querycount, self.failcount, self.querycount - self.okcount - self.failcount,")"
    def process_block(self,event,client):
        self.okcount += 1
    def process_error(self,errno,msg,client):
        self.failcount += 1
    def get_block(self,no,client):
        opp = client.get_block(no)
        opp.on_result(self.process_block)
        opp.on_error(self.process_error)
        self.querycount += 1

tid = sys.argv[1]
test = Test(tid)
obs = textFileLogObserver(sys.stdout)
log = Logger(observer=obs,namespace="node-test")
client = RpcClient(reactor,log,nodelist=tid,stop_when_empty=True,rpc_timeout=15,max_non_rotate=5)
for block in range(123000,123100):
    test.get_block(block,client)
client()
reactor.run()
test.report()

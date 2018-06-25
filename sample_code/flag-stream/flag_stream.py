#!/usr/bin/python
import json
import io
from twisted.internet import reactor
from twisted.logger import Logger, textFileLogObserver
from twisted.web import server,resource
from asyncsteem import ActiveBlockChain
from os.path import join, dirname, realpath

class FlagHub:
    def __init__(self):
        self.log = [[]]
    def flag(self,voter,author):
        self.log[-1].append([voter,author])
    def tick(self):
        self.log.append([])
        if len(self.log) > 30:
            self.log = self.log[-30:]
    def get_log(self):
        return self.log

class FlagWebServer(resource.Resource):
    isLeaf = True
    def __init__(self,hub):
        self.hub = hub
    def render_GET(self, request):
        head = '<html><head><meta http-equiv="refresh" content="15"></head><body><ul>\n' 
        body = ""
        m = 0
        count = 0
        log = self.hub.get_log()
        for minute in reversed(log):
            for cell in reversed(minute):
                count += 1
                if count < 30:
                    line = "<li>" + cell[0] + " -> " + cell[1] + " (" + str(m) +")</li>\n"
                    body = body + line
            m += 1
        if count == 0:
            body = "<li>WAIT (" + str(len(log)) + ")</li>\n"
        foot = "\n</ul></body></html>"
        return bytes(head + body + foot)

class FlagStream:
    def __init__(self,hub):
        self.hub = hub
        self.curmin = ""
    def vote(self,tm,vote_event,client):
        if vote_event["weight"] < 0:
            self.hub.flag(vote_event["voter"],vote_event["author"])
    def block(self,tm,block_event,client):
        if tm[:-3] > self.curmin:
            self.curmin = tm[:-3]
            self.hub.tick()

mypath = dirname(realpath(__file__))
obs = textFileLogObserver(io.open(join(mypath,"flag_stream.log"), "a"))
log = Logger(observer=obs,namespace="asyncsteem")
bc = ActiveBlockChain(reactor,log=log,nodelist="stage")
hub = FlagHub()
tb = FlagStream(hub)
bc.register_bot(tb,"flag_stream")
ws = FlagWebServer(hub)
s = server.Site(ws)
reactor.listenTCP(4080,s)
reactor.run()

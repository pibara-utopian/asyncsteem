from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.internet import defer
import time
import json 

class StringProducer(object):
    #implements(IBodyProducer)
    def __init__(self, body):
        self.body = body
        self.length = len(body)
    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)
    def pauseProducing(self):
        pass
    def stopProducing(self):
        pass

class Client:
    def __init__(self,reactor,nodes,cb):
        self.nodes = nodes
        self.node_index = 0
        self.reactor = reactor
        self.agent = Agent(reactor)
        self.cb = cb
        self.id = 0
        self.starttime = -1
        self.timeoutCall = None
        self.last_rotate = 0
        print "Starting off with node",nodes[self.node_index]
    def next_node(self,reason):
        now = time.time()
        ago = now - self.last_rotate
        if ago > 26:
            self.last_rotate = now
            self.node_index = (self.node_index + 1) % len(self.nodes)
            print "Switching to node",self.nodes[self.node_index],":",reason
    def handlerFunctionClosure(self,name):
        self.id = self.id + 1
        my_id = self.id
        def cbBody(body):
            obj = None
            try:
                obj = json.loads(body)
            except:
                self.next_node("Non-JSON response from server")
            if obj != None and self.starttime > -1:
                endtime = time.time()
                latency = endtime - self.starttime
                if latency > 20:
                    self.next_node("Over 20 seconds json-rpc response time")
            if obj != None and "result" in obj.keys():
                self.cb(obj["result"]) 
            else:
                self.cb(dict())
        def handle_response(response):
            if self.timeoutCall.active():
                self.timeoutCall.cancel()
            d = readBody(response)
            d.addCallback(cbBody)
            return d
        def handle_error(error):
            if self.timeoutCall.active():
                self.timeoutCall.cancel()
            self.next_node(error.getErrorMessage())
            self.cb(None)
        def handlerFunction(*args):
            callobj = dict()
            callobj["jsonrpc"] = "2.0"
            callobj["method"] = name
            callobj["id"] = self.id
            callobj["params"] = args
            jo = json.dumps(callobj)
            url = "https://" + self.nodes[self.node_index] + "/"
            d = self.agent.request('POST',
                              url,
                              Headers({'User-Agent': ['Async Steem for Python v0.01'], "Content-Type": ["application/json"]}),
                              StringProducer(jo))
            d.addCallback(handle_response)
            d.addErrback(handle_error)
            self.timeoutCall = self.reactor.callLater(15, d.cancel)
            self.starttime = time.time()
            return d
        return handlerFunction
    def __getattr__(self,name):
        return self.handlerFunctionClosure(name)


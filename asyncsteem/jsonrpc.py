from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.internet import defer

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
        self.agent = Agent(reactor)
        self.cb = cb
        self.id = 0
    def next_node(self):
        self.node_index = (self.node_index + 1) % len(self.nodes)
    def handlerFunctionClosure(self,name):
        self.id = self.id + 1
        my_id = self.id
        def cbBody(body):
            obj = json.loads(body)
            if "result" in obj.keys():
                self.cb(obj["result"])
        def handle_response(response):
            d = readBody(response)
            d.addCallback(cbBody)
            return d
        def handle_error(error):
            print "Error:",error.value.reasons[0]
            self.next_node()
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
            return d
        return handlerFunction
    def __getattr__(self,name):
        return self.handlerFunctionClosure(name)


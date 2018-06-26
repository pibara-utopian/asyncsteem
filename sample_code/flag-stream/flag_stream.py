#!/usr/bin/python
import json
import io
from twisted.internet import reactor, endpoints
from twisted.logger import Logger, textFileLogObserver
from twisted.web import server,resource
from twisted.web.static import File
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



class SnapShot(resource.Resource):
    isLeaf = True
    def __init__(self,hub):
        self.hub = hub
    def render_GET(self, request):
        vertexes = set()
        edges = set()
        count = 0
        log = self.hub.get_log()
        for minute in reversed(log):
            for cell in reversed(minute):
                count += 1
                if count < 40:
                    vertex1 = cell[0]
                    vertex2 = cell[1]
                    edge = vertex1 + "->" + vertex2
                    vertexes.add(vertex1)
                    vertexes.add(vertex2)
                    edges.add(edge);
        rval = {}
        rval["nodes"] = []
        name2num = {}
        v_id = 0
        for vertex in vertexes:
            v_id += 1
            name2num[vertex] = v_id
            nod = {}
            nod["id"] = v_id
            nod["label"] = vertex
            rval["nodes"].append(nod)
        rval["edges"] = []
        for edge in edges:
            [node1,node2] = edge.split("->")
            edg = {}
            edg["from"] = name2num[node1]
            edg["to"] = name2num[node2]
            edg["arrows"] = "to"
            rval["edges"].append(edg)
        return json.dumps(rval)

class FlagWebServer(resource.Resource):
    def __init__(self,hub):
        self.hub = hub
        self.children = ["/","/snapshot"]
    def getChild(self, name, request):
        if request.uri == '/snapshot':
            return SnapShot(self.hub)
        else:
            if request.uri == '/vis.js':
                return File("visjs/dist/vis.js")
            else:
                if request.uri == '/':
                    return File("index.html")
                else:
                    return resource.NoResource()


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
observer = textFileLogObserver(io.open(join(mypath,"flag_stream.log"), "a"))
logger = Logger(observer=observer,namespace="asyncsteem")
blockchain = ActiveBlockChain(reactor,log=logger,nodelist="stage")
hub = FlagHub()
steembot = FlagStream(hub)
blockchain.register_bot(steembot,"flag_stream")
#
root = FlagWebServer(hub)
factory = server.Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 4080)
endpoint.listen(factory)
reactor.run()

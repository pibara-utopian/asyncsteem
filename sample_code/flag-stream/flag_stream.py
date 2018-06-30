#!/usr/bin/python
import json
import io
from twisted.internet import reactor, endpoints
from twisted.logger import Logger, textFileLogObserver
from twisted.web import server,resource
from twisted.web.static import File
from datetime import datetime
from twisted.internet.task import LoopingCall
from asyncsteem import ActiveBlockChain
from os.path import join, dirname, realpath

class FlagHub:
    def __init__(self,max_node_count = 32):
        self.event_seq = 0
        self.node_seq = 0
        self.max_node_count = max_node_count
        self.currentgraph = {}
        self.currentgraph["nodes"] = []
        self.currentgraph["edges"] = []
        self.currentgraph["seq"] = 0
        self.accountset = set()
        self.lasttick = datetime.utcnow()
        self.event_events = dict()
    def trim(self,seq):
        while len(self.currentgraph["nodes"]) > self.max_node_count:
            seq1 = seq
            index = -1
            oldest_node_index = -1
            node_id = -1
            for node in self.currentgraph["nodes"]:
                index += 1
                if node["upd"] < seq1:
                    seq1 = node["upd"]
                    node_id = node["id"]
                    oldest_node_index = index
            del self.currentgraph["nodes"][oldest_node_index]
            if not (seq in self.event_events):
                self.event_events[seq] = []
            ee = dict()
            ee["id"] = node_id
            ee["type"] = "drop_node"
            self.event_events[seq].append(ee)
            new_edges = []
            for edge in self.currentgraph["edges"]:
                if edge["from"] !=  node_id and edge["to"] != node_id:
                    new_edges.append(edge)
            self.currentgraph["edges"] = new_edges
            if seq1 in self.event_events:
                del self.event_events[seq1]
    def get_seq(self,time):
        self.event_seq += 1
        return self.event_seq;
    def add_node(self,seq,account):
        self.accountset.add(account)
        self.node_seq += 1
        nod = {}
        nod["id"] = self.node_seq
        nod["label"] = account
        nod["seq"] = seq
        nod["upd"] = seq
        self.currentgraph["nodes"].append(nod)
        if not (seq in self.event_events):
            self.event_events[seq] = []
        ee = dict()
        ee["node"] = nod
        ee["type"] = "add_node"
        self.event_events[seq].append(ee)
    def keep_node(self,seq,account):
        for node in self.currentgraph["nodes"]:
            if node["label"] == account:
                node["upd"] = seq
    def has_edge(self,voter,author):
        f = None
        t = None
        for account in self.currentgraph["nodes"]:
            if account["label"] == voter:
                f = account["id"]
            if account["label"] == author:
                t = account["id"]
        if f == None or t == None:
            return False
        for edge in self.currentgraph["edges"]:
            if edge["from"] == f and edge["to"] == t:
                return True
        return False
    def add_edge(self,seq,voter,author):
        f = None
        t = None
        for account in self.currentgraph["nodes"]:
            if account["label"] == voter:
                f = account["id"]
            if account["label"] == author:
                t = account["id"]
        edg = {}
        edg["from"] = f
        edg["to"] = t
        edg["arrows"] = "to"
        edg["seq"] = seq
        edg["upd"] = seq
        self.currentgraph["edges"].append(edg)
        if not (seq in self.event_events):
            self.event_events[seq] = []
        ee = dict()
        ee["edge"] = edg
        ee["type"] = "add_edge"
        self.event_events[seq].append(ee)
    def keep_edge(self,seq,voter,author):
        f = None
        t = None
        for account in self.currentgraph["nodes"]:
            if account["label"] == voter:
                f = account["id"]
            if account["label"] == author:
                t = account["id"]
        for edge in self.currentgraph["edges"]:
            if edge["from"] == f and edge["to"] == t:
                edge["upd"] = seq
    def flag(self,voter,author,time):
        seq = self.get_seq(time)
        added_node = False
        for account in [voter,author]:
            if not account in self.accountset:
                self.add_node(seq,account)
                added_node = True
            else:
                self.keep_node(seq,account);
        if not self.has_edge(voter,author):
            self.add_edge(seq,voter,author)
        else:
            self.keep_edge(seq,voter,author)
        if added_node:
            self.trim(seq)
        self.currentgraph["seq"] = seq
    def set_behind(self,ts,seconds):
        self.lasttick = ts
    def real_tick(self):
        pass
    def get_graph(self):
        return self.currentgraph
    def get_updates(self,oldseq):
        rval = dict()
        rval["seq"] = self.event_seq
        rval["updates"] = []
        for seq in range(oldseq + 1, rval["seq"] + 1):
            if seq in self.event_events:
                for update in self.event_events[seq]:
                    rval["updates"].append(update)
        return rval
        


class SnapShot(resource.Resource):
    isLeaf = True
    def __init__(self,hub):
        self.hub = hub
    def render_GET(self, request):
        return json.dumps(self.hub.get_graph())

class Updates(resource.Resource):
    isLeaf = True
    def __init__(self,hub):
        self.hub = hub
    def render_GET(self, request):
        #FIXME, need a real Updates that includes the seq we are updating 'from'.
        return json.dumps(self.hub.get_updates(7))

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
                    if request.uri == '/updates':
                        return Updates(self.hub)
                    else:
                        return resource.NoResource()

class FlagStream:
    def __init__(self,hub):
        self.hub = hub
    def vote(self,tm,vote_event,client):
        if vote_event["weight"] < 0:
            self.hub.flag(vote_event["voter"],vote_event["author"],tm)
    def behind(self,ts,behind_obj,client):
        self.hub.set_behind(ts,behind_obj["seconds"])

mypath = dirname(realpath(__file__))
observer = textFileLogObserver(io.open(join(mypath,"flag_stream.log"), "a"))
logger = Logger(observer=observer,namespace="asyncsteem")
#
hub = FlagHub(8)
lc = LoopingCall(hub.real_tick)
lc.start(3)
#
blockchain = ActiveBlockChain(reactor,log=logger,nodelist="stage")
steembot = FlagStream(hub)
blockchain.register_bot(steembot,"flag_stream")
#
root = FlagWebServer(hub)
factory = server.Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 4080)
endpoint.listen(factory)
#
#
reactor.run()

#!/usr/bin/python
import json
import io
from twisted.internet import reactor, endpoints
from twisted.logger import Logger, textFileLogObserver
from twisted.web import server,resource
from twisted.web.static import File
from datetime import datetime
from asyncsteem import ActiveBlockChain
from os.path import join, dirname, realpath

#Bussiness logic for keeping track of the latest set of flags and the involved accounts
class FlagHub:
    #Constructor
    def __init__(self,max_node_count = 32):
        #Every flag will get a unique incremental event sequence number
        self.event_seq = 0
        #Every account involved not currently part of the latest set of accounts being
        #kept for visualization will get its own unique node sequence number
        self.node_seq = 0
        #The same for edge sequences
        self.edge_seq = 0
        #For visualization we only keep track of this number of accounts involved in
        #flagging recently.
        self.max_node_count = max_node_count
        #Initialize the graph description with an empty nodes and edges set.
        self.currentgraph = {}
        self.currentgraph["nodes"] = []
        self.currentgraph["edges"] = []
        self.currentgraph["seq"] = 0
        #Keep a set of currently monitored accounts for quick lookup.
        self.accountset = set()
        #Initialize empty collection of per flag-event graph modifications for diferential patching.
        self.event_events = dict()
    def _trim(self,seq):
        #Run loop if we have more than the max number of accounts and drop excess nodes untill we no longer do.
        while len(self.currentgraph["nodes"]) > self.max_node_count:
            #Initialize important variables, these should get updated.
            seq1 = seq
            index = -1
            oldest_node_index = -1
            node_id = -1
            #Look and find the account in our node list that hasn't been updated the longest.
            for node in self.currentgraph["nodes"]:
                index += 1
                if node["upd"] < seq1:
                    seq1 = node["upd"]
                    node_id = node["id"]
                    oldest_node_index = index
            #Keep a copy of the node that we'll delete from the list
            nod = self.currentgraph["nodes"][oldest_node_index]
            #First delete the account from our set
            self.accountset.remove(nod["label"])
            #delete that node
            del self.currentgraph["nodes"][oldest_node_index]
            #If there is no event list yet for the current event sequence number, create an empty one first.
            if not (seq in self.event_events):
                self.event_events[seq] = []
            #Create a 'drop_node' object for dropping this account node and add it to the event list.
            ee = dict()
            ee["node"] = nod
            ee["type"] = "drop_node"
            self.event_events[seq].append(ee)
            #Create a new empty list of 'filtered' edges
            new_edges = []
            for edge in self.currentgraph["edges"]:
                if edge["from"] !=  node_id and edge["to"] != node_id:
                    #If the dropped account isn't mentioned in the edge, add it to the filtered edges list
                    new_edges.append(edge)
                else:
                    #Otherwise, add a 'drop_edge' event to the event list for the current event sequence number.
                    ee2 = dict()
                    ee2["type"] = "drop_edge"
                    ee2["edge"] = edge
                    self.event_events[seq].append(ee2)
            #Replace the old unfiltered list of edges with the new filtered one.
            self.currentgraph["edges"] = new_edges
            #We don't want to keep track of old stuff forever, delete anything from the per event sequence event list
            #that is at least as old as the last update of the just removed account.
            for sequence in self.event_events.keys():
                if sequence <= seq1:
                    del self.event_events[sequence]
    def _get_seq(self):
        #Increment event_sequence and return a new unique one
        self.event_seq += 1
        return self.event_seq;
    def _add_node(self,seq,account):
        #For quick lookup, add account name to set
        self.accountset.add(account)
        #Create a new node record for our nodes list and append it to the list.
        self.node_seq += 1
        nod = {}
        nod["id"] = self.node_seq
        nod["label"] = account
        nod["seq"] = seq
        nod["upd"] = seq
        self.currentgraph["nodes"].append(nod)
        #If there is no event list yet for the current event sequence number, create an empty one first.
        if not (seq in self.event_events):
            self.event_events[seq] = []
        #Add a new 'add_node' event for use in diferential updates and bind it to the current event sequence.
        ee = dict()
        ee["node"] = nod
        ee["type"] = "add_node"
        self.event_events[seq].append(ee)
    def _keep_node(self,seq,account):
        #Find the account in the current list of nodes
        for node in self.currentgraph["nodes"]:
            if node["label"] == account:
                #Update the 'upd' field to recors this account received updated info on this event.
                node["upd"] = seq
    def _has_edge(self,voter,author):
        f = None
        t = None
        #First check if both accounts for this edge exist in the node list.
        for account in self.currentgraph["nodes"]:
            if account["label"] == voter:
                f = account["id"]
            if account["label"] == author:
                t = account["id"]
        #If they don't, we don't need to look for the edge as it can not exist.
        if f == None or t == None:
            return False
        #If they do, we look through the list of edges to see if the current one exists already.
        for edge in self.currentgraph["edges"]:
            if edge["from"] == f and edge["to"] == t:
                return True
        return False
    def _add_edge(self,seq,voter,author):
        f = None
        t = None
        #Find the id for both accounts involved.
        for account in self.currentgraph["nodes"]:
            if account["label"] == voter:
                f = account["id"]
            if account["label"] == author:
                t = account["id"]
        #Create a new unique edge object.
        self.edge_seq += 1
        edg = {}
        edg["id"] = self.edge_seq
        edg["from"] = f
        edg["to"] = t
        edg["arrows"] = "to"
        edg["seq"] = seq
        edg["upd"] = seq
        #Append it to the edges list
        self.currentgraph["edges"].append(edg)
        #If there is no event list yet for the current event sequence number, create an empty one first.
        if not (seq in self.event_events):
            self.event_events[seq] = []
        #Also add the new edge creation to the event list for the current event sequence
        ee = dict()
        ee["edge"] = edg
        ee["type"] = "add_edge"
        self.event_events[seq].append(ee)
    def _keep_edge(self,seq,voter,author):
        f = None
        t = None
        #Find the ids for the accounts involved
        for account in self.currentgraph["nodes"]:
            if account["label"] == voter:
                f = account["id"]
            if account["label"] == author:
                t = account["id"]
        #find the specific edge
        for edge in self.currentgraph["edges"]:
            if edge["from"] == f and edge["to"] == t:
                #Update the 'upd'field indicating the update during the current event sequence.
                edge["upd"] = seq
    def flag(self,voter,author):
        #Get a unique (incremental) sequence number for this flag event.
        seq = self._get_seq()
        #We haven't added any node (yet)
        added_node = False
        for account in [voter,author]:
            if not account in self.accountset:
                #If either voter or author isn't currently in the account set, add a new node for the account
                self._add_node(seq,account)
                added_node = True
            else:
                #If the account already was part of the set, record that we just had an other event for the account in question.
                self._keep_node(seq,account);
        #Create edge if it didn't exist yet.
        if not self._has_edge(voter,author):
            self._add_edge(seq,voter,author)
        else:
            #If it did, keep track of the fact the edge got an other event.
            self._keep_edge(seq,voter,author)
        #If we just added one or more nodes, maybe we need to trim our graph to keep it from growing too big.
        if added_node:
            self._trim(seq)
        #Keep track of the event sequence number in our current graph
        self.currentgraph["seq"] = seq
    def get_graph(self):
        #Return our complete current graph.
        return self.currentgraph
    def get_updates(self,oldseq):
        #Create an updated object to contain all updates since the named old sequence
        rval = dict()
        #How far do these updates reach
        rval["seq"] = self.event_seq
        #Oncattenated list of updates
        rval["updates"] = []
        #Everything from our last sequence (excluding the last sequence itself upto the current sequence.
        for seq in range(oldseq + 1, rval["seq"] + 1):
            if seq in self.event_events:
                #Add each event from any of the consecutive sequence numbers into our updates list
                for update in self.event_events[seq]:
                    rval["updates"].append(update)
        return rval
        

class SnapShot(resource.Resource):
    isLeaf = True
    def __init__(self,hub):
        self.hub = hub
    def render_GET(self, request):
        return json.dumps(self.hub.get_graph())

class DesignatedUpdates(resource.Resource):
    isLeaf = True
    def __init__(self,hub,oldseq):
        self.hub = hub
        self.oldseq = oldseq
    def render_GET(self, request):
        return json.dumps(self.hub.get_updates(self.oldseq))

class Updates(resource.Resource):
    isLeaf = False
    def __init__(self,hub):
        self.hub = hub
        self.children = []
    def getChild(self, name, request):
        try:
            return DesignatedUpdates(self.hub,int(name))
        except:
            return resource.NoResource()
    def render_GET(self, request):
        return "<HTML><HEAD><TITLE>updates</TITLE></HEAD><BODY><H1>UPDATES</H1></BODY></HTML>"
        

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
                    if request.uri[:8] == '/updates':
                        return Updates(self.hub)
                    else:
                        return resource.NoResource()

class FlagStream:
    def __init__(self,hub):
        self.hub = hub
    def vote(self,tm,vote_event,client):
        if vote_event["weight"] < 0:
            self.hub.flag(vote_event["voter"],vote_event["author"])

mypath = dirname(realpath(__file__))
observer = textFileLogObserver(io.open(join(mypath,"flag_stream.log"), "a"))
logger = Logger(observer=observer,namespace="asyncsteem")
#
hub = FlagHub(20)
#
blockchain = ActiveBlockChain(reactor,log=logger,nodelist="default")
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

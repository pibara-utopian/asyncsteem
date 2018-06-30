#!/usr/bin/python
"""Version of the JSON-RPC library that should work as soon as full-API nodes start implementing the actual JSON-RPC specification"""
from __future__ import print_function
import time
import json
import nodesets
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.internet import defer

#Simple helper class for JSON-RPC response storage 
class _StringProducer(object):
    """Helper class, implements IBodyProducer"""
    #implements(IBodyProducer)
    def __init__(self, body):
        self.body = body
        self.length = len(body)
    def startProducing(self, consumer):
        """startProducing"""
        consumer.write(self.body)
        return defer.succeed(None)
    def pauseProducing(self):
        """dummy pauseProducing, does nothing"""
        pass
    def stopProducing(self):
        """dummy stopProducing, does nothing"""
        pass

#This class holds a queued JSON-RPC command and also holds references to it's callbacks
class _QueueEntry(object):
    """Helper class for managing in-queue JSON-RPC command invocations"""
    def __init__(self, arpcclient, command, arguments, cmd_id, log):
        self.rpcclient = arpcclient    #We keep a reference to the RpcClient that we pass to content and error handlers. 
        self.command = command         #The name of the API call
        self.arguments = arguments     #The API call arguments
        self.cmd_id = cmd_id           #Sequence number for this command 
        self.result_callback = None    #Callback for the result, defaults to None
        self.error_callback = None     #Callback for error results, defaults to None
        self.log = log                 #The asynchonous logger
    def on_result(self, callback):
        """Set the on_result callback"""
        self.result_callback = callback
    def on_error(self, callback):
        """Set the on_error callback"""
        self.error_callback = callback
    def _get_rpc_call_object(self):
        """Return a partial JSON-RPC structure for this object."""
        callobj = dict()
        callobj["jsonrpc"] = "2.0"
        callobj["method"] = self.command
        callobj["id"] = self.cmd_id
        callobj["params"] = self.arguments
        return callobj
    def _handle_result(self, result):
        """Call the supplied user result handler or act as default result handler."""
        if self.result_callback != None:
            #Call the result callback but expect failure.
            try:
                self.result_callback(result, self.rpcclient)
            except Exception as ex:
                self.log.failure("Error in result handler for '{cmd!r}'.",cmd=self.command)
        else:
            #If no handler is set, all we do is log.
            self.logg.error("Error: no on_result defined for '{cmd!r}' command result: {res!r}.",cmd=self.command,res=result)
    def _handle_error(self, errno, msg):
        """Call the supplied user error handler or act as default error handler."""
        if self.error_callback != None:
            #Call the error callback but expect failure.
            try:
                self.error_callback(errno, msg, self.rpcclient)
            except Exception as ex:
                self.log.failure("Error in error handler for '{cmd!r}'.",cmd=self.command)
        else:
            #If no handler is set, all we do is log.
            self.log.error("Notice: no on_error defined for '{cmd!r}, command result: {msg!r}",cmd=self.command,msg=msg)


class RpcClient(object):
    """Core JSON-RPC client class."""
    def __init__(self,
                 areactor,                 #The Twisted reactor
                 log,                      #The asynchonous logger
                 nodes=None,               #If set, nodes overrules the nodelist list of nodelist. NOTE, this will set max_batch_size to one!
                 max_batch_size=None,      #If set, max_batch_size overrules the max_batchsize of nodelist.
                 nodelist = "default",     #Other than "default", "stage" can be used and will use api.steemitstage.com 
                                           # with a max_batch_size of 16
                 parallel=16,              #Maximum number of paralel outstanding HTTPS JSON-RPC at any point in time. 
                 rpc_timeout=15,           #Timeout for a single HTTPS JSON-RPC query.
                 stop_when_empty= False):  #Stop the reactor then the command queue is empty.
        """Constructor for asynchonous JSON-RPC client.
        
        Args:
                areactor : The Twisted reactor
                log      : The Twisted asynchonous logger
                nodes    : List of API nodes, you normally should NOT use this, if you use this variable, also use max_batch_size!
                max_batch_size : The max batch size to use for JSON-RPC batched calls. Only use with nodes that support batched RPC calls!
                nodelist : Name of the nodelist to use. "default" and "stage" are currently valid values for this field.
                parallel : Maximum number of paralel outstanding HTTPS JSON-RPC at any point in time.
                rpc_timeout : Timeout (in seconds) for a single HTTPS JSON-RPC query.
                stop_when_empty : Boolean indicating if reactor should be stopped when the command queue is empty and no active HTTPS 
                                  sessions remain.
        """
        self.reactor = areactor
        self.log = log
        if nodes:
            #If nodes is defined, overrule nodelist with custom list of nodes.
            self.nodes = nodes
            self.max_batch_size = 1
            self.prefix_method = False
        else:
            #See nodesets.py for content. We use the nodes and max_batch_size as specified by the nodelist argument.
            self.nodes = nodesets.nodeset[nodelist]["nodes"]
            self.max_batch_size = nodesets.nodeset[nodelist]["max_batch_size"]
            self.prefix_method = nodesets.nodeset[nodelist]["prefix_method"]
        if max_batch_size != None:
            self.max_batch_size = max_batch_size
        self.parallel = parallel
        self.rpc_timeout = rpc_timeout
        self.node_index = 0            #Start of with the first JSON-RPC node in the node list.
        self.agent = Agent(areactor)   #HTTP(s) Agent
        self.cmd_seq = 0               #Unique sequence number used for commands in the command queue.
        self.last_rotate = 0           #Errors may come in batches, we keep track of the last rotate to an other node to avoid responding to
                                       #errors from previois nodes.
        self.errorcount = 0            #The number of errors seen since the previous node rotation.
        self.entries = dict()          #Here the actual commands from the command queue are stored, keyed by sequence number.
        self.queue = list()            #The actual command queue is just a list of sequence numbers.
        self.active_call_count = 0     #The current number of active HTTPS POST calls. 
        self.stop_when_empty = stop_when_empty
        self.log.info("Starting off with node {node!r}.",node = self.nodes[self.node_index])
    def _next_node(self):
        #We may have reason to move on to the next node, check how long ago we did so before and how many errors we have seen since.
        now = time.time()
        ago = now - self.last_rotate
        self.errorcount = self.errorcount + 1
        #Only if whe have been waiting a bit longer than the RPC timeout time, OR we have seen a bit more than the max amount of
        # paralel HTTPS requests in errors, then it will be OK to rotate once more.
        if ago > (self.rpc_timeout + 2) or self.errorcount > (self.parallel + 1) :
            if len(self.nodes) > 1:
                self.log.error("Switching from {oldnode!r} to an other node due to error.",oldnode=self.nodes[self.node_index])
                self.last_rotate = now
                self.node_index = (self.node_index + 1) % len(self.nodes)
                self.errorcount = 0
                self.log.info("New node is: {node!r}", node=self.nodes[self.node_index])
            else:
                self.log.error("Can't rotate to different node despite of errors. Node set contains just one node.")
                self.last_rotate = now
                self.errorcount = 0
    def __call__(self):
        """Invoke the object to send out some of the queued commands to a server"""
        dv = None
        #Push as many queued calls as the self.max_batch_size and the max number of paralel HTTPS sessions allow for.
        while self.active_call_count < self.parallel and self.queue:
            #Get a chunk of entries from the command queue so we can make a batch.
            subqueue = self.queue[:self.max_batch_size]
            self.queue = self.queue[self.max_batch_size:]
            #Send a single batch to the currently selected RPC node.
            dv = self._process_batch(subqueue)
        #If there is nothing left to do, there is nothing left to do
        if not self.queue and self.active_call_count == 0:
            self.log.error("Queue is empty and no active HTTPS-POSTs remaining.")
            if self.stop_when_empty:
                #On request, stop reactor when queue empty while no active queries remain.
                self.reactor.stop() 
        return dv
    def _process_batch(self, subqueue):
        """Send a single batch of JSON-RPC commands to the server and process the result."""
        try:
            timeoutCall = None
            jo = None
            if self.max_batch_size == 1:
                #At time of writing, the regular nodes have broken JSON-RPC batch handling.
                #So when max_batch_size is set to one, we assume we need to work around this fact.
                jo = json.dumps(self.entries[subqueue[0]]._get_rpc_call_object())
            else:
                #The api.steemitstage.com node properly supports JSON-RPC batches, and so, hopefully soon, will the other nodes.
                qarr = list()
                for num in subqueue:
                    qarr.append(self.entries[num]._get_rpc_call_object())
                jo = json.dumps(qarr)
            url = "https://" + self.nodes[self.node_index] + "/"
            url = str.encode(url)
            deferred = self.agent.request('POST',
                                          url,
                                          Headers({"User-Agent"  : ['Async Steem for Python v0.6.1'],
                                                   "Content-Type": ["application/json"]}),
                                          _StringProducer(jo))
            def process_one_result(reply):
                """Process a single response from an JSON-RPC command."""
                try:
                    if "id" in reply:
                        reply_id = reply["id"]
                        if reply_id in self.entries:
                            match = self.entries[reply_id]
                            if "result" in reply:
                                #Call the proper result handler for the request that this response belongs to.
                                match._handle_result(reply["result"])
                            else:
                                if "error" in reply and "code" in reply["error"]:
                                    msg = "No message included with error"
                                    if "message" in reply["error"]:
                                        msg = reply["error"]["message"]
                                    #Call the proper error handler for the request that this response belongs to.
                                    match._handle_error(reply["error"]["code"], msg)
                                else:
                                    self.log.error("Error: Invalid JSON-RPC response entry.")
                            #del self.entries[reply_id]
                        else:
                            self.log.error("Error: Invalid JSON-RPC id in entry {rid!r}",rid=reply_id)
                    else:
                        self.log.error("Error: Invalid JSON-RPC response without id in entry: {reply!r}:",reply=reply)
                except Exception as ex:
                    self.log.failure("Error in _process_one_result {err!r}",err=str(ex))
            def handle_response(response):
                """Handle response for JSON-RPC batch query invocation."""
                try:
                    #Cancel any active timeout for this HTTPS call.
                    if timeoutCall.active():
                        timeoutCall.cancel()
                    def cbBody(bodystring):
                        """Process response body for JSON-RPC batch query invocation."""
                        try:
                            results = None
                            #The bosy SHOULD be JSON, it not always is.
                            try:
                                results = json.loads(bodystring)
                            except Exception as ex:
                                #If the result is NON-JSON, may want to move to the next node in the node list
                                self.log.error("Non-JSON response from server")
                                self._next_node()
                                #Add the failed sub-queue back to the command queue, we shall try again soon.
                                self.queue = subqueue + self.queue
                            if results != None:
                                ok = False
                                if isinstance(results, dict):
                                    #Running in legacy single JSON-RPC call mode (no batches), process the result of the single call.
                                    process_one_result(results)
                                    ok = True
                                else:
                                    if isinstance(results, list):
                                        #Running in batch mode, process the batch result, one response at a time
                                        for reply in results:
                                            process_one_result(reply)
                                        ok = True
                                    else:
                                        #Completely unexpected result type, may want to move to the next node in the node list.
                                        self.log.error("Error: Invalid JSON-RPC response, expecting list as response on batch.")
                                        self._next_node()
                                        #Add the failed sub-queue back to the command queue, we shall try again soon.
                                        self.queue = subqueue + self.queue
                                if ok == True:
                                    #Clean up the entries dict by removing all fully processed commands that now are no longer in the queu.
                                    for request_id in subqueue:
                                        if request_id in self.entries:
                                            del self.entries[request_id]
                                        else:
                                            self.log.error("Error: No response entry for request entry in result: {rid!r}.",rid=request_id)
                        except Exception as ex:
                            self.log.failure("Error in cbBody {err!r}",err=str(ex))
                        #This HTTPS POST is now fully processed.
                        self.active_call_count = self.active_call_count - 1
                        #Invoke self, possibly sending new queues RPC calls to the current node
                        self()
                    deferred2 = readBody(response)
                    deferred2.addCallback(cbBody)
                    return deferred2
                except Exception as ex:
                    self.log.failure("Error in handle_response {err!r}",err=str(ex))
                    #If something went wrong, the HTTPS POST isn't active anymore.
                    self.active_call_count = self.active_call_count - 1
                    #Invoke self, possibly sending new queues RPC calls to the current node
                    self()
            deferred.addCallback(handle_response)
            def _handle_error(error):
                """Handle network level error for JSON-RPC request."""
                try:
                    #Abandon any active timeout triggers
                    if timeoutCall.active():
                        timeoutCall.cancel()
                    #Unexpected error on HTTPS POST, we may want to move to the next node.
                    self.log.error("Error on HTTPS POST : {cls!r} : {err!r}",cls=error.type.__name__,err=error.getErrorMessage())
                    self._next_node()
                except Exception as ex:
                    self.log.failure("Error in _handle_error {err!r}",err=str(ex))
                #Add the failed sub-queue back to the command queue, we shall try again soon.
                self.queue = subqueue + self.queue
                ##If something went wrong, the HTTPS POST isn't active anymore.
                self.active_call_count = self.active_call_count - 1
                #Invoke self, possibly sending new queues RPC calls to the current node
                self()
            deferred.addErrback(_handle_error)
            timeoutCall = self.reactor.callLater(self.rpc_timeout, deferred.cancel)
            #Keep track of the number of active parallel HTTPS posts.
            self.active_call_count = self.active_call_count + 1
            return deferred
        except Exception as ex:
            self.log.failure("Error in _process_batch {err!r}",err=str(ex))
    def __getattr__(self, name):
        def addQueueEntry(*args):
            """Return a new in-queue JSON-RPC command invocation object with auto generated command name from __getattr__."""
            try:
                #A unique id for each command.
                self.cmd_seq = self.cmd_seq + 1
                #Create a new queu entry
                self.entries[self.cmd_seq] = _QueueEntry(self, name, args, self.cmd_seq, self.log)
                #append it to the command queue
                self.queue.append(self.cmd_seq)
                #Return handle to the new entry for setting callbacks on.
                return self.entries[self.cmd_seq]
            except Exception as ex:
                self.log.failure("Error in addQueueEntry {err!r}",err=str(ex))
        class api:
            def __init__(self,name,client):
                self.name = name
                self.client = client
            def __getattr__(self, name):
                return self.client.__getattr__(self.name + "." + name)
        if self.prefix_method == True:
            if name[-4:] == "_api":
                return api(name,self)
            else:
                if not "." in name:
                    name = "condenser_api." + name
                    return addQueueEntry
                else:
                    return addQueueEntry
        else:
            return addQueueEntry
    #Need to be able to check if RpcClient equatesNone
    def __eq__(self, val):
        if val is None:
            return False
        return True

if __name__ == "__main__":
    from twisted.internet import reactor
    from twisted.logger import Logger, textFileLogObserver
    from datetime import datetime as dt
    import dateutil.parser
    import sys
    #When processing a block we call this function for each downvote/flag
    def process_vote(vote_event,clnt):
        #Create a new JSON-RPC entry on the queue to fetch post info, including detailed vote info
        opp = clnt.get_content(vote_event["author"],vote_event["permlink"])
        #This one is for processing the results from get_content
        def process_content(event, client):
            #We geep track of votes given and the total rshares this resulted in.
            start_rshares = 0.0
            #Itterate over all votes to count rshares and to find the downvote we are interested in.
            found = False
            for vote in  event["active_votes"]:
                #Look if it is our downvote.
                if vote["voter"] == vote_event["voter"] and vote["rshares"] < 0:
                    found = True
                    #Diferentiate between attenuating downvotes and reputation eating flags.
                    if start_rshares + float(vote["rshares"]) < 0:
                        print(vote["time"],\
                              "FLAG",\
                              vote["voter"],"=>",vote_event["author"],\
                              vote["rshares"]," rshares (",\
                              start_rshares , "->", start_rshares + float(vote["rshares"]) , ")")
                    else:
                        print(vote["time"],\
                              "DOWNVOTE",\
                              vote["voter"],"=>",vote_event["author"],\
                              vote["rshares"],"(",\
                              start_rshares , "->" , start_rshares + float(vote["rshares"]) , ")")
                #Update the total rshares recorded before our downvote
                start_rshares = start_rshares + float(vote["rshares"])
            if found == False:
                print("vote not found, possibly to old.",vote_event["voter"],"=>",vote_event["author"],vote_event["permlink"])
        #Set the above closure as callback.
        opp.on_result(process_content)
    #This is a bit fiddly at this low level,  start nextblock a bit higer than where we start out
    nextblock = 19933100
    obs = textFileLogObserver(sys.stdout)
    log = Logger(observer=obs,namespace="jsonrpc_test")
    #Create our JSON-RPC RpcClient
    rpcclient = RpcClient(reactor,log,nodelist="stage")
    #Count the number of active block queries
    active_block_queries = 0
    sync_block = None
    #Function for fetching a block and its operations.
    def get_block(blk):
        """Request a single block asynchonously."""
        global active_block_queries
        #This one is for processing the results from get_block
        def process_block(event, client):
            """Process the result from block getting request."""
            global active_block_queries
            global nextblock
            global sync_block
            active_block_queries = active_block_queries - 1
            if event != None:
                if sync_block != None and blk >= sync_block:
                    sync_block = None
                #Itterate over all operations in the block.
                for t in event["transactions"]:
                    for o in t["operations"]:
                        #We are only interested in downvotes
                        if o[0] == "vote" and o[1]["weight"] < 0:
                            #Call process_vote for each downvote
                            process_vote(o[1],client)
                #fetching network clients alive.
                get_block(nextblock)
                nextblock = nextblock + 1
                if active_block_queries < 8:
                    treshold = active_block_queries * 20
                    behind = (dt.utcnow() - dateutil.parser.parse(event["timestamp"])).seconds
                    if behind >= treshold:
                        print("Behind",behind,"seconds while",active_block_queries,"queries active. Treshold =",treshold)
                        print("Spinning up an extra parallel query loop.")
                        get_block(nextblock)
                        nextblock = nextblock + 1
            else:
                if sync_block == None or blk <= sync_block:
                    sync_block = blk
                    get_block(blk)
                else:
                    print("Overshot sync_block")
                    if active_block_queries == 0:
                        print("Keeping one loop alive")
                        get_block(blk)
                    else:
                        print("Scaling down paralel HTTPS queries",active_block_queries)
        #Create a new JSON-RPC entry on the queue to fetch a block.
        opp = rpcclient.condenser_api.get_block(blk)
        active_block_queries = active_block_queries + 1
        #Bind the above closure to the result of get_block
        opp.on_result(process_block)
    #Kickstart the process by kicking off eigth block fetching operations.
    for block in range(19933000, 19933100):
        get_block(block)
    #By invoking the rpcclient, we will process queue entries upto the max number of paralel HTTPS requests.
    rpcclient()
    #Start the main twisted event loop.
    reactor.run()

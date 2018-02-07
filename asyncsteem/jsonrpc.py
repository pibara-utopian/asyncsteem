#!/usr/bin/python
"""Version of the JSON-RPC library that should work as soon as full-API nodes start implementing the actual JSON-RPC specification"""
from __future__ import print_function
import time
import json
from termcolor import colored
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.internet import defer

try:
    from termcolor import colored
    class DefaultLogger(object):
        def __init__(self):
            self.prefix = "jsonrpc"
        def set_prefix(self, prefix):
            self.prefix = prefix
        def log(self,message,explanation,color):
            print(colored(self.prefix,"yellow"),":",colored(message,color),explanation)
        def error(self,message,explanation=""):
            self.log(message,explanation,"red")
        def warning(self,message,explanation=""):
            self.log(message,explanation,"cyan")
        def notice(self,message,explanation=""):
            self.log(message,explanation,"green")
        def info(self,message,explanation=""):
            self.log(message,explanation,"blue")
except:
    class DefaultLogger(object):
        def __init__(self):
            self.prefix = "jsonrpc"
        def set_prefix(self, prefix):
            self.prefix = prefix
        def log(message,explanation):
            print(self.prefix,":",message,"#",explanation)
        def error(self,message,explanation=""):
            self.log(message,explanation)
        def warning(self,message,explanation=""):
            self.log(message,explanation)
        def notice(self,message,explanation=""):
            self.log(message,explanation)
        def info(self,message,explanation=""):
            self.log(message,explanation)

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

class QueueEntry(object):
    """Helper class for managing in-queue JSON-RPC command invocations"""
    def __init__(self, arpcclient, command, arguments, cmd_id, logger):
        self.rpcclient = arpcclient
        self.command = command
        self.arguments = arguments
        self.cmd_id = cmd_id
        self.result_callback = None
        self.error_callback = None
        self.logger = logger
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
            try:
                self.result_callback(result, self.rpcclient)
            except Exception as ex:
                self.logger.error("Error in result handler for '" +
                              self.command +
                              "' command result :",
                              str(ex))
        else:
            self.logger.error("Error: no on_result defined for '" +
                          self.command +
                          "' command result",str(result))
    def _handle_error(self, errno, msg):
        """Call the supplied user error handler or act as default error handler."""
        if self.error_callback != None:
            try:
                self.error_callback(errno, msg, rpcclient)
            except Exception as ex:
                self.logger.error("Error in error handler for '" +
                              self.command +
                              "' command result :",
                              str(ex))
        else:
            self.logger.error("Notice: no on_error defined for '" +
                          self.command +
                          "' command result",str(msg))



class RpcClient(object):
    """Core JSON-RPC client class."""
    def __init__(self,
                 areactor,
                 nodes=["rpc.buildteam.io",
                        "steemd.minnowsupportproject.org",
                        "steemd.pevo.science",
                        "rpc.steemviz.com",
                        "seed.bitcoiner.me",
                        "rpc.steemliberator.com",
                        "api.steemit.com",
                        "steemd.privex.io"],
                 parallel=16,
                 max_batch_size=1,
                 rpc_timeout=15,
                 logger = DefaultLogger()):
        """Constructor for asynchonour JSON-RPC client"""
        self.reactor = areactor
        self.nodes = nodes
        self.parallel = parallel
        self.max_batch_size = max_batch_size
        self.rpc_timeout = rpc_timeout
        self.node_index = 0
        self.agent = Agent(areactor)
        self.cmd_seq = 0
        self.last_rotate = 0
        self.errorcount = 0
        self.entries = dict()
        self.queue = list()
        self.active_call_count = 0
        self.logger = logger
        self.logger.info("Starting off with node "+nodes[self.node_index])
    def _next_node(self, reason):
        now = time.time()
        ago = now - self.last_rotate
        self.errorcount = self.errorcount + 1
        if ago > self.rpc_timeout or self.errorcount >= self.parallel:
            self.logger.notice("Swithing from " + self.nodes[self.node_index] + " to an other node due to error",reason)
            self.last_rotate = now
            self.node_index = (self.node_index + 1) % len(self.nodes)
            self.errorcount = 0
            self.logger.info("Switching to node " + self.nodes[self.node_index])
    def __call__(self):
        """Invoke the object to send out some of the queued commands to a server"""
        dv = None
        start_count = self.active_call_count
        while self.active_call_count < self.parallel and self.queue:
            subqueue = self.queue[:self.max_batch_size]
            self.queue = self.queue[self.max_batch_size:]
            dv = self._process_batch(subqueue)
        if not self.queue and self.active_call_count == 0:
            self.reactor.stop()
        end_count = self.active_call_count
        return dv
    def _process_batch(self, subqueue):
        """Send a single batch of JSON-RPC commands to the server and process the result."""
        timeoutCall = None
        jo = None
        if self.max_batch_size == 1:
            jo = json.dumps(self.entries[subqueue[0]]._get_rpc_call_object())
        else:
            qarr = list()
            for num in subqueue:
                qarr.append(self.entries[num]._get_rpc_call_object())
            jo = json.dumps(qarr)
        url = "https://" + self.nodes[self.node_index] + "/"
        url = str.encode(url)
        deferred = self.agent.request('POST',
                                      url,
                                      Headers({"User-Agent"  : ['Async Steem for Python v0.01'],
                                               "Content-Type": ["application/json"]}),
                                      _StringProducer(jo))
        def process_one_result(reply):
            """Process a single response from an JSON-RPC command."""
            if "id" in reply:
                reply_id = reply["id"]
                if reply_id in self.entries:
                    match = self.entries[reply_id]
                    if "result" in reply:
                        match._handle_result(reply["result"])
                    else:
                        if "error" in reply and "code" in reply["error"]:
                            msg = "No message included with error"
                            if "message" in reply["error"]:
                                msg = reply["error"]["message"]
                            match._handle_error(reply["error"]["code"], msg)
                        else:
                            self.logger.error("Error: Invalid JSON-RPC response entry.")
                    del self.entries[reply_id]
                else:
                    self.logger.error("Error: Invalid JSON-RPC id in entry:"+str(reply_id))
            else:
                self.logger.error("Error: Invalid JSON-RPC response without id in entry:"+str(reply_id))
        def handle_response(response):
            """Handle response for JSON-RPC batch query invocation."""
            if timeoutCall.active():
                timeoutCall.cancel()
            def cbBody(bodystring):
                """Process response body for JSON-RPC batch query invocation."""
                results = None
                try:
                    results = json.loads(bodystring)
                except Exception as ex:
                    self._next_node("Non-JSON response from server")
                    self.queue = subqueue + self.queue
                    self.active_call_count = self.active_call_count - 1
                    self()
                if results != None:
                    if isinstance(results, dict):
                        process_one_result(results)
                    else:
                        if isinstance(results, list):
                            for reply in results:
                                process_one_result(reply)
                        else:
                            self.logger.error("Error: Invalid JSON-RPC response, expecting list as response on batch.")
                    for request_id in subqueue:
                        if request_id in self.entries:
                            del self.entries[request_id]
                            self.logger.error("Error: No response entry for request entry in result:"+str(request_id))
                    self.active_call_count = self.active_call_count - 1
                    self()
            deferred2 = readBody(response)
            deferred2.addCallback(cbBody)
            return deferred2
        deferred.addCallback(handle_response)
        def _handle_error(error):
            """Handle network level error for JSON-RPC request."""
            if timeoutCall.active():
                timeoutCall.cancel()
            self._next_node(error.getErrorMessage())
            self.queue = subqueue + self.queue
            self.active_call_count = self.active_call_count - 1
            self()
        deferred.addErrback(_handle_error)
        timeoutCall = self.reactor.callLater(self.rpc_timeout, deferred.cancel)
        self.active_call_count = self.active_call_count + 1
        return deferred
    def __getattr__(self, name):
        def addQueueEntry(*args):
            """Return a new in-queue JSON-RPC command invocation object with auto generated command name from __getattr__."""
            self.cmd_seq = self.cmd_seq + 1
            self.entries[self.cmd_seq] = QueueEntry(self, name, args, self.cmd_seq, self.logger)
            self.queue.append(self.cmd_seq)
            return self.entries[self.cmd_seq]
        return addQueueEntry
    #Need to be able to check if RpcClient equatesNone
    def __eq__(self, val):
        if val is None:
            return False
        return True

if __name__ == "__main__":
    from twisted.internet import reactor
    from datetime import datetime as dt
    import dateutil.parser
    #When processing a block we call this function for each downvote/flag
    def process_vote(vote_event,clnt):
        #Create a new JSON-RPC entry on the queue to fetch post info, including detailed vote info
        opp = clnt.get_content(vote_event["author"],vote_event["permlink"])
        #This one is for processing the results from get_content
        def process_content(event, client):
            #We geep track of votes given and the total rshares this resulted in.
            start_rshares = 0.0
            #Itterate over all votes to count rshares and to find the downvote we are interested in.
            for vote in  event["active_votes"]:
                #Look if it is our downvote.
                if vote["voter"] == vote_event["voter"] and vote["rshares"] < 0:
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
        #Set the above closure as callback.
        opp.on_result(process_content)
    #This is a bit fiddly at this low level,  start nextblock a bit higer than where we start out
    nextblock = 19656009
    #Create our JSON-RPC RpcClient
    rpcclient = RpcClient(reactor)
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
        opp = rpcclient.get_block(blk)
        active_block_queries = active_block_queries + 1
        #Bind the above closure to the result of get_block
        opp.on_result(process_block)
    #Kickstart the process by kicking off eigth block fetching operations.
    for block in range(19656000, 19656008):
        get_block(block)
    test = rpcclient.get_dynamic_global_properties()
    def process_result(msg, rpcclient):
        print("      ",msg)
    test.on_result(process_result)
    #By invoking the rpcclient, we will process queue entries upto the max number of paralel HTTPS requests.
    rpcclient()
    #Start the main twisted event loop.
    reactor.run()

import jsonrpc

class CallbackAdd:
    def __init__(self,queue,name,args):
        self.queue = queue
        self.name  = name
        self.args  = args
    def __call__(self,cb):
        self.queue.command_queue.append([self.name,self.args,cb])
        self.queue._do_work()

class AsyncQueue:
    def __init__(self,reactor,nodes=["rpc.buildteam.io",
                                     "steemd.minnowsupportproject.org",
                                     "steemd.pevo.science",
                                     "rpc.steemviz.com",
                                     "seed.bitcoiner.me",
                                     "rpc.steemliberator.com",
                                     "api.steemit.com",
                                     "steemd.privex.io"],parallel = 8):
        self.reactor = reactor #Twisted reactor to use
        self.nodes=nodes       #List of steemit full API nodes
        self.rpc = jsonrpc.Client(reactor,nodes,self,parallel)
        self.id = 0
        self.command_queue = list()
    def __getattr__(self,name):
        return self._handlerFunctionClosure(name)
    def _handlerFunctionClosure(self,name):
        def handlerFunction(*args):
            a = list(args)
            return CallbackAdd(self,name,a)
        return handlerFunction
    def _do_work(self):
        print "DEBUG:", self.command_queue

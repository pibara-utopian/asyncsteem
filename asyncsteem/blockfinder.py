import dateutil.parser
import jsonrpc
from termcolor import colored

class DateFinder:
    def __init__(self,reactor,date,callback,nodes=["rpc.buildteam.io",
                                                   "steemd.minnowsupportproject.org",
                                                   "steemd.pevo.science",
                                                   "rpc.steemviz.com",
                                                   "seed.bitcoiner.me",
                                                   "rpc.steemliberator.com",
                                                   "api.steemit.com",
                                                   "steemd.privex.io"],rpc=None):
        self.reactor = reactor #Twisted reactor to use
        self.nodes=nodes
        #if rpc == None:
        self.rpc = jsonrpc.Client(reactor,nodes,self)
        #else:
        #    self.rpc = rpc
        self.date = date
        self.reactor = reactor
        self.callback = callback
        self.upper_limit = -1
        self.lower_limit = 0
        self.best_guess = None
        print "DateFinder created for",date
    def __call__(self,blk):
        print " - DateFinder looking at",self.best_guess
        if blk != None and "timestamp" in blk:
            ts = blk["timestamp"]
            ddt = dateutil.parser.parse(ts)
            if ddt < self.date:
                #Our best guess was to early
                if self.upper_limit > 0 and self.upper_limit - self.best_guess < 2:
                    #Seems our upper limit is our match.
                    print "DateFinder found block:",self.best_guess+1
                    self.callback(self.best_guess+1)
                else:
                    #Make our previous best guess our lower limit and try again
                    self.lower_limit = self.best_guess
                    self.start()
            else:
                #Our best guess was either to late or spot on.
                if self.best_guess - self.lower_limit < 2:
                    #Seems our best guess is indeed our match.
                    print "DateFinder found block:",self.best_guess
                    self.callback(self.best_guess)
                else:
                    self.upper_limit = self.best_guess
                    self.start()
        else:
            if blk != None:
                print "Oops, ( Blk", self.best_guess,")",self.lower_limit,self.upper_limit,blk
            self.upper_limit = self.best_guess 
            self.start()
    def start(self):
        if self.upper_limit == -1:
            #We haven't seen anything above the target date yet, we need to look higher
            if self.lower_limit < 1:
                self.best_guess = 5000000
            else:
                self.best_guess = self.lower_limit * 3
        else:
            self.best_guess = int((self.upper_limit + self.lower_limit)/2)
        self.rpc.get_block(self.best_guess)

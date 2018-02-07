#!/usr/bin/python
import sys
from datetime import timedelta
import time
from termcolor import colored
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain

class WatchingTheWatchers:
    def __init__(self):
        pass
    def update(self,downvoter, downvoted, dvpower, flagpower):
        pass
        #print "DOWNVOTE : ",downvoter,"=>",downvoted,"downvote =",dvpower,"flag",flagpower
    def set_account_info(self,account,vp,racc,proxy):
        pass
        #print "ACCOUNT INFO:",account,"vote-power :",vp,"recovery :",racc,"proxy :",proxy
    def report(self):
        print "[REPORT]"

class WatchingTheWatchersBot:
    def __init__(self,wtw):
        self.stopped=None
        self.wtw = wtw
        self.looked_up = set()
    def vote(self,tm,vote_event,client):
        def process_vote_content(event, aclient):
            start_rshares = 0.0
            for vote in  event["active_votes"]:
                if vote["voter"] == vote_event["voter"] and vote["rshares"] < 0:
                    if start_rshares + float(vote["rshares"]) < 0:
                        flag_power = 0 - start_rshares - float(vote["rshares"])
                    else:
                        flag_power = 0
                    downvote_power = 0 - vote["rshares"] - flag_power
                    self.wtw.update(vote["voter"],vote_event["author"],downvote_power,flag_power)
        def lookup_accounts(acclist):
            def user_info(accounts,bclient):
                if len(acclist) != len(accounts):
                    print "OOPS:",len(acclist),len(accounts),acclist
                for index in range(0,len(accounts)):
                    a = accounts[index]
                    account = acclist[index]
                    vp = (float(a["vesting_shares"].split()[0]) + \
                          float(a["received_vesting_shares"].split()[0]) - \
                          float(a["delegated_vesting_shares"].split()[0]))/1000000.0
                    racc = None
                    proxy = None
                    if a["recovery_account"] != "steem":
                        racc = a["recovery_account"]
                    if a["proxy"] != "" :
                        proxy = a["proxy"]
                    self.wtw.set_account_info(account,vp,racc,proxy)
                    accl2 = list()
                    if racc!= None and not racc in self.looked_up:
                        accl2.append(racc)
                    if proxy != None and not proxy in self.looked_up:
                        accl2.append(proxy)
                    if len(accl2) > 0:
                        lookup_accounts(accl2)
            op = client.get_accounts(acclist)
            op.on_result(user_info)
        if self.stopped == None or self.stopped > tm:
            if vote_event["weight"] < 0:
                opp = client.get_content(vote_event["author"],vote_event["permlink"])
                opp.on_result(process_vote_content)
                al = list()
                if not vote_event["voter"] in self.looked_up:
                    al.append(vote_event["voter"])
                    self.looked_up.add(vote_event["voter"])
                if not vote_event["author"] in self.looked_up:
                    al.append(vote_event["author"])
                    self.looked_up.add(vote_event["author"])
                if len(al) > 0:
                    lookup_accounts(al)
    def day(self,tm,event,client):
        self.stopped = tm

print "Constructing ActiveBlockChain"
bc = ActiveBlockChain(reactor,rewind_days=1)
print "Constructing bot"
wtw = WatchingTheWatchers()
tb = WatchingTheWatchersBot(wtw)
print "Regestering bot"
bc.register_bot(tb,"watchingthewatchers")
print "Starting main event loop"
reactor.run()
print "Done"
wtw.report()

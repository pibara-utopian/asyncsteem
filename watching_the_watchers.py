#!/usr/bin/python
import sys
from datetime import timedelta
import time
from termcolor import colored
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain

class WatchingTheWatchers:
    def __init__(self):
        self.dvcount = 0
        self.account_type = dict()
        self.account_relations = dict()
        self.by_voter = dict()
        self.by_target = dict()
        self.by_pair = dict()
    def update(self,downvoter, downvoted, dvpower, flagpower):
        pair = downvoter + "/" + downvoted
        if not downvoter in self.by_voter:
            self.by_voter[downvoter] = [0.0,0.0]
        if not downvoted in self.by_target:
            self.by_target[downvoted] = [0.0,0.0]
        if not pair in self.by_pair:
            self.by_pair[pair] = [0.0,0.0]
        self.by_voter[downvoter][0] = self.by_voter[downvoter][0] + dvpower
        self.by_voter[downvoter][1] = self.by_voter[downvoter][1] + flagpower
        self.by_target[downvoted][0] = self.by_target[downvoted][0] + dvpower
        self.by_target[downvoted][1] = self.by_target[downvoted][1] + flagpower
        self.by_pair[pair][0] = self.by_pair[pair][0] + dvpower
        self.by_pair[pair][0] = self.by_pair[pair][0] + flagpower
        self.dvcount = self.dvcount + 1
        if self.dvcount % 100 == 0:
            print self.dvcount,"downvotes so far."
    def set_account_info(self,account,fish,related):
        self.account_type[account] = fish
        if len(related) > 0:
            self.account_relations[account] = related
    def report(self,tm):
        print "[REPORT]",tm
        print " * account_type :",self.account_type
        print
        print " * account_relations :",self.account_relations
        print
        print " * by voter :",self.by_voter
        print
        print " * by target :",self.by_target
        print
        print " * by pair :",self.by_pair
        print
        self.dvcount = 0
        self.account_type = dict()
        self.account_relations = dict()
        self.by_voter = dict()
        self.by_target = dict()
        self.by_pair = dict()

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
                    fish = "redfish"
                    if vp >= 1.0:
                        fish = "minnow"
                    if vp >= 10.0:
                        fish = "dolphin"
                    if vp >= 100:
                        fish = "orca"
                    if vp > 1000:
                        fish = "whale"
                    racc = None
                    proxy = None
                    related = list()
                    if a["recovery_account"] != "steem" and a["recovery_account"] != "":
                        related.append(a["recovery_account"])
                    if a["proxy"] != "" :
                        related.append(a["proxy"])
                    self.wtw.set_account_info(account,fish,related)
                    accl2 = list()
                    if racc!= None and not racc in self.looked_up:
                        accl2.append(racc)
                    if proxy != None and not proxy in self.looked_up:
                        accl2.append(proxy)
                    if len(accl2) > 0:
                        lookup_accounts(accl2)
            op = client.get_accounts(acclist)
            op.on_result(user_info)
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
        self.wtw.report(tm)

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

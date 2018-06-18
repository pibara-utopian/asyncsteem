#!/usr/bin/python
import json
import sys
import io
from twisted.internet import reactor
from twisted.logger import Logger, textFileLogObserver
from asyncsteem import ActiveBlockChain

class Count:
    def __init__(self):
        self.count = dict()
        self.count["flag"] = dict()
        self.count["downvote"] = dict()
        self.count["flag"]["by_flagger"] = dict()
        self.count["flag"]["by_flaggee"] = dict()
        self.count["flag"]["by_pair"] = dict()
        self.count["downvote"]["by_flagger"] = dict()
        self.count["downvote"]["by_flaggee"] = dict()
        self.count["downvote"]["by_pair"] = dict()
        self.count["meta"] = dict()
    def flag(self,flagger,flaggee,rshares):
        if flagger in self.count["flag"]["by_flagger"]:
            self.count["flag"]["by_flagger"][flagger] += rshares
        else:
            self.count["flag"]["by_flagger"][flagger] = rshares
        if flaggee in self.count["flag"]["by_flaggee"]:
            self.count["flag"]["by_flaggee"][flaggee] += rshares
        else:
            self.count["flag"]["by_flaggee"][flaggee] = rshares
        pair = flagger + "->" + flaggee
        if pair in self.count["flag"]["by_pair"]:
            self.count["flag"]["by_pair"][pair] += rshares
        else:
            self.count["flag"]["by_pair"][pair] = rshares
    def downvote(self,flagger,flaggee,rshares):
        if flagger in self.count["downvote"]["by_flagger"]:
            self.count["downvote"]["by_flagger"][flagger] += rshares
        else:
            self.count["downvote"]["by_flagger"][flagger] = rshares
        if flaggee in self.count["downvote"]["by_flaggee"]:
            self.count["downvote"]["by_flaggee"][flaggee] += rshares
        else:
            self.count["downvote"]["by_flaggee"][flaggee] = rshares
        pair = flagger + "->" + flaggee
        if pair in self.count["downvote"]["by_pair"]:
            self.count["downvote"]["by_pair"][pair] += rshares
        else:
            self.count["downvote"]["by_pair"][pair] = rshares
    def accounts(self):
        rval = set(self.count["flag"]["by_flagger"].keys())
        rval = rval.union(set(self.count["flag"]["by_flaggee"].keys()))
        rval = rval.union(set(self.count["downvote"]["by_flagger"].keys()))
        rval = rval.union(set(self.count["downvote"]["by_flaggee"].keys()))
        return list(rval)
    def setmeta(self,name,obj):
        self.count["meta"][name] = obj
    def dump(self):
        with open("watching_the_watchers.json","w") as outfile:
            outfile.write(json.dumps(self.count))

class TestBot:
    def __init__(self,count):
        self.count = count
        self.tm = None
        self.daycount = 0
    def comment(self,tm,comment_event,client):
        def process_votes_error(errno, msg, rpcclient):
            pass
        def process_votes(vote_events,c2):
            rshares = 0.0
            def flag(voter,vote_rshares):
                self.count.flag(voter,comment_event["author"],vote_rshares)
            def downvote(voter,vote_rshares):
                self.count.downvote(voter,comment_event["author"],vote_rshares)
            def flag_or_downvote(voter,vote_rshares):
                if rshares <= 0.0:
                    flag(voter,0 - vote_rshares)
                else:
                    if (rshares + vote_rshares) >= 0:
                        downvote(voter,0 - vote_rshares)
                    else :
                        downvote(voter,rshares)
                        flag(voter, 0 - vote_rshares - vote_rshares)
            if (len(vote_events) > 0):
                for vote in vote_events:
                    if isinstance(vote["rshares"], basestring):
                        vote["rshares"] = float(vote["rshares"])
                    if vote["rshares"] < 0.0:
                        flag_or_downvote(vote["voter"],vote["rshares"])
                    rshares += vote["rshares"]
        opp = client.get_active_votes(comment_event["author"],comment_event["permlink"])
        opp.on_result(process_votes)
        opp.on_error(process_votes_error)
    def day(self,tm,event,client):
        accounts= self.count.accounts()
        extra = list()
        for account in accounts:
            def process_accounts(accounts_event,c2):
                if len(accounts_event) == 0:
                    print "Empty response for get_accounts for '" + account + "'"
                    return
                obj = dict()
                try:
                    obj["vesting_shares"] = float(accounts_event[0]["vesting_shares"].split()[0])
                except:
                    obj["vesting_shares"] = accounts_event[0]["vesting_shares"]
                    print "vest:",obj["vesting_shares"]
                try:
                    obj["received_vesting_shares"] = float(accounts_event[0]["received_vesting_shares"].split()[0])
                except:
                    obj["received_vesting_shares"] = accounts_event[0]["received_vesting_shares"]
                    print "received:",obj["vesting_shares"]
                try:
                    obj["delegated_vesting_shares"] = float(accounts_event[0]["delegated_vesting_shares"].split()[0])
                except:
                    obj["delegated_vesting_shares"] = accounts_event[0]["delegated_vesting_shares"]
                    print "delegated:",obj["delegated_vesting_shares"]
                try:
                    obj["reputation"] = int(accounts_event[0]["reputation"])
                except:
                    obj["reputation"] = accounts_event[0]["reputation"]
                    print "reputation:",obj["reputation"]
                obj["proxy"] = accounts_event[0]["proxy"]
                obj["recovery_account"] = accounts_event[0]["recovery_account"]
                count.setmeta(accounts_event[0]["name"],obj)
                if obj["proxy"] != "" and not obj["proxy"] in accounts and not obj["proxy"] in extra:
                    extra.append(obj["proxy"])
                    opp2 = client.get_accounts([obj["proxy"]])
                    opp2.on_result(process_accounts)
                if not obj["recovery_account"] in accounts and not obj["recovery_account"] in extra: 
                    extra.append(obj["recovery_account"])
                    opp3 = client.get_accounts([obj["recovery_account"]])
                    opp3.on_result(process_accounts)
            opp = client.get_accounts([account])
            opp.on_result(process_accounts)

obs = textFileLogObserver(io.open("watching_the_watchers.log", "a"))
print "NOTE: asyncsteem logging to watching_the_watchers.log"
log = Logger(observer=obs,namespace="asyncsteem")
bc = ActiveBlockChain(reactor,rewind_days=8,day_limit=1,log=log,nodelist="stage",stop_when_empty=True)
count = Count()
tb = TestBot(count)
bc.register_bot(tb,"testbot")
reactor.run()
count.dump()
print "DONE"

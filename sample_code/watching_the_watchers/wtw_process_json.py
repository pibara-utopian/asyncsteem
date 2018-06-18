#!/usr/bin/python
import json
import math
import pygraphviz as pgv

def torep(raw):
    if raw == 0:
        return 25
    if raw > 0:
        rval = int((math.log10(raw) - 9)*9+25)
        if rval < 25:
            rval = 25
        return rval
    else:
        return int(25 - (math.log10(0 - raw) - 9)*9)

class FlagJson:
    def __init__(self):
        with open("watching_the_watchers.json") as fil:
            self.data =json.loads(fil.read())
    def proxy_and_creator(self,accounts):
        rval = set()
        for account in accounts:
            if account in  self.data["meta"]:
                if self.data["meta"][account]["proxy"] != "":
                    rval.add(self.data["meta"][account]["proxy"])
                if not self.data["meta"][account]["recovery_account"] in ["steem","anonsteem",""]:
                    rval.add(self.data["meta"][account]["recovery_account"])
        return rval
    def account_subset(self,col,topn,maxn):
        #First get the top n flaggers and flagees
        rval = set()
        for subset in ["by_flagger","by_flaggee"]:
            top = sorted(self.data[col][subset].items(), key=lambda kv: kv[1])[-topn:]
            for pair in top:
                rval.add(pair[0])
        #Then add proxy and creator accounts
        rval = rval.union(self.proxy_and_creator(rval))
        #Finaly add accounts + creator accounts from pair list untill maxn
        spairs = sorted(self.data[col]["by_pair"].items(), key=lambda kv: kv[1])
        while len(spairs) > 0 and len(rval)  < maxn:
            pair = set(spairs.pop()[0].split("->"))
            rval2 = rval.union(pair).union(self.proxy_and_creator(pair))
            if len(rval2) > maxn:
                return rval
            rval = rval2
        return rval
    def nodelist(self,col,accounts):
        for account in accounts:
            meta = dict()
            meta["name"] = account
            meta["reputation"] = 25
            meta["fish"] = "none"
            if account in self.data["meta"].keys():
                meta["fish"] = "redfish"
                m = self.data["meta"][account]
                meta["reputation"] = torep(m["reputation"])
                vests = m["vesting_shares"] + m["received_vesting_shares"] - m["delegated_vesting_shares"]
                mvests = vests * 1.0 / 1000000.0
                if mvests > 1000:
                    meta["fish"] = "whale"
                else:
                    if mvests > 100:
                        meta["fish"] = "orca"
                    else:
                        if mvests > 10:
                            meta["fish"] = "dolphin"
                        else:
                            if mvests > 1:
                                meta["fish"] = "minnow"
            if account in self.data[col]["by_flagger"].keys():
                meta["flagger"] = True
            else:
                meta["flagger"] = False
            if account in self.data[col]["by_flaggee"].keys():
                meta["flagged"] = True
            else:
                meta["flagged"] = False
            yield meta
    def arclist(self,col,accounts):
        for pair in self.data[col]["by_pair"].keys():
            [flagger,flagged]  =  pair.split("->")
            if flagger in accounts and flagged in accounts:
                rval = dict()
                rval["flagger"] = flagger
                rval["flagged"] = flagged
                rval["weight"] = int(self.data[col]["by_pair"][pair]/1000000)
                yield rval



   
fjson = FlagJson()
accounts = fjson.account_subset("flag",10,32)
G=pgv.AGraph(strict=True,directed=True,bgcolor="antiquewhite1")
for node in fjson.nodelist("flag",accounts):
    fill = False
    if node["fish"] in ["whale","orca","dolphin"]:
        fill = True
    shape = "oval"
    if node["fish"] in ["minnow","dolphin"]:
        shape =  "octagon"
    if node["fish"] =="orca":
        shape = "doubleoctagon"
    if node["fish"] == "whale":
        shape = "tripleoctagon"
    fc = "palegreen"
    clr = "darkgreen"
    if node["flagged"]:
        if node["flagger"]:
            fc = "lightgoldenrod"
            clr = "gold3"
        else:
            fc = "pink"
            clr = "hotpink3"
    key = node["name"]
    if fill:
        G.add_node("@"+key,fillcolor=fc,shape=shape,style="filled")
    else:
        G.add_node("@"+key,color=clr,fillcolor='white',shape=shape)
for arc in fjson.arclist("flag",accounts):
    w = int((math.log10(arc["weight"] ) - 2) * 2)
    if w < 1:
        w = 1
    G.add_edge("@" + arc["flagger"],"@" + arc["flagged"],penwidth = w)
G.layout(prog="fdp")
G.draw("wtw.png")

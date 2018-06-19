#!/usr/bin/python
import json
import math
import pygraphviz as pgv
import sys

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
    def __init__(self,jsonfile):
        with open(jsonfile) as fil:
            self.data =json.loads(fil.read())
        with open("whitelist.json") as fil2:
            dat = json.loads(fil2.read())
            self.recovery_whitelist = dat["recovery_account"]
            self.flag_whitelist = dat["flag"]
    def proxy_and_creator(self,accounts):
        rval = set()
        for account in accounts:
            if account in  self.data["meta"]:
                if self.data["meta"][account]["proxy"] != "":
                    rval.add(self.data["meta"][account]["proxy"])
                if not self.data["meta"][account]["recovery_account"] in self.recovery_whitelist:
                    rval.add(self.data["meta"][account]["recovery_account"])
        return rval
    def account_subset(self,col,topn,maxn):
        #First get the top n flaggers and flagees
        rval = set()
        for subset in ["by_flagger","by_flaggee"]:
            top = sorted(self.data[col][subset].items(), key=lambda kv: kv[1])[-topn:]
            for pair in top:
                if not pair[0] in self.flag_whitelist:
                    rval.add(pair[0])
        #Then add proxy and creator accounts
        rval = rval.union(self.proxy_and_creator(rval))
        #Finaly add accounts + creator accounts from pair list untill maxn
        spairs = sorted(self.data[col]["by_pair"].items(), key=lambda kv: kv[1])
        while len(spairs) > 0 and len(rval)  < maxn:
            pair = spairs.pop()[0].split("->")
            if not pair[0] in self.flag_whitelist and not pair[0] in self.flag_whitelist:
                rval2 = rval.union(set(pair)).union(self.proxy_and_creator(set(pair)))
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
    def related_arclist(self,col,accounts):
        for account in accounts:
            if account in self.data["meta"].keys():
                m = self.data["meta"][account]
                if m["proxy"] != "":
                    rval = dict()
                    rval["account"] = account
                    rval["peer"] = m["proxy"]
                    rval["ptype"] = "proxy"
                    yield rval
                if not m["recovery_account"] in self.recovery_whitelist:
                    rval = dict()
                    rval["account"] = account
                    rval["peer"] = m["recovery_account"]
                    rval["ptype"] = "recovery"
                    yield rval
    def arclist(self,col,accounts):
        for pair in self.data[col]["by_pair"].keys():
            [flagger,flagged]  =  pair.split("->")
            if flagger in accounts and flagged in accounts:
                rval = dict()
                rval["flagger"] = flagger
                rval["flagged"] = flagged
                rval["weight"] = int(self.data[col]["by_pair"][pair]/1000000)
                yield rval
    def top(self,col,subset,topn):
        top = sorted(self.data[col]["by_" + subset].items(), key=lambda kv: kv[1])[-topn:]
        top.reverse()
        for p in top:
            account = p[0]
            rval = dict()
            rval["account"] = account
            yield rval


if len(sys.argv) < 2:
    print "Please supply json file"
    sys.exit(1)
jsonfile = sys.argv[1]
date = jsonfile.split(".")[0].split("-",1)[1]
print date
fjson = FlagJson(jsonfile)
for col in ["flag","downvote"]:
    for scale in ["large","small"]:
        nc = 128
        top = 16
        if scale == "small":
            nc = 20
            top = 4
        accounts = fjson.account_subset(col,top,nc)
        G=pgv.AGraph(strict=True,directed=True,bgcolor="antiquewhite1",splines="polyline")
        for node in fjson.nodelist(col,accounts):
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
        for arc in fjson.arclist(col,accounts):
            w = int((math.log10(arc["weight"] ) - 2) * 1.5)
            if w < 1:
                w = 1
            G.add_edge("@" + arc["flagger"],"@" + arc["flagged"],penwidth = w)
        for arc in fjson.related_arclist(col,accounts):
            if arc["ptype"] == "proxy":
                G.add_edge("@" + arc["account"],"@" + arc["peer"],penwidth = 2,color='blue')
            else:
                G.add_edge("@" + arc["account"],"@" + arc["peer"],penwidth = 2,color='red')
        G.layout(prog="fdp")
        G.draw("wtw-" + date + "-" + col + "-" + scale + ".png")
with open("wtw-" + date + ".MD", "w") as mdfile:
    mdfile.write("# Flag-war stats for posts made on " + date + "\n\n")
    mdfile.write("This daily post lists stats on the top downvoters and top downvoted regarding to posts ")
    mdfile.write("that just closed their six-and-a-half-day voting window.\n\nThe script that generated ")
    mdfile.write("this post, batch-processes downvotes and upvotes on one day of posts at the moment that ")
    mdfile.write("voting has closed for that day. The below lists show the top accounts involved in high ")
    mdfile.write("powered down voted on both sides of the downvoting process.\n\n")
    mdfile.write("Votes are sorted by timestamp of casting as to distinguish between the **downvote** and ")
    mdfile.write("the **flag** part of the negative vote. This is an important distinction as the downvote ")
    mdfile.write("part will only cut into the payout of the post in question while any vote that would ")
    mdfile.write("bring the payout below zero will end up cutting into the reputation of the author of the ")
    mdfile.write("original blog post or comment.\n\n")
    burl = "https://rmeijer.home.xs4all.nl/wtw/wtw-"
    for col in ["flag","downvote"]:
        mdfile.write("<H2>Top " + col + "s</H2>")
        lurl = burl + date + "-" + col + "-large.png"
        surl = burl + date + "-" + col + "-small.png"
        imglink = '<A HREF="' + lurl + '"><img src="' + surl + '"></A>' 
        mdfile.write(imglink + "<br>\n")
        mdfile.write("<i>(Click image for more detailed image)</i><br>\n")
        for by in ["flagger","flaggee"]:
            mdfile.write("<H3>By " + by + "</H3>")
            mdfile.write("<TABLE>")
            mdfile.write("<TR><TH>Position</TH><TH>Account</TH><TH>Link</TH></TR>")
            cnt = 0
            for cell in fjson.top(col,by,25):
                cnt = cnt + 1
                mdfile.write("<TR><TD>"+str(cnt)+"</TD>")
                mdfile.write("<TD>@" + cell["account"] + "</TD>")
                mdfile.write('<TD><A HREF="https://steemd.com/@' + cell["account"] + '">steemd</A></TD></TR>\n')
            mdfile.write("</TABLE>\n")
    mdfile.write('<hr><div class="pull-left"><a href="https://discordapp.com/invite/fmE7Q9q">')
    mdfile.write('<img src="https://steemitimages.com/DQmNQmR2sgebuWg4pZgPyLEVD5DqtS5VjpZDhkxQya6wf4a/freezepeach-icon.png"></a></div>')
    mdfile.write("If you feel you've been wrongly flagged, check out @freezepeach, the flag abuse neutralizer.")
    mdfile.write('See the <a href="https://steemit.com/introduceyourself/@freezepeach/freezepeach-the-flag-abuse-neutralizer">intro post</a> for more details, or join the ')
    mdfile.write('<a href="https://discordapp.com/invite/fmE7Q9q">discord server.</a><hr>')



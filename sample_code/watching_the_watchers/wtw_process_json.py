#!/usr/bin/python
import json
import math
import pygraphviz as pgv
import sys
import os
import time
from os import listdir
from os.path import isfile, join
from sets import Set
from beem import Steem
import paramiko

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
    def __init__(self,jsonfile,mypath):
        with open(jsonfile) as fil:
            self.data =json.loads(fil.read())
        with open(join(mypath,"whitelist.json")) as fil2:
            dat = json.loads(fil2.read())
            self.recovery_whitelist = dat["recovery_account"]
            self.flag_whitelist = dat["flag"]
        with open(join(mypath,"wtw-config.json")) as fil3:
            self.conf = json.loads(fil3.read())
            self.baseurl = self.conf["img-base-url"]
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
    def account_to_node(self,account):
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
        associates = list(self.proxy_and_creator([account]))
        meta["associates"] = ""
        if len(associates) > 0:
            for associate in associates:
                if meta["associates"] != "":
                    meta["associates"] += " "
                meta["associates"] += "@" + associate
        return meta
    def nodelist(self,col,accounts):
        for account in accounts:
            meta = self.account_to_node(account)
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

mypath = os.path.dirname(os.path.realpath(__file__))
sources = []

for f in listdir(mypath):
    filepath =join(mypath, f)
    if isfile(filepath) and f[-5:] == ".json" and f[:22] == "watching_the_watchers-":
        date = f[22:-5]
        dparts = date.split("-")
        if len(dparts) == 3:
            target = "wtw-" + date + ".MD"
            targetpath = join(mypath, target)
            if not isfile(targetpath):
                sources.append(filepath)
        else:
            print "Invalid date:", date, "for file",f
firstoutput = True
if len(sources) == 0:
    print "No unprocessed JSON files found."
for jsonfile in sources:
    if firstoutput == False:
        print "Sleeping for five minutes before processing next unpublished post:", jsonfile
        time.sleep(303)
    firstoutput = False
    print "Processing ", jsonfile
    pstruct = {}
    pstruct["image"] = [];
    pstruct["links"] = ["https://discordapp.com/invite/fmE7Q9q","https://steemit.com/introduceyourself/@freezepeach/freezepeach-the-flag-abuse-neutralizer"]
    pstruct["app"] = "watching-the-watchers/0.02"
    pstruct["format"] = "markdown"
    pstruct["tags"] = ["stats","steem","steemit","flags","flagwars"]
    pstruct["users"] = ["freezepeach"]
    date = jsonfile.split(".")[0].split("-",1)[1]
    print date,"(",jsonfile,")"
    fjson = FlagJson(jsonfile,mypath)
    baseurl = fjson.baseurl
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
                    G.add_node("@"+key,fillcolor=fc,shape=shape,style="filled",label="@"+key+"\l("+str(node["reputation"]) + ")")
                else:
                    G.add_node("@"+key,color=clr,fillcolor='white',shape=shape,label="@"+key+"\l("+str(node["reputation"]) + ")")
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
            if scale == "large": 
                for ofext in ["pdf","svg"]:
                    outfile = "wtw-" + date + "-" + col + "-" + scale + "." + ofext
                    G.draw(join(mypath, outfile), format=ofext)
            else:
                for ofext in ["png"]:
                    outfile = "wtw-" + date + "-" + col + "-" + scale + "." + ofext
                    G.draw(join(mypath,outfile), format=ofext)
                    if not baseurl + outfile in pstruct["image"]:
                        pstruct["image"].append(baseurl + outfile)
    for fish in ["redfish","minnow","dolphin","orca","whale","robocop"]:
        fishfile = fish + ".png"
        if not baseurl + fishfile in pstruct["image"]:
            pstruct["image"].append(baseurl + fishfile)
    allusers = Set() 
    with open(join(mypath, "wtw-" + date + ".MD"), "w") as mdfile:
        mdfile.write("# Flag-war stats for posts made on " + date + "\n\n")
        mdfile.write("This daily post lists stats on the top downvoters and top downvoted regarding to posts ")
        mdfile.write("that just closed their six-and-a-half-day voting window.\n\nThe script that generated ")
        mdfile.write("this post, batch-processes downvotes and upvotes on one day of posts at the moment that ")
        mdfile.write("voting has closed for that day. The below lists show the top accounts involved in high ")
        mdfile.write("powered down voted on both sides of the downvoting process.\n\n")
        mdfile.write("Votes are sorted by timestamp of casting as to distinguish between the **downvote** and ")
        mdfile.write("the **flag**-only part of the negative vote.\n\n")
        mdfile.write('<i>The <A HREF="https://github.com/pibara-utopian/asyncsteem">asyncsteem</A> script used ')
        mdfile.write('to create this post is available as part of the *asyncsteem* sample_code.</i>.') 
        burl = baseurl + "wtw-"
        for col in ["flag","downvote"]:
            mdfile.write("<H2>Top " + col + "s</H2>")
            lurl = burl + date + "-" + col + "-large.svg"
            surl = burl + date + "-" + col + "-small.png"
            purl = burl + date + "-" + col + "-large.pdf"
            imglink = '<A HREF="' + lurl + '"> <IMG src="' + surl + '"></A>' 
            mdfile.write(imglink + "<br>\n")
            mdfile.write('<i>(Click image for more detailed image, or click <A HREF="' + purl + '">here</A> for a PDF version.)</i><br>\n')
            for by in ["flagger","flaggee"]:
                mdfile.write("<H3>By " + by + "</H3>")
                mdfile.write("<TABLE>")
                mdfile.write('<TR><TH>Position</TH><TH></TH><TH>Account</TH><TH>Link</TH><TH>Associates</TH></TR>')
                cnt = 0
                for cell in fjson.top(col,by,25):
                    node = fjson.account_to_node(cell["account"])
                    rep = node["reputation"]
                    if cell["account"] in fjson.flag_whitelist:
                        fish = '<td><img src="' + baseurl+ 'robocop.png"></td>'
                    else:
                        fish = '<td><img src="' + baseurl+ node["fish"] + '.png"></td>'
                    cnt = cnt + 1
                    mdfile.write("<TR><TD>"+str(cnt)+"</TD>")
                    mdfile.write(fish)
                    allusers.add(cell["account"])
                    mdfile.write("<TD>@" + cell["account"] + " (" + str(node["reputation"])  + ")</TD>")
                    mdfile.write('<TD><A HREF="https://steemd.com/@' + cell["account"] + '">steemd</A></TD>')
                    mdfile.write('<TD>' + node["associates"] + "</TD></TR>\n\n")
                mdfile.write("</TABLE>\n")
        mdfile.write('<hr><div class="pull-left"><a href="https://discordapp.com/invite/fmE7Q9q">')
        mdfile.write('<img src="https://steemitimages.com/DQmNQmR2sgebuWg4pZgPyLEVD5DqtS5VjpZDhkxQya6wf4a/freezepeach-icon.png"></a></div>')
        mdfile.write("If you feel you've been wrongly flagged, check out @freezepeach, the flag abuse neutralizer.")
        mdfile.write('See the <a href="https://steemit.com/introduceyourself/@freezepeach/freezepeach-the-flag-abuse-neutralizer">intro post</a> for more details, or join the ')
        mdfile.write('<a href="https://discordapp.com/invite/fmE7Q9q">discord server.</a><hr>')
    for user in allusers:
        pstruct["users"].append(user)
    with open(join(mypath, "wtw-steem-meta-" + date + ".json"), "w") as jsonfile:
        jsonfile.write(json.dumps(pstruct))
    transport = paramiko.Transport((fjson.conf["ssh-server"], 22))
    transport.connect(username = fjson.conf["ssh-account"], password = fjson.conf["ssh-password"])
    sftp = paramiko.SFTPClient.from_transport(transport)
    for grp in ["downvote","flag"]:
        for size in ["large", "small"]:
            formats = ["png"]
            if size == "large":
                formats = ["svg","pdf"]
            for fmt in formats:
                filename = "wtw-" + date + "-" + grp + "-" + size + "." + fmt
                sftp.put(join(mypath,filename),"WWW/wtw/" + filename)
                print "Uploaded", filename, "to",fjson.conf["ssh-server"]
    beneficiaries = [{'account':'freezepeach', 'weight':5000},{'account':'pibara', 'weight':5000}]
    metafile = join(mypath,"wtw-steem-meta-" + date + ".json")
    postfile = join(mypath,"wtw-" + date + ".MD")
    with open(metafile) as m:
        json_metadata = json.loads(m.read())
    with open(postfile) as p:
        body = p.read()
    s = Steem(keys=fjson.conf["steem-posting-key"], nobroadcast=False)
    subject = "Flag-war stats for posts made on " + date
    tx = s.post(subject, body, author=fjson.conf["steem-account"], tags=["stats","steem","steemit","flags","flagwars"],
                        json_metadata=json_metadata, beneficiaries=beneficiaries)
print "DONE"


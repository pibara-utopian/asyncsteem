#!/usr/bin/python3
from os.path import isfile, join
from beem import Steem
import os
import json
mypath = os.path.dirname(os.path.realpath(__file__))
beneficiaries = [{'account':'freezepeach', 'weight':5000},{'account':'pibara', 'weight':5000}]
date = "2018-06-18"  #FIXME, need to process the latest date from previous step only
with open(join(mypath,"wtw-config.json")) as fil3:
    conf = json.loads(fil3.read())
metafile = join(mypath,"wtw-steem-meta-" + date + ".json")
postfile = join(mypath,"wtw-" + date + ".MD")
with open(metafile) as m:
    json_metadata = json.loads(m.read())
with open(postfile) as p:
    body = p.read()
s = Steem(keys=conf["steem-posting-key"], nobroadcast=False)
subject = "Flag-war stats for posts made on " + date
tx = s.post(subject, body, author=conf["steem-account"], tags=["stats","steem","steemit","flags","flagwars"],
                    json_metadata=json_metadata, beneficiaries=beneficiaries)
print(tx)

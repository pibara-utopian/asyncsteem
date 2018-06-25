#!/usr/bin/python
from os.path import isfile, join
import paramiko
import os
import json
mypath = os.path.dirname(os.path.realpath(__file__))
date = "2018-06-18" #FIXME, need to process the latest date from previous step only
with open(join(mypath,"wtw-config.json")) as fil3:
    conf = json.loads(fil3.read())
transport = paramiko.Transport((conf["ssh-server"], 22))
transport.connect(username = conf["ssh-account"], password = conf["ssh-password"])
sftp = paramiko.SFTPClient.from_transport(transport)
for grp in ["downvote","flag"]:
    for size in ["large", "small"]:
        formats = ["png"]
        if size == "large":
            formats = ["svg","pdf"]
        for fmt in formats:
            filename = "wtw-" + date + "-" + grp + "-" + size + "." + fmt
            sftp.put(join(mypath,filename),"WWW/wtw/" + filename)
            print "Uploaded", filename, "to",conf["ssh-server"]

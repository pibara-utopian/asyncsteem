#!/usr/bin/python
import sys
import json
import socket
from twisted.internet import reactor
from twisted.logger import Logger, textFileLogObserver
from asyncsteem import RpcClient

def process_account_info(event,client):
    obj = json.loads(event[0]["json_metadata"])
    candidates = []
    for rep in obj["report"]:
        candidates.append(rep["node"])
    candidates +=  obj["failing_nodes"].keys()
    candidates += obj["nodes"]
    candidates_set = set(candidates)
    candidate_list = []
    for candidate in candidates:
        if candidate[:8] == "https://" and len(candidate.split(":")) == 2:
            host = str(candidate[8:])
            candidate_list.append(host)
    for apinode in candidate_list:
            print apinode

def process_error(errno,msg,client):
    print msg

obs = textFileLogObserver(sys.stdout)
log = Logger(observer=obs,namespace="node-test")
client = RpcClient(reactor,log,stop_when_empty=False,rpc_timeout=15)
opp = client.get_accounts(["fullnodeupdate"])
opp.on_result(process_account_info)
opp.on_error(process_error)
client()
reactor.run()

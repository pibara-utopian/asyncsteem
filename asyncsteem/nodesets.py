#!/usr/bin/python
import copy
import json
def _make_nodesets():
    sets = dict()
    allnodes = ["api.steemitdev.com",
            "api.steemit.com",
            "api.steem.house",
            "api.steemitstage.com",
            "rpc.buildteam.io",
            "steemd.privex.io",
            "rpc.curiesteem.com",
            "seed.bitcoiner.me",
            "steemd.pevo.science",
            "rpc.steemviz.com",
            "rpc.steemliberator.com",
            "appbasetest.timcliff.com",
            "steemd.minnowsupportproject.org",
            "steemd.steemgigs.org",
            "api.steemit.com",
            "api.steem.house",
            "rpc.buildteam.io",
            "rpc.curiesteem.com",
            "steemd.privex.io"]
    for index in range(0,len(allnodes)):
        host = allnodes[index]
        for batchsize in [1,4]:
            hnam = "t" + str(index) + "-" + str(batchsize)
            for prefixmethod in [False,True]:
                nam = hnam
                if prefixmethod:
                    nam += "t"
                else:
                    nam += "f"
                sets[nam] = dict()
                sets[nam]["nodes"] = [host]
                sets[nam]["max_batch_size"] = batchsize
                sets[nam]["prefix_method"] = prefixmethod
    sets["stage"] = dict()
    sets["stage"]["nodes"] = ["api.steemit.com",
            "api.steemitstage.com"]
    sets["stage"]["max_batch_size"] = 16
    sets["stage"]["prefix_method"] = True
    sets["default"] = dict()
    sets["default"]["nodes"] = ["api.steemit.com",
            "api.steemitstage.com",
            "rpc.buildteam.io"]
    sets["default"]["max_batch_size"] = 1
    sets["default"]["prefix_method"] = False
    return sets

nodeset = _make_nodesets()
#print json.dumps(nodeset)

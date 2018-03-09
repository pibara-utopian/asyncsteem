#!/usr/bin/python
import copy
def _make_nodesets():
    sets = dict()
    defaultset = dict()
    defaultset["nodes"]=["rpc.buildteam.io",
                         "steemd.minnowsupportproject.org",
                         "steemd.pevo.science",
                         "rpc.steemviz.com",
                         "seed.bitcoiner.me",
                         "rpc.steemliberator.com",
                         "api.steemit.com",
                         "steemd.privex.io"]
    defaultset["max_batch_size"] = 1
    defaultset["prefix_method"] = False
    sets["default"] = defaultset
    stageset = dict()
    stageset["nodes"]=["api.steemitstage.com"]
    stageset["max_batch_size"] = 16
    stageset["prefix_method"] = True
    sets["stage"] = stageset
    stagesetone = dict()
    stagesetone["nodes"]=["api.steemitstage.com"]
    stagesetone["max_batch_size"] = 1
    stagesetone["prefix_method"] = True
    sets["bench_stage"] = stagesetone
    for num in range(0,len(defaultset["nodes"])):
        benchset = dict()
        benchset["nodes"]=[defaultset["nodes"][num]]
        benchset["max_batch_size"] = 1
        benchset["prefix_method"] = False
        sets["bench" + str(num+1)] = copy.deepcopy(benchset)
    abset = dict()
    abset["nodes"]=["appbasetest.timcliff.com"]
    abset["max_batch_size"] = 1
    abset["prefix_method"] = True
    sets["appbase"] = abset
    return sets

nodeset = _make_nodesets()

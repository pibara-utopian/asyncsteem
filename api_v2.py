#!/usr/bin/python
# NOTE: This script does NOT work, its meant as a blue sky example of how I hope the final version API could function.
from twisted.internet import reactor
from asyncsteem import ActiveBlockChain, AsyncQueue
from datetime import timedelta
import time
from termcolor import colored

class WatchingTheWatchersBot:
    def __init__(self):
        self.daycount = 0
    def vote(self,event_time,event,batch):
        #Outer closure for processing voted uppon comment
        def vote_comment(comment_event):
            #Middle closure for processing voter account info
            def voter_info(voter_account):
                #Inner clusure for processing author account_info
                def votee_info(votee_account):
                    #Silly print to test if API works as expected
                    print event["voter"],event["author"],event["permlink"],vote["rshares"],voter_account["recovery_account"],votee_account["recovery_account"]
                #Add a get_account RPC call to an upcomming batch, call votee_info on result, do nothing on error.
                batch.get_account(event["author"]).on_result(votee_info)
            #Check if the comment contains a list of votes.
            if "votes" in comment_event and isinstance(comment_event["votes"],list):
                for vote in comment_event["votes"]:
                    #Only process the DOWN-vote that actually matches the outer event.
                    if event["voter"] == vote["voter"] and vote["weight"] < 0:
                        #Add a get_account RPC call to an upcomming batch, call voter_info on result, do nothing on error.
                        batch.get_account(event["voter"]).on_result(voter_info) 
        #Only process DOWN-votes
        if event["weight"] < 0:
            #Add a get_account RPC call to an upcomming batch, call vote_comment on result, do nothing on error.
            batch.get_comment(event["author"],event["permlink"]).on_result(vote_comment)
    def day(self,tm,event,batch):
        #Closure for doing any final stuff for run.
        def final():
            print colored("* DAY completed, shutting down.","green")
        #Through the batch object, tell the ActiveBlockChain to NOT produce any more blockchain events for this bot.
        #After all child RCP calls are completed, final will be called.
        batch.abort(final)

#Create an ActiveBlockChain object for streaming blockchain events. Start at 0:00 one day before today, run upto 4 clients in paralel and use batches of 1 .. 32 RPC calls.
bc = ActiveBlockChain(reactor,rewind_days=1,parallel = 4, max_batch_size = 32)
#Initialize bot
tb = WatchingTheWatchersBot()
#Register the bot (there can be more than one)
bc.register_bot(tb,"watchingthewatchers")
#Kickstart the ActiveBlockChain object
bc.start()
#Twisted main event loop
reactor.run()


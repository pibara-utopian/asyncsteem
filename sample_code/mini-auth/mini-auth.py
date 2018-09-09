#!/usr/bin/python
#Some basic imports
import json
import time
import io
import os
from datetime import datetime
import dateutil
from os.path import join, dirname, realpath
#Some base twisted imports
from twisted.internet import reactor, endpoints
from twisted.logger import Logger, textFileLogObserver
from twisted.web import server,resource
from twisted.web.static import File
from twisted.web.util import redirectTo
#Asyncsteem import for talking to JSON-RPC steem API nodes.
from asyncsteem import ActiveBlockChain, RpcClient
#Blake2 keyed hashing for cookie signing
from pyblake2 import blake2b
#Random numbers for unique cookie id
from random import randint
#Asynchonous Redis library for storing some persistent data with.
from cyclone import redis
#Jinja2 templates for HTML output.
from jinja2 import Environment, FileSystemLoader

#This is our hub class that is used both from the blockchain streamer and from the web server.
class CookieUtil:
    def __init__(self,secret,logger):
        #Callback for setting the redis connection.
        def setDb(db):
            self.db = db
            self.logger.info("Connected to Redis")
        #We use a secret for BLAKE2 signing of our cookies
        self.secret = secret.encode("ascii")
        self.logger = logger
        #The local Redis is used to keep a persistent store of cookie to authenticated user mappings
        self.db = None
        d = redis.Connection()
        d.addCallback(setDb)
        #Try to keep a record of how far behind we are.
        self.last_blocktime = datetime.utcfromtimestamp(0)
    def new_cookie(self):
        #Take a large random number
        random_buffer = hex(randint(0,1000000000000000000000000000000000000000000))[2:-1]
        #Create a signature for that number using our secret
        signature = blake2b(data=random_buffer,key=self.secret,digest_size=48).hexdigest()
        #Make a cookie string from the random number and its signature. Noone can make a valid cookie but us.
        random_string = str(random_buffer).encode("ascii")
        cookie = random_string + "-" + signature
        return cookie
    def valid_cookie(self,cookie):
        if cookie == None:
            return False
        #Split up the cookie into the original random number and its signature.
        [cookie_id,signature1] = cookie.split("-");
        cookie_buffer = cookie_id.encode("ascii");
        #Calculate the signuture of the random bit again.
        signature2 = blake2b(data=cookie_buffer,key=self.secret,digest_size=48).hexdigest()
        #The existing signature should be the same as the new one.
        ok = (signature1 == signature2)
        if ok and self.db != None:
            #If the cookie is OK, keep a record of when this cookie was last used in our Redis server.
            k = cookie_id + "-lastvisit"
            v = str(time.time())
            d=self.db.set(k,v)
        return ok
    def authenticated_user(self,cookie_id):
        if self.db == None:
            return None
        #Look up if the cookie is linked to an authenticated user.
        k = cookie_id + "-steemauth"
        return self.db.get(k)
    def blocktime(self,tm):
        #Remember the last blocktime
        self.last_blocktime = tm
    def process_transfer(self,frm, memo):
        if self.db != None:
            #If we register a potentially authenticating transfer in the blochchain,
            #look in Redis to see if we gave the memo out as cookie id.
            k1 = memo[:40] + "-lastvisit"
            ltp = self.db.get(k1)
            def process_last_time(lasttime):
                #If the last time isn't None, this is a cookie id we know
                if lasttime != None:
                    self.logger.info("Known cookie id in transaction.")
                    #Check if this cookie id has already been registered to a steemit account
                    k2 = memo[:40] + "-steemauth"
                    acp = self.db.get(k2)
                    def process_account(account):
                        #If the memo holds a valid cookie id that has never been registered to any steem account before
                        if account == None:
                            #Store the cookie steem-account mapping.
                            d=self.db.set(k2,frm)
                            self.logger.info("Cookie has now been linked to a steemit user.")
                        else:
                            self.logger.info("This particular cookie id was already registered to a steem user before.")
                    #Above is asynchounous callback for result from Redis
                    acp.addCallback(process_account)
                else:
                    self.logger.info("Transaction without valid cookie id")
            #Above is asynchounous callback for result from Redis
            ltp.addCallback(process_last_time)
        else:
            self.logger.error("No Redis Db connection yet while processing transfer.")
    def behind_string(self):
        #Return how many time has passed since last block we saw.
        behind = datetime.utcnow() - self.last_blocktime
        return str(behind)

#Main function this server provides to authenticated users. List stale followed accounts.
#This functionality was borowed from a script by @tcpolymath.
def report_on_followers(request,steemaccount,cu,reactor,log,template,etemplate):
    def process_following(event,client):
        #Process the followed accounts response from the API node.
        def process_accounts(event2,client2):
            #Make a list of all accounts that didn't post for more than 40 days.
            stale_accounts = []
            for account in event2:
                name = account["name"]
                inactive = (datetime.utcnow() - dateutil.parser.parse(account["last_post"])).days
                if inactive > 40:
                    ias = str(inactive)
                    stale_accounts.append({"name": name , "inactive" : ias})
            #Use jinja2 to return a simple report
            html = template.render(authenticated = steemaccount, results=stale_accounts, behind=cu.behind_string())
            request.write(html.encode("ascii")) 
            request.finish()
        def process_accounts_err(errno,msg,client):
            html = etemplate.render(message=msg)
            request.write(html.encode("ascii"))
            request.finish()
        #Make a list with the accounts that we follow.
        accountlist = [];
        for entry in event:
            accountlist.append(entry["following"])
        #Request account info on all followed accounts.
        opp2 = client.get_accounts(accountlist)
        opp2.on_result(process_accounts)
        opp2.on_error(process_accounts_err)
    def process_following_err(errno,msg,client):
        html = etemplate.render(message=msg)
        request.write(html.encode("ascii"))
        request.finish()
    #STEEM JSON-RPC client.
    client = RpcClient(reactor,log,stop_when_empty=False,rpc_timeout=40)
    #Start by querying up to 1000 folowers of the authenticared account.
    opp = client.get_following(steemaccount,"","blog",1000)
    opp.on_result(process_following)
    opp.on_error(process_following_err)
    client()

#Simple twisted web resource that sets cookie if needed and redirects to functionality page.
class SetCookieIfNeeded(resource.Resource):
    isLeaf = True
    def __init__(self,cu):
        self.cu = cu
    def render_GET(self, request):
        oldcookie = request.getCookie("steemauth")
        #Only create a fresh new cookie if non was already set.
        if oldcookie == None:
            newcookie = self.cu.new_cookie()
            request.addCookie("steemauth",newcookie)
        #Redirect to service.
        return redirectTo("/steemauth",request)

#Our base resource and authentication check.
class SteemAuth(resource.Resource):
    isLeaf = True
    def __init__(self,cu, account,templates,reactor,log):
        self.cu = cu
        self.account = account
        self.templates = templates
        self.reactor = reactor
        self.log = log
    def render_GET(self, request):
        #If we are here, there should be a cookie
        oldcookie = request.getCookie("steemauth")
        #Check if the cookie is actually a valid one we created ourselv
        if cu.valid_cookie(oldcookie):
            #Take just the cookie id from the cookie.
            cookie_id = oldcookie.split("-")[0]
            #Get defered for a possible authenticated user from this cookie id.
            sa = self.cu.authenticated_user(cookie_id)
            def get_steemacount_from_redis(steemaccount):
                if steemaccount == None:
                    #If the user isn't authenticated yet, return authentication page.
                    self.log.info("Cookie not assigned to any steemit user")
                    rv = self.templates["askauth"].render(account=account,
                            session=cookie_id, 
                            behind=cu.behind_string()
                        )
                    request.write(rv.encode("ascii"))
                    request.finish()
                else:
                    #If the user is authenticated, run core business logic as borowed from @tcpolymaths script.
                    self.log.info("Cookie matches authenticated steemit user")
                    req = request
                    template = self.templates["following"]
                    etemplate = self.templates["error"]
                    report_on_followers(req,steemaccount,cu,self.reactor,self.log,template,etemplate)
                return
            #If there is a Redis problem, sa will ne None
            if sa == None :
                html = self.templates["error"].render(message="No connection to local Redis database")
                return html.encode("ascii")
            else :
                #Let the defered callback above handle the result from the Redis lookup
                sa.addCallback(get_steemacount_from_redis)
                return server.NOT_DONE_YET
        else:
            newcookie = self.cu.new_cookie()
            request.addCookie("steemauth",newcookie)
            return redirectTo("/steemauth",request)

#Our mini authentication server with some basic helo world functionality.
class MiniAuthWebServer(resource.Resource):
    def __init__(self,cu, account,reactor,log):
        self.cu = cu
        self.children = ["/","/steemauth"]
        self.account = account
        self.reactor = reactor
        self.log = log
        thisdir = os.path.dirname(os.path.abspath(__file__))
        #We do our synchonous IO for loading Jinja2 templates at server start.
        j2_env = Environment(loader=FileSystemLoader(thisdir),trim_blocks=True)
        self.templates = dict();
        self.templates["askauth"] = j2_env.get_template('authenticate.tmpl')
        self.templates["following"] = j2_env.get_template('following.tmpl')
        self.templates["error"] = j2_env.get_template('error.tmpl')
    def getChild(self, name, request):
        if request.uri == '/steemauth':
            return SteemAuth(cu, self.account,self.templates,self.reactor, self.log)
        else:
            if request.uri == '/':
                return SetCookieIfNeeded(self.cu);
            else:
                return resource.NoResource()

#This is the basic asyncsteem bot.
class TransferStream:
    def __init__(self,cu,account):
        self.cu = cu
        self.account = account
    #We listen only to transfers
    def transfer(self,tm,transfer_event,client):
        frm = transfer_event["from"]
        to = transfer_event["to"]
        memo = transfer_event["memo"]
        #For keeping track of if we are behind on the blockchain.
        self.cu.blocktime(tm)
        #Only process transfers to one single account, our owner.
        if to == self.account:
            self.cu.process_transfer(frm, memo)

#Get config with owner account name and unique unguessable secret
mypath = os.path.dirname(os.path.abspath(__file__))
with open(mypath + "/mini-auth.json") as configjsonfile:
    conf = json.load(configjsonfile)
secret = conf["secret"]
account = conf["account"]
#Set up logging
observer = textFileLogObserver(io.open(join(mypath,"mini-auth.log"), "a"))
logger = Logger(observer=observer,namespace="asyncsteem")
#Asyncsteem blochchain streamer
blockchain = ActiveBlockChain(reactor,log=logger,nodelist="default")
#Our CookieUtil is the main hub of our program
cu = CookieUtil(secret,logger)
#Instantiate our bot and link it to our blockchain
steembot = TransferStream(cu,account)
blockchain.register_bot(steembot,"flag_stream")
#Run our HTTP server on port 5080
root = MiniAuthWebServer(cu,account,reactor,logger)
factory = server.Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 5080)
endpoint.listen(factory)
#Start twisted reactor.
reactor.run()

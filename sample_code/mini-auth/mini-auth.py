#!/usr/bin/python
import json
import time
import io
import os
from twisted.internet import reactor, endpoints
from twisted.logger import Logger, textFileLogObserver
from twisted.web import server,resource
from twisted.web.static import File
from twisted.web.util import redirectTo
from datetime import datetime
import dateutil
from asyncsteem import ActiveBlockChain, RpcClient
from os.path import join, dirname, realpath
from pyblake2 import blake2b
from random import randint
from cyclone import redis
from jinja2 import Environment, FileSystemLoader

#This is our hub class that is used both from the blockchain streamer and from the web server.
class CookieUtil:
    def __init__(self,secret,logger):
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
        if ok:
            #If the cookie is OK, keep a record of when this cookie was last used in our Redis server.
            k = cookie_id + "-lastvisit"
            v = str(time.time())
            d=self.db.set(k,v)
        return ok
    def authenticated_user(self,cookie_id):
        #Look up if the cookie is linked to an authenticated user.
        k = cookie_id + "-steemauth"
        return self.db.get(k)
    def blocktime(self,tm):
        #Remember the last blocktime
        self.last_blocktime = tm
    def process_transfer(self,frm, memo):
        #If we register a potentially authenticating transfer in the blochchain 
        k1 = memo[:40] + "-lastvisit"
        k2 = memo[:40] + "-steemauth"
        ltp = self.db.get(k1)
        def process_last_time(lasttime):
            if lasttime != None:
                self.logger.info("Known cookie id in transaction.")
                acp = self.db.get(k2)
                def process_account(account):
                    #If the memo holds a valid cookie id that has never been registered to any steem account before
                    if account == None:
                        #Store the cookie steem-account mapping.
                        d=self.db.set(k2,frm)
                        self.logger.info("Cookie has now been linked to a steemit user.")
                    else:
                        self.logger.info("This particular cookie id was already registered to a steem user before.")
                acp.addCallback(process_account)
            else:
                self.logger.info("Transaction without valid cookie id")
        ltp.addCallback(process_last_time)
    def behind_string(self):
        #Return how many time has passed since last block we saw.
        behind = datetime.utcnow() - self.last_blocktime
        return str(behind)

def report_on_followers(request,steemaccount,cu,reactor,log,template,etemplate):
    def process_following(event,client):
        def process_accounts(event2,client2):
            stale_accounts = []
            for account in event2:
                name = account["name"]
                inactive = (datetime.utcnow() - dateutil.parser.parse(account["last_post"])).days
                if inactive > 40:
                    ias = str(inactive)
                    stale_accounts.append({"name": name , "inactive" : ias})
            html = template.render(authenticated = steemaccount, results=stale_accounts, behind=cu.behind_string())
            request.write(html.encode("ascii")) 
            request.finish()
        def process_accounts_err(errno,msg,client):
            html = etemplate.render(message=msg)
            request.write(html.encode("ascii"))
            request.finish()
        accountlist = [];
        for entry in event:
            accountlist.append(entry["following"])
        opp2 = client.get_accounts(accountlist)
        opp2.on_result(process_accounts)
        opp2.on_error(process_accounts_err)
    def process_following_err(errno,msg,client):
        html = etemplate.render(message=msg)
        request.write(html.encode("ascii"))
        request.finish()
    client = RpcClient(reactor,log,stop_when_empty=False,rpc_timeout=40)
    opp = client.get_following(steemaccount,"","blog",1000)
    opp.on_result(process_following)
    opp.on_error(process_following_err)
    client()

class SetCookieIfNeeded(resource.Resource):
    isLeaf = True
    def __init__(self,cu):
        self.cu = cu
    def render_GET(self, request):
        oldcookie = request.getCookie("steemauth")
        if oldcookie == None:
            newcookie = self.cu.new_cookie()
            request.addCookie("steemauth",newcookie)
        return redirectTo("/steemauth",request)

class SteemAuth(resource.Resource):
    isLeaf = True
    def __init__(self,cu, account,templates,reactor,log):
        self.cu = cu
        self.account = account
        self.templates = templates
        self.reactor = reactor
        self.log = log
    def render_GET(self, request):
        oldcookie = request.getCookie("steemauth")
        if cu.valid_cookie(oldcookie):
            cookie_id = oldcookie.split("-")[0]
            sa = self.cu.authenticated_user(cookie_id)
            def get_steemacount_from_redis(steemaccount):
                if steemaccount == None:
                    self.log.info("Cookie not assigned to any steemit user")
                    rv = self.templates["askauth"].render(account=account,
                            session=cookie_id, 
                            behind=cu.behind_string()
                        )
                    request.write(rv.encode("ascii"))
                    request.finish()
                else:
                    self.log.info("Cookie matches authenticated steemit user")
                    req = request
                    template = self.templates["following"]
                    etemplate = self.templates["error"]
                    report_on_followers(req,steemaccount,cu,self.reactor,self.log,template,etemplate)
                return
            sa.addCallback(get_steemacount_from_redis)
            return server.NOT_DONE_YET
        else:
            newcookie = self.cu.new_cookie()
            request.addCookie("steemauth",newcookie)
            return redirectTo("/steemauth",request)

class MiniAuthWebServer(resource.Resource):
    def __init__(self,cu, account,reactor,log):
        self.cu = cu
        self.children = ["/","/steemauth"]
        self.account = account
        self.reactor = reactor
        self.log = log
        thisdir = os.path.dirname(os.path.abspath(__file__))
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

class TransferStream:
    def __init__(self,cu,account):
        self.cu = cu
        self.account = account
    def transfer(self,tm,transfer_event,client):
        frm = transfer_event["from"]
        to = transfer_event["to"]
        memo = transfer_event["memo"]
        self.cu.blocktime(tm)
        if to == self.account:
            self.cu.process_transfer(frm, memo)

mypath = os.path.dirname(os.path.abspath(__file__))
with open(mypath + "/mini-auth.json") as configjsonfile:
    conf = json.load(configjsonfile)
secret = conf["secret"]
account = conf["account"]
observer = textFileLogObserver(io.open(join(mypath,"mini-auth.log"), "a"))
logger = Logger(observer=observer,namespace="asyncsteem")
blockchain = ActiveBlockChain(reactor,log=logger,nodelist="default")
cu = CookieUtil(secret,logger)
steembot = TransferStream(cu,account)
blockchain.register_bot(steembot,"flag_stream")
root = MiniAuthWebServer(cu,account,reactor,logger)
factory = server.Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 5080)
endpoint.listen(factory)
reactor.run()

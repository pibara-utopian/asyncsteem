#!/usr/bin/python
try:
    import syslog
    class DefaultLogger(object):
        def __init__(self,prefix="jsonrpc"):
            syslog.openlog(prefix,logoption=syslog.LOG_PID)
        def set_prefix(self, prefix):
            syslog.openlog(prefix,logoption=syslog.LOG_PID)
        def _log(self,message,explanation,level):
            syslog.syslog(level, message)
            if explanation != "":
                syslog.syslog(level, "     - " + explanation)
        def error(self,message,explanation=""):
            self._log(message,explanation,syslog.LOG_ERR)
        def warning(self,message,explanation=""):
            self._log(message,explanation,syslog.LOG_WARNING)    
        def notice(self,message,explanation=""):
            self._log(message,explanation,syslog.LOG_NOTICE)
        def info(self,message,explanation=""):
            self._log(message,explanation,syslog.LOG_INFO)

except:
    try:
        from termcolor import colored
        print(colored(self.prefix,"yellow"),":",colored("No syslog, logging to console.",color))
        class DefaultLogger(object):
            def __init__(self,prefix="jsonrpc"):
                self.prefix = prefic
            def set_prefix(self, prefix):
                self.prefix = prefix
            def log(self,message,explanation,color):
                print(colored(self.prefix,"yellow"),":",colored(message,color),explanation)
            def error(self,message,explanation=""):
                self.log(message,explanation,"red")
            def warning(self,message,explanation=""):
                self.log(message,explanation,"cyan")
            def notice(self,message,explanation=""):
                self.log(message,explanation,"green")
            def info(self,message,explanation=""):
                self.log(message,explanation,"blue")
    except:
        print("WARNING: No syslog, logging to console. Install termcolor if you desire colored logging.")
        class DefaultLogger(object):
            def __init__(self,prefix="jsonrpc"):
                self.prefix = prefix
            def set_prefix(self, prefix):
                self.prefix = prefix
            def log(message,explanation):
                print(self.prefix,":",message,"#",explanation)
            def error(self,message,explanation=""):
                self.log(message,explanation)
            def warning(self,message,explanation=""):
                self.log(message,explanation)
            def notice(self,message,explanation=""):
                self.log(message,explanation)
            def info(self,message,explanation=""):
                self.log(message,explanation)


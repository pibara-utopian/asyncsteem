# asyncsteem
Twisted based asynchonous python steem API. 

This project is meant to be a next generation version of what is now [steempersist](https://github.com/pibara/steempersist).
The *steempersist* project currently uses the [steem-python](https://github.com/steemit/steem-python) that in turn is a library that has rather a lot of dependencies, including a bleeding-edge version of python unavailable in most Linux repo's, makining it a pain to install and use for the non tech-savy users. Further, *steem-python* is a rather fiddly API that doesn't integrate with the python defacto asynchonous framework [twisted](https://twistedmatrix.com/trac/), and that seems to have a rather ad-hoc approach to error handling, making it even harder to build robust end-user geared application on top of it.

This work in progress library aims to re-implement the *steempersist* core library and subset of the steem-python functionality in an *asynchonic* python 2.x (and possibly python 3.x) library that works in conjunction with *twisted*. Once the core librarary is complete, the *steempersist* bot collection will be ported to *asyncsteem*.

If you wish to stay informed on my progress on this library, please follow [@mattockfs](https://steemit.com/@mattockfs) on steemit.  

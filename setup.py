from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name='asyncsteem',
    version='0.6.1',
    description='Asynchonous library for usage of the STEEM JSON-RPC API',
    long_description="""A Twisted based asynchonous library for creating simple STEEM based bots
    that use the STEEM JSON-RPC API.

    Asyncsteem is meant to make it extremely easy to build a simle stats oriented bot that either
    follows the blockchain as it grows, or that runs as a daily cron job.
    The library currently only support 'unsigned' operations, signed operations are planned for 
    the 0.7 version. Signed operations should make asyncsteem suitable for non-stats bots such as
    simple 'away' bots.
    """,
    url='https://github.com/pibara-utopian/asyncsteem',
    author='Rob J Meijer',
    author_email='pibara@gmail.com',
    license='BSD',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Operating System :: OS Independent',
        'Environment :: Other Environment',
        'Framework :: Twisted'
    ],
    keywords='steemit steem json-rpc',
    install_requires=['twisted',
                      'datetime'],
    packages=find_packages(),
)

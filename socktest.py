#! /usr/bin/env python3

import re
import time
import socket

# List of common ports/protocols
portlist = {
    7:     ['echo'],             20:  ['ftp'],              21:  ['ftp'],
    22:    ['ssh','scp'],        23:  ['telnet'],           25:  ['smtp'],
    53:    ['dns'],              67:  ['dhcp','bootp'],     68:  ['dhcp','bootp'],
    80:    ['http'],             88:  ['kerberos','krb'],  110:  ['pop3'],
    123:   ['ntp','time'],      143:  ['imap','imap4'],    389:  ['ldap'],
    443:   ['https'],           464:  ['kerberos','krb'],  465:  ['smtps'],
    500:   ['isakmp'],          515:  ['lpd','lpr'],       587:  ['smtps','tls'],
    631:   ['cupsd'],           636:  ['ldaps'],           989:  ['ftps'],
    990:   ['ftps'],            993:  ['imaps','imap4s'],  995:  ['pops','pop3s'],
    1194:  ['ovpn','openvpn'], 1701:  ['l2tp'],           1723:  ['pptp'],
    2049:  ['nfs'],            2483:  ['ora'],            2484:  ['ora'],
    3389:  ['rdp','ts'],       5900:  ['vnc'],            8080:  ['http','proxy'],
}
t= []

def testConnection(rhost, rport):
    # Test connection
    if rport in t: return None
    t.append(rport)
    if rport in portlist.keys(): name = '('+portlist[rport][0]+')'
    else: name = ''
    
    try:
        if not args.printopen: print('trying ', rhost, ':{:<5s} {:<10s}'.format(str(rport), name), ' ... ', sep='', end='')
        s = socket.socket()
        s.connect((rhost, rport))
    except socket.error as e:
        if args.verbose:
            print(e)
        elif args.printopen:
            pass
        else:
            print('failed')
        return False
    else:
        if args.printopen: print('trying ', rhost, ':{:<5s} {:<10s}'.format(str(rport), name), ' ... ', sep='', end='')
        lhost = socket.gethostname()
        lport = str(s.getsockname()[1])
        print('connected')
        if args.verbose:
            print('   {', '<->'.join([':'.join([lhost, str(lport)]), ':'.join([rhost, str(rport)])]), '}', sep='')
        s.close()
        return True

def checkPort(n):
    l = []
    if n.isdigit():
        l.append(int(n))
    elif n.__contains__('-'):
        x = [int(y) for y in n.split('-')]
        if x[0] > x[1]:
            print('Invalid range given! Use `<hostname>:<x>-<y>` where <x>\nand <y> are numeric and <y> is greater than <x>')
            exit(1)
        y = range(x[0], x[1])
        for z in y:
            l.append(z)
        l.append(x[1])
    elif n.lower() == 'all':
        l = list(portlist.keys())
    elif n.isalnum():
        x = [int(k) for k,v in portlist.items() if v.__contains__(n.lower())]
        if len(x) < 1:
            print('Port name', n, 'not known!')
            parser.print_help(); exit(1)
        for z in x:
            l.append(z)
    else:
        print('Invalid port specification:', n)
        parser.print_help(); exit(1)
    return l

def printList():
    l = []
    for a in portlist.values():
        for b in a:
            if b in l:
                pass
            else:
                l.append(b)
    l.sort()
    for s in l: print(s+' ', end='')
    print()
    return True

if __name__ == '__main__':
    # Get arguments
    import argparse
    parser = argparse.ArgumentParser(description='Checks availability of remote ports',
                     epilog='Use special keyword "all" for <port> to test all common port numbers')
    args = [('-v', '--verbose', 'output error messages', dict(action='store_true')                   ),
        ('-l', '--list',    'list known protocols',  dict(action='store_true', dest='printlist') ),
        ('-o', '--open',    'only show open ports',  dict(action='store_true', dest='printopen') )]
    for arg1, arg2, arghelp, options in args:
        parser.add_argument(arg1, arg2, help=arghelp, **options)
    parser.add_argument('target', help='remote target', metavar='<hostname>:<port>', nargs='?', default=None)
    parser.add_argument('delay', help='delay between tests in seconds (def: 0)', nargs='?', default=0, type=int)
    args = parser.parse_args()
    
    # initial checks
    if args.verbose and args.printopen:
        print('Please use only one of --open and --verbose')
        parser.print_usage()
        exit(1)
    if args.printlist: printList()
    if args.target == None:
        if not args.printlist: parser.print_usage()
        exit(2)

    # Main tests
    try:
        host, dport = args.target.split(':')
    except:
        parser.print_help(); exit(2)

    if dport.__contains__(','):
        dport = dport.split(',')
    
    port = []
    if type(dport) is type('string'):
        port = checkPort(dport)
    else:   #if list
        for a in dport:
            r = checkPort(a)
            for b in r:
                port.append(b)
    
    port.sort()
    if len(port) == 0:
        print('Unable to decypher port specifications!')
        parser.print_help(); exit(3)

    for p in port:
        try:
            time.sleep(args.delay)
            testConnection(host, p)
        except KeyboardInterrupt:
            print()
            print('User cancelled')
            exit()

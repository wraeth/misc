#!/usr/bin/env python3

"""
Searches metadata.xml files in Gentoo Portage tree to find proxy maintainers.
"""

import collections
import os
import re

Details = collections.namedtuple('Details', ['desc', 'packages'])

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


def main():
    """Entry point."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--portdir', help='Portage tree root', default='/usr/portage')
    parser.add_argument(
        '-o', '--output', help='Output file', default='userlist.txt')
    parser.add_argument(
        '-d', '--desc', help='Include maint description', action='store_true')
    args = parser.parse_args()

    u = listProxyMaintainers(args.portdir, args.desc)
    addrs = list(u.keys())
    addrs.sort()

    pkgcount = 0
    fh = open(args.output, 'a')
    for addr in addrs:
        for pkg in u[addr].packages:
            print(' '.join([addr, pkg, u[addr].desc]), file=fh)
        pkgcount += len(u[addr].packages)
    fh.close()

    print('Got {!s} users maintaining {!s} packages'.format(
        len(addrs), pkgcount))


def listProxyMaintainers(portdir: str, add_desc: bool = False) -> dict:
    """Wrapper for listing proxy maintainers, returns dict."""
    assert isinstance(portdir, str)
    userlist = {}
    for metadata in findMetadataFiles(portdir):
        readMetadata(metadata, userlist, add_desc)
    return userlist


def findMetadataFiles(portdir: str) -> list:
    """Searches for metadata.xml files and returns list of paths."""
    assert isinstance(portdir, str)
    return [os.path.join(r, 'metadata.xml')
        for r, s, f in os.walk(portdir) if 'metadata.xml' in f]


def readMetadata(meta_file: str, maintainers: dict, add_desc: bool = False) -> None:
    """Reads a metadata file and saves proxy-maint to outfile."""
    assert isinstance(meta_file, str)
    assert isinstance(maintainers, dict)
    assert os.path.isfile(meta_file)

    m = ET.parse(meta_file).getroot()
    try:
        if 'proxy-maintainers' not in [h.text for h in m.findall('herd')]:
            return
    except AttributeError:
        return

    for maintainer in m.findall('maintainer'):
        package = '/'.join(meta_file.split(os.sep)[3:5])
        mail = maintainer.find('email').text
        if 'gentoo.org' in mail:
            # a dev isn't a user maintainer
            return
        try:
            desc = maintainer.find('description').text
        except AttributeError:
            # maintainer doesn't have a desc
            return
        if re.search('assign *bugs *to|proxy', desc, re.I):
            if not add_desc:
                desc = ''
            try:
                maintainers[mail].packages.append(package)
            except KeyError:
                maintainers[mail] = Details(desc, [package])


if __name__ == '__main__':
    main()


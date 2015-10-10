#!/usr/bin/env python3

"""
Searches metadata.xml files in Gentoo Portage tree to find proxy maintainers.
"""

import collections
import os

Details = collections.namedtuple('Details', ['desc', 'packages'])

try:
    import xml.etree.cElementTree as ElementTree
except ImportError:
    import xml.etree.ElementTree as ElementTree


def main():
    """Entry point."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--portdir', help='Portage tree root', default='/usr/portage')
    parser.add_argument(
        '-d', '--desc', help='Include maint description', action='store_true')
    parser.add_argument(
        '-m', '--maintainer', help='List packages for maintainer')
    parser.add_argument(
        '-O', '--orphans', help='List all orphaned packages', action='store_true')
    args = parser.parse_args()

    u = list_proxy_maintainers(args.portdir, args.desc)
    addrs = list(u.keys())
    addrs.sort()

    if args.orphans:
        all_pkgs = [p for a in addrs for p in u[a].packages]
        all_pkgs.sort()
        [print(p) for p in all_pkgs]
    elif args.maintainer:
        try:
            [print(p) for p in u[args.maintainer].packages]
        except KeyError:
            print("Address not found as proxy-maintainer: %r" % args.maintainer)
    else:
        pkgcount = 0
        for a in addrs:
            [print(a, p, u[a].desc) for p in u[a].packages]
            pkgcount += len(u[a].packages)
        print('Got %s users maintaining %s packages' % (len(addrs), pkgcount))


def list_proxy_maintainers(portdir: str, add_desc: bool = False) -> dict:
    """Wrapper for listing proxy maintainers, returns dict."""
    assert isinstance(portdir, str)
    userlist = {}
    for metadata in find_metadata_files(portdir):
        read_metadata(metadata, userlist, add_desc)
    return userlist


def find_metadata_files(portdir: str) -> list:
    """Searches for metadata.xml files and returns list of paths."""
    assert isinstance(portdir, str)
    for root, subdirs, files in os.walk(portdir):
        if 'metadata.xml' in files:
            yield os.path.join(root, 'metadata.xml')


def read_metadata(meta_file: str, maintainers: dict, add_desc: bool = False) -> None:
    """Reads a metadata file and saves proxy-maint to outfile."""
    assert isinstance(meta_file, str)
    assert isinstance(maintainers, dict)
    assert os.path.isfile(meta_file)

    m = ElementTree.parse(meta_file).getroot()
    try:
        if 'proxy-maintainers' not in [h.text for h in m.findall('herd')]:
            return
    except AttributeError:
        return

    for maintainer in m.findall('maintainer'):
        package = '/'.join(meta_file.split(os.sep)[-3:-1])
        mail = maintainer.find('email').text
        # Assume the maintainer without an official '@gentoo.org' email
        # address to be the proxy user
        if 'gentoo.org' not in mail:
            if add_desc:
                try:
                    desc = maintainer.find('description').text.replace('\n', ' ')
                except AttributeError:
                    desc = ''
            else:
                desc = ''
            try:
                maintainers[mail].packages.append(package)
            except KeyError:
                maintainers[mail] = Details(desc, [package])

if __name__ == '__main__':
    main()


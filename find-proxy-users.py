#!/usr/bin/env python3

"""
Searches metadata.xml files in Gentoo Portage tree to find proxy maintainers.
"""

import argparse
import collections
import os
import sys

unmaintained_addrs = tuple(['', 'NO MAINTAINER', 'maintainer-needed@gentoo.org'])

try:
    import xml.etree.cElementTree as ElementTree
except ImportError:
    import xml.etree.ElementTree as ElementTree


class Maintainer:

    """Simple class to store maintainer information."""

    def __init__(self, address: str, description: str=None):
        """Class instantiation."""
        self.address = address
        self.description = description

    def __repr__(self):
        """Returns address of the maintainer."""
        return self.address

    def __cmp__(self, other) -> bool:
        """Override for self comparing."""
        return self.address == other.address


class Package:

    """Contains information about individual packages."""

    def __init__(self, metadata: str):
        """Object instantiation."""
        self.metadata = metadata
        self.atom = '/'.join(self.metadata.split(os.sep)[-3:-1])
        self.maintainers = []

        meta = ElementTree.parse(self.metadata).getroot()
        self.herds = [elem.text for elem in meta.findall('herd')]
        for maintainer in meta.findall('maintainer'):
            address = maintainer.find('email').text
            try:
                desc = maintainer.find('description').text.replace('\n', ' ')
            except AttributeError:
                desc = None
            self.maintainers.append(Maintainer(address, desc))

        del meta

    def __repr__(self):
        """Returns the package atom."""
        return self.atom

    def is_officially_maintained(self) -> bool:
        """Determines if package is officially maintained and returns bool."""
        if len(self.herds) > 1 or 'proxy-maintainers' not in self.herds:
            return True
        officially_maintained = True
        for maintainer in self.maintainers:
            if 'gentoo.org' not in maintainer.address:
                officially_maintained = False
        return officially_maintained

    def is_orphan(self) -> bool:
        """Determines if package is an orphan and returns bool."""
        if self.is_officially_maintained():
            return False

        am_orphan = True
        for maintainer in self.maintainers:
            if 'gentoo.org' not in maintainer.address:
                am_orphan = False
            elif maintainer.address in unmaintained_addrs:
                pass
            else:
                am_orphan = False

        if len(self.herds) > 0 and 'proxy-maintainers' not in self.herds:
            am_orphan = False

        return am_orphan

    def get_proxy_maintainer(self) -> Maintainer:
        """Returns the address of the proxy maintainer of the package or None for unmaintained."""
        user = None
        if len(self.maintainers) == 0:
            user = Maintainer('NO MAINTAINER')
        for maintainer in self.maintainers:
            if maintainer in unmaintained_addrs:
                user = maintainer
            if 'gentoo.org' not in maintainer.address:
                user = maintainer

        # this is for unusual circumstance, such as package belonging to proxy-maint herd
        # but only have an @gentoo.org address assigned as maintainer
        if user is None:
            for maintainer in self.maintainers:
                user = maintainer
        return user


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--portdir', help='Portage tree root', default='/usr/portage')
    parser.add_argument('-d', '--desc', help='Include maint description', action='store_true')
    parser.add_argument('-H', '--herd', help='Limit results to packages owned by HERD')

    subparsers = parser.add_subparsers(help='commands')

    local_parser = subparsers.add_parser('local', help='Find locally installed proxy-maintainer packages')
    local_parser.add_argument('-i', '--input', help='Package list', type=argparse.FileType('r'), default='-')
    local_excl = local_parser.add_mutually_exclusive_group()
    local_excl.add_argument('-o', '--orphans', help='List orphan packages only', action='store_true')
    local_excl.add_argument('-m', '--maintainer', help='Show package maintainer', action='store_true')
    local_parser.set_defaults(mode='local')

    user_parser = subparsers.add_parser('users', help='List users who proxy-maintain packages')
    user_parser.add_argument('-a', '--address', help='Only list packages for <address>')
    user_parser.add_argument('-p', '--list-atoms', help='Print list of maintained atoms', action='store_true')
    user_parser.set_defaults(mode='users')

    orphan_parser = subparsers.add_parser('orphans', help='List all orphaned packages')
    orphan_parser.set_defaults(mode='orphans')
    
    args = parser.parse_args()

    # print help if no mode is given
    if 'mode' not in args:
        parser.print_help()
        return -1

    if args.mode == 'local':
        return list_local_packages(args)
    elif args.mode == 'users':
        return list_user_maintainers(args)
    elif args.mode == 'orphans':
        return list_orphan_packages(args)
    else:
        parser.print_help()
        return -1


def list_local_packages(args: argparse.Namespace) -> int:
    """List proxy-maint packages installed on system as identified by input."""
    assert isinstance(args, argparse.Namespace)

    # don't hang if no input file or pipe
    if sys.stdin.isatty():
        print('ERROR: input file or pipe required for local package lists', file=sys.stderr)
        return 2

    files = [os.path.join(args.portdir, line.strip(), 'metadata.xml') for line in args.input.readlines()]
    files.sort()
    maintainers = {}

    for metadata in files:
        if not os.path.isfile(metadata):
            # skip packages in overlays
            continue
        package = Package(metadata)
        if package.is_officially_maintained():
            continue

        # if we're filtering by a specific herd
        if args.herd is not None:
            if args.herd not in package.herds:
                continue

        # if we're only listing orphans (no maintainer at all)
        if args.orphans:
            if package.is_orphan():
                print(package)
            continue

        # if we're listing the proxy maintainer
        if args.maintainer:
            maintainer = package.get_proxy_maintainer()
            try:
                maintainers[maintainer.address][1].append(package)
            except KeyError:
                maintainers[maintainer.address] = [maintainer, [package]]

        # if we're just listing the packages
        else:
            print(package)

    # if we're listing by proxy maintainer, sort and print
    if len(list(maintainers.keys())) > 0:
        maintainer_list = list(maintainers.keys())
        maintainer_list.sort()
        for address in maintainer_list:
            maintainer = maintainers[address][0]
            print(maintainer.address, end='')
            if args.desc:
                print(' (%s)' % maintainer.description, end='')
            print()
            for package in maintainers[address][1]:
                print('   ', package)
            print()

    return 0


def list_user_maintainers(args: argparse.Namespace) -> int:
    """Lists all packages that have a non-developer maintainer assigned."""
    assert isinstance(args, argparse.Namespace)

    maintainers = {}
    for path in find_metadata_files(args.portdir):
        package = Package(path)
        if package.is_officially_maintained() or package.is_orphan():
            continue

        maintainer = package.get_proxy_maintainer()

        # filter by single maintainer if one was given
        if args.address:
            if maintainer.address != args.address:
                continue

        try:
            maintainers[maintainer.address][1].append(package)
        except KeyError:
            maintainers[maintainer.address] = [maintainer, [package]]

    maintainer_list = list(maintainers.keys())
    maintainer_list.sort()
    for address in maintainer_list:
        maintainer = maintainers[address][0]
        print(maintainer.address, end='')
        if args.desc:
            print(' (%s)' % maintainer.description, end='')
        if args.list_atoms or args.address:
            print()
            for package in maintainers[address][1]:
                print('   ', package)
            print()
        else:
            print('  packages: %s' % len(maintainers[address][1]))

    return 0


def list_orphan_packages(args: argparse.Namespace) -> int:
    """Lists all found orphan packages."""
    assert isinstance(args, argparse.Namespace)

    for path in find_metadata_files(args.portdir):
        package = Package(path)
        if package.is_orphan() is not True:
            continue
        print(package)
    return 0


def find_metadata_files(portdir: str) -> list:
    """Searches for metadata.xml files and returns list of paths."""
    assert isinstance(portdir, str)
    for root, subdirs, files in os.walk(portdir):
        # Skip category metadata (such as sys-apps/metadata.xml)
        if os.path.dirname(root) == portdir:
            continue
        if'metadata.xml' in files:
            yield os.path.join(root, 'metadata.xml')


if __name__ == '__main__':
    exit(main())
